# Story 6.10: Fuzzy NL Question Routing

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Nicolas (operator of the Maps of Making Bernard bot),
I want free-text messages that today classify as `intent="unknown"` to be routed through the Story 6.9 tool-calling agent (`agent.run()`) instead of hard-stopping at `bernard.unknown_ack()`,
so that coordinator-onboarding questions ("how can you help me?", "what's up with this space?") get an honest, tool-backed answer or an honest "can't do that, logged it" instead of a dead end — and every unresolved question is captured as roadmap signal for scoping future wide-scope (`query` folded in) and multi-turn-memory work, rather than guessed at.

This is the narrower of two options discussed as Story 6.9's Task 6 stretch goal (deferred there, out of scope for the write-path spike). Scope for 6.10 is **narrow by explicit operator decision**: only `unknown` intent is rerouted. `query` and `nl_discovery` intents keep their existing, working dispatch paths untouched — folding `query` into the agent loop too ("wide" scope) and adding cross-message conversational memory are both explicitly deferred to a follow-up story, seeded by the gap data this story starts collecting.

## Acceptance Criteria

1. `harness/router.py`'s `intent == "unknown"` branch (currently `return bernard.unknown_ack()`, line 26-27) calls `agent.run(message, session_id=session_id, adapter=adapter)` instead. The final fallback branch (line 38-39, `log.warning("router.intent_not_implemented", ...)` for a classifier result matching none of the known intents) is **not** changed — it's a different failure mode (classifier returned something unrecognized, not "no intent found") and stays a hard `unknown_ack()`.
2. `query` and `nl_discovery` branches in `router.py` are untouched — same dispatch calls, same behavior, zero risk to the already-working read paths.
3. `agent.run()` requires no new code path for this — it already builds tools via `agent_tools.build_tools(power_level)` and already has `read_space`/`query_map`/`log_gap` (and `propose_write` for coordinators). Confirm via test that a `power_level < 100` fuzzy question still only gets the non-write tool set (regression check on the existing 6.9 permission gate, not new gating logic).
4. `harness/bernard_agent_prompt.py` gains an explicit scope-boundary rule: Bernard answers questions about Maps of Making spaces/network/data only. An off-topic ask (e.g. "what's the weather", "who won the game") gets a short, in-character refusal (busy, no-nonsense register per [[project_bernard_character]]) — **not** a `log_gap` call. `log_gap(gap_kind="capability")` is reserved for on-topic asks Bernard can't currently fulfill (missing tool/data), not off-topic noise — conflating the two would pollute the roadmap-signal data this story exists to start collecting.
5. Every fuzzy question that reaches the agent and does **not** resolve to a satisfying answer (agent itself decides it can't fulfill the request — not a hard classifier rule) results in exactly one `log_gap(gap_kind="capability", raw_request=..., note=..., room_id=...)` call, reusing the existing SQLite table from Story 6.9 (`agent_tools._write_capability_gap`) unchanged. No new storage mechanism.
6. `harness/tests/test_router.py` (new or extended if it exists) asserts: an `unknown`-classified message calls `agent.run()`, not `bernard.unknown_ack()`; `query`/`nl_discovery` classified messages still call their existing dispatch functions unchanged (regression guard); the final unrecognized-intent fallback still returns `bernard.unknown_ack()` without calling `agent.run()`.
7. `harness/tests/test_agent.py` gains a case for the off-topic guardrail: given a canned off-topic user message and a mocked LLM response reflecting the refusal, assert `log_gap` is **not** called (distinguishing "declined to answer" from "logged as a gap").
8. Live Matrix verification (per [[epic_3_retro_findings]] DoD): a previously-dead-ending fuzzy question ("how can you help me?") now gets an agent-produced answer instead of the canned unknown_ack; an off-topic question gets an in-character refusal with no capability-gap row written; a genuinely unresolvable on-topic question ("what's the isochrone from a space that doesn't exist") produces both an honest response and a new row in the capability-gaps table.
9. **Every fuzzy question routed through the agent is logged, resolved or not** — not just failures. New `agent_tools.log_fuzzy_question(raw_request, resolved: bool, room_id)` writes one row per fuzzy question to a new SQLite table (`fuzzy_questions`: `timestamp, raw_request, resolved, room_id`), reusing the same DB file/precedent as the existing capability-gaps table (same `heartbeat_log.db`-style pattern, see [[heartbeat_303_staleness_fix]]). This is analytics, not the gap-signal mechanism from AC #5 — the two are logged independently (a resolved question is never a gap; an unresolved on-topic question is both a gap row AND a `resolved=false` analytics row). Off-topic refusals count as `resolved=true` (Bernard correctly declined — not a capability gap, not a failure to analyze).

## Tasks / Subtasks

- [ ] Task 1: Reroute `unknown` intent (AC: #1, #2)
  - [ ] Change `harness/router.py` line 26-27 from `bernard.unknown_ack()` to `await agent.run(message, session_id=session_id, adapter=adapter)`
  - [ ] Leave `query`/`nl_discovery` branches and the final `log.warning(...)` fallback branch exactly as-is
- Task 2: Off-topic scope-boundary prompt rule (AC: #4)
  - [ ] Add explicit rule to `harness/bernard_agent_prompt.py`: refuse off-topic asks in-character, do not call `log_gap` for them
  - [ ] Keep the existing "on-topic but unfulfillable → `log_gap(gap_kind='capability')`" rule from Story 6.9 intact; the new rule is additive, distinguishing the two cases
- [ ] Task 3: Tests (AC: #3, #6, #7)
  - [ ] `harness/tests/test_router.py`: unknown→agent.run assertion, query/nl_discovery regression guard, fallback-branch-still-unknown_ack assertion
  - [ ] `harness/tests/test_agent.py`: permission-gate regression check for fuzzy questions (non-coordinator gets no `propose_write` even when asking a free-text question), off-topic-refusal-does-not-call-log_gap case
- [ ] Task 4: Fuzzy-question analytics logging (AC: #9)
  - [ ] New `fuzzy_questions` SQLite table (new file or same DB as capability-gaps table — follow `_capability_gaps_db_path`/`_init_capability_gaps_db` precedent in `agent_tools.py`), columns `timestamp, raw_request, resolved, room_id`
  - [ ] `agent_tools.log_fuzzy_question(raw_request, resolved, room_id)` — called once per fuzzy question at the end of `agent.run()`'s fuzzy-question path (resolved=True for a satisfying answer or an off-topic refusal, resolved=False for an on-topic gap)
  - [ ] Keep independent from `log_gap` — a gap row and an analytics row are both written for an unresolved on-topic question, but they answer different questions later (what's broken vs. how much fuzzy-question traffic exists at all)
- [ ] Task 5: Live VPS verification (AC: #8) — manual, record outcome in Completion Notes
- [ ] Task 6: Scope check — confirm no `query`/`nl_discovery` dispatch code touched; confirm no multi-turn/conversation-memory work was added (explicitly out of scope, see Scope Guardrails)

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

### Debug Log References

### Completion Notes List

### File List

### Change Log
