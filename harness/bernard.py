from pathlib import Path

import structlog
import yaml

log = structlog.get_logger()

_voice: dict | None = None

VOICE_PATH = Path(__file__).parent / "bernard_voice.yaml"


def load_voice() -> dict:
    """Load Bernard's bot-voice strings at startup. Only the graceful-ack
    path lands here; the full voice audit is Story 6.5."""
    global _voice
    if _voice is not None:
        return _voice
    if VOICE_PATH.exists():
        with open(VOICE_PATH) as f:
            _voice = yaml.safe_load(f) or {}
    else:
        log.warning("bernard_voice.yaml not found", path=str(VOICE_PATH))
        _voice = {}
    return _voice


def _bot(key: str, default: str, **kwargs) -> str:
    text = load_voice().get("bot", {}).get(key, default)
    return text.format(**kwargs) if kwargs else text


def ping_ack() -> str:
    return _bot("ping_ack", "Still here.")


def unknown_ack() -> str:
    return _bot("unknown_ack", "Not sure what you mean by that.")


def link_tutorial(public_key: str, tutorial_md: str) -> str:
    return _bot("link_tutorial", "{tutorial}", public_key=public_key, tutorial=tutorial_md)


def link_failed_ack() -> str:
    return _bot("link_failed_ack", "I couldn't generate a key for that space — check the space slug is registered, then try again.")


def no_deploy_key_ack() -> str:
    return _bot("no_deploy_key_ack", "I can read your profile but I can't edit it yet — run `!mom link` first so I get write access.")


def update_failed_ack() -> str:
    return _bot("update_failed_ack", "That update didn't go through — check the field path and value, then try again.")


def query_failed_ack() -> str:
    return _bot("query_failed_ack", "Couldn't reach the directory right now — try again in a moment.")


def update_succeeded_ack(sha: str) -> str:
    return _bot("update_succeeded_ack", "Done. Committed as {sha}.", sha=sha[:8])


def update_committed_ack(sha: str, field_path: str, value: str) -> str:
    return _bot("update_committed_ack", "Saved — committed as {sha}. Waiting for CDN propagation…", sha=sha[:8])


def propagation_confirmed_ack(refresh_note: str) -> str:
    return _bot("propagation_confirmed_ack", "Map updated. {refresh_note} Hard-refresh your browser.", refresh_note=refresh_note)


def propagation_timeout_ack(sha: str) -> str:
    return _bot("propagation_timeout_ack", "Commit {sha} landed but CDN hasn't propagated after 10 minutes — the map will catch up on its own.", sha=sha[:8])


def open_ack(sha: str) -> str:
    return _bot("open_ack", "Marked as open — committed as {sha}. Waiting for CDN propagation…", sha=sha[:8])


def close_ack(sha: str) -> str:
    return _bot("close_ack", "Marked as closed — committed as {sha}. Waiting for CDN propagation…", sha=sha[:8])


def already_set_ack(state: str) -> str:
    return _bot("already_set_ack", "Already {state}. No commit needed.", state=state)


def write_confirmation_expired_ack() -> str:
    return _bot("write_confirmation_expired_ack", "No confirmation within a minute — dropping that one. Ask again if you still want it.")


def read_only_ack(user: str = "") -> str:
    display = user[1:user.index(":")] if user.startswith("@") and ":" in user else user or "friend"
    return _bot("read_only_ack", "I'm sorry, {user}, I'm afraid I can't do that. You don't have the right permissions.", user=display)


def field_not_allowed_ack(fields: list) -> str:
    return _bot("field_not_allowed_ack", "That field isn't editable through me.", fields=", ".join(fields))


def invalid_bool_ack() -> str:
    return _bot("invalid_bool_ack", "state.open needs to be `true`, `false`, or `null`.")


def invalid_matrix_id_ack() -> str:
    return _bot("invalid_matrix_id_ack", "contact.matrix should look like `@username:server`.")


def status_no_link_ack() -> str:
    return _bot("status_no_link_ack", "This room isn't linked to a space yet. Register one with `!mom link {slug}` first.")


def status_lifecycle_ack(name: str, state_line: str, updated_at: str, subset: str = "", unlock_line: str = "") -> str:
    text = _bot("status_lifecycle", "**{name}** · {state_line}\nLast updated: {updated_at}\n{unlock_line}",
                name=name, state_line=state_line, updated_at=updated_at, unlock_line=unlock_line)
    if subset:
        text += f"\nTier: {subset}"
    return text.strip()


def hours_found_ack(name: str, hours: str) -> str:
    return _bot("hours_found", "**{name}** opens: {hours}", name=name, hours=hours)


def hours_missing_ack(name: str) -> str:
    return _bot("hours_missing", "**{name}** hasn't listed opening hours yet.", name=name)


def _get_nested(data: dict, field: str):
    """Navigate a dot-path into a dict. Returns (value, found: bool)."""
    parts = field.split(".")
    node = data
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


# Known readable fields in display order: (dot-path, label)
_READ_FIELDS = [
    ("space",              "name"),
    ("url",                "website"),
    ("state.open",         "state.open"),
    ("contact.matrix",     "contact.matrix"),
    ("contact.irc",        "contact.irc"),
    ("contact.twitter",    "contact.twitter"),
    ("mom.memberOf",       "mom.memberOf"),
]


