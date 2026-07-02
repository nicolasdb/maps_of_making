# Story 6.11: Collapse NL Answer Paths — Single Orchestrator, FAQ Cache, Tier-2 Escalation

Status: draft

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Nicolas (operator of the Maps of Making Bernard bot),
I want exactly one system answering natural-language questions — `agent.py`'s tool-calling loop, with `nl_to_sparql.py`'s SPARQL-generation folded in as a callable tool and a small FAQ cache in front of it — instead of two disagreeing NL systems (`router.py`'s `nl_discovery` branch calling `nl_to_sparql.dispatch()` directly, vs. `unknown`/`query`/`write` calling `agent.run()`),
so that a question like "how many spaces are open now in Berlin and which one?" gets one consistent answer, on the project's configured default model, with one gap-log mechanism — not a coin-flip between two code paths with different models and different failure behavior.

This is the collapse-first slice of the target architecture from `_bmad-output/planning-artifacts/mom_handoff_2026-07-02.md` and tonight's roundtable resolution of the Winston/Nicolas fork: **`agent.py` is the orchestrator, not `nl_to_sparql.py`.** Tier 0 (FAQ semantic cache) and Tier 2 (Sonnet escalation) both live inside/in-front-of that one loop. Full model-tiering infrastructure, `networks/*.yaml` manifests, persona packs, and Oxpecker are explicitly out of scope — this story proves the collapsed wiring works live on the exact question that surfaced the divergence, nothing more.

## Acceptance Criteria

1. `harness/router.py`'s `nl_discovery` branch (currently `return await nl_to_sparql.dispatch(message, session_id=session_id)`, line 36-37) is removed. Every classified intent (`unknown`, `query`, `nl_discovery`, `write`) that isn't a pending-action confirmation now reaches `agent.run()` — `nl_discovery` messages get `fuzzy=False` (confidently classified, same treatment as `query`, excluded from fuzzy-question analytics per the existing `fuzzy` kwarg semantics from Story 6.10).
2. `nl_to_sparql.py`'s LLM→SPARQL→execute capability is exposed as a new tool in `agent_tools.py`'s `READ_TOOLS` catalog (name: `query_sparql`), callable by the agent loop when `query_map`'s fixed-shape `find`/`nearby`/`network` functions (`harness/query_commands.py`) don't match the question's intent. `nl_to_sparql.dispatch()` (the `Message`-shaped, router-facing entry point) is removed; its internals (`_load_ontology_cache`, `_strip_fence`, `_escape_sparql_literal`, `FORBIDDEN` check, `_emit_gap_triple` callers) are refactored into a plain callable (e.g. `nl_to_sparql.generate_and_run(question: str, model: str, session_id: str) -> dict`) that `agent_tools.query_sparql()` wraps, matching the shape of `agent_tools.query_map()`'s passthrough to `query_commands`.
3. The hardcoded `model="anthropic/claude-sonnet-4-5"` at `nl_to_sparql.py:166` is removed. `generate_and_run()` takes `model` as a required parameter — it does not choose its own model. `harness/llm_client.py` gains a `SONNET_MODEL` constant (replacing the removed hardcoded string as the single named reference to the escalation model) alongside the existing `MODEL`/`DEFAULT_MODEL`.
4. `agent.py`'s tool-calling loop (`run()`, `harness/agent.py:29-96`) gains Tier-2 escalation, triggered by exactly two conditions (no other heuristic, no "implied intent" judgment call):
   - **Trigger A (tool error):** a `query_sparql` tool call in the current iteration returns `{"error": ...}` from `_dispatch_tool`.
   - **Trigger B (empty-but-specific):** a `query_sparql` tool call returns zero bindings AND `message.text` (case-insensitive) contains at least one of a fixed keyword list: `"how many"`, `"how much"`, `"which one"`, `"which "`, `"count"`. This list lives as a module-level constant (`agent.py::_SPECIFIC_ANSWER_KEYWORDS`, same shape as `query_commands._STATE_KEYWORDS`) — not a free-text/LLM judgment of "did the question imply specificity."

   On either trigger, the loop retries that single iteration's `complete_with_tools` call with `model=llm_client.SONNET_MODEL` instead of `llm_client.MODEL`, once per run (a per-run boolean flag, not a per-iteration counter — escalation happens at most once across all `MAX_TOOL_ITERATIONS`). A second Trigger A/B condition after the escalated retry does NOT re-escalate — it falls through to the normal `unknown_ack()`/gap-log path at loop end. This is the only place a model choice other than `llm_client.MODEL` is made anywhere in the harness.
5. Tier 0 FAQ cache stub: new `harness/faq_cache.py` holds a small, hand-seeded list of `{trigger, sparql_template, description}` entries — **exactly one seeded pair for this story** (a validated SPARQL template answering "how many spaces are open now in Berlin and which one?" using `schema:addressLocality` + `mom:openNow`, matching the pattern the map's materializer already uses correctly). `router.py` checks the FAQ cache (simple substring/keyword match against `trigger`, no embeddings/semantic-similarity infra — that's explicitly deferred) before intent classification runs. **A cache hit does NOT bypass the model call.** Concrete mechanism: `agent.run()` gains a `faq_hint: str = ""` parameter; when non-empty, `run()` builds the `system` argument to `complete_with_tools` as `bernard_agent_prompt.SYSTEM_PROMPT + "\n\n" + FAQ_HINT_TEMPLATE.format(hint=faq_hint)` instead of the bare `SYSTEM_PROMPT` — a plain string suffix, no new message role, no change to `llm_client.complete_with_tools`'s signature. `FAQ_HINT_TEMPLATE` lives in `bernard_agent_prompt.py` alongside `SYSTEM_PROMPT`, worded so Gemma treats it as a validated pattern to prefer, not an instruction to skip tool-calling. Gemma still runs, still decides how to use the hint (typically: call `query_sparql`/`query_map` with the hinted shape rather than free-generating from scratch), and the loop still produces the response through the normal tool-calling path. A cache miss passes `faq_hint=""`; behavior is unchanged from Task 2's routing. This proves the RAG-injection wiring, not the cache's coverage — one entry is sufficient DoD for this story.
6. Single gap-log mechanism: `agent_tools.log_gap()`'s `gap_kind == "ontology"` branch (`harness/agent_tools.py:217-224`, currently calling `nl_to_sparql._emit_gap_triple()`) is repointed to `_write_capability_gap()` (the existing `capability_gaps.db` SQLite table), with a new `gap_kind` column value (`"ontology"` vs `"capability"`) added to the `capability_gaps` table schema so the two kinds remain distinguishable downstream. `nl_to_sparql._emit_gap_triple()` and the `GAP_INSERT` SPARQL template (`nl_to_sparql.py:87-97, 131-144`) are deleted. Before deletion: confirmed via `grep -rn "urn:mak:gaps\|mom:OntologyGap" harness/ scripts/ infra/ web/` that no code outside `nl_to_sparql.py` and its own tests reads that graph — no downstream reader to migrate. (Grep already run 2026-07-02 during the pre-story engineering review — zero hits outside the writer and `test_nl_to_sparql.py`; re-run as part of Task 1 to catch any drift before deleting.)
7. `harness/tests/test_router.py` is updated: the `nl_discovery` regression-guard assertion (added in 6.10, asserting `nl_to_sparql.dispatch` is called unchanged) is replaced with an assertion that `nl_discovery`-classified messages call `agent.run(fuzzy=False)`, same as `query`. A new test asserts a FAQ-cache-hit message calls `agent.run(..., faq_hint=<matched entry>)` — the model call still happens, only the hint payload differs from a cache miss (which calls `agent.run()` with no hint).
8. `harness/tests/test_agent.py` gains, matching AC #4's two named triggers exactly:
   - Trigger A: mocked `query_sparql` tool call returns `{"error": ...}` → next LLM call in the same run uses `model=llm_client.SONNET_MODEL`.
   - Trigger B, positive: mocked `query_sparql` returns zero bindings, `message.text` contains `"how many"` → escalates.
   - Trigger B, negative (regression guard): mocked `query_sparql` returns zero bindings, `message.text` contains none of `_SPECIFIC_ANSWER_KEYWORDS` (e.g. a generic "tell me about spaces in Ghent") → does NOT escalate, normal empty-result handling proceeds on `llm_client.MODEL`.
   - Escalation ceiling: escalated call also fails (Trigger A or B again) → falls through to `unknown_ack()`/gap-log, no second escalation, no third model attempt.
   - `faq_hint` passthrough: `agent.run(..., faq_hint="...")` results in `complete_with_tools`'s `system` kwarg containing the hint text appended to `SYSTEM_PROMPT`; `agent.run()` with no `faq_hint` (default `""`) results in the bare `SYSTEM_PROMPT`, unchanged from pre-6.11 behavior.
9. `harness/tests/test_nl_to_sparql.py` is updated for the new `generate_and_run(question, model, session_id)` signature (model no longer defaulted/hardcoded inside the module — tests must pass it explicitly); gap-emission tests are moved/renamed to assert against `agent_tools._write_capability_gap` with `gap_kind="ontology"` instead of `_emit_gap_triple`/`urn:mak:gaps`.
10. **Live DoD gate (per [[epic_3_retro_findings]] — pytest passing is not sufficient):** two live checks against the real VPS/Oxigraph, not fixtures, before this story is marked done:
    - Live Matrix round-trip: send "how many spaces are open now in Berlin and which one?" to the deployed bot. Confirm the FAQ-cache hit is logged (hint passed into `agent.run()`, distinguishable in logs from a hint-less run) and the answer matches what the map already correctly shows for Berlin (per the confirmed-correct `addressLocality` check) — or, if `mom:openNow` is genuinely absent for those spaces, confirm the reply explains the liveness-data gap in-character rather than a bare "nothing matches."
    - A second live question that deliberately misses the FAQ cache and exercises the `query_sparql` tool through the full agent loop (e.g. a city with no seeded FAQ entry), confirmed against the live Oxigraph store directly (`curl`/SPARQL, not pytest fixture) to match the tool's returned answer.
    - Both runs' log lines and query text captured in this story's Completion Notes, same evidentiary bar as Story 6.10's live-verification rounds.

## Tasks / Subtasks

- [ ] Task 1: Confirm no downstream readers of `<urn:mak:gaps>` before touching it (AC #6)
  - [ ] Re-run `grep -rn "urn:mak:gaps\|mom:OntologyGap" harness/ scripts/ infra/ web/` — must return only `nl_to_sparql.py` and its own tests
  - [ ] If any other hit appears, stop and flag — do not proceed with deletion until that reader is migrated or confirmed dead
- [ ] Task 2: Router collapse (AC #1)
  - [ ] Remove `nl_discovery` branch's `nl_to_sparql.dispatch()` call in `harness/router.py`
  - [ ] Route `nl_discovery` through `agent.run(..., fuzzy=False)`, same call shape as the existing `query` branch
  - [ ] Remove now-unused `import nl_to_sparql` from `router.py` if `dispatch()` was its only use
- [ ] Task 3: Fold `nl_to_sparql` into the tool catalog (AC #2, #3)
  - [ ] Refactor `nl_to_sparql.dispatch()` into `nl_to_sparql.generate_and_run(question, model, session_id)` — same internals (ontology cache, `FORBIDDEN` check, `_strip_fence`, `_escape_sparql_literal`), returns a dict (bindings + sparql text + count), not a pre-formatted Bernard string
  - [ ] Remove hardcoded model from `nl_to_sparql.py:166`; caller supplies `model`
  - [ ] Add `agent_tools.query_sparql(question: str, model: str) -> dict` wrapping `nl_to_sparql.generate_and_run()`
  - [ ] Add `query_sparql` tool schema to `READ_TOOLS` in `agent_tools.py`, wire into `agent.py::_dispatch_tool`
  - [ ] Add `llm_client.SONNET_MODEL` constant
- [ ] Task 4: Tier-2 escalation inside `agent.py`'s loop (AC #4, #8)
  - [ ] Add `agent.py::_SPECIFIC_ANSWER_KEYWORDS = ("how many", "how much", "which one", "which ", "count")` module constant
  - [ ] Track per-run escalation state (has this run already retried once on `SONNET_MODEL`?) — a local boolean, not a counter
  - [ ] Trigger A: `query_sparql` tool result is `{"error": ...}` → escalate
  - [ ] Trigger B: `query_sparql` tool result has zero bindings AND `message.text.lower()` contains any of `_SPECIFIC_ANSWER_KEYWORDS` → escalate
  - [ ] On trigger (A or B, first occurrence only), retry that iteration's `complete_with_tools` call with `model=llm_client.SONNET_MODEL`
  - [ ] Second Trigger A/B after the escalated retry → existing `unknown_ack()`/gap-log fallback, no further retry
- [ ] Task 5: Tier-0 FAQ cache stub (AC #5, #7)
  - [ ] New `harness/faq_cache.py`: seeded list with one entry (Berlin-open-spaces validated SPARQL template)
  - [ ] `router.py` checks FAQ cache before `intent_classifier.classify()`; hit → `agent.run(..., faq_hint=entry.description + entry.sparql_template)`; miss → `agent.run()` with default `faq_hint=""`
  - [ ] Add `FAQ_HINT_TEMPLATE` string constant to `bernard_agent_prompt.py` (worded as "here's a validated pattern for a similar question, prefer it if it fits" — not an instruction to skip tools)
  - [ ] `agent.py::run()` gains `faq_hint: str = ""` param; when non-empty, `system` arg to `complete_with_tools` becomes `bernard_agent_prompt.SYSTEM_PROMPT + "\n\n" + bernard_agent_prompt.FAQ_HINT_TEMPLATE.format(hint=faq_hint)`; when empty, `system` is the bare `SYSTEM_PROMPT` (byte-identical to pre-6.11) — no other change to loop control flow, tool dispatch, or iteration count
- [ ] Task 6: Single gap-log mechanism (AC #6)
  - [ ] Add `gap_kind` column to `capability_gaps` table (migration-safe `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN` guard for existing DB files)
  - [ ] Repoint `log_gap(gap_kind="ontology")` to `_write_capability_gap(..., gap_kind="ontology")`
  - [ ] Delete `nl_to_sparql._emit_gap_triple`, `GAP_INSERT`, and the now-unused `sparql_client.run_update` call site in that module (confirm no other caller of `run_update` breaks)
- [ ] Task 7: Tests (AC #7, #8, #9)
  - [ ] `test_router.py`: nl_discovery→agent.run(fuzzy=False) assertion; FAQ-cache-hit-bypasses-classify assertion
  - [ ] `test_agent.py`: Tier-2 escalation-on-failure and escalation-does-not-loop-twice cases
  - [ ] `test_nl_to_sparql.py`: updated for `generate_and_run(question, model, session_id)` signature; gap assertions moved to `capability_gaps`/`gap_kind="ontology"`
- [ ] Task 8: Live VPS verification (AC #10) — manual, requires live Matrix/VPS access; run and record before closing this story, not deferred to a follow-up (unlike 6.10's Task 5, this story's entire premise is a live-observed bug — it does not ship without the live repro)
- [ ] Task 9: Scope check — confirm no `networks/*.yaml` manifest work, no persona-pack work, no Oxpecker work was added; confirm `query_commands.find`/`nearby`/`network` and their `!mom find` literal-command caller are untouched (only the NL paths collapse, not the literal-command path)

## Dev Notes

- **Orchestrator decision (roundtable, 2026-07-02):** `agent.py`'s tool-calling loop stays the outer harness, unchanged in shape. `nl_to_sparql.py`'s direct-SPARQL-generation capability is not a competing top-level path — it becomes one tool among others (`read_space`, `query_map`, now `query_sparql`, `log_gap`, `propose_write`) that the loop calls. This resolves the Winston/Nicolas fork: the handoff's three-tier model (`mom_handoff_2026-07-02.md`) described direct-SPARQL-with-cache-and-tiering, which read as closer to `nl_to_sparql.py`'s shape than `agent.py`'s tool-calling shape — but Nicolas confirmed live that the *orchestrator* (routing, escalation, gap logging, Matrix I/O) is `agent.py`, and Tier 0/2 are additions in front of and inside that loop, not a replacement architecture.
- **Why this collapses two disagreeing systems, not three parallel ones:** per the live grep in `router.py:25-40`, `query_commands.dispatch()` is already a dead unwired stub (found during 6.10) with no callers besides the still-present-but-orphaned `query_commands.find`/`nearby`/`network` functions used by `agent_tools.query_map` and the literal `!mom find` command — that path is fine and untouched. The only real fork was `nl_discovery` → `nl_to_sparql.dispatch()` (RDF gap graph, hardcoded Sonnet) vs. everything else → `agent.run()` (SQLite gap tables, Gemma default). This story closes that fork.
- **FAQ cache is intentionally dumb, and it is RAG, not a bypass.** One seeded entry, substring match, no embeddings, no ranking. Nicolas explicitly corrected the initial design here: a cache hit does not skip the model call — it injects the matched template/description as context so Gemma's tool-calling loop still runs and still decides, just with a validated pattern to lean on instead of generating from scratch. The point of this slice is proving that injection wiring (router checks cache before classify, hit or miss both still reach `agent.run()`) exists and works live, not building a good cache or a cache-as-shortcut. Expanding coverage is explicitly deferred to a follow-up story once there's real fuzzy-question volume data (from Story 6.10's `fuzzy_questions` table) to know which questions are worth pre-validating templates for.
- **Tier-2 escalation trigger is narrow by design**, matching the roundtable's "escalate on validation-gate failure or detected complexity," not "escalate whenever unsure." Broadening the trigger conditions is a tuning question for after live data exists, not this story.
- If implementing this story seems to require building out the full `networks/*.yaml` manifest system, persona packs, or Oxpecker integration described elsewhere in the handoff — stop, that's out of scope, flagged explicitly by the operator for a later story.

### Project Structure Notes

- Modified files: `harness/router.py`, `harness/agent.py`, `harness/agent_tools.py`, `harness/nl_to_sparql.py`, `harness/llm_client.py`
- New files: `harness/faq_cache.py`, `harness/tests/test_faq_cache.py` (if FAQ-cache logic warrants its own unit tests beyond the router integration test)
- Untouched: `harness/query_commands.py`, `harness/commands.py` (literal `!mom find` path), `harness/bernard_agent_prompt.py` (no prompt changes required by this story unless Tier-2 escalation needs a prompt-visible signal — check during Task 4; if so, treat as additive per the 6.10 Rule 7/8 precedent, don't rewrite existing rules)

### References

- `_bmad-output/planning-artifacts/mom_handoff_2026-07-02.md` — target three-tier architecture this story's Tier 0/2 slices are drawn from
- [Source: harness/router.py#L13-43] — current `route()` dispatch, all four branches this story touches or leaves alone
- [Source: harness/agent.py#L29-96] — the loop Tier-2 escalation is added inside
- [Source: harness/agent_tools.py#L213-224] — `log_gap`'s ontology/capability split, collapsing to one table
- [Source: harness/nl_to_sparql.py#L87-97,131-144,166] — `GAP_INSERT`/`_emit_gap_triple` (deleted) and the hardcoded model (removed)
- [[project_query_dispatch_was_dead_stub]] — why `query` already routes through `agent.run()`, precedent this story extends to `nl_discovery`
- [[feedback_llm_must_not_claim_untaken_actions]] — Rule 8 precedent from 6.10; keep in mind if Tier-2 escalation ever needs prompt-visible framing
- [[epic_3_retro_findings]] — pytest passing ≠ done; live integration is the real DoD, directly why AC #10 / Task 8 is not deferrable for this story
- [[feedback_integration_testing]] — mock tests hide protocol bugs; live integration required

## Scope Guardrails

- **Collapse-first, tier-later**: this story proves ONE routing engine with a minimal Tier 0 stub and a narrow Tier 2 trigger. It does not build out full semantic-cache infrastructure, does not build a general model-tiering policy engine, and does not expand FAQ coverage beyond the one seeded pair.
- **Out of scope, explicitly deferred per the handoff**: full `networks/*.yaml` manifest system, persona packs, Oxpecker integration. Do not touch these while "in here."
- **`query_commands.py`'s `find`/`nearby`/`network` and the literal `!mom find` command are untouched.** Only the two NL-question paths (`nl_discovery` direct-dispatch vs. `agent.run()`) collapse into one. The map's own materializer/GeoJSON query path (confirmed correct via `addressLocality` on 2026-07-02) is not part of this story at all.
- **No new gap-storage mechanism.** The collapse reuses the existing `capability_gaps` SQLite table (adding one `gap_kind` column), it does not invent a third store.
- This story does not close out the handoff's full target architecture — only the fork Nicolas and Winston raised tonight. Remaining handoff scope (cache expansion, tiering policy generalization, curated-FAQ authoring workflow) gets its own follow-up story once this slice has run live.

## Dev Agent Record

### Agent Model Used

_To be filled by dev-story execution._

### Debug Log References

_To be filled by dev-story execution._

### Completion Notes List

_To be filled by dev-story execution._

### File List

_To be filled by dev-story execution._

### Change Log

_To be filled by dev-story execution._
