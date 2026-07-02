# Story 6.10: Fuzzy NL Question Routing

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Nicolas (operator of the Maps of Making Bernard bot),
I want free-text messages that today classify as `intent="unknown"` to be routed through the Story 6.9 tool-calling agent (`agent.run()`) instead of hard-stopping at `bernard.unknown_ack()`,
so that coordinator-onboarding questions ("how can you help me?", "what's up with this space?") get an honest, tool-backed answer or an honest "can't do that, logged it" instead of a dead end — and every unresolved question is captured as roadmap signal for scoping future wide-scope (`query` folded in) and multi-turn-memory work, rather than guessed at.

This is the narrower of two options discussed as Story 6.9's Task 6 stretch goal (deferred there, out of scope for the write-path spike). Scope for 6.10 is **narrow by explicit operator decision**: only `unknown` intent is rerouted. `query` and `nl_discovery` intents keep their existing, working dispatch paths untouched — folding `query` into the agent loop too ("wide" scope) and adding cross-message conversational memory are both explicitly deferred to a follow-up story, seeded by the gap data this story starts collecting.

## Acceptance Criteria

1. `harness/router.py`'s `intent == "unknown"` branch (currently `return bernard.unknown_ack()`, line 26-27) calls `agent.run(message, session_id=session_id, adapter=adapter)` instead. The final fallback branch (line 38-39, `log.warning("router.intent_not_implemented", ...)` for a classifier result matching none of the known intents) is **not** changed — it's a different failure mode (classifier returned something unrecognized, not "no intent found") and stays a hard `unknown_ack()`.
2. ~~`query` and `nl_discovery` branches in `router.py` are untouched — same dispatch calls, same behavior, zero risk to the already-working read paths.~~ **Superseded 2026-07-02 (live verification):** `query_commands.dispatch()` turned out to be an unwired stub (always `unknown_ack()`, never finished post-6.3) — not a working path at all. Operator approved same-day scope widening: `query` now also routes through `agent.run()` (fuzzy=False). `nl_discovery` remains untouched.
3. `agent.run()` requires no new code path for this — it already builds tools via `agent_tools.build_tools(power_level)` and already has `read_space`/`query_map`/`log_gap` (and `propose_write` for coordinators). Confirm via test that a `power_level < 100` fuzzy question still only gets the non-write tool set (regression check on the existing 6.9 permission gate, not new gating logic).
4. `harness/bernard_agent_prompt.py` gains an explicit scope-boundary rule: Bernard answers questions about Maps of Making spaces/network/data only. An off-topic ask (e.g. "what's the weather", "who won the game") gets a short, in-character refusal (busy, no-nonsense register per [[project_bernard_character]]) — **not** a `log_gap` call. `log_gap(gap_kind="capability")` is reserved for on-topic asks Bernard can't currently fulfill (missing tool/data), not off-topic noise — conflating the two would pollute the roadmap-signal data this story exists to start collecting.
5. Every fuzzy question that reaches the agent and does **not** resolve to a satisfying answer (agent itself decides it can't fulfill the request — not a hard classifier rule) results in exactly one `log_gap(gap_kind="capability", raw_request=..., note=..., room_id=...)` call, reusing the existing SQLite table from Story 6.9 (`agent_tools._write_capability_gap`) unchanged. No new storage mechanism.
6. `harness/tests/test_router.py` (new or extended if it exists) asserts: an `unknown`-classified message calls `agent.run()`, not `bernard.unknown_ack()`; `query`/`nl_discovery` classified messages still call their existing dispatch functions unchanged (regression guard); the final unrecognized-intent fallback still returns `bernard.unknown_ack()` without calling `agent.run()`.
7. `harness/tests/test_agent.py` gains a case for the off-topic guardrail: given a canned off-topic user message and a mocked LLM response reflecting the refusal, assert `log_gap` is **not** called (distinguishing "declined to answer" from "logged as a gap").
8. Live Matrix verification (per [[epic_3_retro_findings]] DoD): a previously-dead-ending fuzzy question ("how can you help me?") now gets an agent-produced answer instead of the canned unknown_ack; an off-topic question gets an in-character refusal with no capability-gap row written; a genuinely unresolvable on-topic question ("what's the isochrone from a space that doesn't exist") produces both an honest response and a new row in the capability-gaps table.
9. **Every fuzzy question routed through the agent is logged, resolved or not** — not just failures. New `agent_tools.log_fuzzy_question(raw_request, resolved: bool, room_id)` writes one row per fuzzy question to a new SQLite table (`fuzzy_questions`: `timestamp, raw_request, resolved, room_id`), reusing the same DB file/precedent as the existing capability-gaps table (same `heartbeat_log.db`-style pattern, see [[heartbeat_303_staleness_fix]]). This is analytics, not the gap-signal mechanism from AC #5 — the two are logged independently (a resolved question is never a gap; an unresolved on-topic question is both a gap row AND a `resolved=false` analytics row). Off-topic refusals count as `resolved=true` (Bernard correctly declined — not a capability gap, not a failure to analyze).

## Tasks / Subtasks

- [x] Task 1: Reroute `unknown` intent (AC: #1, #2)
  - [x] Change `harness/router.py`'s unknown branch from `bernard.unknown_ack()` to `await agent.run(message, session_id=session_id, adapter=adapter, fuzzy=True)`
  - [x] Leave `query`/`nl_discovery` branches and the final `log.warning(...)` fallback branch exactly as-is
- [x] Task 2: Off-topic scope-boundary prompt rule (AC: #4)
  - [x] Add explicit rule to `harness/bernard_agent_prompt.py`: refuse off-topic asks in-character, do not call `log_gap` for them
  - [x] Keep the existing "on-topic but unfulfillable → `log_gap(gap_kind='capability')`" rule from Story 6.9 intact; the new rule is additive, distinguishing the two cases
- [x] Task 3: Tests (AC: #3, #6, #7)
  - [x] `harness/tests/test_router.py`: unknown→agent.run assertion, query/nl_discovery regression guard, fallback-branch-still-unknown_ack assertion
  - [x] `harness/tests/test_agent.py`: permission-gate regression check for fuzzy questions (non-coordinator gets no `propose_write` even when asking a free-text question), off-topic-refusal-does-not-call-log_gap case
- [x] Task 4: Fuzzy-question analytics logging (AC: #9)
  - [x] New `fuzzy_questions` SQLite table (same DB pattern as capability-gaps table — follows `_capability_gaps_db_path`/`_init_capability_gaps_db` precedent in `agent_tools.py`), columns `timestamp, raw_request, resolved, room_id`
  - [x] `agent_tools.log_fuzzy_question(raw_request, resolved, room_id)` — called once per fuzzy question at the end of `agent.run()`'s fuzzy-question path (resolved=True for a satisfying answer or an off-topic refusal, resolved=False for an on-topic gap)
  - [x] Keep independent from `log_gap` — a gap row and an analytics row are both written for an unresolved on-topic question, but they answer different questions later (what's broken vs. how much fuzzy-question traffic exists at all)
- [ ] Task 5: Live VPS verification (AC: #8) — manual, requires live Matrix/VPS access the dev agent does not have; NOT performed, see Completion Notes
- [x] Task 6: Scope check — confirmed no `query`/`nl_discovery` dispatch code touched; confirmed no multi-turn/conversation-memory work was added (explicitly out of scope, see Scope Guardrails)

## Dev Notes

- **This is a routing change, not new agent capability.** `agent.run()`, `agent_tools.py`, `bernard_agent_prompt.py`'s existing rules, and the capability-gaps SQLite table all already exist from Story 6.9 and are reused unchanged except for the one additive prompt rule in Task 2. If implementing this story seems to require new tools or new storage, stop — that's scope creep into the deferred "wide" story.
- **Why narrow, not wide:** operator explicitly confirmed narrow scope for this story. `query` intent already has a working, tested dispatch path (`query_commands.dispatch`) — folding it into the LLM agent loop risks regressing a working feature for a benefit (looser NL phrasing on queries) not yet proven necessary. The capability-gap data this story starts collecting is the evidence base for deciding if/how to fold `query` in later.
- **No multi-turn memory in this story.** The bot is stateless per message except the one exception Story 6.9 built (`PENDING_ACTIONS` for write-confirm only, not general conversation). A user asking a fuzzy follow-up ("what about X") after a fuzzy first question ("tell me about Y") will not have Y's context. This is a known, accepted gap for this story — flagged for the follow-up "wide scope + multi-turn" story, not solved here.
- **The `log_gap` distinction (on-topic-unfulfillable vs. off-topic) is the actual point of this story.** Getting this rule wrong (e.g. logging off-topic noise as capability gaps) would corrupt the exact signal the operator wants to use to scope the next story — treat AC #4/#5/#7 as the most important tests in this story, not the routing change itself (which is a one-line diff).

### Project Structure Notes

- Modified files: `harness/router.py` (one branch, line 26-27), `harness/bernard_agent_prompt.py` (additive rule)
- New files: `harness/tests/test_router.py` if it doesn't already exist (check first — router logic may currently only be covered indirectly via `test_agent.py`/`test_commands.py`)
- Untouched: `harness/agent.py`, `harness/agent_tools.py`, `harness/query_commands.py`, `harness/nl_to_sparql.py`, `harness/commands.py`, `bernard_voice.yaml`

### References

- [Source: harness/router.py#L14-39] — current `route()` dispatch, the `unknown` branch this story changes
- [[project_story_6_9_agent_spike_outcome]] — the agent loop and tool registry this story routes into, unchanged
- [[feedback_bernard_agent_integration_gotchas]] — six integration bugs from 6.9's live testing; re-read before touching `router.py`/`agent.py` again (esp. #3, the router-ordering bug, and #4, the tool-error-fabrication lesson — same LLM-honesty risk applies to off-topic/unfulfillable answers here)
- [[project_epic6_nl_fuzzy_question_next]] — the operator's original framing of this story before scoping
- [[project_bernard_character]] — persona register for the off-topic refusal wording
- [[epic_3_retro_findings]] — pytest passing ≠ done; live integration is the real DoD

## Scope Guardrails

- **Narrow only**: `unknown` intent rerouted. `query`/`nl_discovery` intents NOT touched. Do not fold them in "while we're in here" — that's the deferred wide-scope story.
- **No multi-turn conversation memory.** Do not add cross-message context/history beyond what already exists (`PENDING_ACTIONS` for write-confirm). Sequenced-question continuity is explicitly deferred.
- **`log_gap` discipline**: off-topic → in-character refusal, no log. On-topic-unfulfillable → honest answer + `log_gap(gap_kind="capability")`. Do not blur this line for convenience.
- Once this story ships and has run live long enough to accumulate capability-gap data, a follow-up story uses that data to scope: (a) whether to fold `query` into the agent loop (wide scope), and (b) whether/how to add multi-turn conversational memory. Neither is decided in this story.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

Full suite: `python3 -m pytest tests/ -q` → 105 passed, 3 pre-existing failures in `test_commands.py` (verified pre-existing via `git stash` on this same tree before implementation — a display-name interpolation bug unrelated to this story, not touched).

### Completion Notes List

- Tasks 1–4 and 6 implemented and tested (unit level). Task 5 (live Matrix/VPS verification, AC #8) manual step run live by operator on VPS 2026-07-02 (see below) — found and fixed 2 real bugs same-day (see Change Log).
- `agent.run()` gained a `fuzzy: bool = False` kwarg — additive, defaults False so the existing `write` intent call site and Story 6.9's tests are unaffected. `router.py`'s `unknown` branch passes `fuzzy=True`; `query` branch (see below) passes `fuzzy=False` — routed through the agent but excluded from fuzzy-question analytics since it's a confidently-classified intent, not a fuzzy one.
- `capability_gap_logged` is tracked per-`run()` call (not global) by inspecting `log_gap` tool-call arguments as they're dispatched — resolved-status for the analytics row derives from whether a capability gap was logged during that specific run, not from parsing the final answer text.
- Off-topic guardrail is prompt-only (Rule 7/8 in `bernard_agent_prompt.py`) — no code-level topic classifier, consistent with 6.9's "graceful failure lives in the system prompt" precedent ([[feedback_llm_bot_no_canned_copy_table]]).
- `FUZZY_QUESTIONS_DB_PATH` env var follows the same override pattern as `CAPABILITY_GAPS_DB_PATH`; default `/app/tasks/fuzzy_questions.db` mirrors the existing container path convention.

**Live verification findings (2026-07-02, operator-run on VPS via `make publish`):**

1. **`query_commands.dispatch()` was an unwired stub** — always returned `unknown_ack()` regardless of input, discovered because "could you show me the details of openfab?" classified as `query` and hit the stub, while "read openfab space details" classified `unknown`, routed through the new agent path, and worked correctly. This story's AC #2 / Dev Notes assumed the `query` path "already has a working, tested dispatch path" — that assumption was **wrong**, confirmed via live logs (`query_commands.dispatch_fallback` unconditional). Pre-existing since a post-6.3 commit, not introduced by 6.10.
   **Fix (operator-approved same-day scope widening):** `router.py`'s `query` branch now also routes through `agent.run()` (fuzzy=False), same as `unknown`. `query_commands.dispatch()` itself is left in place (dead code, no callers) rather than deleted, in case a dedicated query dispatcher work resumes later — flag for cleanup in a follow-up story.
2. **Off-topic refusal fabricated a tool call.** Live logs showed `tool_call_count=0` for a weather question, yet Bernard replied "I have logged this capability gap" — it never called `log_gap`, but claimed it had. Rule 7 told the model not to call the tool but never told it not to *say* it did.
   **Fix:** added Rule 8 to `bernard_agent_prompt.py` — never describe an action (logged/noted/recorded/updated/changed) that wasn't backed by an actual tool call this turn.
3. `!mom find open space prague` literal-command duplicate-looking reply in the operator's screenshot was checked against VPS logs — only one `sparql.select_completed`/`message.responded` pair exists; not a backend bug, looks like an Element UI thread-pane rendering coincidence (two panes both landing on the same timestamp). Not pursued further.

Both fixes above were redeployed and confirmed live before the next round (see below) — the "show me openfab"/weather smoke test on VPS is still outstanding as a final re-check, deprioritized while chasing the two bugs below since they were found during the same live session.

**Round 2 findings (2026-07-02, same live session, operator kept digging):**

4. **False mention trigger.** `main_matrix.py`'s `_is_bernard_mention()` matched `^@?bernard[\s,:]+` — a plain French sentence beginning "Bernard s'en fiche..." (Bernard, as grammatical subject, not an address) false-triggered the bot. Pre-existing, unrelated to 6.10's routing, but the operator asked for it fixed in this session ("I don't care which story to blame, let's fix it now").
   **Fix:** `matrix_adapter.py` now detects real Matrix intentional mentions (`m.mentions.user_ids` containing the bot's own mxid) or a literal `@bernard` substring in the raw body, and stamps `Message.is_mention`. `main_matrix.py` uses that flag instead of a loose text-prefix regex. New `harness/tests/test_matrix_adapter.py` (4 tests) using `matrix-nio`'s `RoomMessageText`/`MatrixRoom` shape — required installing `matrix-nio` into `venv` (it's already in `harness/requirements.txt`, just wasn't installed locally). Deployed and confirmed live: a bare "bernard ..." sentence no longer triggers a response; `@bernard`/tap-mention still does.
5. **SpaceAPI spaces invisible to city/tag search.** Operator reported Bernard couldn't find any SpaceAPI-directory spaces in Berlin despite the map showing a confirmed, open one there. Root-caused via direct SPARQL against the live Oxigraph store to **two independent gaps**, both pre-existing (not 6.10-caused, just newly visible because `query` now actually reaches real data instead of the dead stub from finding #1):
   - `infra/link_handler/pipeline.py`'s `write_payload_fields()` (which extracts `schema:addressLocality`/`knowsAbout` from the live payload) only runs when `content_changed=True`. An endpoint whose payload never drifts (static hackerspace info) never triggers it — the fields stay unwritten forever, matching the already-documented [[ops_payload_field_backfill]] gap for a different field set.
   - Independently, `scripts/spaceapi_extract/mom.py`'s `extract_mom()` never derived `schema:addressLocality` from SpaceAPI's free-text `location.address` field at all (only `mom:address`, country, timezone) — so even with #1 fixed, the field would still never be written for SpaceAPI-sourced spaces specifically. `scripts/seed_bundle.py` (the VOW/FabNet bundle importer) already had working free-text address-parsing logic for this, just never shared with the SpaceAPI extraction path.
   **Fix:** (a) `pipeline.py` gained `_payload_fields_absent()` + a one-time backfill call in `run_space_pipeline()`'s `content_changed=False` branch, mirroring the existing `mom:updatedAt` backfill precedent immediately above it. (b) extracted `seed_bundle.py`'s address-parsing regex into a shared `scripts/spaceapi_extract/address.py::parse_locality_from_free_address()`, wired into `extract_mom()`, and re-used by `seed_bundle.py` itself (removes duplicated logic). Also widened the postcode regex from `\d{4}` (Belgian/Dutch-only) to `\d{4,5}` — Germany dominates the dataset (VOW alone: 567 German spaces) and 5-digit postcodes were silently failing to parse under the original pattern, which would have been a live bug in the "fix" itself if shipped unchanged.
   **Verified live:** `curl` against the VPS Oxigraph endpoint directly (`schema:addressLocality` search for "berlin") returned 10 matches post-deploy, including `xhain-hack-makespace` (self-registered) and multiple SpaceAPI-sourced spaces, where it returned zero before the fix. `docker logs maps-link-handler` shows dozens of `[payload-fields] ... backfilled (was absent, content unchanged)` lines firing across the real dataset, not just Berlin.
   New tests: 8 unit tests in `tests/test_spaceapi_extract.py` (parser edge cases + `extract_mom` wiring, all passing locally) + 1 `@pytest.mark.live_integration` test in `tests/test_canary_three_axis_e2e.py` mirroring the existing `mom:updatedAt` backfill test's structure (not run locally — requires local Oxigraph/canary infra not up in this session; verified against the real VPS store instead, consistent with how the rest of this story's live verification was done).

Operator indicated after round 2 they are **not yet satisfied and want to keep digging** — this story is not being closed out yet, more live findings may follow in the same session.

### File List

- `harness/router.py` — modified (unknown → `agent.run(fuzzy=True)`; query → `agent.run(fuzzy=False)`, stub dispatch abandoned; unused `query_commands` import removed)
- `harness/agent.py` — modified (`fuzzy` kwarg, capability-gap tracking, `log_fuzzy_question` calls at all three return points)
- `harness/agent_tools.py` — modified (`fuzzy_questions` SQLite table, `_fuzzy_questions_db_path`, `_init_fuzzy_questions_db`, `log_fuzzy_question`)
- `harness/bernard_agent_prompt.py` — modified (Rule 7: off-topic scope boundary; Rule 8: no claiming un-taken actions)
- `harness/tests/test_router.py` — new
- `harness/tests/test_agent.py` — modified (5 new tests: permission-gate regression, off-topic-no-log_gap, resolved/unresolved fuzzy analytics, write-path-untouched analytics)
- `harness/message.py` — modified (`is_mention: bool` field)
- `harness/matrix_adapter.py` — modified (real `m.mentions`/literal-`@bernard` mention detection)
- `harness/main_matrix.py` — modified (`_is_bernard_mention()` text-regex replaced with `message.is_mention`)
- `harness/tests/test_matrix_adapter.py` — new (4 tests)
- `harness/tests/test_message.py` — modified (field-set assertion updated for `is_mention`)
- `infra/link_handler/pipeline.py` — modified (`SCHEMA_NS` constant, `_payload_fields_absent()`, one-time payload-fields backfill call)
- `scripts/spaceapi_extract/address.py` — new (`parse_locality_from_free_address()`, shared parser)
- `scripts/spaceapi_extract/mom.py` — modified (`extract_mom()` derives `schema:addressLocality` from free-text address)
- `scripts/spaceapi_extract/__init__.py` — modified (exports new parser)
- `scripts/seed_bundle.py` — modified (uses shared parser instead of inline duplicate logic)
- `tests/test_spaceapi_extract.py` — modified (8 new tests)
- `tests/test_canary_three_axis_e2e.py` — modified (1 new `live_integration` test + helper)

### Change Log

- 2026-07-02: Implemented Story 6.10 — unknown intent reroutes through `agent.run(fuzzy=True)`; added off-topic scope-boundary prompt rule; added `fuzzy_questions` analytics table independent of the existing capability-gaps table; unit tests added for router and agent.
- 2026-07-02: Live VPS verification (round 1) found `query_commands.dispatch()` was a dead stub and the off-topic refusal fabricated a "logged" claim without calling the tool. Operator approved same-day scope widening: `query` intent now also routes through `agent.run()`; added prompt Rule 8 forbidding claims of un-taken actions. Redeployed and confirmed live.
- 2026-07-02: Live VPS verification (round 2) found a false mention-trigger bug (any sentence starting with "bernard" false-triggered the bot) and a two-part SpaceAPI data gap (payload-fields backfill never fires on unchanged content; `extract_mom()` never derived city from free-text address at all). Fixed both, redeployed, confirmed live via direct Oxigraph queries and heartbeat logs. Operator not yet satisfied — continuing to dig in the same session.
