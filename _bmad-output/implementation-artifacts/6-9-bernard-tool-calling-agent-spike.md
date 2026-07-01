# Story 6.9: Bernard Tool-Calling Agent Spike

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Nicolas (operator of the Maps of Making Bernard bot),
I want a spike that wires the existing OpenAI-SDK tool-calling loop over Bernard's already-tested effect functions (`git_ops.read_json`, `git_ops.commit_json`, `query_commands`, `nl_to_sparql._emit_gap_triple`) — proving the hardest case, a confirm-before-write `mom.memberOf` array delta — end-to-end on a live Matrix room,
so that Epic 6's `write` intent (currently a stub in `router.py` returning `unknown_ack()`) gets a real conversational-write path, and the team can decide whether native SDK function-calling is sufficient before committing to a heavier framework (nanobot/hermes).

This story supersedes Story 6.5 ("graceful failure + voice pass"). A 2026-06-25 course-correction concluded hand-authoring 19 voice-compliant strings was busywork the right architecture dissolves: if Bernard has an LLM in the loop, persona/voice/graceful-failure come from the **system prompt**, not a string table. See [[feedback_llm_bot_no_canned_copy_table]].

## Acceptance Criteria

1. `harness/llm_client.py` gains `complete_with_tools(system, messages, tools, model, tool_choice=..., session_id=...)` that passes `tools=[...]` to `client.chat.completions.create()` (OpenAI SDK ≥1.30.0 against OpenRouter) and returns `(text, tool_calls, model, latency_ms)`. Catches `openai.APIConnectionError` / `APIStatusError` / `APITimeoutError` and local `ValueError` (missing `OPENROUTER_API_KEY`) — caller maps these to a graceful bedrock ack, never an unhandled exception reaching the user.
2. `harness/agent_tools.py` defines a tool registry wrapping **existing, unmodified** effect functions with OpenAI tool-schema dicts:
   - `read_space(slug_or_room)` → `git_ops.read_json` / `query_commands.fetch_space_json`
   - `query_map(...)` → `query_commands.find` / `nearby` / `network` (read-only, reuse as-is)
   - `propose_write(field_path, new_value)` → validates via `commands._can_write` + `commands._validate_value`/`_coerce_value`, does **NOT** call `git_ops.commit_json`; stores a pending action and returns the computed delta (current value vs. proposed value) for confirmation
   - `log_gap(raw_request, note, gap_kind)` — `gap_kind="ontology"` → `nl_to_sparql._emit_gap_triple` (existing FR41 mechanism, `urn:mak:gaps`, unchanged). `gap_kind="capability"` → new SQLite log table (event/telemetry data, not RDF — GROUP BY roadmap-signal queries are the wrong shape for Oxigraph). Do not force both kinds into one graph.
3. A pending-action store (in-memory dict, keyed by `(room_id, user_id)` or thread root) holds the result of `propose_write` until a confirmation message ("yes"/thread reply) pops it and calls `git_ops.commit_json(space_id, field_path, value, authorized_by=user_id)` for real. `propose_write` is the **only** write-shaped tool exposed to the model — always-confirm-before-write is enforced by construction (no direct commit tool in the schema), not by a prompt instruction alone.
4. **Permission gate before tool exposure**: `router.py`'s call into the new `harness/agent.py` builds the tool list based on `message.power_level`. Callers with `power_level < 100` never receive `propose_write` in their tools — non-coordinators cannot trigger a write path even if they ask the model to.
5. Bernard system prompt (new module or YAML key, e.g. `harness/bernard_agent_prompt.py`) encodes persona (Ron-Swanson-on-fort register, they/them — see [[project_bernard_character]]) plus behavior rules: confirm before any write; echo resolved entities (current + proposed value) before asking; on permission denial, point to `!mom grant`; on an unfulfillable/missing-capability request, call `log_gap(gap_kind="capability")` and say so honestly rather than fabricating an answer.
6. `router.py`'s `write` intent (line 25-27, currently `log.warning("router.intent_not_implemented", ...)` → `bernard.unknown_ack()`) is wired to `agent.run(message, session_id)`. Free-text read questions may also route through the agent (it has `read_space`/`query_map`) to unify "ask about the map" and "edit the map" under one loop — this is a nice-to-have, not required for the spike's go/no-go.
7. `harness/tests/test_agent.py` (new) mocks `llm_client.complete_with_tools` to return canned `tool_calls` and asserts, at minimum:
   - `mom.memberOf` delta arithmetic is computed correctly (add/remove against the existing array)
   - a write is never committed without an intervening confirmation step
   - a `power_level < 100` message never receives `propose_write` in its tool list (assert on the tools passed to `complete_with_tools`, not just on behavior)
   - an unfulfillable request calls `log_gap` with the correct `gap_kind`
