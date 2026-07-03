"""Tests for harness/agent.py + harness/agent_tools.py (Story 6.9 spike):
mom.memberOf delta arithmetic, confirm-before-write gating, permission-gated
tool exposure, and gap-logging on unfulfillable requests."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "infra" / "link_handler"))
sys.path.insert(0, str(ROOT / "infra"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import agent
import agent_tools
import bernard
import bernard_agent_prompt
import llm_client
from message import Message


@pytest.fixture(autouse=True)
def _voice():
    bernard.load_voice()


@pytest.fixture(autouse=True)
def _clear_pending():
    agent_tools.PENDING_ACTIONS.clear()
    yield
    agent_tools.PENDING_ACTIONS.clear()


def _make_message(text: str, power_level: int = 0) -> Message:
    return Message(text=text, user_id="@u:x", room_id="!room:x", platform="matrix", raw=None, power_level=power_level)


def _make_reaction(user_id: str = "@u:x", event_id: str = "") -> Message:
    return Message(text="yes", user_id=user_id, room_id="!room:x", platform="matrix", raw=None,
                    power_level=100, event_id=event_id, via_reaction=True)


def _fake_tool_call(name: str, arguments: dict, call_id: str = "call_1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


# ---------------------------------------------------------------------------
# mom.memberOf delta arithmetic
# ---------------------------------------------------------------------------

def test_member_of_add_appends_new_member():
    result = agent_tools._apply_member_of_delta(["VOW"], "add:Openfab")
    assert result == ["VOW", "Openfab"]


def test_member_of_add_is_idempotent():
    result = agent_tools._apply_member_of_delta(["VOW"], "add:VOW")
    assert result == ["VOW"]


def test_member_of_remove_drops_member():
    result = agent_tools._apply_member_of_delta(["VOW", "Openfab"], "remove:VOW")
    assert result == ["Openfab"]


def test_member_of_bare_value_treated_as_add():
    result = agent_tools._apply_member_of_delta(["VOW"], "Openfab")
    assert result == ["VOW", "Openfab"]


def test_member_of_full_json_array_replaces_wholesale():
    result = agent_tools._apply_member_of_delta(["VOW"], '["Openfab", "Hackerspace"]')
    assert result == ["Openfab", "Hackerspace"]


# ---------------------------------------------------------------------------
# Write is never committed without an intervening confirmation step
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_propose_write_never_commits():
    with patch("agent_tools.commands._can_write", return_value=(True, "ok")), \
         patch("agent_tools.commands._validate_value", return_value=(True, "")), \
         patch("agent_tools.git_ops.resolve_space_for_room", new=AsyncMock(return_value="openfab")), \
         patch("agent_tools.git_ops.read_json", new=AsyncMock(return_value={"mom": {"memberOf": ["VOW"]}})), \
         patch("agent_tools.git_ops.commit_json", new=AsyncMock()) as mock_commit:
        result = await agent_tools.propose_write(
            "mom.memberOf", "add:Openfab", room_id="!room:x", user_id="@u:x", power_level=100,
        )

    assert result["allowed"] is True
    assert result["proposed_value"] == ["VOW", "Openfab"]
    mock_commit.assert_not_called()
    assert agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")]["proposed_value"] == ["VOW", "Openfab"]


@pytest.mark.asyncio
async def test_agent_run_commits_only_after_confirmation():
    tool_call = _fake_tool_call("propose_write", {"field_path": "mom.memberOf", "new_value": "add:Openfab"})

    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(side_effect=[
                ("", [tool_call], "model", 1),
                ("Current: [VOW]. Proposed: [VOW, Openfab]. Confirm?", None, "model", 1),
            ])), \
         patch("agent_tools.commands._can_write", return_value=(True, "ok")), \
         patch("agent_tools.commands._validate_value", return_value=(True, "")), \
         patch("agent_tools.git_ops.resolve_space_for_room", new=AsyncMock(return_value="openfab")), \
         patch("agent_tools.git_ops.read_json", new=AsyncMock(return_value={"mom": {"memberOf": ["VOW"]}})), \
         patch("agent.git_ops.commit_json", new=AsyncMock()) as mock_commit:
        msg = _make_message("add Openfab to VOW's networks", power_level=100)
        first_response = await agent.run(msg, session_id="s1")

    assert "Confirm" in first_response
    mock_commit.assert_not_called()

    with patch("agent.git_ops.commit_json", new=AsyncMock(return_value="abc123")) as mock_commit:
        confirm_msg = _make_reaction()
        second_response = await agent.run(confirm_msg, session_id="s1")

    mock_commit.assert_called_once()
    assert "abc123" in second_response or "abc123"[:7] in second_response


@pytest.mark.asyncio
async def test_confirm_pending_schedules_cdn_poll_when_adapter_given():
    agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab", "created_at": __import__("time").monotonic(),
        "prompt_event_id": None,
    }
    reaction_msg = _make_reaction()
    fake_adapter = object()

    with patch("agent.git_ops.commit_json", new=AsyncMock(return_value="sha1")), \
         patch("agent.commands._poll_and_refresh", new=AsyncMock()) as mock_poll:
        await agent.run(reaction_msg, session_id="s1", adapter=fake_adapter)
        await asyncio.sleep(0)  # let the scheduled task actually run

    mock_poll.assert_called_once_with("openfab", "state.open", "true", "sha1", fake_adapter, reaction_msg)


@pytest.mark.asyncio
async def test_confirm_pending_skips_cdn_poll_without_adapter():
    agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab", "created_at": __import__("time").monotonic(),
        "prompt_event_id": None,
    }
    reaction_msg = _make_reaction()

    with patch("agent.git_ops.commit_json", new=AsyncMock(return_value="sha1")), \
         patch("agent.commands._poll_and_refresh", new=AsyncMock()) as mock_poll:
        await agent.run(reaction_msg, session_id="s1")  # no adapter

    mock_poll.assert_not_called()


@pytest.mark.asyncio
async def test_typed_yes_no_longer_confirms():
    """Confirmation is reaction-only — a typed 'yes' must NOT commit, even
    with a pending action waiting."""
    agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab", "created_at": __import__("time").monotonic(),
        "prompt_event_id": None,
    }
    typed_yes = _make_message("yes", power_level=100)

    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(return_value=("ok", None, "model", 1))), \
         patch("agent.git_ops.commit_json", new=AsyncMock()) as mock_commit:
        await agent.run(typed_yes, session_id="s1")

    mock_commit.assert_not_called()
    assert ("!room:x", "@u:x") in agent_tools.PENDING_ACTIONS  # still pending — untouched


# ---------------------------------------------------------------------------
# Reaction-confirmation must target the actual confirm-ask message; expiry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaction_confirmation_on_wrong_message_is_ignored():
    agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab", "created_at": __import__("time").monotonic(),
        "prompt_event_id": "$correct_event",
    }
    reaction_msg = Message(
        text="yes", user_id="@u:x", room_id="!room:x", platform="matrix", raw=None,
        power_level=100, event_id="$some_other_event", via_reaction=True,
    )

    with patch("agent.git_ops.commit_json", new=AsyncMock()) as mock_commit:
        response = await agent.run(reaction_msg, session_id="s1")

    assert response == ""
    mock_commit.assert_not_called()
    assert ("!room:x", "@u:x") in agent_tools.PENDING_ACTIONS  # not consumed


@pytest.mark.asyncio
async def test_reaction_confirmation_on_correct_message_commits():
    agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab", "created_at": __import__("time").monotonic(),
        "prompt_event_id": "$correct_event",
    }
    reaction_msg = Message(
        text="yes", user_id="@u:x", room_id="!room:x", platform="matrix", raw=None,
        power_level=100, event_id="$correct_event", via_reaction=True,
    )

    with patch("agent.git_ops.commit_json", new=AsyncMock(return_value="sha1")) as mock_commit:
        response = await agent.run(reaction_msg, session_id="s1")

    mock_commit.assert_called_once()
    assert "sha1" in response


@pytest.mark.asyncio
async def test_expired_pending_action_is_not_committed():
    import time as _time
    agent_tools.PENDING_ACTIONS[("!room:x", "@u:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab",
        "created_at": _time.monotonic() - agent_tools.PENDING_ACTION_TTL_SECONDS - 1,
        "prompt_event_id": None,
    }
    reaction_msg = _make_reaction()

    with patch("agent.git_ops.commit_json", new=AsyncMock()) as mock_commit:
        response = await agent.run(reaction_msg, session_id="s1")

    mock_commit.assert_not_called()
    assert ("!room:x", "@u:x") not in agent_tools.PENDING_ACTIONS
    assert response == bernard.write_confirmation_expired_ack()


@pytest.mark.asyncio
async def test_a_different_users_reaction_does_not_confirm_someone_elses_write():
    """(room_id, user_id) keying means Jason reacting ✅ on nicolas's confirm
    prompt looks up a pending action for (room, jason) — which doesn't exist —
    not nicolas's. Confirms cross-user isolation by construction."""
    agent_tools.PENDING_ACTIONS[("!room:x", "@nicolas:x")] = {
        "field_path": "state.open", "current_value": False, "proposed_value": True,
        "space_id": "openfab", "created_at": __import__("time").monotonic(),
        "prompt_event_id": "$nicolas_confirm_prompt",
    }
    jasons_reaction = _make_reaction(user_id="@jason:x", event_id="$nicolas_confirm_prompt")

    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(return_value=("ok", None, "model", 1))), \
         patch("agent.git_ops.commit_json", new=AsyncMock()) as mock_commit:
        await agent.run(jasons_reaction, session_id="s1")

    mock_commit.assert_not_called()
    assert ("!room:x", "@nicolas:x") in agent_tools.PENDING_ACTIONS  # nicolas's write still pending, untouched