def read_list_ack(data: dict) -> str:
    """List all known fields with their current values — like env for the space JSON."""
    lines = [f"Fields for **{data.get('space') or data.get('name', '(unnamed)')}**:"]
    for path, label in _READ_FIELDS:
        val, found = _get_nested(data, path)
        lines.append(f"• `{label}` = {val!r}" if found else f"• `{label}` = (not set)")
    # Flag broken mom:memberOf shape if present
    if "mom:memberOf" in data:
        lines.append(f"• ⚠ `mom:memberOf` = {data['mom:memberOf']!r}  ← literal key, not parsed — use `mom.memberOf`")
    return "\n".join(lines)




def read_field_ack(field: str, data: dict) -> str:
    """Return the exact raw value at a dot-path field. Special diagnostic for mom.memberOf."""
    if field == "mom.memberOf":
        mom_block = data.get("mom") or {}
        nested = mom_block.get("memberOf")
        bare = data.get("memberOf")
        broken = data.get("mom:memberOf")
        if nested is not None:
            return f"`mom.memberOf` = {nested!r}"
        if bare is not None:
            return f"`mom.memberOf` (bare fallback) = {bare!r}  — works, but prefer nesting under `\"mom\": {{\"memberOf\": [...]}}`"
        if broken is not None:
            return (f"⚠ `\"mom:memberOf\"` = {broken!r}  — literal key, **not parsed**.\n"
                    f"Fix: `!mom update mom.memberOf {broken!r}`")
        return "`mom.memberOf` is not set."
    val, found = _get_nested(data, field)
    if not found:
        return f"`{field}` is not set in this space's JSON."
    return f"`{field}` = {val!r}"


def read_slug_not_found_ack(slug: str) -> str:
    return _bot("read_slug_not_found", "No confirmed space found for slug '{slug}' — check the name and try again.", slug=slug)


def find_results_ack(count: int, tag: str, city: str, list_text: str) -> str:
    return _bot("find_results", "Found {count} confirmed space(s) matching '{tag}' in {city}:\n{list}",
                count=count, tag=tag, city=city, list=list_text)


def find_empty_ack(tag: str, city: str, seeded_note: str = "") -> str:
    return _bot("find_empty", "No confirmed spaces match '{tag}' in {city}. {seeded_note}",
                tag=tag, city=city, seeded_note=seeded_note)


def find_open_results_ack(count: int, city: str, list_text: str) -> str:
    return _bot("find_open_results", "Found {count} confirmed space(s) open right now in {city}:\n{list}",
                count=count, city=city, list=list_text)


def find_open_empty_ack(city: str, seeded_note: str = "") -> str:
    return _bot("find_open_empty", "No confirmed spaces are reporting open right now in {city}. {seeded_note}",
                city=city, seeded_note=seeded_note)


def nearby_results_ack(radius: int, city: str, count: int, list_text: str) -> str:
    return _bot("nearby_results", "Within {radius}km of {city} — {count} confirmed space(s):\n{list}",
                radius=radius, city=city, count=count, list=list_text)


def nearby_empty_ack(radius: int, city: str, seeded_note: str = "") -> str:
    return _bot("nearby_empty", "Nothing confirmed within {radius}km of {city}. {seeded_note}",
                radius=radius, city=city, seeded_note=seeded_note)


def network_results_ack(network: str, count: int, list_text: str) -> str:
    return _bot("network_results", "**{network}** — {count} confirmed member(s):\n{list}",
                network=network, count=count, list=list_text)


def network_empty_ack(network: str) -> str:
    return _bot("network_empty", "No confirmed spaces list '{network}' as a network. Check the exact name.",
                network=network)


def _fmt_hours(hours: float) -> str:
    mins = round(hours * 60)
    if mins < 60:
        return f"{mins}min"
    h = mins // 60
    m = mins % 60
    return f"{h}h{m:02d}min" if m else f"{h}h"


_MODE_LABELS = {
    "driving-car": "car",
    "cycling-regular": "bike",
    "foot-walking": "foot",
}


def travel_results_ack(hours: float, origin: str, mode: str, count: int, list_text: str, seeded_note: str = "") -> str:
    label = _MODE_LABELS.get(mode, mode)
    return _bot("travel_results",
                "Within {hours} of {origin} by {mode} — {count} confirmed space(s):\n{list}\n{seeded_note}",
                hours=_fmt_hours(hours), origin=origin, mode=label, count=count, list=list_text, seeded_note=seeded_note)


def travel_timeout_ack(fallback_result: str) -> str:
    return _bot("travel_timeout", "ORS took too long — falling back to a bounding box. {fallback_result}",
                fallback_result=fallback_result)


def travel_ors_unavailable_ack(fallback_result: str = "") -> str:
    return _bot("travel_ors_unavailable", "Travel search is temporarily unavailable. {fallback_result}",
                fallback_result=fallback_result)


