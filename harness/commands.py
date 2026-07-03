"""Literal `!mom <verb>` commands — checked before the LLM intent classifier
(see Story 6.1 Dev Notes "Command parsing, not intent routing"). `!mom link`
and `!mom update` are deterministic, argument-parsed commands, not slot-filled
classifications, so they never go through router.route()/intent_classifier.
"""
import asyncio
import difflib
import os
import re
from typing import Optional

import httpx
import structlog

import bernard
import query_commands
import isochrone
from bot import git_ops
from bot.git_ops import NoChangeError, NoDeployKeyError, NoEndpointError, UnsupportedHostError

log = structlog.get_logger()

# Single registry for dispatch, !mom help, and fuzzy-suggest — they can never drift.
# Each entry: verb → (min_power_level, one_line_description, arg_shape)
COMMAND_REGISTRY = {
    "status":  (0,   "Lifecycle state of this room's linked space", ""),
    "hours":   (0,   "Opening hours of this room's linked space", ""),
    "find":    (0,   "Search confirmed spaces by tag and city, or open/closed state", "{tag|open|closed} {city}"),
    "nearby":  (0,   "Spaces within a radius of a city", "{city} {radius_km}"),
    "network": (0,   "Confirmed spaces in a named network", "{network_name}"),
    "travel":  (0,   "Spaces reachable within N hours (ORS isochrone)", "{origin} {hours}[h] [by bike|by foot|by car]"),
    "read":    (0,   "Read fields from a space's JSON", "[{field}|{slug}]"),
    "help":    (0,   "List available commands", "[verb]"),
    "link":    (100, "Link this room to a space endpoint", "{space_slug}"),
    "update":  (100, "Update a field in this space's JSON", "{field} {value}"),
    "open":    (100, "Mark this space as open", ""),
    "close":   (100, "Mark this space as closed", ""),
}
KNOWN_VERBS = frozenset(COMMAND_REGISTRY)

LINK_HANDLER_URL = os.environ.get("LINK_HANDLER_URL", "http://mak-link-handler:8000")
# Shared secret proving this call came from the bot, not an internet caller —
# /api/ is proxied publicly, so the deploy-key endpoint requires this header
# (Story 6.1 code review finding; same value as link_handler's BOT_KEY_SECRET).
BOT_KEY_SECRET = os.environ.get("BOT_KEY_SECRET", "")

ALLOWED_FIELDS = frozenset({"state.open", "contact.irc", "contact.matrix", "contact.twitter", "mom.memberOf"})

# Origin can be multi-word ("openfab ozu"), so `travel` can't rely on
# positional split(maxsplit=2) like the other commands — it peels the
# trailing duration+mode off the end of the string instead.
_TRAVEL_ARGS_RE = re.compile(
    r"^(?P<origin>.+?)\s+(?P<time>\d+(?:\.\d+)?\s*(?:min|h)?(?:\s*by\s+(?:bike|foot|car))?)$",
    re.IGNORECASE,
)


def _can_write(power_level: int, field_path: str) -> tuple[bool, str]:
    """Single permission gate for all write commands. Returns (allowed, reason).
    Future: swap body to also check per-user grants from Oxigraph."""
    if power_level < 100:
        return False, "read_only"
    if field_path not in ALLOWED_FIELDS:
        return False, "field_not_allowed"
    return True, "ok"


def _validate_value(field_path: str, value: str) -> tuple[bool, str]:
    """Field-specific value validation. Returns (valid, error_message)."""
    if field_path == "state.open":
        if value.lower() not in ("true", "false", "null"):
            return False, bernard.invalid_bool_ack()
    elif field_path == "contact.matrix":
        import re
        if not re.match(r"^@[^:]+:[^:]+$", value):
            return False, bernard.invalid_matrix_id_ack()
    else:
        if not value.strip():
            return False, f"Value for {field_path} cannot be empty."
    return True, ""