# ---------------------------------------------------------------------------
# power_level < 100 never receives propose_write in its tool list
# ---------------------------------------------------------------------------

def test_build_tools_excludes_write_tool_for_non_coordinator():
    tools = agent_tools.build_tools(power_level=0)
    tool_names = {t["function"]["name"] for t in tools}
    assert "propose_write" not in tool_names


def test_build_tools_includes_write_tool_for_coordinator():
    tools = agent_tools.build_tools(power_level=100)
    tool_names = {t["function"]["name"] for t in tools}
    assert "propose_write" in tool_names


@pytest.mark.asyncio
async def test_agent_run_passes_reduced_tools_for_non_coordinator():
    mock_complete = AsyncMock(return_value=("no can do", None, "model", 1))
    with patch("agent.llm_client.complete_with_tools", new=mock_complete):
        msg = _make_message("add Openfab to VOW's networks", power_level=0)
        await agent.run(msg, session_id="s1")

    passed_tools = mock_complete.call_args.kwargs["tools"]
    tool_names = {t["function"]["name"] for t in passed_tools}
    assert "propose_write" not in tool_names


@pytest.mark.asyncio
async def test_fuzzy_question_from_non_coordinator_still_gets_no_write_tool(tmp_path, monkeypatch):
    """Regression check (Story 6.10 AC #3): routing a fuzzy question through
    agent.run(fuzzy=True) does not add a new gating path — the existing
    power_level < 100 gate from Story 6.9 still applies."""
    monkeypatch.setenv("FUZZY_QUESTIONS_DB_PATH", str(tmp_path / "fuzzy_questions.db"))
    mock_complete = AsyncMock(return_value=("here's what I know", None, "model", 1))
    with patch("agent.llm_client.complete_with_tools", new=mock_complete):
        msg = _make_message("how can you help me?", power_level=0)
        await agent.run(msg, session_id="s1", fuzzy=True)

    passed_tools = mock_complete.call_args.kwargs["tools"]
    tool_names = {t["function"]["name"] for t in passed_tools}
    assert "propose_write" not in tool_names


