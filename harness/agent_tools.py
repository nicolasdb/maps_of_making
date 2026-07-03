"""Tool registry for the Bernard tool-calling agent spike (Story 6.9).

Wraps existing, unmodified effect functions (git_ops, commands, query_commands,
nl_to_sparql) with OpenAI tool-schema dicts. `propose_write` is the ONLY
write-shaped tool — there is no commit/execute tool exposed to the model, so
confirm-before-write is enforced by construction, not by prompt instruction.
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional

import structlog

import commands
import nl_to_sparql
import query_commands
from bot import git_ops

log = structlog.get_logger()

CAPABILITY_GAPS_DB_DEFAULT = "/app/tasks/capability_gaps.db"
FUZZY_QUESTIONS_DB_DEFAULT = "/app/tasks/fuzzy_questions.db"


def _capability_gaps_db_path() -> str:
    return os.environ.get("CAPABILITY_GAPS_DB_PATH", CAPABILITY_GAPS_DB_DEFAULT)


def _fuzzy_questions_db_path() -> str:
    return os.environ.get("FUZZY_QUESTIONS_DB_PATH", FUZZY_QUESTIONS_DB_DEFAULT)


def _init_capability_gaps_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS capability_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_request TEXT NOT NULL,
            note TEXT,
            room_id TEXT,
            gap_kind TEXT NOT NULL DEFAULT 'capability'
        )
    """)
    # Migration guard: existing DB files predate the gap_kind column (Story 6.11).
    cols = {row[1] for row in con.execute("PRAGMA table_info(capability_gaps)").fetchall()}
    if "gap_kind" not in cols:
        con.execute("ALTER TABLE capability_gaps ADD COLUMN gap_kind TEXT NOT NULL DEFAULT 'capability'")
    con.commit()
    con.close()