def _coerce_value(field_path: str, value: str):
    """Convert string value to the appropriate Python type for the field."""
    if field_path == "state.open":
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        return None  # "null"
    if field_path == "mom.memberOf":
        import json as _json
        if value.strip().startswith("["):
            return _json.loads(value)  # full JSON array — parse as list
        return [value.strip()]  # single name/URI — wrap in list
    return value


def _to_raw_url(endpoint_url: str) -> str:
    """Return a raw-content URL for polling CDN propagation."""
    if "raw.githubusercontent.com" in endpoint_url:
        return endpoint_url
    if "raw.gitea." in endpoint_url or "codeberg.org/raw" in endpoint_url:
        return endpoint_url
    if "/-/raw/" in endpoint_url:
        return endpoint_url
    raise ValueError(f"Cannot derive a raw polling URL from: {endpoint_url}")


def _extract_field(data: dict, field_path: str):
    """Navigate a dotted field path into a dict."""
    parts = field_path.split(".")
    for part in parts:
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def _values_match(actual, expected_str: str) -> bool:
    """Compare the actual JSON value to the expected string value."""
    if expected_str.lower() == "null":
        return actual is None
    if expected_str.lower() == "true":
        return actual is True
    if expected_str.lower() == "false":
        return actual is False
    return str(actual) == expected_str


async def _trigger_heartbeat(space_id: str) -> str:
    url = f"{LINK_HANDLER_URL}/api/heartbeat-space/{space_id}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url)
        if r.status_code == 200:
            return "Endpoint refresh triggered."
        if r.status_code == 429:
            try:
                retry = r.json().get("retry_after_seconds", 60)
            except Exception:
                retry = 60
            return f"A refresh was already triggered recently — re-ingest will complete within {retry}s."
        return f"Endpoint refresh returned {r.status_code} — map will re-ingest on next scheduled cycle (every ~60s+)."
    except httpx.HTTPError as e:
        return f"Endpoint refresh unreachable ({e}) — map will re-ingest on next scheduled cycle."


async def _poll_and_refresh(space_id: str, field_path: str, value: str, sha: str, adapter, context) -> None:
    try:
        endpoint_url = await git_ops._lookup_endpoint_url(space_id)
        raw_url = _to_raw_url(endpoint_url)

        delay, budget, elapsed, confirmed = 5.0, 600.0, 0.0, False
        while elapsed < budget:
            await asyncio.sleep(delay)
            elapsed += delay
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(raw_url)
                if r.status_code == 200:
                    actual = _extract_field(r.json(), field_path)
                    if _values_match(actual, value):
                        confirmed = True
                        break
            except Exception:
                pass
            delay = min(delay * 2, 60.0)

        if confirmed:
            refresh_note = await _trigger_heartbeat(space_id)
            await adapter.send(bernard.propagation_confirmed_ack(refresh_note), context)
        else:
            await adapter.send(bernard.propagation_timeout_ack(sha), context)
    except Exception as e:
        log.warning("commands.poll_and_refresh_failed", error=str(e))
        try:
            await adapter.send(bernard.propagation_timeout_ack(sha), context)
        except Exception:
            pass


