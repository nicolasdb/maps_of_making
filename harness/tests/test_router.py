"""Tests for harness/router.py (Story 6.10 + 6.11): unknown intent reroutes to
agent.run() (fuzzy=True) instead of a hard unknown_ack; query and nl_discovery
intents both route to agent.run() (fuzzy=False, unchanged call shape) — the
nl_discovery branch's direct nl_to_sparql.dispatch() call was collapsed into
the single agent.run() orchestrator in Story 6.11 (SPARQL generation is now
the query_sparql tool); the final unrecognized-intent fallback stays a hard
unknown_ack; a FAQ-cache hit (Story 6.11 Tier 0) skips classify() but still
reaches agent.run(), just with a faq_hint payload."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "infra" / "link_handler"))
sys.path.insert(0, str(ROOT / "infra"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import agent_tools
import bernard
import router
from message import Message


@pytest.fixture(autouse=True)
def _voice():
    bernard.load_voice()


@pytest.fixture(autouse=True)
def _clear_pending():
    agent_tools.PENDING_ACTIONS.clear()
    yield
    agent_tools.PENDING_ACTIONS.clear()


def _make_message(text: str) -> Message:
    return Message(text=text, user_id="@u:x", room_id="!room:x", platform="matrix", raw=None, power_level=0)


@pytest.mark.asyncio
async def test_unknown_intent_routes_to_agent_run_fuzzy():
    with patch("router.intent_classifier.classify", new=AsyncMock(return_value="unknown")), \
         patch("router.agent.run", new=AsyncMock(return_value="an answer")) as mock_run, \
         patch("router.bernard.unknown_ack") as mock_ack:
        msg = _make_message("how can you help me?")
        result = await router.route(msg, session_id="s1")

    mock_run.assert_called_once_with(msg, session_id="s1", adapter=None, fuzzy=True)
    mock_ack.assert_not_called()
    assert result == "an answer"


@pytest.mark.asyncio
async def test_query_intent_routes_to_agent_run_not_fuzzy():
    with patch("router.intent_classifier.classify", new=AsyncMock(return_value="query")), \
         patch("router.agent.run", new=AsyncMock(return_value="query result")) as mock_run:
        msg = _make_message("could you show me the details of openfab?")
        result = await router.route(msg, session_id="s1")

    mock_run.assert_called_once_with(msg, session_id="s1", adapter=None)
    assert result == "query result"


@pytest.mark.asyncio
async def test_nl_discovery_intent_routes_to_agent_run_not_fuzzy():
    """nl_discovery no longer dispatches directly to nl_to_sparql — SPARQL
    generation is now the query_sparql tool inside agent.run()'s loop
    (Story 6.11 collapse). Same call shape as query."""
    with patch("router.intent_classifier.classify", new=AsyncMock(return_value="nl_discovery")), \
         patch("router.agent.run", new=AsyncMock(return_value="discovery result")) as mock_run:
        msg = _make_message("what ontology terms exist for tools?")
        result = await router.route(msg, session_id="s1")

    mock_run.assert_called_once_with(msg, session_id="s1", adapter=None)
    assert result == "discovery result"


@pytest.mark.asyncio
async def test_faq_cache_hit_calls_agent_run_with_hint():
    """A FAQ-cache hit skips classify() but still reaches agent.run() — the
    model call still happens, only the hint payload differs (Story 6.11 AC #7)."""
    with patch("router.faq_cache.match", return_value={
                "trigger": "open now in berlin",
                "description": "desc",
                "sparql_template": "SELECT * WHERE {}",
            }), \
         patch("router.intent_classifier.classify", new=AsyncMock()) as mock_classify, \
         patch("router.agent.run", new=AsyncMock(return_value="faq answer")) as mock_run:
        msg = _make_message("how many spaces are open now in Berlin and which one?")
        result = await router.route(msg, session_id="s1")

    mock_classify.assert_not_called()
    mock_run.assert_called_once_with(msg, session_id="s1", adapter=None, faq_hint="desc\nSELECT * WHERE {}")
    assert result == "faq answer"


@pytest.mark.asyncio
async def test_faq_cache_miss_calls_agent_run_without_hint():
    with patch("router.faq_cache.match", return_value=None), \
         patch("router.intent_classifier.classify", new=AsyncMock(return_value="query")), \
         patch("router.agent.run", new=AsyncMock(return_value="query result")) as mock_run:
        msg = _make_message("could you show me the details of openfab?")
        result = await router.route(msg, session_id="s1")

    mock_run.assert_called_once_with(msg, session_id="s1", adapter=None)
    assert result == "query result"


@pytest.mark.asyncio
async def test_unrecognized_intent_falls_back_to_hard_unknown_ack():
    with patch("router.intent_classifier.classify", new=AsyncMock(return_value="totally_unrecognized")), \
         patch("router.agent.run", new=AsyncMock()) as mock_run:
        msg = _make_message("gibberish classifier result")
        result = await router.route(msg, session_id="s1")

    mock_run.assert_not_called()
    assert result == bernard.unknown_ack()