# ---------------------------------------------------------------------------
# Unfulfillable request calls log_gap with the correct gap_kind
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_gap_capability_writes_sqlite_row(tmp_path, monkeypatch):
    db_path = str(tmp_path / "capability_gaps.db")
    monkeypatch.setenv("CAPABILITY_GAPS_DB_PATH", db_path)

    await agent_tools.log_gap("what time is it in Taipei", "no timezone tool", "capability", room_id="!room:x")

    import sqlite3
    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT raw_request, note, room_id FROM capability_gaps").fetchall()
    con.close()
    assert rows == [("what time is it in Taipei", "no timezone tool", "!room:x")]


@pytest.mark.asyncio
async def test_log_gap_ontology_writes_capability_gaps_row(tmp_path, monkeypatch):
    """Ontology gaps now share the capability_gaps SQLite table, distinguished
    by gap_kind (Story 6.11 AC #6) — the RDF <urn:mak:gaps> writer is retired."""
    db_path = str(tmp_path / "capability_gaps.db")
    monkeypatch.setenv("CAPABILITY_GAPS_DB_PATH", db_path)

    await agent_tools.log_gap("what's the ontology term for X", "no match", "ontology")

    import sqlite3
    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT raw_request, note, gap_kind FROM capability_gaps").fetchall()
    con.close()
    assert rows == [("what's the ontology term for X", "no match", "ontology")]