async def try_handle(text: str, user_id: str, room_id: str, session_id: str, *, adapter=None, context=None) -> Optional[str]:
    """Return a response string if `text` matches a known literal command,
    else None (caller falls through to the intent classifier)."""
    parts = text.split(maxsplit=2)

    # bare !mom with no verb → help
    if not parts or not parts[0]:
        return bernard.help(
            getattr(context, "power_level", 0) if context is not None else 0,
            "",
            COMMAND_REGISTRY,
        )

    verb = parts[0]
    bound = log.bind(session_id=session_id, room_id=room_id, verb=verb)

    power_level = getattr(context, "power_level", 0) if context is not None else 0

    if verb == "help":
        arg = parts[1] if len(parts) > 1 else ""
        return bernard.help(power_level, arg, COMMAND_REGISTRY)

    if verb == "link" and len(parts) >= 2:
        return await _handle_link(parts[1], room_id, bound)

    if verb == "update" and len(parts) >= 3:
        field_path = parts[1]
        value = parts[2].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return await _handle_update(field_path, value, user_id, room_id, power_level, bound, adapter, context)

    if verb == "open":
        return await _handle_open_close("state.open", "true", user_id, room_id, power_level, bound, adapter, context)

    if verb == "close":
        return await _handle_open_close("state.open", "false", user_id, room_id, power_level, bound, adapter, context)

    if verb == "read":
        arg = parts[1] if len(parts) >= 2 else None
        return await _handle_read(arg, room_id, bound)

    if verb == "status":
        return await _handle_status(room_id, power_level, bound)

    if verb == "hours":
        return await _handle_hours(room_id, bound)

    if verb == "find" and len(parts) >= 3:
        # parts[1]=tag, parts[2]=city (split(maxsplit=2) already separated them)
        return await query_commands.find(parts[1], parts[2])

    if verb == "nearby" and len(parts) >= 3:
        city = parts[1]
        try:
            radius = float(parts[2])
        except ValueError:
            return "Usage: `!mom nearby {city} {radius_km}` — radius must be a number."
        return await query_commands.nearby(city, radius)

    if verb == "network" and len(parts) >= 2:
        network_name = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]
        return await query_commands.network(network_name)

    if verb == "travel" and len(parts) >= 2:
        remainder = " ".join(parts[1:])
        m = _TRAVEL_ARGS_RE.match(remainder)
        if not m:
            return "Usage: `!mom travel {origin} {hours}h` (e.g. `2h` or `30min`, optional `by bike`/`by foot`)"
        return await _handle_travel(m.group("origin").strip(), m.group("time").strip(), room_id, bound)

    # Fuzzy-suggest before falling through to LLM classifier
    if verb in KNOWN_VERBS:
        # Known verb but missing required args — return a usage hint instead of
        # silently falling through to the LLM classifier (which may throw or return
        # a confusing response).
        _, _, arg_shape = COMMAND_REGISTRY[verb]
        if arg_shape:
            return f"Usage: `!mom {verb} {arg_shape}`"
        return None
    matches = difflib.get_close_matches(verb, KNOWN_VERBS, n=1, cutoff=0.7)
    if matches:
        return bernard.did_you_mean_ack(verb, matches[0])
    return None


async def _handle_link(space_slug: str, room_id: str, bound) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{LINK_HANDLER_URL}/api/bot/deploy-key/{space_slug}",
                params={"room_id": room_id},
                headers={"X-Bot-Secret": BOT_KEY_SECRET},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        bound.warning("commands.link_failed", error=str(e))
        return bernard.link_failed_ack()

    bound.info("commands.link_succeeded")
    tutorial_msg = bernard.link_tutorial(data["public_key"], data["tutorial"])

    # Auto-verify: catch the GitHub-Pages-URL bug immediately
    try:
        verify = await git_ops.verify_setup(space_slug)
        tutorial_msg += "\n\n" + bernard.status_report(verify)
    except Exception:
        pass  # verify failure is non-fatal here; !mom status covers it
    return tutorial_msg


async def _handle_update(field_path: str, value: str, authorized_by: str, room_id: str, power_level: int, bound, adapter, context) -> str:
    allowed, reason = _can_write(power_level, field_path)
    if not allowed:
        if reason == "read_only":
            return bernard.read_only_ack(authorized_by)
        if reason == "field_not_allowed":
            return bernard.field_not_allowed_ack(sorted(ALLOWED_FIELDS))
        return bernard.update_failed_ack()

    valid, err = _validate_value(field_path, value)
    if not valid:
        return err

    coerced = _coerce_value(field_path, value)
    try:
        space_id = await git_ops.resolve_space_for_room(room_id)
        sha = await git_ops.commit_json(space_id, field_path, coerced, authorized_by)
    except NoDeployKeyError:
        bound.warning("commands.update_no_key")
        return bernard.no_deploy_key_ack()
    except (NoEndpointError, UnsupportedHostError) as e:
        bound.warning("commands.update_failed", error=str(e))
        return bernard.update_failed_ack()
    except Exception as e:
        bound.warning("commands.update_failed", error=str(e))
        return bernard.update_failed_ack()

    bound.info("commands.update_succeeded", sha=sha)
    if adapter is not None and context is not None:
        asyncio.create_task(_poll_and_refresh(space_id, field_path, value, sha, adapter, context))
    return bernard.update_committed_ack(sha, field_path, value)


