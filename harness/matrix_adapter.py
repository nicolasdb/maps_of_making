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

    # Trigger-suppression regions (plaintext body): a ```fenced``` block, an
    # `inline code` span, or a "> " blockquote line. A @bernard/pill mention
    # that lives ONLY inside one of these is demonstrating the command to
    # someone, not addressing the bot — strip these regions before running
    # mention detection so "try `@bernard find laser`" or "> @bernard ..."
    # doesn't wake Bernard (feature request 2026-07-03).
    _FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
    _INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
    _BLOCKQUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)
    # HTML equivalents in formatted_body (Matrix renders markdown to these).
    _HTML_CODE_QUOTE_RE = re.compile(
        r"<(pre|code|blockquote)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
    )

    @classmethod
    def _strip_quoted_and_code(cls, text: str) -> str:
        text = cls._FENCED_CODE_RE.sub(" ", text)
        text = cls._INLINE_CODE_RE.sub(" ", text)
        text = cls._BLOCKQUOTE_LINE_RE.sub(" ", text)
        return text

    async def _on_message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        if event.sender.lower() == self.client.user_id.lower():
            return
        if self._start_ts_ms and event.server_timestamp < self._start_ts_ms:
            log.debug("matrix.event_skipped_pre_boot", event_id=event.event_id, ts=event.server_timestamp)
            return

        # Strip Matrix fallback quote prefix that clients add to threaded replies
        body = self._FALLBACK_RE.sub("", event.body).strip()

        # Extract thread root event_id if this message is inside a thread
        content = (event.source or {}).get("content", {})
        relates = content.get("m.relates_to", {})
        thread_id = ""
        if relates.get("rel_type") == "m.thread":
            thread_id = relates.get("event_id", "")

        # Mention detection, three independent signals (any one is enough):
        #   1. MSC3952 / Matrix 1.7 m.mentions naming the bot's mxid.
        #   2. A literal "@bernard" anywhere in the plaintext body (how a user
        #      who types the mxid by hand, e.g. Nicolas, comes through).
        #   3. The bot's own mxid inside the formatted_body pill link
        #      (<a href="matrix.to/#/@bernard:...">). Some clients (live:
        #      @jason_p's, 2026-07-03) render a real mention pill via
        #      formatted_body ONLY — no m.mentions field at all, and the
        #      plaintext body carries just the display name "Bernard:" with no
        #      "@". Without this check those pill-mentions were silently
        #      dropped while the identical-looking message from a client that
        #      does emit m.mentions worked fine.
        # A bare "bernard" with no "@"/pill (even "Bernard:"/"Bernard," at the
        # start) is deliberately NOT a mention: ambiguous with talking *about*
        # Bernard ("Bernard, quel personnage!"), needs conversational
        # continuity we don't have yet (decided 2026-07-03).
        #
        # The heuristic signals (2 + 3) run against the body/formatted_body
        # with code + blockquote regions stripped, so a mention shown inside
        # `inline code`, a ```fenced block```, or a "> " quote (i.e. someone
        # demonstrating the command to another user) doesn't wake Bernard.
        # m.mentions (signal 1) stays authoritative and un-stripped: a client
        # only emits it on a genuine, intentional mention, never for text a
        # user typed inside a code span.
        mentioned_ids = content.get("m.mentions", {}).get("user_ids", [])
        formatted_body = content.get("formatted_body", "") or ""
        trigger_body = self._strip_quoted_and_code(event.body)
        trigger_formatted = self._HTML_CODE_QUOTE_RE.sub(" ", formatted_body)
        is_mention = self.client.user_id in mentioned_ids or bool(
            re.search(r"@bernard\b", trigger_body, re.IGNORECASE)
            or self.client.user_id.lower() in trigger_formatted.lower()
        )

        message = Message(
            text=body,
            user_id=event.sender,
            room_id=room.room_id,
            platform="matrix",
            raw=event,
            power_level=room.power_levels.get_user_level(event.sender),
            event_id=event.event_id,
            thread_id=thread_id,
            is_mention=is_mention,
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
            # is_falling_back + m.in_reply_to are the stable-Threads-spec
            # (MSC3440) fields that tell thread-aware clients (Element) this
            # is a genuine threaded reply, not a plain top-level message that
            # happens to carry a thread tag. Without them, Element renders
            # the reply BOTH inside the thread AND as a full duplicate in the
            # main room timeline.
            content["m.relates_to"] = {
                "rel_type": "m.thread",
                "event_id": thread_root,
                "is_falling_back": True,
                "m.in_reply_to": {"event_id": thread_root},
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