@pytest.mark.asyncio
async def test_agent_run_dispatches_log_gap_tool_call(monkeypatch, tmp_path):
    monkeypatch.setenv("CAPABILITY_GAPS_DB_PATH", str(tmp_path / "capability_gaps.db"))
    tool_call = _fake_tool_call("log_gap", {
        "raw_request": "what time is it in Taipei, is it open now?",
        "note": "no timezone capability",
        "gap_kind": "capability",
    })

    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(side_effect=[
                ("", [tool_call], "model", 1),
                ("Can't do that yet — logged it.", None, "model", 1),
            ])):
        msg = _make_message("what time is it in Taipei, is it open now?", power_level=0)
        response = await agent.run(msg, session_id="s1")

    assert "logged" in response.lower()

    import sqlite3
    con = sqlite3.connect(str(tmp_path / "capability_gaps.db"))
    rows = con.execute("SELECT raw_request FROM capability_gaps").fetchall()
    con.close()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Off-topic refusal is distinct from an on-topic capability gap (Story 6.10)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_off_topic_refusal_does_not_call_log_gap(tmp_path, monkeypatch):
    """Given a canned off-topic user message and a mocked LLM response
    reflecting the in-character refusal (no tool call), log_gap must not be
    called — distinguishing 'declined to answer' from 'logged as a gap'."""
    monkeypatch.setenv("FUZZY_QUESTIONS_DB_PATH", str(tmp_path / "fuzzy_questions.db"))
    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(
                return_value=("Not my department. Ask someone who cares about the weather.", None, "model", 1))), \
         patch("agent_tools.log_gap", new=AsyncMock()) as mock_log_gap:
        msg = _make_message("what's the weather like today?", power_level=0)
        response = await agent.run(msg, session_id="s1", fuzzy=True)

    mock_log_gap.assert_not_called()
    assert "weather" in response.lower()


# ---------------------------------------------------------------------------
# Fuzzy-question analytics logging (Story 6.10, AC #9)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fuzzy_question_resolved_logs_analytics_row(tmp_path, monkeypatch):
    monkeypatch.setenv("FUZZY_QUESTIONS_DB_PATH", str(tmp_path / "fuzzy_questions.db"))
    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(
                return_value=("Here's what I know about that space.", None, "model", 1))):
        msg = _make_message("how can you help me?", power_level=0)
        await agent.run(msg, session_id="s1", fuzzy=True)

    import sqlite3
    con = sqlite3.connect(str(tmp_path / "fuzzy_questions.db"))
    rows = con.execute("SELECT raw_request, resolved FROM fuzzy_questions").fetchall()
    con.close()
    assert rows == [("how can you help me?", 1)]


@pytest.mark.asyncio
async def test_fuzzy_question_unresolved_gap_logs_both_gap_and_unresolved_analytics(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPABILITY_GAPS_DB_PATH", str(tmp_path / "capability_gaps.db"))
    monkeypatch.setenv("FUZZY_QUESTIONS_DB_PATH", str(tmp_path / "fuzzy_questions.db"))
    tool_call = _fake_tool_call("log_gap", {
        "raw_request": "what's the isochrone from a space that doesn't exist",
        "note": "no isochrone tool",
        "gap_kind": "capability",
    })

    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(side_effect=[
                ("", [tool_call], "model", 1),
                ("Can't do that yet — logged it.", None, "model", 1),
            ])):
        msg = _make_message("what's the isochrone from a space that doesn't exist", power_level=0)
        await agent.run(msg, session_id="s1", fuzzy=True)

    import sqlite3
    gap_con = sqlite3.connect(str(tmp_path / "capability_gaps.db"))
    gap_rows = gap_con.execute("SELECT raw_request FROM capability_gaps").fetchall()
    gap_con.close()
    assert len(gap_rows) == 1

    fuzzy_con = sqlite3.connect(str(tmp_path / "fuzzy_questions.db"))
    fuzzy_rows = fuzzy_con.execute("SELECT raw_request, resolved FROM fuzzy_questions").fetchall()
    fuzzy_con.close()
    assert fuzzy_rows == [("what's the isochrone from a space that doesn't exist", 0)]