async def _handle_open_close(field_path: str, value: str, authorized_by: str, room_id: str, power_level: int, bound, adapter, context) -> str:
    allowed, reason = _can_write(power_level, field_path)
    if not allowed:
        if reason == "read_only":
            return bernard.read_only_ack(authorized_by)
        return bernard.field_not_allowed_ack(sorted(ALLOWED_FIELDS))

    coerced = _coerce_value(field_path, value)
    try:
        space_id = await git_ops.resolve_space_for_room(room_id)
        # Build commit message with open/close shorthand voice
        sha = await git_ops.commit_json(space_id, field_path, coerced, authorized_by)
    except NoChangeError:
        return bernard.already_set_ack(state="open" if value == "true" else "closed")
    except NoDeployKeyError:
        bound.warning("commands.open_close_no_key")
        return bernard.no_deploy_key_ack()
    except (NoEndpointError, UnsupportedHostError) as e:
        bound.warning("commands.open_close_failed", error=str(e))
        return bernard.update_failed_ack()
    except Exception as e:
        bound.warning("commands.open_close_failed", error=str(e))
        return bernard.update_failed_ack()

    bound.info("commands.open_close_succeeded", sha=sha, action=value)
    if adapter is not None and context is not None:
        asyncio.create_task(_poll_and_refresh(space_id, field_path, value, sha, adapter, context))
    if value == "true":
        return bernard.open_ack(sha)
    return bernard.close_ack(sha)


async def _handle_status(room_id: str, power_level: int, bound) -> str:
    try:
        space_id = await git_ops.resolve_space_for_room(room_id)
    except NoEndpointError:
        return bernard.status_no_link_ack()

    # Fetch lifecycle data — public-safe fields for all users
    lifecycle_report = await query_commands.space_status(space_id)
    bound.info("commands.status_checked")

    # Coordinators additionally see deploy-key setup status (no key material shown to non-coordinators)
    if power_level >= 100:
        try:
            verify = await git_ops.verify_setup(space_id)
            return lifecycle_report + "\n\n" + bernard.status_report(verify)
        except Exception as e:
            bound.warning("commands.status_verify_failed", error=str(e))
            return lifecycle_report
    return lifecycle_report


async def _handle_hours(room_id: str, bound) -> str:
    try:
        space_id = await git_ops.resolve_space_for_room(room_id)
    except NoEndpointError:
        return bernard.status_no_link_ack()
    try:
        return await query_commands.hours(space_id)
    except Exception as e:
        bound.warning("commands.hours_failed", error=str(e))
        return bernard.query_failed_ack()


async def _handle_read(arg: str | None, room_id: str, bound) -> str:
    # arg with a dot → field path on the linked space JSON
    if arg is not None and "." in arg:
        return await _handle_read_field(arg, room_id, bound)
    # arg without a dot → space slug (public fetch); no arg → linked space self-read
    if arg is not None:
        return await _handle_read_slug(arg, bound)
    return await _handle_read_self(room_id, bound)


async def _handle_read_self(room_id: str, bound) -> str:
    try:
        space_id = await git_ops.resolve_space_for_room(room_id)
    except NoEndpointError:
        return bernard.status_no_link_ack()
    try:
        data = await git_ops.read_json(space_id)
    except NoDeployKeyError:
        return bernard.no_deploy_key_ack()
    except Exception as e:
        bound.warning("commands.read_self_failed", error=str(e))
        return bernard.query_failed_ack()
    return bernard.read_list_ack(data)


