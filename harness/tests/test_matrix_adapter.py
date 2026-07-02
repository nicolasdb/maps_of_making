"""Tests for harness/matrix_adapter.py's mention detection (Story 6.10
follow-up): a message must be an actual @mention (m.mentions naming the bot,
or a literal "@bernard" in the body) to be treated as one — a sentence that
merely starts with the word "bernard" (no @) must NOT false-trigger."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from matrix_adapter import MatrixAdapter

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