@pytest.mark.asyncio
async def test_write_intent_agent_run_does_not_log_fuzzy_analytics(tmp_path, monkeypatch):
    """fuzzy=False (the write-intent call shape, unchanged) must not touch
    the fuzzy_questions table at all."""
    db_path = str(tmp_path / "fuzzy_questions.db")
    monkeypatch.setenv("FUZZY_QUESTIONS_DB_PATH", db_path)
    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(
                return_value=("ok", None, "model", 1))):
        msg = _make_message("set state.open to true", power_level=100)
        await agent.run(msg, session_id="s1")

    assert not Path(db_path).exists()


@pytest.mark.asyncio
async def test_capability_gaps_db_migration_adds_gap_kind_column(tmp_path, monkeypatch):
    """A capability_gaps.db predating Story 6.11 lacks gap_kind — the
    ALTER TABLE guard must backfill it without erroring on the old rows."""
    import sqlite3
    db_path = str(tmp_path / "capability_gaps.db")
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE capability_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_request TEXT NOT NULL,
            note TEXT,
            room_id TEXT
        )
    """)
    con.execute("INSERT INTO capability_gaps (timestamp, raw_request, note, room_id) VALUES ('t', 'old row', '', '')")
    con.commit()
    con.close()

    monkeypatch.setenv("CAPABILITY_GAPS_DB_PATH", db_path)
    await agent_tools.log_gap("new row", "note", "capability")

    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT raw_request, gap_kind FROM capability_gaps ORDER BY id").fetchall()
    con.close()
    assert rows == [("old row", "capability"), ("new row", "capability")]


# ---------------------------------------------------------------------------
# query_sparql tool (Story 6.11): folds nl_to_sparql into the tool catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_run_dispatches_query_sparql_tool():
    tool_call = _fake_tool_call("query_sparql", {"question": "makerspaces in Ghent"})

    with patch("agent.llm_client.complete_with_tools", new=AsyncMock(side_effect=[
                ("", [tool_call], "model", 1),
                ("Here's what I found.", None, "model", 1),
            ])), \
         patch("agent_tools.query_sparql", new=AsyncMock(
                return_value={"bindings": [{"name": {"value": "OpenFab"}}], "sparql": "SELECT ...", "count": 1})) as mock_qs:
        msg = _make_message("makerspaces in Ghent", power_level=0)
        response = await agent.run(msg, session_id="s1")

    mock_qs.assert_called_once_with("makerspaces in Ghent", model=llm_client.MODEL, session_id="s1")
    assert response == "Here's what I found."


# ---------------------------------------------------------------------------
# Tier-2 escalation (Story 6.11, AC #4/#8): query_sparql error or
# empty-but-specific result retries the NEXT complete_with_tools call on
# SONNET_MODEL, once per run.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tier2_escalates_on_query_sparql_error():
    tool_call = _fake_tool_call("query_sparql", {"question": "how many spaces are in Ghent"})

    mock_complete = AsyncMock(side_effect=[
        ("", [tool_call], "model", 1),
        ("Escalated answer.", None, "model", 1),
    ])
    with patch("agent.llm_client.complete_with_tools", new=mock_complete), \
         patch("agent_tools.query_sparql", new=AsyncMock(return_value={"error": "sparql failed"})):
        msg = _make_message("how many spaces are in Ghent", power_level=0)
        await agent.run(msg, session_id="s1")

    assert mock_complete.call_args_list[0].kwargs["model"] == llm_client.MODEL
    assert mock_complete.call_args_list[1].kwargs["model"] == llm_client.SONNET_MODEL


@pytest.mark.asyncio
async def test_tier2_escalates_on_empty_and_specific_question():
    tool_call = _fake_tool_call("query_sparql", {"question": "how many spaces are open in Ghent"})

    mock_complete = AsyncMock(side_effect=[
        ("", [tool_call], "model", 1),
        ("Escalated answer.", None, "model", 1),
    ])
    with patch("agent.llm_client.complete_with_tools", new=mock_complete), \
         patch("agent_tools.query_sparql", new=AsyncMock(return_value={"bindings": [], "sparql": "SELECT ...", "count": 0})):
        msg = _make_message("how many spaces are open in Ghent", power_level=0)
        await agent.run(msg, session_id="s1")

    assert mock_complete.call_args_list[0].kwargs["model"] == llm_client.MODEL
    assert mock_complete.call_args_list[1].kwargs["model"] == llm_client.SONNET_MODEL


@pytest.mark.asyncio
async def test_tier2_does_not_escalate_on_empty_generic_question():
    """Regression guard: zero bindings alone is not enough — the question
    must also contain one of _SPECIFIC_ANSWER_KEYWORDS."""
    tool_call = _fake_tool_call("query_sparql", {"question": "tell me about spaces in Ghent"})

    mock_complete = AsyncMock(side_effect=[
        ("", [tool_call], "model", 1),
        ("Normal empty-result answer.", None, "model", 1),
    ])
    with patch("agent.llm_client.complete_with_tools", new=mock_complete), \
         patch("agent_tools.query_sparql", new=AsyncMock(return_value={"bindings": [], "sparql": "SELECT ...", "count": 0})):
        msg = _make_message("tell me about spaces in Ghent", power_level=0)
        await agent.run(msg, session_id="s1")

    assert mock_complete.call_args_list[0].kwargs["model"] == llm_client.MODEL
    assert mock_complete.call_args_list[1].kwargs["model"] == llm_client.MODEL


@pytest.mark.asyncio
async def test_tier2_escalation_ceiling_no_second_retry():
    """A second Trigger A/B after the escalated retry falls through to the
    normal unknown_ack()/gap-log path — no third model attempt."""
    tool_call = _fake_tool_call("query_sparql", {"question": "how many spaces are in Ghent"})

    # One entry per agent.MAX_TOOL_ITERATIONS — always a tool call, always
    # triggering Trigger A, so escalation-ceiling behavior isn't tied to a
    # hardcoded iteration count.
    mock_complete = AsyncMock(side_effect=[("", [tool_call], "model", 1)] * agent.MAX_TOOL_ITERATIONS)
    with patch("agent.llm_client.complete_with_tools", new=mock_complete), \
         patch("agent_tools.query_sparql", new=AsyncMock(return_value={"error": "sparql failed"})), \
         patch("agent_tools.log_fuzzy_question") as mock_log_fuzzy:
        msg = _make_message("how many spaces are in Ghent", power_level=0)
        response = await agent.run(msg, session_id="s1", fuzzy=True)

    models_used = [c.kwargs["model"] for c in mock_complete.call_args_list]
    expected = [llm_client.MODEL, llm_client.SONNET_MODEL] + [llm_client.MODEL] * (agent.MAX_TOOL_ITERATIONS - 2)
    assert models_used == expected
    assert response == bernard.unknown_ack()
    mock_log_fuzzy.assert_called_once_with("how many spaces are in Ghent", resolved=False, room_id="!room:x")


# ---------------------------------------------------------------------------
# faq_hint passthrough (Story 6.11, AC #5/#8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_faq_hint_appended_to_system_prompt():
    mock_complete = AsyncMock(return_value=("answer", None, "model", 1))
    with patch("agent.llm_client.complete_with_tools", new=mock_complete):
        msg = _make_message("how many spaces are open now in Berlin and which one?", power_level=0)
        await agent.run(msg, session_id="s1", faq_hint="validated pattern text")

    system_arg = mock_complete.call_args.kwargs["system"]
    assert "validated pattern text" in system_arg
    assert bernard_agent_prompt.SYSTEM_PROMPT in system_arg


@pytest.mark.asyncio
async def test_no_faq_hint_leaves_system_prompt_unchanged():
    mock_complete = AsyncMock(return_value=("answer", None, "model", 1))
    with patch("agent.llm_client.complete_with_tools", new=mock_complete):
        msg = _make_message("what's the status of openfab?", power_level=0)
        await agent.run(msg, session_id="s1")

    assert mock_complete.call_args.kwargs["system"] == bernard_agent_prompt.SYSTEM_PROMPT