async def _handle_read_field(field: str, room_id: str, bound) -> str:
    try:
        space_id = await git_ops.resolve_space_for_room(room_id)
    except NoEndpointError:
        return bernard.status_no_link_ack()
    try:
        data = await git_ops.read_json(space_id)
    except NoDeployKeyError:
        return bernard.no_deploy_key_ack()
    except Exception as e:
        bound.warning("commands.read_field_failed", field=field, error=str(e))
        return bernard.query_failed_ack()
    return bernard.read_field_ack(field, data)


async def _handle_read_slug(slug: str, bound) -> str:
    data = await query_commands.fetch_space_json(slug)
    if data is None:
        return bernard.read_slug_not_found_ack(slug)
    return bernard.read_list_ack(data)


# Rough average speeds for the bounding-box fallback (ORS timeout/unavailable
# degrade path) — the isochrone path itself is mode-aware via ORS profiles,
# but the fallback previously used a single hardcoded 80 km/h for every mode,
# giving "20min by bike" a 26km radius (car speed on a bike request).
_FALLBACK_SPEED_KMH = {"by bike": 15.0, "by foot": 5.0, "by car": 40.0}


async def _handle_travel(origin: str, hours_and_mode: str, room_id: str, bound) -> str:
    """Parse hours+mode from '!mom travel {origin} {hours}[h] [by bike|by foot]'."""
    # Parse mode suffix from hours_and_mode
    mode = ""
    lower_hm = hours_and_mode.lower()
    for suffix in ("by bike", "by foot", "by car"):
        if lower_hm.endswith(suffix):
            mode = suffix
            hours_and_mode = hours_and_mode[:len(hours_and_mode) - len(suffix)].strip()
            break

    lower_time = hours_and_mode.lower()
    if lower_time.endswith("min"):
        hours_str = hours_and_mode[:-3].strip()
        divisor = 60.0
    else:
        hours_str = hours_and_mode.rstrip("hH")
        divisor = 1.0
    try:
        hours_val = float(hours_str) / divisor
    except ValueError:
        return "Usage: `!mom travel {origin} {hours}h` — hours must be a number (e.g. `2h` or `30min`)."

    try:
        result = await isochrone.travel_search(origin, hours_val, mode_input=mode, room_id=room_id)
    except isochrone.OriginAmbiguousError as e:
        return bernard.travel_ambiguous_origin_ack(e.query, e.candidates)
    except isochrone.IsochroneError as e:
        return bernard.travel_ors_unavailable_ack(str(e))

    if result["fallback"]:
        # ORS timed out — degrade to nearby bounding box. Use resolved coords if
        # available so space-name origins (e.g. "superlab") don't re-hit Nominatim.
        speed_kmh = _FALLBACK_SPEED_KMH.get(mode.lower().strip(), 40.0)
        radius_km = hours_val * speed_kmh
        coords = result.get("coords")
        if coords:
            fallback = await query_commands.nearby_from_coords(coords, radius_km)
        else:
            fallback = await query_commands.nearby(origin, radius_km)
        return bernard.travel_timeout_ack(fallback)

    confirmed = result["confirmed"]
    seeded_count = result["seeded_count"]
    mode_label = isochrone.MODE_MAP.get(mode.lower().strip(), "car")

    if not confirmed:
        seeded_note = bernard.seeded_note_ack(seeded_count) if seeded_count > 0 else ""
        speed_kmh = _FALLBACK_SPEED_KMH.get(mode.lower().strip(), 40.0)
        return bernard.nearby_empty_ack(radius=int(hours_val * speed_kmh), city=origin, seeded_note=seeded_note)

    list_text = "\n".join(f"• {s['name']}" for s in confirmed)
    seeded_note = bernard.seeded_note_ack(seeded_count) if seeded_count > 0 else ""
    result_text = bernard.travel_results_ack(
        hours=hours_val, origin=origin, mode=mode_label,
        count=len(confirmed), list_text=list_text, seeded_note=seeded_note,
    )
    if len(confirmed) >= 15:
        result_text += "\n" + bernard.result_cap_note_ack(n=15)
    return result_text
