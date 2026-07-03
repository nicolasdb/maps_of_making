"""Tests for harness/matrix_adapter.py's mention detection (Story 6.10
follow-up): a message must be an actual @mention (m.mentions naming the bot,
or a literal "@bernard" in the body) to be treated as one — a sentence that
merely starts with the word "bernard" (no @) must NOT false-trigger."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from matrix_adapter import MatrixAdapter
from message import Message

BOT_USER_ID = "@bernard:matrix.org"


def _make_adapter() -> MatrixAdapter:
    return MatrixAdapter(homeserver="https://matrix.org", user_id=BOT_USER_ID, access_token="tok")


def _make_room() -> SimpleNamespace:
    power_levels = SimpleNamespace(get_user_level=lambda user_id: 0)
    return SimpleNamespace(room_id="!room:matrix.org", power_levels=power_levels)


def _make_event(body: str, content: dict | None = None, sender: str = "@nicolas:matrix.org") -> SimpleNamespace:
    return SimpleNamespace(
        sender=sender,
        body=body,
        source={"content": content or {}},
        server_timestamp=0,
        event_id="$event1",
    )


@pytest.mark.asyncio
async def test_sentence_starting_with_bernard_but_no_at_sign_is_not_a_mention():
    adapter = _make_adapter()
    event = _make_event("bernard s'en fiche. 'open' = statut now.")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is False


@pytest.mark.asyncio
async def test_literal_at_bernard_in_body_is_a_mention():
    adapter = _make_adapter()
    event = _make_event("@bernard: how can you help me?")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is True


@pytest.mark.asyncio
async def test_m_mentions_naming_the_bot_is_a_mention_even_without_at_in_body():
    adapter = _make_adapter()
    event = _make_event("Bernard, how can you help me?", content={"m.mentions": {"user_ids": [BOT_USER_ID]}})
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is True


@pytest.mark.asyncio
async def test_m_mentions_naming_someone_else_is_not_a_mention():
    adapter = _make_adapter()
    event = _make_event("bernard doesn't care", content={"m.mentions": {"user_ids": ["@someone_else:matrix.org"]}})
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is False


# ---------------------------------------------------------------------------
# Bare "Bernard:"/"Bernard," address (no @, no m.mentions) is deliberately
# NOT a mention (decided 2026-07-03): it's ambiguous with talking *about*
# Bernard ("Bernard, quel personnage!") and disambiguating needs multi-message
# continuity we don't have yet. Only m.mentions or a literal "@bernard" count.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bare_bernard_colon_with_no_at_and_no_mentions_is_not_a_mention():
    adapter = _make_adapter()
    event = _make_event("Bernard: what tools do you have?")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is False


@pytest.mark.asyncio
async def test_literal_at_bernard_mid_sentence_is_a_mention():
    adapter = _make_adapter()
    event = _make_event("hey @bernard, what tools do you have?")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is True


# ---------------------------------------------------------------------------
# formatted_body pill mention, no m.mentions, plaintext body has no "@" (live
# bug, 2026-07-03: @jason_p's client — real event content pulled from Dendrite
# — renders a mention pill purely via a matrix.to link in formatted_body and
# emits no m.mentions field; the plaintext body is just "Bernard: ..."). These
# were silently dropped before we scanned formatted_body for the bot mxid.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_formatted_body_pill_link_without_m_mentions_is_a_mention():
    adapter = _make_adapter()
    event = _make_event(
        "Bernard: can you help me find a laser in Brussels",
        content={
            "format": "org.matrix.custom.html",
            "formatted_body": (
                f'<a href="https://matrix.to/#/{BOT_USER_ID}">@bernard:matrix.org</a>'
                ": can you help me find a laser in Brussels"
            ),
        },
    )
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is True


# ---------------------------------------------------------------------------
# Trigger suppression (feature, 2026-07-03): a @bernard mention shown inside
# `inline code`, a ```fenced block```, or a "> " blockquote is someone
# demonstrating the command to another user, not addressing the bot — must
# NOT wake Bernard. Real m.mentions still counts (a client never emits it for
# code-span text).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_at_bernard_inside_inline_code_is_not_a_mention():
    adapter = _make_adapter()
    event = _make_event("hey jason, try `@bernard find laser brussels`")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is False


@pytest.mark.asyncio
async def test_at_bernard_inside_blockquote_is_not_a_mention():
    adapter = _make_adapter()
    event = _make_event("like this:\n> @bernard what tools do you have?")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is False


@pytest.mark.asyncio
async def test_pill_inside_html_code_span_is_not_a_mention():
    # plaintext body carries no literal "@bernard" — the only mention signal
    # is the formatted_body pill, and it sits inside <code>, so the HTML
    # strip must suppress it.
    adapter = _make_adapter()
    event = _make_event(
        "try this to find a laser",
        content={
            "format": "org.matrix.custom.html",
            "formatted_body": (
                f'try this: <code><a href="https://matrix.to/#/{BOT_USER_ID}">'
                "@bernard</a> find laser</code>"
            ),
        },
    )
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is False


@pytest.mark.asyncio
async def test_at_bernard_outside_code_still_a_mention_even_with_code_elsewhere():
    adapter = _make_adapter()
    event = _make_event("@bernard what does `!mom find` do?")
    await adapter._on_message(_make_room(), event)

    message = adapter._queue.get_nowait()
    assert message.is_mention is True


# ---------------------------------------------------------------------------
# send() thread relation (live bug, 2026-07-02): a reply inside a thread was
# duplicating into the main room timeline in Element — missing the stable-
# Threads-spec fallback fields (is_falling_back, m.in_reply_to) that tell
# thread-aware clients to collapse the reply into the thread only.
# Root cause turned out to be unrelated: a second bot process (local dev
# container) sharing the same Matrix account (@bernard:...) as the VPS bot,
# both replying to the same live events. These fallback fields are the
# correct, spec-compliant behavior — kept as-is.
# ---------------------------------------------------------------------------

def _make_message(thread_id: str = "", event_id: str = "$msg1") -> Message:
    return Message(text="!mom travel", user_id="@u:x", room_id="!room:x", platform="matrix",
                    raw=None, power_level=0, event_id=event_id, thread_id=thread_id)


@pytest.mark.asyncio
async def test_send_in_thread_includes_falling_back_fallback_fields():
    adapter = _make_adapter()
    adapter.client.room_send = AsyncMock(return_value=SimpleNamespace(event_id="$reply1"))
    context = _make_message(thread_id="$thread_root")

    await adapter.send("Usage: ...", context)

    sent_content = adapter.client.room_send.call_args.kwargs["content"]
    assert sent_content["m.relates_to"] == {
        "rel_type": "m.thread",
        "event_id": "$thread_root",
        "is_falling_back": True,
        "m.in_reply_to": {"event_id": "$thread_root"},
    }


@pytest.mark.asyncio
async def test_send_outside_thread_has_no_relates_to():
    adapter = _make_adapter()
    adapter.client.room_send = AsyncMock(return_value=SimpleNamespace(event_id="$reply1"))
    context = _make_message(thread_id="", event_id="")

    await adapter.send("plain reply", context)

    sent_content = adapter.client.room_send.call_args.kwargs["content"]
    assert "m.relates_to" not in sent_content
