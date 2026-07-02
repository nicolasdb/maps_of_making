import asyncio
import dataclasses
import os
import re
import uuid

from dotenv import load_dotenv
import structlog

import agent_tools
import bernard
import commands
import llm_client
import sparql_client
from config import load_config
from matrix_adapter import MatrixAdapter
from router import route

load_dotenv()

log = structlog.get_logger()

COMMAND_PREFIX = "!mom"


def _log_task_exception(task: asyncio.Task) -> None:
    exc = task.exception() if not task.cancelled() else None
    if exc:
        log.error("handle_message.failed", exc_info=exc)


_MENTION_PREFIX_RE = re.compile(r"^@?bernard[\s,:]*", re.IGNORECASE)


async def handle_message(adapter: MatrixAdapter, message) -> None:
    if not message.text:
        return

    session_id = str(uuid.uuid4())
    bound = log.bind(session_id=session_id, adapter="matrix", room_id=message.room_id)

    if message.is_mention:
        # is_mention is decided by the adapter from the event's real
        # m.mentions data (or a literal "@bernard" in the raw body) — NOT by
        # whether the stripped text merely starts with the word "bernard".
        # A sentence like "Bernard s'en fiche..." used to false-trigger here
        # because the old regex ran on message.text with an optional "@".
        # Any leading "@bernard"/"bernard:" address prefix is still stripped
        # from the text so it doesn't leak into the NL question itself.
        nl_text = _MENTION_PREFIX_RE.sub("", message.text, count=1).strip()
        stripped = dataclasses.replace(message, text=nl_text)
        bound.info("message.received", text=nl_text, via="bernard_mention")
    elif message.text.startswith(COMMAND_PREFIX):
        stripped = dataclasses.replace(message, text=message.text[len(COMMAND_PREFIX):].strip())
        bound.info("message.received", text=message.text)
    elif message.via_reaction and (message.room_id, message.user_id) in agent_tools.PENDING_ACTIONS:
        # A ✅ reaction (via_reaction=True, synthesized by MatrixAdapter) is
        # never a mention or a !mom command, so it needs this bypass to reach
        # the router at all. Scoped narrowly: only fires for the synthesized
        # reaction message itself — plain chat from a user with a pending
        # write still requires @mention/!mom like normal (Story 6.9 review
        # finding: this used to fire on ANY message from that user).
        # thread_id is stamped from the pending action's stored thread_root so
        # the commit-ack lands in the SAME Matrix thread as the confirm-ask,
        # instead of starting a new thread rooted at the reaction's target
        # event (see Story 6.9 follow-up: threads were fragmenting).
        pending = agent_tools.PENDING_ACTIONS[(message.room_id, message.user_id)]
        stripped = dataclasses.replace(message, thread_id=pending.get("thread_root", ""))
        bound.info("message.received", text=message.text, via="pending_confirmation")
    else:
        return

    try:
        # Literal !mom <verb> commands (link, update) are matched before the LLM
        # intent classifier — see Story 6.1 Dev Notes "Command parsing, not intent
        # routing". Only messages that don't match a known verb fall through to route().
        response = await commands.try_handle(
            stripped.text, message.user_id, message.room_id, session_id,
            adapter=adapter, context=message,
        )
        if response is None:
            response = await route(stripped, session_id, adapter=adapter)
    except Exception:
        bound.exception("handle_message.unhandled_error")
        response = bernard.unknown_ack()

    if not response:
        # e.g. a reaction confirmation that landed on the wrong message — a
        # deliberate no-op, not an error; nothing to send.
        return

    bound.info("message.responded", response=response)
    sent_event_id = await adapter.send(response, stripped)

    pending_key = (message.room_id, message.user_id)
    pending = agent_tools.PENDING_ACTIONS.get(pending_key)
    if pending is not None and pending.get("prompt_event_id") is None and sent_event_id:
        # This response was the confirm-ask itself (propose_write just ran) —
        # stamp the sent message's event_id so a reaction-confirmation can be
        # matched to this exact prompt, not just any pending action.
        pending["prompt_event_id"] = sent_event_id


async def main() -> None:
    config = load_config()
    bot_cfg = config.get("bot", {})

    llm_client.MODEL = bot_cfg.get("model") or llm_client.DEFAULT_MODEL
    bernard.load_voice()

    homeserver = os.environ.get("MATRIX_HOMESERVER") or bot_cfg.get("matrix_homeserver")
    user_id = os.environ.get("MATRIX_USER_ID")
    access_token = os.environ.get("MATRIX_ACCESS_TOKEN")
    device_id = os.environ.get("MATRIX_DEVICE_ID") or None
    if not (homeserver and user_id and access_token):
        raise ValueError("MATRIX_HOMESERVER/MATRIX_USER_ID/MATRIX_ACCESS_TOKEN must be set in .env or environment")

    sparql_client.OXIGRAPH_ENDPOINT = os.environ.get("OXIGRAPH_ENDPOINT", "http://localhost:7878")

    adapter = MatrixAdapter(homeserver, user_id, access_token, device_id)
    try:
        await adapter.start()
        profile_cfg = bot_cfg.get("profile") or {}
        await adapter.ensure_profile(
            display_name=profile_cfg.get("display_name"),
            avatar_path=profile_cfg.get("avatar_path"),
        )
        log.info("bot.ready", platform="matrix", model=llm_client.MODEL)

        while True:
            try:
                message = await adapter.receive()
            except Exception:
                log.exception("adapter.receive_failed")
                continue
            task = asyncio.create_task(handle_message(adapter, message))
            task.add_done_callback(_log_task_exception)
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(main())
