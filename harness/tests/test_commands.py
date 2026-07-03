"""Router-level tests for harness/commands.py (Story 6.1 + 6.2): `!mom link` /
`!mom update` literal-command parsing, permission gate, CDN-poll flow, and
open/close/status verbs."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "infra" / "link_handler"))  # bot_keys, schema — git_ops's deps
sys.path.insert(0, str(ROOT / "infra"))  # for `from bot import git_ops`
sys.path.insert(0, str(Path(__file__).parent.parent))  # harness/ itself

import bernard
import commands
from bot import git_ops
from message import Message


@pytest.fixture(autouse=True)
def _voice():
    bernard.load_voice()


def _make_context(power_level: int = 0) -> Message:
    return Message(text="", user_id="@u:x", room_id="!room:x", platform="matrix", raw=None, power_level=power_level)


# ---------------------------------------------------------------------------
# Story 6.1 — existing tests (no regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_command_text_falls_through_to_none():
    result = await commands.try_handle("what spaces are open", "@u:x", "!room:x", "sid")
    assert result is None


@pytest.mark.asyncio
async def test_link_command_returns_tutorial_on_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"public_key": "ssh-ed25519 AAAA test", "tutorial": "paste me", "space_id": "openfab"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, params=None, headers=None):
            assert "openfab" in url
            return FakeResponse()

    monkeypatch.setattr(commands.httpx, "AsyncClient", lambda timeout=None: FakeClient())
    monkeypatch.setattr(git_ops, "verify_setup", AsyncMock(side_effect=Exception("skip")))

    result = await commands.try_handle("link openfab", "@u:x", "!room:x", "sid")
    assert "paste me" in result


@pytest.mark.asyncio
async def test_link_command_returns_degraded_ack_on_http_failure(monkeypatch):
    import httpx

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, params=None, headers=None):
            raise httpx.HTTPError("boom")

    monkeypatch.setattr(commands.httpx, "AsyncClient", lambda timeout=None: FakeClient())

    result = await commands.try_handle("link openfab", "@u:x", "!room:x", "sid")
    assert result == bernard.link_failed_ack()


@pytest.mark.asyncio
async def test_update_command_no_deploy_key_becomes_degraded_ack_not_exception(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_commit(space_id, field_path, value, authorized_by):
        raise git_ops.NoDeployKeyError("no key")

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "commit_json", fake_commit)

    ctx = _make_context(power_level=100)
    result = await commands.try_handle('update state.open "true"', "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.no_deploy_key_ack()
    assert "Traceback" not in result


# ---------------------------------------------------------------------------
# Story 6.2 — _can_write permission gate
# ---------------------------------------------------------------------------

def test_can_write_coordinator_allowed_field():
    ok, reason = commands._can_write(100, "state.open")
    assert ok is True
    assert reason == "ok"


def test_can_write_low_power_level_denied():
    ok, reason = commands._can_write(0, "state.open")
    assert ok is False
    assert reason == "read_only"


def test_can_write_coordinator_disallowed_field():
    ok, reason = commands._can_write(100, "space.name")
    assert ok is False
    assert reason == "field_not_allowed"


def test_can_write_power_level_99_denied():
    ok, reason = commands._can_write(99, "state.open")
    assert ok is False
    assert reason == "read_only"


# ---------------------------------------------------------------------------
# _extract_field
# ---------------------------------------------------------------------------

def test_extract_field_top_level():
    assert commands._extract_field({"name": "Test"}, "name") == "Test"


def test_extract_field_nested():
    assert commands._extract_field({"state": {"open": True}}, "state.open") is True


def test_extract_field_missing_key():
    assert commands._extract_field({"state": {}}, "state.open") is None


def test_extract_field_non_dict_intermediate():
    assert commands._extract_field({"state": "not-a-dict"}, "state.open") is None


# ---------------------------------------------------------------------------
# _values_match
# ---------------------------------------------------------------------------

def test_values_match_true():
    assert commands._values_match(True, "true") is True
    assert commands._values_match(False, "true") is False


def test_values_match_false():
    assert commands._values_match(False, "false") is True
    assert commands._values_match(True, "false") is False


def test_values_match_null():
    assert commands._values_match(None, "null") is True
    assert commands._values_match(False, "null") is False


def test_values_match_string():
    assert commands._values_match("#room:libera.chat", "#room:libera.chat") is True
    assert commands._values_match("#other:libera.chat", "#room:libera.chat") is False


# ---------------------------------------------------------------------------
# Permission refusals via try_handle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_from_low_power_level_is_refused():
    ctx = _make_context(power_level=0)
    result = await commands.try_handle('update state.open "true"', "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.read_only_ack()


@pytest.mark.asyncio
async def test_update_disallowed_field_is_refused():
    ctx = _make_context(power_level=100)
    result = await commands.try_handle('update space.name "Cool Lab"', "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.field_not_allowed_ack(sorted(commands.ALLOWED_FIELDS))


@pytest.mark.asyncio
async def test_open_from_low_power_level_is_refused():
    ctx = _make_context(power_level=0)
    result = await commands.try_handle("open", "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.read_only_ack()


@pytest.mark.asyncio
async def test_close_from_low_power_level_is_refused():
    ctx = _make_context(power_level=0)
    result = await commands.try_handle("close", "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.read_only_ack()


# ---------------------------------------------------------------------------
# _trigger_heartbeat
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_heartbeat_200(monkeypatch):
    class FakeResp:
        status_code = 200

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, **kwargs):
            return FakeResp()

    monkeypatch.setattr(commands.httpx, "AsyncClient", lambda timeout=None: FakeClient())
    note = await commands._trigger_heartbeat("openfab")
    assert "triggered" in note


@pytest.mark.asyncio
async def test_trigger_heartbeat_429(monkeypatch):
    class FakeResp:
        status_code = 429

        def json(self):
            return {"retry_after_seconds": 45}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, **kwargs):
            return FakeResp()

    monkeypatch.setattr(commands.httpx, "AsyncClient", lambda timeout=None: FakeClient())
    note = await commands._trigger_heartbeat("openfab")
    assert "45s" in note


@pytest.mark.asyncio
async def test_trigger_heartbeat_http_error(monkeypatch):
    import httpx

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, **kwargs):
            raise httpx.HTTPError("timeout")

    monkeypatch.setattr(commands.httpx, "AsyncClient", lambda timeout=None: FakeClient())
    note = await commands._trigger_heartbeat("openfab")
    assert "unreachable" in note


# ---------------------------------------------------------------------------
# _handle_update spawns background task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_update_spawns_background_task(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_commit(space_id, field_path, value, authorized_by):
        return "abc1234deadbeef"

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "commit_json", fake_commit)

    tasks_created = []

    def fake_create_task(coro):
        tasks_created.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(commands.asyncio, "create_task", fake_create_task)

    ctx = _make_context(power_level=100)
    adapter = MagicMock()
    result = await commands.try_handle(
        'update state.open "true"', "@u:x", "!room:x", "sid",
        adapter=adapter, context=ctx,
    )
    assert "abc1234" in result
    assert len(tasks_created) == 1


# ---------------------------------------------------------------------------
# _poll_and_refresh unit test (confirmed path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_poll_and_refresh_sends_follow_up_when_confirmed(monkeypatch):
    async def fake_lookup(space_id):
        return "https://raw.githubusercontent.com/owner/repo/main/space.json"

    async def fake_sleep(delay):
        pass

    class FakeGetResp:
        status_code = 200

        def json(self):
            return {"state": {"open": True}}

    class FakeGetClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, url):
            return FakeGetResp()

    async def fake_trigger(space_id):
        return "Endpoint refresh triggered."

    monkeypatch.setattr(git_ops, "_lookup_endpoint_url", fake_lookup)
    monkeypatch.setattr(commands.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(commands.httpx, "AsyncClient", lambda timeout=None: FakeGetClient())
    monkeypatch.setattr(commands, "_trigger_heartbeat", fake_trigger)

    sent = []

    class FakeAdapter:
        async def send(self, text, ctx):
            sent.append(text)

    await commands._poll_and_refresh("openfab", "state.open", "true", "abc1234", FakeAdapter(), _make_context())

    assert len(sent) == 1
    assert "updated" in sent[0].lower() or "Map" in sent[0]


# ---------------------------------------------------------------------------
# open/close verbs via try_handle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_verb_coordinator(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_commit(space_id, field_path, value, authorized_by):
        assert field_path == "state.open"
        assert value is True
        return "abc1234deadbeef"

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "commit_json", fake_commit)
    monkeypatch.setattr(commands.asyncio, "create_task", lambda coro: (coro.close(), MagicMock())[1])

    ctx = _make_context(power_level=100)
    result = await commands.try_handle("open", "@u:x", "!room:x", "sid", context=ctx)
    assert "open" in result.lower()


@pytest.mark.asyncio
async def test_close_verb_coordinator(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_commit(space_id, field_path, value, authorized_by):
        assert field_path == "state.open"
        assert value is False
        return "abc1234deadbeef"

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "commit_json", fake_commit)
    monkeypatch.setattr(commands.asyncio, "create_task", lambda coro: (coro.close(), MagicMock())[1])

    ctx = _make_context(power_level=100)
    result = await commands.try_handle("close", "@u:x", "!room:x", "sid", context=ctx)
    assert "closed" in result.lower()


# ---------------------------------------------------------------------------
# status verb
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_verb_happy_path(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_verify(space_id):
        return {
            "ok": True,
            "checks": {"url": True, "key": True, "remote": True},
            "remote": "git@gitlab.com:openfab/endpoint.git",
            "branch": "main",
            "file_path": "spaceapi.json",
            "errors": [],
        }

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "verify_setup", fake_verify)

    ctx = _make_context(power_level=100)
    result = await commands.try_handle("status", "@u:x", "!room:x", "sid", context=ctx)
    assert "Remote" in result
    assert "main" in result


@pytest.mark.asyncio
async def test_status_verb_error_path(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_verify(space_id):
        return {
            "ok": False,
            "checks": {"url": False},
            "remote": None,
            "branch": None,
            "file_path": None,
            "errors": ["No endpoint URL registered. Run `!mom link` first."],
        }

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "verify_setup", fake_verify)

    ctx = _make_context(power_level=100)
    result = await commands.try_handle("status", "@u:x", "!room:x", "sid", context=ctx)
    assert "issue" in result.lower() or "!mom link" in result


# ---------------------------------------------------------------------------
# Value validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_state_open_invalid_value_refused():
    ctx = _make_context(power_level=100)
    result = await commands.try_handle('update state.open "maybe"', "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.invalid_bool_ack()


@pytest.mark.asyncio
async def test_update_contact_matrix_invalid_format_refused():
    ctx = _make_context(power_level=100)
    result = await commands.try_handle('update contact.matrix "notavalidid"', "@u:x", "!room:x", "sid", context=ctx)
    assert result == bernard.invalid_matrix_id_ack()


@pytest.mark.asyncio
async def test_update_command_success_returns_committed_ack(monkeypatch):
    async def fake_resolve(room_id):
        return "openfab"

    async def fake_commit(space_id, field_path, value, authorized_by):
        assert field_path == "contact.irc"
        assert value == "#room:libera.chat"
        return "abc1234deadbeef"

    monkeypatch.setattr(git_ops, "resolve_space_for_room", fake_resolve)
    monkeypatch.setattr(git_ops, "commit_json", fake_commit)
    monkeypatch.setattr(commands.asyncio, "create_task", lambda coro: (coro.close(), MagicMock())[1])

    ctx = _make_context(power_level=100)
    result = await commands.try_handle('update contact.irc "#room:libera.chat"', "@u:x", "!room:x", "sid", context=ctx)
    assert "abc1234" in result


# ---------------------------------------------------------------------------
# !mom travel fallback speed (live bug, 2026-07-02): "20min by bike" produced
# a 26km search radius — the ORS-timeout bounding-box fallback used a single
# hardcoded 80 km/h for every travel mode, i.e. car speed on a bike request.
# ---------------------------------------------------------------------------

import isochrone
import query_commands


@pytest.mark.asyncio
async def test_travel_fallback_uses_bike_speed_not_car_speed(monkeypatch):
    monkeypatch.setattr(isochrone, "travel_search", AsyncMock(
        return_value={"confirmed": [], "seeded_count": 0, "fallback": True, "coords": (50.85, 4.35)}))
    nearby_mock = AsyncMock(return_value="nothing")
    monkeypatch.setattr(query_commands, "nearby_from_coords", nearby_mock)

    ctx = _make_context(power_level=0)
    await commands.try_handle("travel openfab 20min by bike", "@u:x", "!room:x", "sid", context=ctx)

    radius_km = nearby_mock.call_args[0][1]
    assert radius_km == pytest.approx((20 / 60) * 15.0)  # bike speed, not 80 km/h


@pytest.mark.asyncio
async def test_travel_fallback_uses_car_speed_by_default(monkeypatch):
    monkeypatch.setattr(isochrone, "travel_search", AsyncMock(
        return_value={"confirmed": [], "seeded_count": 0, "fallback": True, "coords": (50.85, 4.35)}))
    nearby_mock = AsyncMock(return_value="nothing")
    monkeypatch.setattr(query_commands, "nearby_from_coords", nearby_mock)

    ctx = _make_context(power_level=0)
    await commands.try_handle("travel openfab 1h", "@u:x", "!room:x", "sid", context=ctx)

    radius_km = nearby_mock.call_args[0][1]
    assert radius_km == pytest.approx(40.0)


@pytest.mark.asyncio
async def test_travel_ambiguous_origin_reports_candidates_not_a_guess(monkeypatch):
    monkeypatch.setattr(isochrone, "travel_search", AsyncMock(
        side_effect=isochrone.OriginAmbiguousError("hub", ["Hub Alpha", "Hub Beta"])))

    ctx = _make_context(power_level=0)
    result = await commands.try_handle("travel hub 1h", "@u:x", "!room:x", "sid", context=ctx)

    assert "Hub Alpha" in result
    assert "Hub Beta" in result


# ---------------------------------------------------------------------------
# !mom travel multi-word origin (live bug, 2026-07-02): "openfab ozu 20min by
# bike" split(maxsplit=2) chopped the origin at the first space, sending only
# "openfab" as origin and "ozu 20min by bike" as the hours arg (fails to
# parse). travel now peels the trailing duration+mode off the end instead.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_travel_multi_word_origin_is_not_truncated(monkeypatch):
    travel_mock = AsyncMock(
        return_value={"confirmed": [], "seeded_count": 0, "fallback": False, "results": []})
    monkeypatch.setattr(isochrone, "travel_search", travel_mock)

    ctx = _make_context(power_level=0)
    await commands.try_handle("travel openfab ozu 20min by bike", "@u:x", "!room:x", "sid", context=ctx)

    origin_arg = travel_mock.call_args[0][0]
    assert origin_arg == "openfab ozu"
