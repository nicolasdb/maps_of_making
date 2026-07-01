import asyncio
import re
import time
from pathlib import Path

import structlog
from nio import AsyncClient, InviteMemberEvent, MatrixRoom, ReactionEvent, RoomMessageText, UploadResponse

from message import Message

log = structlog.get_logger()

# The ONE confirmation signal for a pending write (Story 6.9 follow-up).
# Deliberately a single emoji, not a set — one clear signal, not a menu of
# equivalent options. Typed "yes" confirmation was removed entirely in favor
# of this.
CONFIRM_REACTION = "✅"


class MatrixAdapter:
    """ChannelAdapter for Matrix via matrix-nio. Buffers incoming room text
    messages onto an internal queue so receive() can be awaited one at a time,
    independent of nio's callback-driven sync loop."""

    def __init__(self, homeserver: str, user_id: str, access_token: str, device_id: str | None = None):
        self.client = AsyncClient(homeserver, user_id)
        self.client.access_token = access_token
        self.client.user_id = user_id
        self.client.device_id = device_id
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._sync_task: asyncio.Task | None = None
        self._start_ts_ms: int = 0  # events older than this are pre-boot; drop them
        self.client.add_event_callback(self._on_message, RoomMessageText)
        self.client.add_event_callback(self._on_invite, InviteMemberEvent)
        self.client.add_event_callback(self._on_reaction, ReactionEvent)

    async def _on_invite(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        # matrix-nio does not auto-join invites (by design, per its own
        # examples) — without this callback, every invite sits pending
        # until something calls client.join() explicitly.
        if event.state_key != self.client.user_id:
            return
        await self.client.join(room.room_id)
        log.info("matrix.invite_joined", room_id=room.room_id)

    # Matrix fallback quote: lines starting with "> " followed by a blank line
    _FALLBACK_RE = re.compile(r"^(>[^\n]*\n)+\n", re.MULTILINE)

    async def _on_message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        if event.sender.lower() == self.client.user_id.lower():
            return
        if self._start_ts_ms and event.server_timestamp < self._start_ts_ms:
            log.debug("matrix.event_skipped_pre_boot", event_id=event.event_id, ts=event.server_timestamp)
            return

        # Strip Matrix fallback quote prefix that clients add to threaded replies
        body = self._FALLBACK_RE.sub("", event.body).strip()

        # Extract thread root event_id if this message is inside a thread
        relates = (event.source or {}).get("content", {}).get("m.relates_to", {})
        thread_id = ""
        if relates.get("rel_type") == "m.thread":
            thread_id = relates.get("event_id", "")

        message = Message(
            text=body,
            user_id=event.sender,
            room_id=room.room_id,
            platform="matrix",
            raw=event,
            power_level=room.power_levels.get_user_level(event.sender),
            event_id=event.event_id,
            thread_id=thread_id,
        )
        await self._queue.put(message)

    # Strip variation selectors (U+FE0E/U+FE0F) — many Matrix clients append
    # U+FE0F ("emoji presentation") to reaction keys, so a client-sent ✅
    # often arrives as "✅️", not the bare "✅" glyph. Comparing
    # without stripping these silently drops every reaction.
    _VARIATION_SELECTORS = str.maketrans("", "", "︎️")

    async def _on_reaction(self, room: MatrixRoom, event: ReactionEvent) -> None:
        if event.sender.lower() == self.client.user_id.lower():
            return
        if self._start_ts_ms and event.server_timestamp < self._start_ts_ms:
            log.debug("matrix.reaction_skipped_pre_boot", event_id=event.event_id)
            return
        normalized_key = event.key.translate(self._VARIATION_SELECTORS)
        if normalized_key != CONFIRM_REACTION:
            log.debug("matrix.reaction_ignored", key=event.key, sender=event.sender, reacts_to=event.reacts_to)
            return
        log.info("matrix.reaction_matched", sender=event.sender, room_id=room.room_id, reacts_to=event.reacts_to)

        # Synthesize a bare "yes" message — the router only acts on it if this
        # (room, user) actually has a pending confirmation; otherwise it's a
        # no-op, same as an unprompted "yes" typed with no pending write.
        # event_id is the REACTED-TO message, so agent._confirm_pending can
        # verify the reaction landed on the actual confirm prompt, not some
        # unrelated older message.
        message = Message(
            text="yes",
            user_id=event.sender,
            room_id=room.room_id,
            platform="matrix",
            raw=event,
            power_level=room.power_levels.get_user_level(event.sender),
            event_id=event.reacts_to,
            via_reaction=True,
        )
        await self._queue.put(message)

    async def start(self) -> None:
        # Record boot time before initial sync so _on_message can drop
        # any pre-boot events that fire during the catchup sync.
        self._start_ts_ms = int(time.time() * 1000)
        resp = await self.client.sync(timeout=0, full_state=False)
        since = getattr(resp, "next_batch", None)
        self._sync_task = asyncio.create_task(
            self.client.sync_forever(timeout=30000, since=since)
        )
        log.info("matrix.sync_started", since=since, start_ts_ms=self._start_ts_ms)

    async def ensure_profile(self, display_name: str | None = None,
                             avatar_path: str | None = None) -> None:
        """Idempotently assert Bernard's Matrix profile on boot. Display name is
        set only when it differs from the current value; the avatar is uploaded
        only when none is set yet (a fresh homeserver). To force-swap an existing
        avatar later, run harness/set_profile.py."""
        if display_name:
            resp = await self.client.get_displayname(self.client.user_id)
            current = getattr(resp, "displayname", None)
            if current != display_name:
                await self.client.set_displayname(display_name)
                log.info("matrix.displayname_set", name=display_name)

        if avatar_path:
            resp = await self.client.get_avatar(self.client.user_id)
            existing = getattr(resp, "avatar_url", None)
            if existing:
                log.info("matrix.avatar_present_skip", avatar_url=existing)
                return
            path = Path(avatar_path)
            if not path.is_file():
                log.warning("matrix.avatar_missing", path=str(path))
                return
            with path.open("rb") as f:
                upload, _ = await self.client.upload(
                    f, content_type="image/png",
                    filename=path.name, filesize=path.stat().st_size,
                )
            if isinstance(upload, UploadResponse):
                await self.client.set_avatar(upload.content_uri)
                log.info("matrix.avatar_set", avatar_url=upload.content_uri)
            else:
                log.warning("matrix.avatar_upload_failed", resp=str(upload))

    async def receive(self) -> Message:
        return await self._queue.get()

    async def send(self, response: str, context: Message) -> str:
        """Send a response. Returns the sent event_id (empty string on failure)."""
        content: dict = {"msgtype": "m.text", "body": response}
        thread_root = context.thread_id or context.event_id
        if thread_root:
            content["m.relates_to"] = {
                "rel_type": "m.thread",
                "event_id": thread_root,
            }
        resp = await self.client.room_send(
            room_id=context.room_id,
            message_type="m.room.message",
            content=content,
        )
        return getattr(resp, "event_id", "") or ""

    async def close(self) -> None:
        if self._sync_task:
            self._sync_task.cancel()
        await self.client.close()