8. Live integration (the real DoD per [[epic_3_retro_findings]] — pytest passing is necessary, not sufficient): on the VPS Matrix room (unencrypted), as a coordinator, `@bernard add VOW to <space>'s networks` → Bernard echoes current + proposed `mom.memberOf` array → asks for confirmation → `yes` → commit lands with a real SHA → `!mom read mom.memberOf` reflects the change. As a non-coordinator, the same request is refused (agent never had `propose_write`). An unfulfillable ask (e.g. "what time is it in Taipei, is it open now?") produces an honest "can't do that yet, logged it" response and a new row/triple from `log_gap`.
9. A written decision record (in this story's Dev Notes / Completion Notes, not a separate doc) states: does native OpenAI SDK function-calling suffice, or is a framework (nanobot/hermes) needed? This spike's *outcome* answers the question — the story does not decide it in advance.
10. `bernard_voice.yaml`'s scope is **not** expanded and its existing keys are **not** deleted in this story. The full retirement of most `bernard_voice.yaml` voice keys is explicitly deferred to a follow-up once the spike is validated (see Scope Guardrails). The hardcoded graceful-failure bedrock ack (LLM-down fallback) stays as-is and is untouched — it must keep working when the LLM path itself is unavailable, so it cannot be replaced by anything that depends on the LLM being up.

## Tasks / Subtasks

- [ ] Task 1: `llm_client.complete_with_tools()` (AC: #1)
  - [ ] Add function signature mirroring `complete_with_system`'s auth/client-construction pattern (lines 51-90 of `harness/llm_client.py`) — same `OPENROUTER_API_KEY` env check, same `AsyncOpenAI` client construction, same `REQUEST_TIMEOUT_SECONDS`
  - [ ] Pass `tools=tools, tool_choice=tool_choice` (default `"auto"`) to `client.chat.completions.create(...)`
  - [ ] Return `(text, tool_calls, model, latency_ms)` — `tool_calls` is `resp.choices[0].message.tool_calls` (may be `None`)
  - [ ] Wrap the call in try/except for `openai.APIConnectionError`, `openai.APIStatusError`, `openai.APITimeoutError`; re-raise as a local exception type the caller can catch, or return a sentinel the caller checks — pick whichever matches the existing `complete`/`complete_with_system` error-handling convention (they currently let `ValueError` propagate for missing key; no try/except around the request itself — confirm this is intentional before adding new handling here, since none of the existing functions catch these openai exceptions today)
- [ ] Task 2: `harness/agent_tools.py` — tool registry (AC: #2)
  - [ ] `read_space(slug_or_room)` wrapping `git_ops.read_json` (space_id known) and `query_commands.fetch_space_json` (slug known) — reuse, do not reimplement JSON fetch/parse
  - [ ] `query_map(...)` wrapping `query_commands.find` / `nearby` / `network` — read-only passthroughs
  - [ ] `propose_write(field_path, new_value)`:
    - call `commands._can_write(power_level, field_path)` — reject early with the existing `(bool, reason)` contract if not allowed
    - call `commands._validate_value(field_path, value)` and `commands._coerce_value(field_path, value)` — reuse the existing field-specific logic (esp. `mom.memberOf`'s JSON-array-or-single-name coercion at `commands.py:82-87`)
    - for `mom.memberOf` specifically: read the current array via `read_space`, compute the new array (add/remove semantics — clarify with epic reframe intent, not just "replace"), store `{field_path, current_value, proposed_value, space_id}` in the pending-action store, return the delta for the model to echo
    - never call `git_ops.commit_json` directly
  - [ ] `log_gap(raw_request, note, gap_kind)`:
    - `gap_kind="ontology"` → call `nl_to_sparql._emit_gap_triple(raw_request, note)` unchanged
    - `gap_kind="capability"` → new SQLite table (new file, e.g. `harness/capability_gaps.db` or reuse an existing sqlite path if one exists — check `heartbeat_log.db` pattern in [[heartbeat_303_staleness_fix]] for precedent); columns at minimum: `timestamp, raw_request, note, room_id`
- [ ] Task 3: Pending-action store + confirmation flow (AC: #3)
  - [ ] In-memory dict in `harness/agent.py` (or a small dedicated module), keyed by `(room_id, user_id)` — simplest correct key per the plan; thread_id-keying is a stated alternative but adds complexity for a spike
  - [ ] Confirmation message handling: a subsequent message from the same `(room_id, user_id)` matching a "yes"/affirmative pattern (or a threaded reply if using `thread_id`) pops the pending entry and calls `git_ops.commit_json(space_id, field_path, coerced_value, authorized_by=user_id)`
  - [ ] Handle `git_ops.commit_json`'s existing raised errors (`NoDeployKeyError`, `NoChangeError`, `NoEndpointError`, `UnsupportedHostError`, pydantic `ValidationError`) by mapping each to an honest spoken response, not a stack trace
- [ ] Task 4: Permission-gated tool exposure (AC: #4)
  - [ ] In `harness/agent.py`'s entry point (e.g. `agent.run(message, session_id)`), branch tool list construction on `message.power_level >= 100` (same threshold as `commands._can_write`) — build the full tool list (including `propose_write`) only for coordinators; everyone else gets `read_space`/`query_map`/`log_gap` only
- [ ] Task 5: Bernard agent system prompt (AC: #5)
  - [ ] New module/YAML key — persona register per [[project_bernard_character]] (they/them, Ron-Swanson-on-fort)
  - [ ] Encode: confirm-before-write always; echo resolved entities; permission-denial → `!mom grant` pointer; missing-capability → call `log_gap` + say so
  - [ ] Do NOT retire or duplicate `bernard_voice.yaml` keys here — this prompt covers the agent's *reasoning* paths only (NL query, NL write, "what can you do"); the hardcoded bedrock ack stays separate and untouched (AC #10)
- [ ] Task 6: Wire into `router.py` (AC: #6)
  - [ ] Replace the `# write: not implemented yet` stub (`harness/router.py:25-27`) with a call to `agent.run(message, session_id=session_id)`
  - [ ] Optional/stretch: also route free-text/read-shaped intents through the agent — do not let this expand scope beyond the spike's write-path goal if time-boxed
- [ ] Task 7: Tests (AC: #7)
  - [ ] `harness/tests/test_agent.py`, following `harness/tests/test_commands.py`'s existing fixture/mocking conventions (`pytest.mark.asyncio`, `AsyncMock`, `_make_context`-style `Message` builder, `bernard.load_voice()` autouse fixture)
  - [ ] Mock `llm_client.complete_with_tools` to return canned `tool_calls` matching the OpenAI tool-call response shape
  - [ ] Assert memberOf delta arithmetic, confirm-gating (no `git_ops.commit_json` call before confirmation), permission-by-construction (inspect the `tools` argument passed to `complete_with_tools`, don't just check behavior), and gap-logging on unfulfillable requests
- [ ] Task 8: Live VPS verification (AC: #8) — manual, not automated; record outcome in Completion Notes
- [ ] Task 9: Decision record (AC: #9) — write the go/no-go finding into Dev Notes once the spike is run
- [ ] Task 10: Scope check (AC: #10) — confirm no `bernard_voice.yaml` keys were touched; note if any temptation arose to expand scope and why it was resisted or why an exception was made

## Dev Notes

- **This is a spike, not a production feature.** The goal is to prove the tool-calling loop pattern over existing effect functions on the hardest case (`mom.memberOf` full-array rewrite). `state.open` and other scalar fields should generalize trivially afterward — do not build separate machinery for them in this story.
- **Effects layer is reused unchanged.** `git_ops.py`, `commands._can_write`/`_validate_value`/`_coerce_value`, and `query_commands.py` are NOT modified by this story. If a change to any of them seems necessary, stop and reconsider the tool wrapper design rather than editing tested, working code.
- **Bot is currently fully stateless** (fresh `uuid` session_id per message, logging only — no cross-message state). The pending-action store introduced here is the first piece of cross-message state in the harness. Keep it in-memory and simple (a module-level dict) — no new persistence layer for the spike.
- **Confirm-before-write is enforced by construction**, not by asking the LLM nicely in the prompt: `propose_write` is exposed to the model, but there is no `commit_write`/`execute_write` tool. The system prompt describes the flow for the LLM's narration, but the actual gate is "the model literally cannot call a tool that commits."

### Project Structure Notes

- New files: `harness/agent.py`, `harness/agent_tools.py`, `harness/tests/test_agent.py`, Bernard agent system prompt (module or YAML key — follow existing `bernard_voice.yaml` / `harness/bernard.py` split, see [[feedback_bernard_voice_yaml_is_ssot]] for why voice content belongs in YAML, though this spike's system-prompt text is a different concern than the copy-table it replaces)
- Modified files: `harness/llm_client.py` (add `complete_with_tools`, no changes to existing `complete`/`complete_with_system`), `harness/router.py` (wire `write` intent, lines 25-27)
- Untouched: `infra/bot/git_ops.py`, `harness/commands.py`, `harness/query_commands.py`, `harness/nl_to_sparql.py`, `bernard_voice.yaml`
- **Deploy gotcha**: `infra/bot/git_ops.py` is baked into the bot Docker image, not bind-mounted for live testing — a live VPS test (AC #8) needs a rebuilt image + `make publish` (rsync-based deploy, see [[infra_vps_deploy_rsync]]), not a live-edit loop.

### References

- Plan: `~/.claude/plans/eventual-leaping-dream.md` (full technical exploration — effect function inventory, LLM client gap, message fields, test conventions)
- [Source: harness/router.py#L12-27] — current `route()` dispatch and the `write` stub
- [Source: harness/llm_client.py#L51-90] — `complete_with_system` pattern to mirror for `complete_with_tools`
- [Source: harness/commands.py#L46-119] — `ALLOWED_FIELDS`, `_can_write`, `_validate_value`, `_coerce_value`
- [Source: infra/bot/git_ops.py#L46-62,217,306] — `NoDeployKeyError`/`UnsupportedHostError`/`NoEndpointError`/`NoChangeError`, `resolve_space_for_room`, `read_json`, `commit_json`
- [Source: harness/nl_to_sparql.py#L131] — `_emit_gap_triple` (existing FR41 ontology-gap mechanism, reused for `gap_kind="ontology"`)
- [Source: harness/message.py] — `Message` dataclass already carries `user_id`, `room_id`, `power_level`, `event_id`, `thread_id`
- [[feedback_llm_bot_no_canned_copy_table]] — why this story supersedes 6.5's original scope
- [[feedback_no_cut_planned_epic6]] — this is planned Epic 6 work, not scope creep
- [[project_bernard_character]] — persona/voice register for the system prompt
- [[epic_3_retro_findings]] — pytest passing ≠ done; live integration is the real DoD
- [[infra_vps_deploy_rsync]] — deploy mechanics for the live verification step

## Scope Guardrails

- Spike proves `mom.memberOf` delta first (hardest case: full-array rewrite, not a scalar set). Do not build generalized multi-field UI beyond what's needed to prove this one path plus trivial scalar reuse.
- **Out of scope, log honestly via `log_gap(gap_kind="capability")` rather than half-implementing:** schema authoring / extended-field setup (belongs to the bundle/wormhole epic, see [[project_schema_bundle_model]]); tool-reasoning requiring new capabilities not yet built (e.g. timezone/clock lookups).
- **Do not decide nanobot vs. hermes vs. "native SDK is enough" up front** — this spike's outcome answers that question (AC #9). Building toward a specific framework choice mid-spike is scope creep.
- Once the spike is validated (decision record written, live test passed), a **follow-up story** retires most of `bernard_voice.yaml`'s voice keys and re-cuts a "Bernard as tool-calling agent" story for the remaining hardening work. That retirement is explicitly NOT part of this story (AC #10).

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