def _init_fuzzy_questions_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS fuzzy_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_request TEXT NOT NULL,
            resolved INTEGER NOT NULL,
            room_id TEXT
        )
    """)
    con.commit()
    con.close()


def _write_capability_gap(raw_request: str, note: str, room_id: str, gap_kind: str = "capability") -> None:
    from datetime import datetime, timezone

    path = _capability_gaps_db_path()
    _init_capability_gaps_db(path)
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO capability_gaps (timestamp, raw_request, note, room_id, gap_kind) VALUES (?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), raw_request, note, room_id, gap_kind),
    )
    con.commit()
    con.close()


def log_fuzzy_question(raw_request: str, resolved: bool, room_id: str = "") -> None:
    """Analytics for every fuzzy (unknown-intent) question routed through the
    agent — independent of log_gap. A resolved question is never a gap; an
    unresolved on-topic question is both a gap row (log_gap) AND a
    resolved=false row here. Off-topic refusals count as resolved=true."""
    from datetime import datetime, timezone

    path = _fuzzy_questions_db_path()
    _init_fuzzy_questions_db(path)
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO fuzzy_questions (timestamp, raw_request, resolved, room_id) VALUES (?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), raw_request, int(resolved), room_id),
    )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Pending-action store — first piece of cross-message state in the harness.
# Keyed by (room_id, user_id). In-memory, module-level dict; no persistence
# layer for this spike (Dev Notes: "Bot is currently fully stateless").
# ---------------------------------------------------------------------------
PENDING_ACTIONS: dict[tuple[str, str], dict] = {}

# How long a proposed write stays confirmable. A ✅ reaction after this
# window is treated as expired rather than silently committing a possibly-stale delta.
PENDING_ACTION_TTL_SECONDS = 60


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------

async def read_space(slug_or_room: str, room_id: str) -> dict:
    """Read a space's JSON. If slug_or_room looks like a room-linked space
    (empty/None), resolve via the room; else treat as a public slug fetch."""
    if not slug_or_room:
        space_id = await git_ops.resolve_space_for_room(room_id)
        return await git_ops.read_json(space_id)
    data = await query_commands.fetch_space_json(slug_or_room)
    if data is None:
        raise ValueError(f"No space found for slug {slug_or_room!r}")
    return data


async def query_map(kind: str, **kwargs) -> str:
    """Read-only passthrough to query_commands.find/nearby/network."""
    if kind == "find":
        return await query_commands.find(kwargs["tag"], kwargs["city"])
    if kind == "nearby":
        return await query_commands.nearby(kwargs["city"], float(kwargs["radius_km"]))
    if kind == "network":
        return await query_commands.network(kwargs["network_name"])
    raise ValueError(f"Unknown query_map kind: {kind!r}")


async def query_sparql(question: str, model: str, session_id: str = "") -> dict:
    """Read-only passthrough to nl_to_sparql.generate_and_run — for questions
    that don't fit query_map's fixed find/nearby/network shapes. `model` is
    supplied by the caller (agent.py's _dispatch_tool), not chosen here."""
    return await nl_to_sparql.generate_and_run(question, model=model, session_id=session_id)


# ---------------------------------------------------------------------------
# propose_write — the only write-shaped tool. Never calls git_ops.commit_json.
# ---------------------------------------------------------------------------

async def propose_write(
    field_path: str, new_value: str, *, room_id: str, user_id: str, power_level: int, thread_root: str = ""
) -> dict:
    """Validate a proposed write and stash it in PENDING_ACTIONS for confirmation.
    Returns the delta (current vs. proposed) for the model to echo back to the user.
    Never calls git_ops.commit_json — that only happens on a later confirmation message."""
    allowed, reason = commands._can_write(power_level, field_path)
    if not allowed:
        return {"allowed": False, "reason": reason}

    if (room_id, user_id) in PENDING_ACTIONS:
        return {"allowed": False, "reason": "pending_action_exists"}

    valid, err = commands._validate_value(field_path, new_value)
    if not valid:
        return {"allowed": False, "reason": "invalid_value", "detail": err}

    space_id = await git_ops.resolve_space_for_room(room_id)

    if field_path == "mom.memberOf":
        current_data = await git_ops.read_json(space_id)
        current_array = commands._extract_field(current_data, field_path) or []
        proposed_array = _apply_member_of_delta(current_array, new_value)
        proposed_value = proposed_array
        current_value = current_array
    else:
        current_data = await git_ops.read_json(space_id)
        current_value = commands._extract_field(current_data, field_path)
        proposed_value = commands._coerce_value(field_path, new_value)

    import time

    PENDING_ACTIONS[(room_id, user_id)] = {
        "field_path": field_path,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "space_id": space_id,
        "created_at": time.monotonic(),
        "prompt_event_id": None,  # stamped by main_matrix once the confirm-ask has actually been sent
        "thread_root": thread_root,  # kept stable across the confirm-ask + commit-ack so both land in the same Matrix thread
    }
    return {
        "allowed": True,
        "field_path": field_path,
        "current_value": current_value,
        "proposed_value": proposed_value,
    }


def _apply_member_of_delta(current_array: list, new_value: str) -> list:
    """add:X / remove:X semantics against the existing mom.memberOf array;
    a bare value (no add:/remove: prefix) is treated as add: for convenience.
    A full JSON array replaces the array wholesale (existing _coerce_value shape)."""
    current_array = list(current_array)
    value = new_value.strip()
    if value.startswith("["):
        return commands._coerce_value("mom.memberOf", value)
    if value.lower().startswith("add:"):
        member = value[4:].strip()
        if member not in current_array:
            current_array.append(member)
        return current_array
    if value.lower().startswith("remove:"):
        member = value[7:].strip()
        return [m for m in current_array if m != member]
    # bare value → add
    if value not in current_array:
        current_array.append(value)
    return current_array


# ---------------------------------------------------------------------------
# log_gap — ontology gaps reuse the existing FR41 mechanism; capability gaps
# get a new SQLite table (event/telemetry data, wrong shape for Oxigraph).
# ---------------------------------------------------------------------------

async def log_gap(raw_request: str, note: str, gap_kind: str, room_id: str = "") -> None:
    """Both gap kinds share the capability_gaps SQLite table now — the
    ontology-vs-capability distinction is a column value, not a separate
    store (Story 6.11, AC #6; retires the RDF <urn:mak:gaps> writer)."""
    if gap_kind not in ("ontology", "capability"):
        raise ValueError(f"Unknown gap_kind: {gap_kind!r}")
    _write_capability_gap(raw_request, note, room_id, gap_kind=gap_kind)


# ---------------------------------------------------------------------------
# OpenAI tool-schema dicts
# ---------------------------------------------------------------------------

READ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_space",
            "description": "Read a space's JSON fields. Pass empty string to read the room-linked space, or a slug to look up any public space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slug_or_room": {"type": "string", "description": "Space slug, or empty string for the current room's linked space"},
                },
                "required": ["slug_or_room"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_map",
            "description": "Search confirmed spaces: find by tag+city, nearby by city+radius, or network by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["find", "nearby", "network"]},
                    "tag": {"type": "string"},
                    "city": {"type": "string"},
                    "radius_km": {"type": "string"},
                    "network_name": {"type": "string"},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_sparql",
            "description": "Generate and run a SPARQL query for a question that doesn't fit query_map's fixed find/nearby/network shapes. Use when the question needs a different filter/combination than those three support.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The user's natural-language question, verbatim"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_gap",
            "description": "Log a request Bernard can't fulfill — either a missing ontology concept (gap_kind=ontology) or a missing bot capability (gap_kind=capability).",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_request": {"type": "string"},
                    "note": {"type": "string"},
                    "gap_kind": {"type": "string", "enum": ["ontology", "capability"]},
                },
                "required": ["raw_request", "note", "gap_kind"],
            },
        },
    },
]

WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_write",
        "description": "Propose a change to a field on the room-linked space. Does NOT commit — stashes the change pending user confirmation. Returns current vs. proposed value for you to echo back before asking to confirm.",
        "parameters": {
            "type": "object",
            "properties": {
                "field_path": {"type": "string", "description": "e.g. state.open, contact.matrix, mom.memberOf"},
                "new_value": {"type": "string", "description": "For mom.memberOf: 'add:X', 'remove:X', or a full JSON array"},
            },
            "required": ["field_path", "new_value"],
        },
    },
}


def build_tools(power_level: int) -> list[dict]:
    """Permission gate before tool exposure. Callers with power_level < 100
    never receive propose_write — non-coordinators cannot trigger a write path
    even if they ask the model to."""
    tools = list(READ_TOOLS)
    if power_level >= 100:
        tools.append(WRITE_TOOL)
    return tools