def travel_ambiguous_origin_ack(query: str, candidates: list[str]) -> str:
    return _bot("travel_ambiguous_origin",
                "'{query}' matches multiple spaces: {candidates}. Try again with the exact name.",
                query=query, candidates=", ".join(candidates))


def seeded_note_ack(count: int) -> str:
    return _bot("seeded_note",
                "{count} seeded space(s) also fall in range — they haven't registered an endpoint yet. Want me to list them?",
                count=count)


def result_cap_note_ack(n: int) -> str:
    return _bot("result_cap_note", "Showing first {n} results — use `!mom find` with a tag and city to narrow down.", n=n)


def did_you_mean_ack(verb: str, suggestion: str) -> str:
    return _bot("did_you_mean", "There's no `{verb}`. Did you mean `!mom {suggestion}`?",
                verb=verb, suggestion=suggestion)


def unknown_command_ack(verb: str) -> str:
    return _bot("unknown_command", "I don't know `{verb}`. Try `!mom help`.", verb=verb)


def bernard_nl_stub_ack() -> str:
    return _bot("bernard_nl_stub", "Natural-language questions are on the roadmap. For now: `!mom help` lists what I can do.")


def nl_result_ack(count: str | int, list_text: str, sparql_block: str) -> str:
    return _bot("nl_result_ack",
                "Found {count} space(s) matching your question.\n\n{list_text}\n\n> How I searched\n> ```sparql\n> {sparql_block}\n> ```",
                count=count, list_text=list_text, sparql_block=sparql_block)


def nl_empty_ack() -> str:
    return _bot("nl_empty_ack",
                "Nothing in the directory matches that — the question's logged so it can inform what gets added.")


def nl_gap_ack() -> str:
    return _bot("nl_gap_ack",
                "I couldn't form a query that fits the directory — your question's logged as a gap for ontology curation. Could you rephrase?")


def nl_invalid_sparql_ack() -> str:
    return _bot("nl_invalid_sparql_ack",
                "That question produced something I'm not allowed to run. Try rephrasing, or use `!mom help` for the commands I support.")


_READ_HELP = """`!mom read` — Show this space's known fields and current values
`!mom read {field}` — Exact raw value of a dot-path field (e.g. `state.open`, `contact.matrix`, `mom.memberOf`)
`!mom read {slug}` — Same field summary for any registered space (e.g. `!mom read superlab`)

Field paths use dot notation matching the JSON structure.
For `mom.memberOf`, Bernard also diagnoses broken key shapes."""

_UPDATE_FIELD_HELP = """`!mom update {field} {value}` — Update a field in this space's JSON (coordinator only)

Editable fields:
• `state.open` — `true` / `false` / `null`
• `contact.matrix` — `@username:server`
• `contact.irc` — IRC nick or channel
• `contact.twitter` — Twitter/X handle
• `mom.memberOf` — full network list (always replaces the whole array)
  Single name:  `!mom update mom.memberOf FabTafel`
  Multiple:     `!mom update mom.memberOf ["urn:mak:network/fabtafel","urn:mak:network/vulca"]`
  Bare names are auto-expanded to `urn:mak:network/<slug>`.
  To add or remove individual entries, use `@bernard` (coming in 6.4)."""


def help(power_level: int, verb_arg: str, registry: dict) -> str:
    """Render !mom help output. If verb_arg is a known verb, show details for just that verb."""
    if verb_arg and verb_arg in registry:
        if verb_arg == "update":
            return _UPDATE_FIELD_HELP
        if verb_arg == "read":
            return _READ_HELP
        min_pl, description, arg_shape = registry[verb_arg]
        arg_str = f" {arg_shape}" if arg_shape else ""
        return f"`!mom {verb_arg}{arg_str}` — {description}"

    header = _bot("help_header", "Here's what I do.")
    read_lines = []
    write_lines = []
    for verb, (min_pl, description, arg_shape) in registry.items():
        arg_str = f" {arg_shape}" if arg_shape else ""
        line = f"• `!mom {verb}{arg_str}` — {description}"
        if min_pl < 100:
            read_lines.append(line)
        else:
            write_lines.append(line)

    parts = [header, "", "**Look things up:**", "\n".join(read_lines)]
    if power_level >= 100:
        parts += ["", "**Changes things:**", "\n".join(write_lines)]
    else:
        parts += ["", "**Changes things** (coordinator only — not available to you):",
                  "\n".join(write_lines)]
    return "\n".join(parts)


def status_report(verify: dict) -> str:
    if verify["ok"]:
        return _bot(
            "status_ok_ack",
            "Everything looks set up.\n• Remote: {remote}\n• Branch: {branch}\n• File: {file_path}",
            remote=verify.get("remote", ""),
            branch=verify.get("branch", ""),
            file_path=verify.get("file_path", ""),
        )
    error_list = verify.get("errors", [])
    errors = "\n".join(f"• {e}" for e in error_list)
    template = load_voice().get("bot", {}).get(
        "status_error_ack",
        "Setup check found {n} issue(s):\n{errors}\nRun `!mom link` to fix the key or re-register with the correct URL.",
    )
    return template.replace("{n}", str(len(error_list))).replace("{errors}", errors)
