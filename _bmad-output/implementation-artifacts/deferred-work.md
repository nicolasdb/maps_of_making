# Deferred Work

## Deferred from: code review of 13-3-persona-voice-port-bernard-yaml-to-hermes (2026-08-15)

- Manny reference-doc symlink conversion + mom-vocab.md DISTINCT/escaping fixes bundled into 13.3's diff, outside its stated File List scope — confirmed intentional by Nicolas ("manny = intentional fixes"), no further action.
- `hermes-data/active_profile` deleted + gitignored in the same diff — confirmed intentional by Nicolas, no further action.
- Bianca's SOUL.md gained a "Mise en scène" section (didascalie convention), outside AC9's stated "sole functional deltas" for this persona-only story — confirmed intentional (bianca served as the structural template), no further action.
- SOUL.md core token count (714) exceeds AC3's 700 hard ceiling — confirmed intentional by Nicolas: purpose over strict token count, no trim required.

## Deferred from: hetzner-gateway VPS log-hygiene work (2026-07-31)

### `maps-link-handler` logs its own healthcheck at ~473 lines/min

Measured on the VPS: **4735 log lines in a 10-minute sample**, overwhelmingly
`INFO: 127.0.0.1 - "GET /health HTTP/1.1" 200 OK` from the container's own Docker
healthcheck. That is roughly **60 MB/day**, and it had grown the container's json
log to **2.8 GB** — by far the largest single file on a 38 GB disk that was at
79% and has a confirmed OOM history.

Deferred to this repo because the fix belongs here, not in the gateway. Either:

- filter `/health` out of uvicorn's access log (a logging filter on
  `uvicorn.access`, dropping records whose path is `/health`), or
- lengthen `healthcheck.interval` in `infra/`'s compose for `mak-link-handler`.

The first is better — it keeps the healthcheck responsive while removing the noise.

**Already mitigated host-side (2026-07-31), so this is not urgent:** Docker now
caps json-file logs at 10 MB × 3 per container via `/etc/docker/daemon.json`, and
all containers were recreated so the cap is bound. Disk went 79% → 45%. What
remains is a usability cost, not a capacity one: `docker logs maps-link-handler`
is unreadable, and the 30 MB window holds only ~8 hours before real events are
evicted by healthcheck noise — which is exactly when you would want them.

Same pattern, smaller, in `time-tracker-bmad`'s `webhook-custom3` (~14 lines/min).

Full context and evidence:
`hetzner-gateway/backlog/2026-07-31-vps-capacity-and-log-hygiene.md`.

Note for whoever picks this up: `maps-nginx`'s bind-mounted log dir
(`data/logs/nginx/`) is now rotated by a host-side logrotate stanza managed from
`hetzner-gateway/ops/logrotate/nginx-gateway`. If that container is ever renamed,
the `postrotate` there must be updated too.

## Deferred from: code review of story-13-2-bernardo-profile-scaffold-read-parity-mom-data-plane (2026-07-08)

### Commit hygiene: unrelated concerns bundled in one commit

`1878dbf` bundles infra hardening (docker-compose.yml), a large planning re-scope
(epics.md write-auth section), and story docs in a single commit. Real but not
actionable now — pre-existing practice in this repo, not introduced by this diff.

## Deferred from: code review of story-13-1-parametrize-graph-endpoint-shared-oxigraph-skill (2026-07-07)

### scratch profile `.env` bootstrap has no validation

Nothing creates or checks `hermes/hermes-data/profiles/scratch/.env` — a typo (e.g.
`oxigraph:7878` instead of `scratch-oxigraph:7878`) would silently pass and hit the
wrong store, same failure class already hit once with `active_profile`. Deferred:
scratch is a temporary, test-only profile — no bootstrap tooling justified for it.

### Permission-denied `.env` indistinguishable from "missing"

hermes SKILL.md's endpoint-resolution grep can't tell "file unreadable" from "line not
found" — both yield empty output, so the agent reports "GRAPH_ENDPOINT not defined" even
when the real cause is a filesystem permission issue. Pre-existing edge case in the new
resolution logic, low priority — revisit if a profile's `.env` permissions cause a
confusing STOP message in the field.

### No automated test/CI gate for endpoint resolution

By design per Epic 6 retro discipline: live verification is the DoD for this epic, not a
pytest surface. Not actionable as a code fix in this story.

## Deferred from: code review of story-6-11-collapse-nl-answer-paths (2026-07-03)

### Rule 3a's unconfirmed-count nudge relies on the LLM tallying rows itself

`bernard_agent_prompt.py` rule 3a asks Gemma to report "N unregistered listing(s) also
match" when reading `query_sparql`'s per-row `?confirmed` boolean, but the tool result
carries no aggregate count — the model must count unconfirmed rows itself. This story's
own live-debugging history (slug-guessing after Tier-2 escalation, missed `log_gap`
calls) shows this class of task is where the model is least reliable. Not fixed here —
revisit if live data shows the reported counts are wrong; a code-level `COUNT`/tally in
`agent_tools.query_sparql`'s return shape would remove the reliance if it recurs.

### Confirmed rows have no ordering precedence under result truncation

`nl_to_sparql.py`'s worked SPARQL examples bind `?confirmed` per row but never `ORDER BY`
it. No truncation logic exists yet in this diff, so it's not exploitable today — but if a
future change caps `query_sparql` results for display, confirmed matches could be dropped
in favor of unconfirmed ones since nothing prioritizes them. Add `ORDER BY DESC(?confirmed)`
(or equivalent) if/when truncation is introduced.

## Deferred from: `!mom gaps` live testing (2026-07-03)

### `log_gap` is pure LLM self-report — no code-level backstop, real misses confirmed live

While testing the newly-shipped `!mom gaps` read command (empty by design right after
deploy — `/app/tasks` volume was just fixed to persist across redeploys), tried to
generate a gap live and found the logging itself is unreliable, not just the storage.

**Current mechanism:** `log_gap` (`agent_tools.py`) fires ONLY when the model chooses to
call the tool, per `bernard_agent_prompt.py` rules 4 (capability gap) / 5 (ontology gap).
No code in `agent.py` force-logs a gap on any condition — no threshold, no auto-trigger
on an empty/failed tool result. Separate `fuzzy_questions.db` analytics table
(`log_fuzzy_question`) only fires when `router.route()` classifies intent as `"unknown"`
(`router.py:34-35`); `query`/`nl_discovery`-classified messages are explicitly excluded
from it too (`router.py:37-45`).

**Live proof, two real gap-shaped questions, neither logged anywhere:**
- "Bernard: how many spaces in Berlin I could visit this week-end if it rains?" —
  Bernard's own reply said "I cannot factor in weather forecasts" (textbook rule-4
  capability gap) but never called `log_gap`.
- "Bernard: which space in Brussels shared partnership on european project?" — no
  ontology term for "partnership"/"funded" (rule-5 ontology gap); Bernard just said "no
  space matches," indistinguishable from a genuine zero-result query.

Both likely classified as `query`/`nl_discovery` intent (not `unknown`), so neither
`capability_gaps.db` nor `fuzzy_questions.db` recorded them — the roadmap signal
`log_gap` exists to collect is silently lost for exactly the cases that matter.

**Options for a future story (not built, needs a decision, not just an implementation):**
1. Strengthen/re-example rules 4/5 in `bernard_agent_prompt.py` — cheapest, but prompt-only
   compliance already failed once this session (mention-detection bare-name attempt) and
   may fail again the same way.
2. Code backstop in `agent.py`: after the tool loop, if no tool call returned real
   data-bearing results (or `query_sparql` returned `count=0`) and `log_gap` was never
   called, auto-log a gap with a heuristically-guessed `gap_kind`. Deterministic, catches
   every miss, but blunter — can't distinguish "genuinely zero real matches" from "model
   should have flagged this as unsupported" as well as the model itself can.
3. Widen `fuzzy_questions` logging to cover every `agent.run()` call (not just
   `fuzzy=True`), so the "resolved" analytics counter isn't blind to
   `query`/`nl_discovery`-classified misses even before touching `log_gap` itself.
→ New story. `!mom gaps` (just shipped) is the read-side fix; this is the write-side
reliability gap underneath it — worth fixing before relying on gap data as a real
roadmap signal.

## Deferred from: Story 6.11 AC#10 live verification (2026-07-03)

### City search matches literal `addressLocality` string, not metro-area geography

Surfaced while cross-checking Bernard's `query_sparql` answers against live Oxigraph
for "which spaces near Ghent have laser cutters". Bernard correctly answered "no
confirmed spaces, but 1 unconfirmed (Timelab) matches" — but the map's own Find UI
search box for "ghent" also only returns 2 spaces (Zeus WPI, Timelab), while the map
visibly shows many more dots clustered right around Ghent. **Ingegno Maker Space**
(laser-tagged, real coords 51.0503,3.6572 — ~5km from Ghent center, `geolocationFidelity:
"high"`) is invisible to both searches.

**Root cause, live-verified via direct Oxigraph query on Ingegno's graph
(`urn:mak:space/ingegno-maker-space-drongen`):** `schema:addressLocality "Drongen"`.
Drongen is a real deelgemeente (merged sub-municipality) of Ghent since a 1977
municipal merger — administratively part of Ghent, but keeps its own official postal
locality name (postcode 9031). **The data is correct, not corrupted.**

Both the web Find UI (`web/app.js` `filteredSpaces()`, `hay.includes(q)` against
`s.city`) and Bernard's generated SPARQL (`CONTAINS(LCASE(STR(?city)), LCASE("ghent"))`,
from `nl_to_sparql.py`'s worked examples) do a plain substring match on the literal
locality string — neither has any concept of metro-area/administrative hierarchy or a
geo-radius fallback. Any big city with annexed districts carrying distinct locality
names hits this: Brussels (Ixelles, Schaerbeek, Anderlecht, Uccle…), Cologne, Paris
(arrondissements/suburb communes). `!mom nearby`/`!mom travel` already use real
geo-radius (bbox/ORS) and do NOT have this problem — only `find`/`network`-shaped city
filters and the web Find text box are affected.

**Scope for a future story:**
- Replace/augment substring city match with geocoded-radius matching (reuse the
  geocoding already built for `!mom nearby`/`travel`) in both `web/app.js`'s filter
  and `nl_to_sparql.py`'s SPARQL generation guidance.
- Needs a city→lat/lon resolution step before filtering — either live-geocode the
  search term (cost/latency) or maintain a small locality-alias table (Drongen→Ghent,
  Ixelles→Brussels, etc.) as a stopgap.
- Audit how many spaces across the dataset have a distinct-from-parent-city locality
  within known metro areas before choosing alias-table vs. live-geocode.
- Related but distinct from the older VOW/fabtafle profile-URL-as-endpoint deferral
  below — that's about a wrong field value (profile page mistaken for a fetchable
  endpoint); this is about a correct field value being too fine-grained for a
  city-name substring search. Don't conflate the two fixes.
→ New story, not folded into 6.11 (which already closed AC#10 with the endpointUrl-
confirmed-vs-seeded distinction verified correct against live data).

## Deferred from: @bernard write-path testing (2026-06-24)

### ORPHANED: NL→write slot-filling (the `write` intent has no handler)

**Status:** untracked gap, surfaced during 6.4 live testing. Needs a story (to be created from a clean session). Logically sequences **before Story 6.5** — 6.5 is the graceful-failure/voice pass over *functional* paths, and this path is not yet functional, so 6.5 would have nothing to polish here.

**Symptom (observed live on VPS, 2026-06-24):**
- `@bernard close` → ✅ committed `529e5dce` (literal verb → `commands.try_handle` → `_handle_open_close`)
- `@bernard set openfab as closed now` → ❌ `unknown_ack`
- `@bernard I want you to update the JSON file of the current space to close` → ❌ `unknown_ack`

**Root cause:** the write *mechanism* is complete and power-gated (Stories 6.1/6.2 → deploy-key → git commit → heartbeat re-ingest; permission gate `_can_write` at `harness/commands.py:49`), but it is **only reachable via literal `!mom <verb>` commands**. NL-phrased writes fall through `commands.try_handle` → `router.route()`, where the intent classifier *correctly* returns `write` — but `harness/router.py` has `# write: not implemented yet` → `bernard.unknown_ack()`. So the `write` branch is a stub.

**This contradicts the original Epic 6 vision**, which explicitly promised NL writes via slot-filling:
- `epics.md:1683` — *"A coordinator typing 'update our Tuesday hours to 10–18' … reach[es] the same Bernard — a different skill fires."*
- `epics.md:1693` — *"Gemma … for slot-filling + formatting."*
- `epics.md:1714` — classifier returns `write|query|nl_discovery|unknown` (the classifier half shipped; the slot-filling half never did).

**Scope of the missing piece (smaller than 6.4 — machinery + gate already exist):**
A `write` intent handler that:
1. Slot-fills `(field_path, value)` from the NL message using Gemma (constrained to `ALLOWED_FIELDS`: `state.open`, `contact.irc/matrix/twitter`, `mom.memberOf`).
2. Calls the existing `_handle_update` / `_handle_open_close` with the **sender's Matrix power level** — so the permission gate (`_can_write`, ≥100) is unchanged and simply becomes reachable via NL.
3. Confirms intent before committing (writes are irreversible-ish via git history; a slot-fill misread should not silently commit). Bernard voice: echo back the parsed `(field → value)` for confirmation, or commit-then-report with the SHA + revert path.
4. Graceful failure when slot-filling is ambiguous (→ folds into 6.5 voice pass once functional).

**Note:** write skillset is **Matrix-only** for the PoC (room power-level model has no Discord/Telegram equivalent — `epics.md:1845`). Keep the NL→write handler behind the same Matrix-only guard.

---

## Deferred from: party-mode roundtable on Epic 6 bot UX + IoP/OKW (2026-06-19)

### RESOLVED + REFRAMED: "IoP" = Internet of Production Alliance → OKW interop opportunity

The earlier "IoP naming ambiguity (Internet of Places vs Internet of Production)" is **resolved and superseded.** "IoP" = the **Internet of Production Alliance** (internetofproduction.org) — a network contact who **supports MoM and would replace their stale Open Know-Where (OKW) map with it**, because their map suffers the exact staleness phenomenon MoM's heartbeat/freshness model solves. This is the strongest external validation the project has had.

The IoP Alliance maintains a family of open standards:
- **OKW (Open Know-Where)** — open data model + mapping standard for facility/makerspace/fab-lab **location, capacity, capabilities**. THE established standard for MoM's exact domain. Spec: https://standards.internetofproduction.org/pub/okw/release/2 (rel. 2, launched Apr 2021). Five linked classes (Facility anchor); fields: GPS coords, postal address, contact, machines-per-facility with a controlled classification tag list (CNC/Router/Power tool/Drill/Saw…), materials worked. Delivery formats: CSV / SQLite / JSON.
- **OKH (Open Know-How)** — hardware design + manufacturing-instruction metadata ("HOW to fabricate"). The sleeper value: OKW (where) + OKH (how) → Bernard answers "which live, verified makerspace near X can build this design?"
- **IoP Ontology** — semantic manufacturing framework (machines, parts, materials, workflows).

**Agreed architectural model — the "crosswalk cartridge":** mom: stays the canonical, audience-neutral core (freshness/heartbeat is the universal value). Each customer/community slots in a **swappable per-audience ontology overlay** — OKW for the IoP Alliance, **OSLO** for Flemish education, and whatever the next community brings. Implemented as Winston's three layers, sequenced:
1. **Crosswalk file (no code, first step):** `ontology/crosswalks/mom-to-okw.ttl` — static RDF (`skos:closeMatch`/`relatedMatch`, OKW version pinned in a header comment). Zero runtime dependency, fully reversible. This is the "compliance receipt."
2. **`ext_okw` vertical (when real OKW-native data exists):** store OKW-native fields as-is under `ext_okw:`; don't coerce mom fields into OKW shape. Additive — spaces without OKW data unaffected.
3. **Export endpoint (the thing IoP actually wants):** `infra/link_handler/routers/export_okw.py` — SPARQL-queries Oxigraph, serializes to OKW JSON via **explicit Python mapping, no reasoner**. MVP proof-of-partnership = one GET → one MoM space as valid OKW JSON.
- **OKW ingestion = separate parallel importer** (`scripts/import_okw.py`, mirrors `seed_csv.py`), NOT the heartbeat (heartbeat's contract is SpaceAPI endpoints). Write to a separate graph (`urn:mak:okw/...`); space-identity reconciliation is the hardest part — defer it.

**Coupling traps to avoid:** don't import OKW namespace at the core layer; don't make OKW fields required in ingest; don't run query-time inference; pin OKW version in the crosswalk so a v2 bump forks the file, not the schema. MoM stays OKW-*interoperable*, not OKW-*native* — it serves SpaceAPI sources that will never speak OKW.

**Two questions to resolve WITH the Alliance before building (Mary + John):**
1. *Why* did their OKW map stale — a heartbeat problem (MoM solves) or a contributor-adoption problem (MoM does NOT)? Diagnose before committing, or inherit their failure conditions.
2. Does "compliance" obligate MoM to follow OKW spec changes forever? Who owns MoM's schema when OKW v2 drops? Position as "an OKW-compliant implementation," NOT "the official OKW reference implementation" (compliance ≠ stewardship).

**Consequence already applied to Story 6.4:** `iop.ttl` scoped down to minimal spatial-only vocabulary; `iop:Equipment` left as a bare stub (capability semantics belong in the OKW crosswalk, not minted under `iop:`); `iop.ttl` NOT published to the ontology repo yet. OKH + IoP-Ontology integration explicitly deferred — separate from bounded OKW compliance.

→ Seeded as an epic stub in epics.md ("OKW / multi-ontology crosswalk interoperability"). This is a **partnership feature track**, distinct from core user work.

### Bernard thread-reply bug → patch on Story 6.3 (do before 6.4 ships)

`harness/matrix_adapter.py` `send()` always sets `m.relates_to.event_id = msg.event_id`. Correct for a root-message trigger; **broken when the trigger is itself already inside a thread** — it points the thread root at a non-root event_id, which Matrix clients reject/mishandle silently. Low impact for one-shot `!mom`, but every multi-turn `@bernard` NL conversation (6.4) hits it. Fix (Amelia, citable):
- `harness/message.py`: add `thread_root_id: str | None = None` to `Message`.
- `harness/matrix_adapter.py` `_on_message`: read incoming `content["m.relates_to"]`; if `rel_type == "m.thread"`, `thread_root_id = relates["event_id"]` (per Matrix spec this IS the thread root — no recursion), else `None`.
- `send()`: `root = msg.thread_root_id or msg.event_id` → thread the reply to `root`.
- ACs: root-message flow unchanged (None → today's behavior); unit test asserts a follow-up-in-thread emits the root id, not the follow-up's id.

### @bernard rate-limit → guard before any public/federated rollout

Every `@bernard` mention triggers a billed Sonnet completion (6.4). No rate-limit = unbounded spend in a busy/federated room. Minimum guard: per-user cooldown (new `harness/rate_limiter.py`) or room-level token budget. Pairs with the still-open Story 6.0 deferral "no allowlist/access control on `!mom` commands." Not 6.4 scope; required before public exposure.

### Bernard prompt + guardrail quality → its own story (post-6.4)

`nl_to_sparql.py` is the NL→SPARQL translation layer (closest thing to an agentic "skill") but is a pure translation function, not a guardrail-tuning surface. Refining Bernard's system prompt, injection guardrails, and voice consistency is a distinct prompt-engineering/safety story — different AC shape and risk surface than 6.4's wiring. **Don't write it until 6.4 ships and produces 2–3 real bad answers to fix** (John: triggered by observed failure, not anticipation).

### Multi-platform `Message` contract hardening → seed with the multi-platform adapter epic

Before a second adapter (Discord/Telegram) exists, harden the boundary so platform-specific identity (MXID format, room vs guild/channel) never leaks past the adapter. Add to `Message` now: sender display name, room/channel ID, a platform enum. Verify `router.py`/`commands.py` have **zero imports from `matrix_adapter.py`** (precondition for the mini-API to import `harness/` core without pulling Matrix deps). Permission model is the trap: `read_only_ack` is gated on MXID parsing — Discord/Telegram have different identity shapes, so a naive port could bypass the read-only gate. → epic stub in epics.md.

## Deferred from: Story 6.3 operator testing (2026-06-18)

- **"One space just outside the range" teaser** — After a travel search, surface the nearest confirmed space that falls *just outside* the isochrone polygon (shapely `poly.exterior.distance(Point)` for each non-member space). Bernard copy: "There's a space Xmin past your limit — worth the detour?" High UX value, medium effort. → future Epic 6 story.

- **Pre-warm isochrone cache per claimed space at heartbeat** — At heartbeat time, for each claimed space, pre-compute the `[0.30, 1.0]` driving-car polygons and populate the in-memory cache. First user to ask `!mom travel <city>` near a registered space gets instant results. This is the "tier reward" angle: the map is richer for spaces that have registered. → future Epic 6 story, post-traction.

- **Regional discovery lens (above-2h travel)** — `!mom travel Marseille 15h by train` → not a polygon search, but a city-list answer: "Within 15h of Marseille by train: Paris (12 spaces), Lyon (4 spaces), …". Requires a different query shape (cluster by city/region, not point-in-polygon). Logged today as `isochrone.above_bucket_range` signal to measure actual demand before designing. → new story, Epic 6 or later.

- **`!mom network fabtafel` returned no response during testing** — Command was sent but no Bernard reply observed in the export. No error in logs either — likely the space graph exists but `mom:memberOf` predicate is absent for fabtafel spaces in Oxigraph. Investigate data vs query mismatch. → check data quality before marking network command fully done.

## Deferred from: deploy-homeserver-bot-nginx (2026-06-18)

- Bernard cannot operate in E2E-encrypted Matrix rooms — messages arrive as `MegolmEvent` and are silently dropped. Rooms must be created without encryption for now. Fix requires `AsyncClientConfig(encryption_enabled=True)` + a persistent key store (SQLite) + TOFU device verification in matrix-nio. Candidate for Epic 6.5 or a standalone infra story before the public demo.

## Deferred from: code review of story-6.1 (2026-06-16)

## Deferred from: code review of story-6.2 (2026-06-17)

- `COORDINATOR_ONLY_FIELDS` not defined as explicit guard — spec names `frozenset({"space.name", "url"})` as a separation sentinel; safe today since those fields aren't in `ALLOWED_FIELDS`, but no code prevents future accidental promotion. Add guard when `ALLOWED_FIELDS` is next modified.

- `StrictHostKeyChecking=no` / no `IdentitiesOnly=yes` on `git_ops.py`'s SSH calls — specified verbatim in Story 6.1's own Dev Notes crypto snippet; weakens host-key verification for the bot's git operations (MITM risk), revisit if/when a known_hosts pinning strategy is adopted.
- `!mom update` failure messages collapse `NoEndpointError`/`UnsupportedHostError`/schema-validation/git-SSH failures into one generic `update_failed_ack()` — hides the real cause already present in logs. Self-acknowledged in story Completion Notes; candidate for Epic 6.5 (graceful failure / Bernard voice pass) or 6.2.
- GitHub raw-URL regex in `_repo_remote_for` handles `refs/heads/{branch}/{path}` but not `refs/tags/{tag}/{path}` — consistent with the story's documented "GitHub/Gitea best-effort, untested" scope; will need a regex case if/when a tag-based raw URL is registered.
- `SpaceAPISchema`'s `extra="allow"` (infra/link_handler/schema.py) makes `git_ops.patch_json`'s schema-validation guard weaker than AC4 implies — most unknown field paths pass validation regardless of value. Pre-existing schema design, not introduced by Story 6.1; tighten if/when Story 6.2's field whitelist lands.
- Blocking sync crypto/disk I/O (`bot_keys.generate_and_store`, `load_private_key`) called directly from async endpoint/command handlers with no `asyncio.to_thread` — minor event-loop-blocking smell under concurrent room load, not yet a measured problem.
- Unhandled `cryptography.fernet.InvalidToken` / missing `BOT_KEY_SECRET` env var collapses into the same generic "update failed" ack as any other failure — same root cause as the failure-messaging item above; a misconfigured secret currently looks identical to a network blip from the room's perspective.

## FIXED: orphaned test imports from materialize_geojson.py deletion (2026-06-16)

**Status: resolved — quick fix done during Story 6.0 dev-story session, not a new deferred item.**

`scripts/materialize_geojson.py` was deleted 2026-06-03 (commit `6ddf9db`, honest-inventory
triage) as a hand-synced duplicate of the live `_rematerialize_geojson` in
`infra/link_handler/main.py`. Two test files were never repointed at the time, so they had
been silently failing at collection ever since (`ModuleNotFoundError`, `fixture 'live_stack'
not found`) — these failures pre-dated and were unrelated to Story 6.0, surfaced only while
running the full regression suite for that story.

**Fix applied:**
- `tests/test_canary_three_axis_e2e.py` and `tests/test_materializer_three_tokens.py` —
  added a `_materialize_feature()` / `_materialize_spaces()` helper that drives the live async
  `_rematerialize_geojson()` directly (monkeypatches `OXIGRAPH_ENDPOINT`/`GEOJSON_OUTPUT`,
  runs via a preserved event loop — `asyncio.run()` was tried first but closes the loop and
  broke a sibling test using the deprecated `get_event_loop()` pattern; switched to
  `get_event_loop()`/`run_until_complete()` instead).
- `tests/test_materializer_three_tokens.py` — implemented the `live_stack` fixture, which
  never existed anywhere in the repo (these tests had *always* errored at collection, even
  before the script deletion — confirmed via full git history search).
- `test_three_tokens_missing_exits_nonzero` — explicitly `@pytest.mark.skip`'d. It asserts a
  `sys.exit(1)` CLI contract that only ever belonged to the deleted standalone script; the
  live async path is deliberately fail-silent per Story 3.9 Dev Notes ("fail-silent for async
  heartbeat, fail-loud for batch script"). No replacement CLI exists to assert against.

**Net result:** all collection-time crashes eliminated (`9 failed, 85 passed, 3 errors` →
`8 failed, 88 passed, 1 skipped`). **Not fixed, left as pre-existing/out-of-scope** (now
visible for the first time since collection used to fail before these could even run):
- `test_axis_b_ages_independently_when_content_unchanged`,
  `test_axis_c_flips_independently_on_open_now_change` — the live materializer iterates the
  full ~600-space Oxigraph dataset, too slow for these tests' sub-2-second timing thresholds.
- `test_three_tokens_all_present`, `test_observed_at_from_sqlite_not_oxigraph` — Oxigraph
  canonicalizes `xsd:dateTime` literals (precision/timezone notation) on storage, breaking
  these tests' string-equality assertions against the value as originally written.

If picked up again: the timing tests need either a scoped/filtered materialization path or a
relaxed threshold; the dateTime tests need comparison via parsed datetime equality, not string
equality. → revisit opportunistically, not blocking.

## PARKED (needs fresh eyes): Axis-B-as-tombstone contradiction (2026-06-11, updated 2026-06-15)

**Status: acute symptom resolved — structural design question still open. Do NOT change precedence or death-word semantics until model is settled.**

**What was fixed (2026-06-15):** The immediate "reachable but dead" symptom is gone. Root cause was `mom:updatedAt` never being seeded for SpaceAPI-directory spaces: null `updated_at` → Axis B → `dead` regardless of reachability. Fix: pipeline now stamps `mom:updatedAt = observed_at` on first heartbeat for any claimed space missing the predicate (`_updated_at_absent` backfill in `pipeline.py`). Anchor is `observed_at` (when WE first reached the space), not `last_modified` (when the server last touched the file — stale for static JSON). After `make rebuild && make seed-spaceapi && make heartbeat`, 0 false-dead / zombie / aging spaces remain at current demo scale.

**What was tried and reverted:** `state.lastchange` (SpaceAPI `last_open_change` field) was briefly used as a second input to `_lastActivity(s)` to cover spaces with null `updated_at`. Reverted: spaces self-report this timestamp unreliably (values from 2013–2019 common), producing false aging/zombie/dead on ~16 spaces with fresh `observed_at`. The backfill from `observed_at` makes this bypass unnecessary.

**What is still structurally unresolved:**
- Axis B is a **"content changed?" clock** (`updated_at` = content-change only), yet it emits `dead`/`zombie` (death words) and sits at the **loudest** precedence (`B → A → C`).
- Long-lived static spaces will accumulate age past thresholds (180 d dead, 90 d zombie) and show 🪦 — even if reachable and answering — once their backfill-seeded `updated_at` ages out. This is deferred until first real coordinator dispute ("why is my space stale?").
- Nicolas's caution stands: **reachability ≠ alive** (a static JSON answers forever). The agreed direction: "stop *asserting* alive/dead from untrustworthy stamps; only report facts we hold."

Two candidate resolutions (pick when fresh):
- **(a)** Keep Axis B's names but move it to the **bottom** of precedence (A and C win; B only shows when otherwise idle); null → neutral, not `dead`.
- **(b)** Axis B stops emitting death words entirely — floor = `aging`; `dead`/`zombie` move to **Axis A** (reachability), the only signal we actually gather ourselves.

Settle the doc (`docs/architecture/03-freshness-axes.md`) FIRST, then bring `computeAxisB` + `computeMarker` (`app.js:561, 590`) to match. Mother Sands HTTP-date side-issue is resolved (✅ `_to_iso_datetime` in pipeline.py, image rebuilt).

## Deferred: overlapping/stale directory sources — VOW & fabtafle profile-URLs as endpoints (2026-06-11)

Surfaced while fixing "updated unknown". A space is treated as **claimed** when `mom:endpointUrl` is present, but the VOW/fabtafle scrapers write the **directory profile page** (e.g. `https://offene-werkstaetten.org/werkstatt/...`) into that field. Result: 641 spaces (566 `scraped-vow` + 75 `scraped-fabtafle`) look claimed but are never fetchable SpaceAPI endpoints — only **1 of 566** VOW URLs is a real endpoint. They render `seeded` (grey) with "updated unknown" — honest, but they shouldn't occupy the claimed bucket.

This is the **core MoM problem**, not a quick fix: directory sources (VOW, fabtafle, SpaceAPI directory) are independently stale and overlap irregularly — many VOW entries ARE on SpaceAPI (those get a real `endpointUrl` + a `profileUrl`, e.g. Eigenbaukombinat), many are not, and not all SpaceAPI spaces are in VOW. Needs a deliberate story on:
- distinguishing a fetchable SpaceAPI `endpointUrl` from a human-readable directory `profileUrl` at seed time (don't let a profile URL claim a space);
- deduplicating/merging the same physical space appearing across sources;
- a provenance/trust model for which source's facts win when they disagree.
→ New story (Epic 4 or a dedicated "source reconciliation" epic). Do NOT fold into the freshness work.


## Deferred from: code review of 5-0-gl-rendering-substrate-world-view (2026-06-07)

- **Percentile bbox collapses with 2 spaces** — `pct(arr, 0.05)` and `pct(arr, 0.95)` both return index 0 when length=2; bounds collapse to a point, MapLibre snaps to maxZoom:7 silently. Not triggered at 111 spaces. Fix when space count drops near 2.
- **Beacon rAF runs every frame when pulse=off** — `startBeacon` tick calls `setPaintProperty` on every frame even when pulse is disabled; no RAF cancel path. Minor CPU overhead. Optimize if it becomes measurable.
- **`_beaconRAF` never cancelled** — module-level, no stop path. Would leak if `initMap()` were ever called twice. Add a `stopBeacon()` if re-init becomes a requirement.
- **`ingestGeoJSON` crashes on null geometry** — `f.geometry.coordinates[...]` throws if `f.geometry` is null (valid RFC 7946). Add a null-geometry guard before the map call.
- **TOCTOU in `applyUrlParams()`** — `map.once('load', ...)` callback never fires if the `load` event already fired before `applyUrlParams()` runs. Consider using `map.loaded()` check + immediate call pattern.

## Deferred from: Story 3.11 — bundle-choice config file (2026-05-22)

- **Schema-bundle selection config** — a config mechanism to declare which schema
  layers a space's payload is processed against (`core`, `core+mom`, `core+mom+fab`, …).
  Deferred because it has nothing to drive yet: the extractor pipeline runs
  `extract_core` + `extract_mom` unconditionally and `extract_fab` does not exist.
  A bundle config now would be inert — the same status as the `ext_fab` data added
  to `data/canary/baseline.json` in this story.
  **Natural design when it lands (pair with `extract_fab`):** two-part —
  (1) the space declares *what it is* in its own SpaceAPI document
  (`ext_mom.bundle: ["core","mom","fab"]`); (2) `infra/link_handler/config.yaml`
  gains a `bundles:` block mapping *bundle name → extractor layers* (how to process
  each). Identity stays with the space, processing rules stay in config. The
  extractor dispatch in `pipeline.py` / `load_canary.py` / `seed_spaceapi.py` then
  composes layers per the declared bundle instead of hardcoding core+mom.
  → Epic 9 (fab.ttl extraction + `extract_fab`)

## Deferred from: code review of 3-8b-corrected-token-model (2026-05-19)

- **`content_changed=True` default on `_fetch_last_snapshot` exception** — every 200 response after Oxigraph query failure advances `mom:updatedAt` silently; pre-existing default behavior [transformer.py:741-747]
- **Canary SPARQL prefix mismatch in `_fetch_last_snapshot`** — filter `urn:mak:space/` never matches canary graphs (`urn:mak:canary/`); canary always `content_changed=True`; pre-existing [transformer.py]
- **Error path `consecutive_failures` not persisted to SQLite** — `classify_endpoint_health` called with `+1` but value never written back; health never advances through degradation levels; pre-existing [transformer.py:681-698]
- **Legacy fallback `_build_sparql_update` still writes `mom:operationalState` + `mom:lastFetched`** — violates three-token contract when `transform_to_sparql` raises an exception; pre-existing path [main.py:787]
- **304 path `last_open_now` goes stale during 304 streaks** — `effective_marker` can report `open` indefinitely after space closes; pre-existing [transformer.py:667]

## Deferred from: Story 3.8 operator verification (2026-05-19)

- **Registration flow does not call clean canary pipeline after rematerialization** —
  `_rematerialize_geojson()` is called at line 853 of `main.py` after a space registers.
  This overwrites `spaces.geojson` with the fat SPARQL shape (29 properties, `observed_at: None`)
  for all spaces including Mother Sands. `_run_clean_canary_pipeline()` is only called from
  `_heartbeat_job()`, so the canary feature stays fat until the next 10-min heartbeat corrects it.
  **Story 3.9 must resolve this** by making `_rematerialize_geojson()` itself produce the clean
  shape (with `mom:observedAt` read from Oxigraph for all spaces) — at which point the canary
  pipeline patch step becomes redundant and can be merged or dropped.
  Relevant locations: `main.py:50-54` (`_heartbeat_job` sequence), `main.py:853` (registration
  call site), `main.py:166-186` (`_SPARQL_SELECT` UNION block for `urn:mak:canary` — currently
  queries `mom:lastFetched`/`mom:lastUpdated` which are empty after Story 3.8; needs
  `mom:observedAt` added). → Story 3.9

## Deferred from: Epic 3 retro party-mode roundtable (2026-05-18)

- **`spaces.geojson` payload-slimming** — `web/data/spaces.geojson` currently force-feeds every
  space's *full* data (all card fields) into browser memory. The map marker only needs a small
  "render set": stable `UID`, `geolocation`, `observed_at` (lifecycle colour), and whatever the
  filters key on. Card-detail fields could be fetched on demand instead of held in memory for
  every space. Optimization: trim per-feature `properties` to the render set; serve card data
  via a `GET /space/{uid}` read API in `mak-link-handler` reading from SQLite (NOT browsers
  running SPARQL — that puts Oxigraph on the request hot path). **Constraint:** `observed_at`
  MUST stay in the render set — it is lifecycle-critical and the marker can never fetch it
  lazily. This is a performance/architecture change, explicitly NOT a freshness fix — kept out
  of Epic 3.5 scope. → Epic 5+ (revisit when the GeoJSON is too big to ship whole, or card data
  genuinely needs second-fresh accuracy).

## Deferred from: code review of 3-5-core-ttl-crosswalk-csv (2026-05-18)

- `core:Place rdfs:subClassOf mom:Space` cross-layer dependency — both layers always load together per ADR-016; revisit at Epic 9 fab.ttl extraction (`ontology/core.ttl`)
- No check that `core_field` IRI values actually exist in ontology files — typos pass `validate_crosswalk.py` silently; add an ontology-load check in a future validator pass (`scripts/validate_crosswalk.py`)
- `owl:versionInfo "0.1"` with no `dcterms:created`/`dcterms:modified` in `core.ttl` — pre-existing pattern in `mom.ttl`; add provenance metadata when ontology is promoted to canonical repo
- UTF-8 BOM not handled by `validate_crosswalk.py` — low risk for this git-tracked project; add `encoding="utf-8-sig"` if CSV editing outside of git-native tools is ever needed

## Deferred from: Story 3.2 lore session (2026-05-06) — Mother Sands / Unit M canary space

### Concept
A live canary makerspace used as operational proof-of-life for the full MOM backend. Appears on the public map as a real space — because it *is* real in all the ways that matter to the system. Two registers:

- **Mother Sands** — public display name. The mythical eighth Maunsell sea fort that was never built. Pinned to a historically plausible gap in the Thames estuary arc between the Army group (Red Sands / Shivering Sands / Nore) and the Navy group further east.
- **Unit M** — operator callsign used in heartbeat logs, admin dashboard, and sprint docs. The "secret eighth fort" framing. Also the identity used for lifecycle-relocation: on each death/rebirth cycle, Unit M migrates to the next fort in the U2–U7 rotation (U1 / Roughs Tower is excluded — that's Sealand's platform; not our property to claim).

### Lore
The Maunsell sea forts (1942–1945) were the first line of defence for the Thames estuary — anti-aircraft and naval gun platforms in international waters. In the 1960s they became pirate radio stations (Radio Caroline, Radio City, Radio Sutch): unauthorized signals of truth broadcast outside any official channel's permission. Mother Sands inherits both lineages. MOM's mission — an unofficial signal about what makerspaces *actually* are, outside any network's approved narrative — maps cleanly onto the pirate-radio metaphor. The "ask Mom" oracle feature extends it further: the fort is the thing you radio when you need an honest answer.

The space's declared specialties: AI systems, linked open data, geography/cartography, offshore engineering, pirate-radio history. Spirit: anarchist-creative, open-source, international-waters freedom-of-information. Vibe: second-hand offshore platform, solar-powered, satellite uplink, dry-erase ontology diagrams on the bulkhead walls.

### Technical implementation (deferred to Epic 4 / canary story)
- `mom.mapsofmaking.org` is the **space's website** (MOM wiki/explainer, human-readable). The **SpaceAPI JSON endpoint** is a distinct file path on the same host: `https://mom.mapsofmaking.org/mom_v15status.json` (or `/spaceapi.json`). `schema:url` points to the root; the heartbeat polls the file path. These must not be conflated.
- `mom:simulatedAge` annotation on the space record: `classify_lifecycle` respects this override when present, allowing Phase 2 lifecycle-cycle demo without waiting 30–180 real days. `classify_lifecycle` already accepts a `days_since_last_update` parameter — add a seam to read override from the space's named graph if present.
- **Phase 1 (endpoint health cycle):** Script flips `state.open` true→false→true on a 15-min cycle; then drops the endpoint (HTTP 503) to exercise `broken` health. Fully live, no fakery.
- **Phase 2 (lifecycle cycle):** Script sets `mom:simulatedAge` to 0 → 95 → 200 → 0 on the same 15-min cadence, walking the map marker through confirmed → aging → zombie → dead → confirmed. Visible on the public map as real state changes.
- **Relocation on death:** On each `dead` → `confirmed` rebirth, the script updates `schema:geo` coordinates to the next fort in the U2–U7 array:
  - U2 Sunk Head: 51.7347° N, 1.2369° E
  - U3 Tongue Sands: 51.4964° N, 1.2344° E
  - U4 Knock John: 51.5039° N, 0.9928° E
  - U5 Nore: 51.4431° N, 0.7441° E
  - U6 Red Sands: 51.4656° N, 0.9725° E
  - U7 Shivering Sands: 51.5261° N, 1.0814° E
  - (Mother Sands fixed home: approx. 51.60° N, 1.15° E — the gap in the arc)
- The `mom.mapsofmaking.org` subdomain can host the MOM explainer wiki alongside the SpaceAPI JSON endpoint. The space's website field points there; the wiki explains what MOM is and why the canary exists. → Coordinate with nginx/subdomain setup in Epic 4.

### Dependencies
- `mom:simulatedAge` seam in `classify_lifecycle` (1-line change)
- `mom.mapsofmaking.org` subdomain configured in hetzner-gateway nginx (reuse existing pattern from `admin.mapsofmaking.com`)
- A small Python script (or GitHub Action) running the cycle: reads current state from the SpaceAPI JSON, increments index, writes next state, commits



## Deferred from: code review of 3-1-heartbeat-scheduler (2026-05-05)

- **Circular import (transformer ← main)** — `process_one_space` uses `from main import SpaceAPISchema, classify_subset, _build_sparql_update` at call time. Works at runtime; breaks test isolation. Extract shared types to `schemas.py` in a future refactor story.
- **Concurrent scheduler + manual trigger race** — Both code paths write to Oxigraph and rematerialize GeoJSON independently with no asyncio lock. Safe at 6 spaces / 10min; add mutex in Epic 4 ops story.
- **Mobile suppression of refresh button** — Not confirmed in diff; likely inherited from Zone 3 CSS (Story 3.0-A). Verify in CSS audit during Epic 5 polish.
- **APScheduler startup failure has no `/health` signal** — Spec requires catch+log (not fail-fast). Add scheduler health status to `/health` in Epic 4 observability.
- **SVG innerHTML duplicated 3× in click handler** — Extract to `_REFRESH_SVG` const in future UI pass.
- **New `httpx.AsyncClient` per space per heartbeat cycle** — Harmless at 6 spaces; pass shared client when scaling to larger fleet.
- ~~**`_rematerialize_geojson` called unconditionally even on "not_modified"** — Skip rematerialize when outcome is `"not_modified"` in manual endpoint; minor I/O waste.~~ → **resolved 2026-05-06 in Story 3.2 AC6**
- **Cooldown UX refinement (pilot)** — Current: 60s cooldown starts on any non-rate-limited attempt, including 404 (no endpoint). Pilot improvement: only engage cooldown after a successful or not-modified fetch; 404 (space has no endpoint) should not lock out the user. → post-demo pilot story.

## Deferred from: code review of 3-0-A-space-profile-card-ux-refinement (2026-05-05)

- **D1 — Raw `s.error_type` displayed to user when key not in ERROR_LABELS** — broken spaces with unlisted error types show internal key strings (e.g., `dns_resolution_failed`) in the info banner. Text-safe (no XSS). Defer to Epic 5 UX polish / coordinator feedback story.
- **D2 — Network label externalization** — Currently network URNs are displayed as uppercased final segment (e.g., `urn:mak:network/vow` → `VOW`). This works for known networks but is fragile for federation/arbitrary networks. Solution: add network resource definitions to ontology with `rdfs:label`, surface via SPARQL optional lookup in both materialize_geojson.py and main.py SPARQL queries, add `networkLabels: { urn → label }` dict to GeoJSON binding, render from that in UI. → Epic 5 networking polish or Epic 4 admin dashboard refactor.

## Deferred from: code review of 2-7-card-zones-pydantic-schema-foundation (2026-04-28)

- ~~**W1 — "last fetch never ago" timestamp display bug** — `timeAgo()` receives a date-only `YYYY-MM-DD` string; needs a full ISO datetime. Pre-existing; visible now because a real coordinator space was registered. → Epic 5 / Story 4.2 fetch history polish.~~ → **resolved 2026-05-06 in Story 3.2 AC7 (`last_updated` now full ISO datetime; lifecycle copy reads `last_updated`, endpoint copy reads `last_fetched`)**
- **W2 — No fetch timeout on Zone 3 /raw fetch** — indefinite loading state on slow server. Pre-existing pattern across app fetches. → Epic 5 UI polish.
- **W3 — Zone 3 error state: 500 vs network timeout collapse to same "Source unavailable."** — minor UX gap; spec allows this. → monitor.
- **D2 — SpaceAPI schemaErrors[] not surfaced in validation drawer** — `POST /api/validate-url` does not call SpaceAPI validator or return field-level errors. "→ See schema guide" link is the current help. Full error surfacing deferred. → Epic 5 coordinator-feedback polish.

## Deferred from: infra-nginx-new-domains spec + Epic 2 retro (2026-04-28 / 2026-04-29)

- **Epic 4 Story 4.0 — Full mission-control dashboard** — spec `4-0-admin-foundation-subdomain-auth-space-comparison.md` (status: draft). Builds on top of the admin subdomain routing and basic landing page implemented in this story. Dashboard will display space ingestion lifecycle: seed data, live URL data, stored triples, and map card views side-by-side. Required for grant demos showing diagnostic capabilities.

- **Admin nginx routing setup for Story 4.0** — current state: `admin.mapsofmaking.com` routes through gateway-nginx (`07-admin-mapsofmaking.conf`: `proxy_pass http://maps-nginx/admin/`) → maps-nginx (`location /admin` in `infra/nginx/conf.d/app.conf`). Auth is `auth_basic` with htpasswd on maps-nginx (not gateway). Landing page is `web/admin.html` → `/var/www/mapsofmaking/admin.html` in container. Story 4.0 replaces `web/admin.html` with a real dashboard; nginx config needs no changes.

- **nginx quirk: `alias` + regex location = 500** — `alias` directive does not work with regex `location ~ ...` blocks in nginx (produces 500). Use `try_files /absolute-path.html =404` instead, which resolves relative to `root`. Applies to any future static file served at a non-root URL path. → keep in mind for Story 4.0 if adding sub-pages under `/admin/`.

## Deferred from: code review of 1-3-docker-compose-stack-nginx-security-routing (2026-04-24)

- **Docker images not pinned to specific versions** — `infra/link_handler/Dockerfile` uses `python:3.12-slim` (no patch pin); `docker-compose.yml` uses `:latest` tags. Future deploys may break silently.
- **CORS `*` overly permissive on /sparql/query** — Intentional for public endpoint now; consider restricting to known origins when admin/write paths are added in Epic 5.
- **LINK_SECRET env var never consumed in stub** — Passed to mak-link-handler but ignored until Epic 3 (Story 3.3) implements actual HMAC token signing.
- **nginx /claim/ has minimal proxy headers** — Missing `X-Forwarded-Proto`, `X-Forwarded-Host`. Full headers needed when claim handler does origin-aware logic in Epic 3.
- **No SPARQL query complexity limits / DoS protection** — No timeout or depth limit on public /sparql/query. Add nginx `limit_req` or oxigraph timeout config in future infra hardening story.
- **No graceful shutdown timeout for uvicorn** — Single-worker stub; add `--timeout-graceful-shutdown 30` when claim handler processes real transactions in Epic 3.
- **gateway network external precondition not verified** — `docker-compose up` fails if hetzner-gateway network doesn't exist. Add to VPS setup runbook.
- **nginx starts before upstreams are ready (early 502s on cold start)** — On `docker compose up -d`, first few requests may hit 502. Acceptable for current scale; add startup ordering with `condition: service_healthy` sweep if SLA requires cold-start reliability.
- **No upstream fallback for oxigraph or mak-link-handler downtime** — Bare 502 on upstream failure. Add `error_page 502 /50x.html` or upstream backup when resilience becomes a requirement.

## Deferred from: code review of 1-5-map-reads-from-oxigraph-geojson-materialization (2026-04-25)

- **Fixed temp filename `.geojson.tmp`** — `scripts/materialize_geojson.py`: concurrent invocations write to the same temp file, last writer wins then renames. Low risk while manually invoked; becomes real when Epic 3 scheduler triggers materialize on each ingest cycle. Fix: use `tempfile.NamedTemporaryFile` in the same directory.
- **GROUP_CONCAT `|` separator** — SPARQL query uses `|` as separator for specialties. A specialty containing `|` (possible with user-supplied data in Epic 2) will be split incorrectly. Epic 2 normalization pass should enforce no-pipe constraint in specialty values.
- **countryLabel() only handles FR/DE** — `web/app.js`: all other countries display raw ISO codes (e.g. `BE`, `NL`). Needs a full country lookup map. Defer to Epic 5 UI polish.

## Deferred from: code review of 1-4-author-mom-ontology-v0-load-mom-iop-into-oxigraph (2026-04-24)

- **distrobox fallback silent failure when container not running** — `scripts/load_ontology.sh`: if `maps-oxigraph` is not running, `podman inspect` fails silently, `CONTAINER_IP` is empty, script proceeds with the original unreachable URL without a clear diagnostic error message.
- **No `--max-time` on curl PUTs in load_ontology.sh** — load script can hang indefinitely on slow VPS or stalled container; health check has `-m 1` but actual PUT calls don't.

## Deferred from: Story 3.2 lore session — SpaceAPI federation seeding (2026-05-07)

- **SpaceAPI directory has out-of-range coordinates** — ~5% of endpoints report lat/lon outside valid ranges (e.g., Unix timestamps as coordinates). The seed script now validates `-90 ≤ lat ≤ 90` and `-180 ≤ lon ≤ 180` before writing. **Lesson:** external directories require validation; silently dropping bad records is better than crashing the map renderer mid-loop.

- **SpaceAPI directory is global, map is bounded to Europe** — The directory has 244+ spaces worldwide; the demo map is bounded to Europe ([-25, 34], [45, 72]). The seed script now filters to bounding box at seed time, reducing GeoJSON bloat and preventing out-of-map spaces from draining resources. **Pilot story:** generalize to configurable geographic scope when federation expands.

- **Network membership preservation through heartbeat required dual fixes** — (1) SPARQL GROUP_CONCAT with STR() wrapper (resolved in prior session); (2) `_sparql_iri` scheme validation now accepts `urn:` URIs (resolved this session). Without both, heartbeat would silently strip `mom:memberOf` triples during space updates. **Pattern:** external identifier scheme support must reach from seed → heartbeat → materialization.

- **Filter clearing after registration is essential UX** — When a user registers a new space with no network membership, active network filter chips would hide the dot. Now: registration flow clears all filters before rendering, ensuring the newly registered space is visible. **Lesson:** registration/creation flows should reset filter state to show the new item.

- **Coordinate validation prevents renderMarkers() cascade failure** — When `renderMarkers()` encounters a space with invalid lat/lon, MapLibre throws. Previously, error silently bubbled, aborting the loop before later spaces (including openfab) got markers. Now: skip invalid spaces with a console warning, continue rendering. **Pattern:** per-item error handling in render loops beats fail-on-first.

## Deferred from: Story 2.0 — UI Dataset Toggle and User Preferences (2026-04-25)

- **Legend does not show health map states** — `web/maps-of-making.html`: legend only lists seeded/confirmed/open/unlinked/broken. When health map is ON, aging ⚠️ / zombie 🧟 / dead 🪦 markers appear with no legend entry. Add a conditional legend section that shows when health map is active. → Epic 5 UI polish.
- **Status filter chips don't include health states** — `web/app.js` `buildFilterChips()`: statuses array is `['seeded','confirmed','open','unlinked','broken']`. When health map is ON, users can't filter by aging/zombie/dead. → Epic 5 (Story 5-5 tweaks panel decision).
- **Emoji in SVG markers: cross-browser rendering risk** — aging/zombie/dead markers use SVG `<text>` with emoji (⚠️🧟🪦). Rendering is browser/OS-dependent; may be invisible or misaligned on some Android WebViews. Replace with inline SVG glyphs if reported. → monitor, fix if bug reported.

## Deferred from: code review of Story 2.0 (2026-04-26)

- **Orphaned selected marker after GeoJSON reload** — Selection state in UI diverges from GeoJSON state if selection changes during reload. Requires larger state management refactor. → Epic 5 architecture pass.
- **DOM race: highlightSelected() async to renderMarkers()** — Visual glitch on slow networks when highlight called before tiles render. Timing issue from initial architecture, not introduced by this story. → Epic 5 rendering optimization.
- **geolocationFidelity enum not validated** — Future features using fidelity-based filtering will silently break on invalid enum values. Requires schema validation layer in SPARQL or backend. → Epic 2/5 data validation scope.
- **Search with untrusted data** — Specialty field concatenated directly into search haystack with no sanitization. Low risk in text search context but fragile pattern for future features. → Data validation and trust boundary refactor (Epic 2 scope).

## Deferred from: code review of 2-1-coordinator-url-onboarding-e2e (2026-04-26)

- **F7 — No auth on `/api/register-url`** — open-registration is spec-mandated ("without creating an account"); endpoint is open write to triplestore. Add rate-limiting and/or simple token in Epic 5 hardening story.
- **F8 — DROP SILENT overwrites on slug collision** — spec says "creating or overwriting `<urn:mak:space/{slug}>`"; two different spaces with the same slug silently clobber each other. Add collision detection / disambiguation in Epic 5.
- **F14 — Trailing slash on URI produces empty `space_id` in `_binding_to_feature`** — only triggered by externally sourced URIs with trailing slash; current internal generation cannot produce this.
- **F15 — GeoJSON re-fetch failure leaves new space out of `state.spaces`** — `selectSpace`/`embedSpace` silently find nothing if rematerialization hasn't completed when the browser re-fetches. Spec explicitly allowed re-fetch approach; patch in Epic 5 UX pass (patch state from API response as fallback).
- **F19 — `confirmed_at` column in `seed_transition.py` shows `mom:lastFetched`** — no distinct `mom:confirmedAt` triple is written at registration time; if the space is ever re-fetched, the column drifts from actual registration time. Add a `mom:confirmedAt` triple in the SPARQL UPDATE if this distinction matters in Epic 3+ tooling.

## Deferred from: Story 2.6 — Mobile Responsive Layout (2026-04-27 / 2026-04-28)

### Feature Requests & Design Decisions

- **Shareable query URL** — "I filtered to confirmed + open + electronics in Hamburg — here's the link." Implies URL state management for active filters as query params (e.g. `?filter=confirmed&city=hamburg&specialty=electronics`). Similar to the embed code snippet but as a shareable URL. Right for pilot when coordinators share filtered map views to communities. → Epic 5 or dedicated pilot story.
- **Swipe-to-dismiss bottom sheets** — drag-handle is visual only in 2.6; actual swipe gesture to dismiss requires a touch event handler. Low priority until user feedback confirms it's missed. → Epic 5 polish.
- **Health map suppressed on mobile** — design decision: health map toggle (Tweaks panel) is a desktop analytics feature; mobile defaults to fresh/confirmed view only. If a mobile health map use case emerges from pilot, revisit. → monitor.
- **Brave browser geolocation** — Brave on Android 16 silently blocks the permission prompt even when site is "allowed" in Brave settings. Not our bug; could add a "please use Chrome/Firefox" tooltip on silent denial if user research shows it's a real friction point for pilots. → monitor.
- **Near me button: no proximity highlight** — map flies to user location but spaces are not visually emphasised. Story spec marked this optional; implement distance-based dimming if pilot feedback requests it. → Epic 5.
- **Makefile `publish` does not pin `--force` semantics** — `seed_import.py --force` always clears and reloads the RFF mock graph. Once we have real coordinator data in prod we may want to skip RFF reload by default; add a `make publish-seed` vs `make publish` split. → Epic 3 / infra hardening.

### Code Review Findings (2026-04-28)

- **Redundant marker re-render optimization** [web/app.js:337] — Renders all markers on chip click instead of toggling filter state and selectively updating. Works correctly but inefficient; optimization deferred to post-launch refactor. Lower priority than functional patches.
- **Drawer state race condition** [web/app.js:780-803] — Rapid drawer open/close mutations could cause double syncTopbar() calls. Unlikely to manifest in real usage; defensive fix deferred to Epic 5 polish phase. Pre-emptive complexity not needed for current scope.
- **Inconsistent error handling pattern** [web/app.js:673-678] — Uses string interpolation for error messages inconsistently; Promise.reject() on line 473 already covers the core issue. Code quality improvement deferred to next refactor cycle. Not a functional bug.

## Deferred from: Story 2.2 — Detail Drawer (2026-04-26)

- ~~**Admin: delete test/self-registered spaces**~~ → **Folded into Story 4.5 (Admin Delete Space), Epic 4 replan 2026-05-28.** ACs cover Oxigraph `DROP GRAPH` for space + canary, `snapshot_store.db` row delete, rematerialize, canary-slug protection, action-log entry. See `epics.md` §Story 4.5.

## Deferred from: SKILL.md dual-validator exercise (2026-04-28)

Generating a real openfab.jsonld against the `space-jsonld-generator` skill exposed gaps between our doc and reality. Park these — demo unblocked at `mom:required` tier; SpaceAPI compatibility is nice-to-have.

- **SpaceAPI v14 minimum-fields requirement is non-trivial** — A partial JSON-LD (mom:required tier: name + coords) does NOT pass `validator.spaceapi.io`. SpaceAPI v14 mandates `space`, `logo`, `url`, `location.{lat,lon,address}`, `state`, `contact`, `api_compatibility` together. Our "subset tiers" model is correct in spirit (more fields = more interop) but the jump from `mom:card` → `spaceapi:compatible` is a cliff, not a gradient. → Story 2.7 review pass: rephrase tier docs to be honest about the cliff.
- **SpaceAPI validator UI hides `schemaErrors[]`** — The web UI reports failure with no actionable detail. The API response includes a `schemaErrors[]` array (per [SpaceApi/validator](https://github.com/SpaceApi/validator)). `scripts/validate_dual.py` now surfaces these as `_schema_errors_summary`. A future coordinator UI should pass these through verbatim instead of a generic "failed" message. → Epic 5 coordinator-feedback polish.
- **Dual-shape JSON-LD template is the canonical output** — `web/test-fixtures/SKILL.md` rewritten: SpaceAPI v14 flat keys (`space`, `location.lat`, …) with a JSON-LD `@context` that aliases each to mom/schema.org IRIs. One file, both validators. The Pydantic `SpaceAPISchema` was extended (`space`, `location.lat/lon/address` accepted alongside `schema:*` keys). → covered, but Story 2.7 review should re-validate that AC1 / classify_subset still describes the dual-shape inputs accurately.
- **`@id` semantics need a doc explainer for coordinators** — `@id` is the IRI of the entity, not the file URL. The validator ignores it. Several confused questions in the dual-validator exercise; SKILL.md now documents this but a coordinator-facing FAQ entry would help. → Epic 6 / coordinator onboarding.
- **`mom:operationalState` vs SpaceAPI `state` is a name collision** — SpaceAPI's `state` is dynamic open/closed; mom's `mom:operationalState` is long-term lifecycle (`active`/`dormant`/`closed`). Coordinators conflate them. SKILL.md aliases `state` → `mom:dynamicState` in the JSON-LD context to avoid the clash, but the ontology should grow an explicit `mom:dynamicState` term to make this legitimate. → Ontology repo update.
- **"AI" tag vocabulary is fluid** — `agentic-ai`, `embedded-systems`, `ai-assisted-design`, `ai-empowered`, `aiot` are all valid, all mean different things to different coordinators. No clear canonical vocabulary yet. The `mom.ttl` ontology should grow a `mom:Activity` SKOS hierarchy (with `skos:altLabel` for synonyms across languages) so Oxigraph can resolve queries semantically rather than string-matching. → Ontology repo + new story (semantic layer for activity tags).
- **Missing `opening_hours` for openfab.jsonld** — Founder didn't supply hours; file is at `mom:required` tier. → Pending input from coordinator before re-validating.

## Deferred from: Story 2.1 — Coordinator URL Onboarding E2E (2026-04-26)

- **Fixed temp filename in `_rematerialize_geojson()`** — `infra/link_handler/main.py` writes to a fixed `.geojson.tmp` path, same race condition as `materialize_geojson.py` (already noted above). Low risk while single-worker; becomes real when Epic 3 scheduler triggers concurrent rematerializations. Fix: `tempfile.NamedTemporaryFile` in same directory. → Epic 3 scheduler story.
- **Description and opening hours written to Oxigraph but not surfaced** — `register-url` writes `schema:description` and `schema:openingHours` to the named graph but the SPARQL SELECT (and therefore the space card) doesn't read them back. Gap between what's stored and what's displayed. → Story 2.2 detail drawer scope.
- **PII enforcement deferred** — Only `foaf:mbox` and `schema:Person` trigger the soft warning; `schema:email` / `schema:telephone` removed (business contact info). Full enforcement (hard block + admin alert for unambiguous personal data) is a separate hardening story. → Epic 5 or dedicated security hardening.
- **Geocoding hint for spaces missing coordinates** — When `coords_found: false`, the UI tells the user to add `schema:geo`. A nice-to-have improvement: if the JSON-LD contains `schema:address`, offer a geocoding lookup to pre-fill the latitude/longitude for them to paste into their file. No cost (Nominatim free tier), reduces friction. → Epic 5 UI polish or dedicated onboarding UX story.

## Deferred from: code review of 3-0-ingestion-transformation-layer-spaceapi-json-to-mom-json-ld (2026-05-01)

- **SQLite concurrency risk in fetch_endpoint_conditional** — `transformer.py:fetch_endpoint_conditional` — synchronous SQLite calls in async context; concurrent heartbeats for same space_id can race. Single-worker deployment safe; becomes real when Story 3.1 heartbeat scheduler introduces concurrent fetches. Fix: use `BEGIN EXCLUSIVE` transaction or aiosqlite. → Story 3.1
- **Lifecycle clock resets to "confirmed" on DB wipe / container rebuild** — `process_one_space` computes `days_since_last_update` from `heartbeat_log.last_content_updated` (SQLite). If the DB is wiped (container rebuild, volume removal), all spaces lose their content-update history and lifecycle resets to `confirmed` regardless of actual age. Low risk in prod (volume persists); real friction in dev where container rebuilds are frequent. Fix: on startup, backfill `last_content_updated` from `mom:lastUpdated` in Oxigraph for any space_id missing from the DB. → Story 3.3 or early Epic 4 ops hardening.
- **Module-level _config/_activity_map singletons never reload** — `transformer.py:19-20` — config and activity map cached forever at module load; container restart is intentional refresh mechanism. If live config reload is ever needed, add a TTL or reload endpoint. → Future ops story
- **_sparql_str missing null byte escape** — `utils.py:12` — null bytes (`\x00`) in names/descriptions would produce invalid SPARQL literals; extremely rare in real SpaceAPI payloads. → Future hardening
- **detect_diff json.dumps silent fallback for non-serializable values** — `transformer.py:152` — sort key raises TypeError on datetime/set values, silently falls back to unsorted list (no diff reported for those elements). Current callers produce only string values from SPARQL results. → Future if detect_diff is reused in other contexts
- **test_transform_idempotent snapshot URI fragile at UTC midnight** — `test_transformer.py:279` — `snap1 == snap2` assertion fails if test runs across date boundary. Use freezegun or inject fixed date. → Test polish
- ~~**Negative age_days from future-dated Last-Modified always returns "confirmed"** — `transformer.py:classify_operational_state` — clock skew on remote server produces negative age_days; all thresholds missed, silently returns "confirmed". Undocumented but acceptable. → Future monitoring story~~ → **resolved 2026-05-06 in Story 3.2 AC1 (clamp to 0 + WARNING log)**

## Deferred from: UX design session for 3-0-A-space-profile-card-ux-refinement (2026-05-04)

- **Manual fetch button wired (disabled stub in 3.0-A)** — ✅ DONE in Story 3.1.
- **True change-detection for "last updated"** — `mom:lastUpdated` written at every successful 200 fetch; does not diff content. "fetched:" timestamp in Zone 3 = last 200 response; field-level change history is nice-to-have for trust/transparency story but not critical for demo. `detect_diff()` exists in transformer.py but is not called. → Epic 7 / future history story. Note: 304 conditional GET already prevents redundant writes when server honours ETags.
- ~~**`state` open/closed dynamic signal → green marker** — SpaceAPI `state` object (dynamic open/closed + lastchange) detected but not yet acted on. If present, could enable green marker and freshness sensing for demo. → Epic 7.~~ → **resolved 2026-05-06 in Story 3.2 AC2/AC5; Epic 7 reframed as parked indefinitely (heartbeat covers it)**
- **Space name collision / duplicate space resolution** — Two unrelated spaces sharing the same name (e.g. OpenFab Brussels vs OpenFab Istanbul) are currently disambiguated only by endpoint URL. No UI for collision detection or coordinator disambiguation. → Pilot phase.
- **Endpoint URL swap / trust attack** — A bad actor could register an existing seeded space's slug with a different endpoint URL, replacing legitimate data. No auth or ownership verification at registration time. → Pilot phase security hardening.
- **Rate limiting persistence across restarts** — Manual fetch cooldown (60s per space) stored in-memory dict; resets on container restart. → Epic 5 polish.

## Deferred from: Space Profile v2 UI implementation (2026-05-05)

- **SVG contact channel icon collection** — Space Profile v2 includes inline SVG icons for email, twitter, mastodon, facebook. All other channels (phone, irc, matrix, foursquare, website, ml, unknown keys) render text abbreviations (`[ph]`, `[#]`, `[mx]`, `[fs]`, `↗`). A full collection of platform SVGs (at minimum the 15 most common SpaceAPI contact keys) is needed before public launch. → Epic 5 / UI polish

## Deferred from: Live demo testing on 2026-05-07

- **Newly registered URL shows no dot on map** — Registration succeeds (profile opens, GeoJSON updated) but the marker doesn't appear on map. Likely race condition or filter state issue. Browser console should be checked for errors during registration flow. → Epic 5 or Pilot debugging.
- **SpaceAPI directory — missing country codes** — seed_spaceapi.py has no source for country/locality; all 197 spaces appear as "197 unknown country" in filter. Only solution is extract from endpoint URL or endpoint's location object (v15 feature, not v14). Lower priority for demo. → Epic 5.
- **SpaceAPI directory — global scope wastes resources** — Fetches all 244 endpoints (~197 reachable); could filter by lat/lon bbox to fit demo's Europe focus. Requires spatial filtering during directory fetch. → Pilot phase.

## Deferred from: SpaceAPI + demo map review (2026-05-07)

- **Spaces with missing or invalid geolocation** — Some seeded SpaceAPI spaces trigger a browser warning because their `schema:geo` coordinates are null or fall outside valid ranges. These are currently included in the GeoJSON with bad coords. Epic 4 mission control is the right place to surface these: health pill + inspection panel showing "no valid coordinates" as a data-quality signal. Ideal showcase for the operator tool use case. → Epic 4.

## Deferred from: SpaceAPI seed + heartbeat integration (2026-05-07)

- **Heartbeat sequential write bottleneck** — `run_heartbeat_cycle` fetches endpoints concurrently (seed_spaceapi.py uses concurrency=20) but writes to Oxigraph one SPARQL UPDATE per space, sequentially. With 197 SpaceAPI endpoints this runs visibly slow on manual trigger. Two complementary fixes: (1) batch Oxigraph writes into a single UPDATE per cycle, (2) process endpoint fetches concurrently using the same asyncio pattern already in `seed_spaceapi.py`. Meaningful refactor of `process_one_space` — worth its own story once pilot traffic justifies it. → Epic 5 / Pilot phase.

## Deferred from: code review of 3-3-mother-sands-diagnostic-canary (2026-05-16)

- **`If-Modified-Since` header unused in canary endpoint** — `data/canary/mother-sands-endpoint.py`: clients without `If-None-Match` always get 200. Diagnostic tool only; ETag path covers production use.
- **TOCTOU race on `SERVED_FILE.read_bytes()`** — `data/canary/mother-sands-endpoint.py`: `FileNotFoundError` if file deleted between exists-check and read. Low-probability in operator context.
- **ETag mtime-only: sub-second collision** — `data/canary/mother-sands-endpoint.py`: two writes within same mtime tick produce colliding ETag. Operator workflow is slow manual steps; acceptable risk.
- **`MODE=timeout` TCP connection FD leak** — `data/canary/mother-sands-endpoint.py`: 120-second hold without explicit close leaks FD in tight loops. Acceptable for diagnostic use.
- **Isolation test uses string assertion, not live ASK query** — `tests/test_canary_scenarios.py`: spec says "ASK query pattern"; hermetic CI has no live Oxigraph. ASK path covered by live coherence report layer.
- **`CANARY_SPACE_ID="mother-sands"` hardcoded in coherence report** — mismatch risk if DB slug derivation differs. Verify during live operator poke before Epic 4.

## Deferred from: code review of 3-2-b-mak-closed-pii-strip (2026-05-07)

- **SPARQL injection via space_uri**: `space_uri` is f-string interpolated into SPARQL strings (`_build_pii_strip_sparql`, `build_state_only_update`, etc.) without using the `_sparql_iri` sanitization helper from `utils.py`. Pre-existing pattern throughout `transformer.py`. → Epic 5 hardening.
- **SQLite concurrency on `consecutive_closed_cycles`**: read-modify-write on the counter is not atomic — two concurrent manual refreshes for the same space could lose a counter increment. Pre-existing pattern for `consecutive_failures`. → Epic 5 hardening.
- **Snapshot ORDER BY lexicographic**: `_fetch_last_snapshot` orders by snapshot graph URI string; relies on ISO datetime lexicographic sort being stable across timezone formats. Pre-existing. → investigate if mixed TZ formats ever appear.

## Deferred from: code review of 3-6-walking-skeleton-observed-at-end-to-end (2026-05-19)

- **`fetch_canary_snapshot` silent None after successful write**: `read_snapshot` is called immediately after `write_snapshot` and returns None silently if the read fails. Practically impossible since the row was just written, but the caller receives None with no error. Story 3.7 adds proper error handling for non-200 paths — consider adding an assertion or explicit error here at that time.

## Deferred from: code review of 3-7-heartbeat-log-observed-at-fetch-status (2026-05-19)

- **No WAL mode / busy timeout on SQLite**: Both `snapshot_store.db` and `heartbeat_log.db` use default journal mode with 0ms busy timeout. Concurrent heartbeat coroutines writing to the same file will intermittently raise `OperationalError: database is locked`. Add `PRAGMA journal_mode=WAL` and `timeout=5` to `sqlite3.connect()` calls.
- **`httpx.RequestError` broad catch includes `InvalidURL`**: `fetch_space_snapshot` catches `httpx.RequestError` (base class) alongside `ConnectError`/`TimeoutException`. A malformed `endpoint_url` will be silently treated as a transient network failure and mark the space unreachable rather than surfacing a config bug. Consider narrowing the catch or logging at ERROR level for `InvalidURL`.

## Deferred from: code review of 3-8-transformer-emits-mom-observedat (2026-05-19)

- **`_read_space_metadata` still reads `mom:lastUpdated`**: SPARQL read path in `transformer.py` queries for `?lastUpdated` which no longer exists in the graph. Returns null/empty silently. → Story 3.9: replace with `mom:observedAt` read when materializer is updated.
- **`content_changed` parameter dead in `transform_to_sparql`**: The parameter is still in the signature and passed at call sites but has no effect on output after Story 3.8 removed the `lastUpdated` branching logic. → Story 3.9 cleanup: remove or repurpose.
- **SPARQL injection via `observed_at` string interpolation**: `observed_at` is interpolated directly into SPARQL f-strings without escaping. `mint_observed_at()` produces safe ISO-8601 Z strings but there is no validation. Pre-existing pattern across the codebase. → Harden if `mint_observed_at` ever accepts external input.
- **Non-canary 304 `graph_uri=None` + `observed_at`**: `build_state_only_update` called with `graph_uri=None, observed_at=<value>` on non-canary 304 produces `GRAPH <None>` in SPARQL DELETE — silently a no-op in Oxigraph. Pre-existing: the original `lastFetched` write had the same defect. → Investigate whether non-canary spaces need the surgical update at all, or fix `_graph` assignment to use the space graph URI on 304.
- **Concurrent registration+heartbeat double-write race on `mom:observedAt`**: Two simultaneous writes for the same slug can interleave DELETE WHERE / INSERT DATA and leave a stale token. Pre-existing architectural pattern; no transaction support in SPARQL 1.1 Update HTTP. → Epic 5 hardening: consider a write serialization layer or idempotent upsert guard.

## Deferred from: code review of story-3.9 (2026-05-19)

- **Dead `effective_marker`/`resolved_status` computation + `status` divergence**: `_binding_to_feature` (main.py:576-592) still computes `resolved_status` from `endpoint_health_raw`/`operational_state` whose source OPTIONALs were removed from the SPARQL SELECT — they now always resolve to `.get()` defaults. `scripts/materialize_geojson.py:binding_to_space` instead hardcodes `status: "unknown"`, so the two materializers emit different `status` semantics for identical data. → Story 3.10 field-slimming (scope-guarded per story Technical Decisions note).
- **`_load_thresholds_from_config` swallows all exceptions**: A malformed or missing `config.yaml` yields an empty `thresholds` block in published GeoJSON with only a logged warning — downstream consumers get no thresholds and no failure signal. Present in both main.py and scripts/materialize_geojson.py. → Minor robustness hardening.
- **Materializer test fragility**: `test_observed_at_from_sqlite_not_oxigraph` claims to verify "not from Oxigraph" but only asserts the SQLite value matches — it cannot distinguish source since `mom:observedAt` is not in the SELECT anyway. Tests also mix subprocess and in-process import contexts, which exercise different `sys.path` side effects. → Test-design cleanup.

## Deferred from: memberOf + country chip pass (2026-05-27)

- **Network membership handshake verification**: Coordinator-JSON `memberOf: ["spaceapi"]` is currently honored on trust — no cross-check that the declared network's directory actually lists the endpoint URL. Implement: at register/heartbeat time, if `memberOf` includes a network slug whose directory we know (spaceapi → directory.spaceapi.io initially), fetch that directory and verify the endpoint URL is present. Emit `mom:membershipStatus "verified"` vs `"self-claimed-unverified"`. UI can then differentiate the chip rendering (e.g., dim self-claimed chips). Required for federation trust before opening registration broadly.
- **SDG ontology + processing**: Canary `baseline.json` now carries `ext_fab.sdgs: [9, 11, 12, 14, 17]` as a placeholder. No triples are written today. Open questions: (a) is SDG a property of the space or of activities/projects within the space? (b) ontology namespace — adopt UN goal URIs (`https://sdgs.un.org/goals/goal11`) or mint `mom:sdg`? (c) UI placement: badge row in card, or filter chip? Decide before extending beyond canary.
- **Reverse-geocode for missing country_code**: SpaceAPI directory yields ~14% country_code coverage (26/192 today). Option A: offline lookup via `reverse_geocoder` Python package, run at seed/heartbeat time, write `mom:countryCode` when unset. Option B: address-tail regex parser (cheaper, less accurate). Picking up Path B's VOW seed bundle will partly mask the gap because VOW records carry structured `schema:addressCountry`. Revisit after VOW lands and we see real coverage gaps.

## Deferred from: code review of 9-3-wizard-core (2026-05-31)
- Multiple gunicorn workers multiply effective Nominatim request rate — each worker has its own RateLimiter (1 req/s), so N workers = N req/s to Nominatim. Fix: shared inter-process rate limiter or single-worker constraint in deploy config.
- 429 from nginx geocode rate-limit shows same message as outage ("Geocoding temporarily unavailable") with no retry hint. Deferred to Story 9.5 Bernard copy pass.
- validateAgainstSchema() in genjson.js only checks top-level schema required fields; nested required (location.lat, location.lon) are not validated. Shallow check gives false confidence.

## Deferred from: code review of 9-5-bernard-voice-copy-pass-curated-voice-artifact (2026-05-31)

- Existing localStorage drafts with `contact_mastodon` key silently orphaned after mastodon→matrix field swap — `loadDraft()` merges all saved keys; mastodon value stored in draft object but never rendered or exported; low impact

## Deferred from: 9.12 honest-derivation (Slice B, 2026-06-01)
- **Timezone derivation (§2 table + §7 open thread) → own story.** §2 wants "Full address → derive lat/lon · country · **timezone**". Slice B derived country + postcode (Nominatim `addressdetails` returns both), but **timezone is NOT in Nominatim's response** — it needs a separate lat/lon→tz lookup (e.g. `timezonefinder`, offline; new dependency). Operator note (2026-06-01): timezone is a real **SpaceAPI field**, not yet used by MoM, but could soon inform location/visitor-aware features — so it has standalone value. Scope when picked up: add tz lookup to `/api/geocode` (or a derive step), return `timezone`, wizard fills it silently like country/postcode, narrate `· <tz>` next to the pin (§3 worked example shows `· CET`). → New Epic 9 geocode/derivation story.

## Deferred from: code review of 9-8-gitlab-tutorial-surface-embedded-guide-raw-url-handoff-register-flow (2026-06-02)
- **golive progress not persisted across page reload.** Tutorial progress (which beat the user reached) is never written to localStorage. On reload, `hasDraft` resume block has no golive references — user returns to fork stub with tutorial collapsed, no indication they were mid-tutorial. Low-impact UX gap; golive is a short 5-step flow. Deferred by design.

## Deferred from: seed-import bundle/CSV-pivot pass (2026-06-04)
- **Makefile detailed analysis + cleanup.** ✅ **DONE (2026-06-05)** — full honest-
  inventory completed; triage + local↔VPS mirror contract written to
  `docs/vps-operations.md` ("Makefile inventory" section). Safe cuts applied: dead
  `seed` deprecation stub removed, duplicate `endpoint` `.PHONY` deduped, stale help
  line dropped. **Two follow-ups carried forward:**
  - **Stack-twin recipe merge.** `seed-spaceapi`/`vps-seed`, `seed-bundle`/`vps-seed-bundle`,
    `rebuild`/`vps-rebuild`, `reset`/`vps-reset` are still hand-written parallel twins.
    Collapsible to the canary `CANARY_OPS`/`PUSH_STEP` variable-override pattern via a
    single `EXEC` selector (dev compose already bind-mounts `scripts/`, so local can run
    `podman exec` with no staging). ~100 lines removable. Touches deploy paths → needs a
    live local+VPS test run before trusting. → infra hardening pass.
  - **`docs/canary-operator-runbook.md` broken against the Makefile.** ✅ **DONE (2026-06-05)**
    — rewrote the operator runbook AND `docs/canary-setup.md` against reality: correct target
    names (`c-reset`/`cb-aging`/…), the single-public-URL architecture (no `:9191` server in
    the request path; both heartbeats fetch `mapsofmaking.org/canary/mother-sands.json`),
    `web/canary/mother-sands.json` (not `served.json`), and removed all references to the
    non-existent `make canary-report` / `canary_coherence_report.py` coherence tool (verification
    is now map-reload + card + isolation SPARQL). Axis A documented honestly as partial — the
    targets author+push but a true timeout/503/DNS fault needs `canary_ops.py set-endpoint` at a
    controllable endpoint. All referenced targets verified to exist.
- **`seed_bundle.py` does not harden bad fields by design.** A corrupt `url` (e.g.
  merge-tool garbage like `"[{'id': 478"`) injected as an IRI causes a 400 and the whole
  record is lost (observed: 21/117 write_failed on raw BE.spaces.json). Decision (Nicolas,
  2026-06-04): do NOT grow the seeder to parse edge cases — clean upstream via the CSV
  pivot (`scripts/seed_csv.py`, which blanks invalid URLs at conversion). Revisit only if
  a real recurring need appears. The nudge philosophy (incomplete data = signal to the
  space to publish a clean endpoint) makes lossy-but-honest acceptable.
- **Status filter conflates two orthogonal axes → Epic 5.** The map's status filter
  chips (`web/app.js` `buildFilterChips`) currently list the *collapsed* `computeMarker`
  label: `seeded, confirmed, open, shut, broken, aging, zombie, dead`. Cheap fix applied
  2026-06-05 (added `aging/zombie/dead` so the new freshness states are at least
  selectable). **Real fix deferred:** `computeMarker` collapses two independent
  dimensions into one label — **health/freshness** (broken / aging / zombie / dead, from
  the three-token model) and **door state** (open / shut). A space can be both `aging`
  AND `open`, but the single-label filter can only match one. Proper solution is to split
  status filtering into two filter groups (health-freshness vs open/shut) so combinations
  work, which is a real UX rethink (chip layout, preset URL param shape, legend). Pair
  with the Epic 5 map-viz lenses work. Touches `filteredSpaces`, `buildFilterChips`,
  `applyUrlParams` (`status=` param), and the preset/embed share URL contract.
- **Preset & embed feature is thin → TBD.** Toolbar "Preset & embed" now opens clean
  (empty name, no stale `center`/`space`) vs the per-card "Embed this space" path which
  pre-populates. Open ideas, not yet scoped: (a) a small **banner in the preset drawer**
  clarifying which mode you're in (filter-preset vs single-space embed); (b) named/saved
  presets; (c) decide the fate of the decorative `preset=<slug>` URL param (emitted but
  never read by `applyUrlParams`). Revisit when presets get real product attention.


## Deferred from: code review of 5-1-unified-find-surface (2026-06-07)

- `filteredSpacesExcluding` duplicates `filteredSpaces` filter logic — risk of silent divergence if a new filter dimension is added to one but not the other; chip counts would mismatch the map. Revisit when adding a new filter axis.
- Single-char query stale in `state.search` after ESC — `isFindActive()` threshold is `>= 2`; typing one char then ESC doesn't reset the partial query; it persists and pre-populates the input on reopen. Acceptable for now; revisit if users report confusion.


## Deferred from: party-mode "what counts as content / liveness" (2026-06-10)  → Story (post-traction)

- **Operator-declared `mom_liveness_optin`.** A coordinator names which core SpaceAPI
  fields feed the liveness (green-dot) signal. Opt-IN, never exclusion — exclusion was
  rejected because it demands the operator understand MoM internals. Lives on the
  coordinator's per-space `mom:` record (sovereignty stance), NOT our pipeline config.
  **Build trigger:** the first real coordinator who disputes a staleness call ("why is my
  space stale when X changed?"). Until then it's speculative config for users who don't
  exist yet (no SpaceAPI-community traction).
- **`detect_diff` two-clock rework — "accept any field change by default".** The agreed
  end-state: stop hand-judging which fields are "real content". Stewardship clock =
  full-payload diff minus a *tiny, fully-named* built-in volatile list (no `...`) and the
  operator's opt-in declaration; Liveness clock = a small allow-list read (`state.open`,
  declared sensors) that drives the green dot and bumps a separate `last_live_at`, never
  `updated_at`. NOTE the trap: diffing genuinely per-fetch-changing VALUES (temperature
  drift, per-fetch `lastchange`) pegs `updated_at` to "0m" forever — a *stable* `state.open`
  does NOT (no diff vs prev snapshot), so state is safe to diff; volatile sensor *values*
  are not. `detect_diff` already returns a structured dict, so the volatile filter is
  additive. Also revisit the unnamed extras in `_IGNORED` — enumerate every excluded path
  or delete it (`pipeline_helpers.py:52`). Pairs with the liveness-optin above.
- **`state.message` is human prose, currently dropped.** Whole-`state` strip discards the
  operator's curated "closed for renovation till July" message along with the churny
  `open`/`lastchange`/`icon`. When the two-clock rework lands, go path-level so
  `state.message` survives into the stewardship diff.

## Deferred from: review of spec-fix-updated-unknown-liveness (2026-06-11)

- **`_updated_at_absent` ASK fires on every unchanged-content heartbeat cycle forever.** After the one-time backfill has fired, the predicate is present and the write is skipped, but the ASK query still executes each cycle for every space that never changes content. At demo scale (hundreds of spaces) this is negligible; at production scale it adds one SPARQL round-trip per unchanged space per 10-min tick. Fix: cache a per-uid "backfill done" flag in snapshot_store (a nullable column) so the ASK is skipped once the backfill is confirmed. `pipeline.py` / `snapshot_store.py`. → Story 4.x (Epic 4 pipeline work).

## Deferred from: code review of story-6.0 (2026-06-16)

- No allowlist / access control on `!mom` commands — any Matrix user on any federated server can invite/message the bot, and every message triggers a billed LLM completion call. `harness/matrix_adapter.py`, `harness/main_matrix.py`. Deferred: out of scope for Story 6.0 spine; revisit before any public/federated rollout.
- Router's `unknown_ack()` response is identical for recognized-but-unimplemented intents (`write`/`query`/`nl_discovery`) and genuinely `unknown` ones — misleading wording, but acceptable until Epic 6.1+ skillsets exist. `harness/router.py`. → Epic 6.1+.
- No automated tests for `router.py`, `matrix_adapter.py`, `main_matrix.py`, or `bernard.py` — only `Message` dataclass and `intent_classifier` are covered. `harness/tests/`.
- `config.py`/`bernard.py` module-level caching (`_config`/`_voice`) has no concurrency guard against concurrent first-call races. `harness/config.py`, `harness/bernard.py`.
- Dendrite Postgres credentials are split across `.env` (`DENDRITE_DB_PASSWORD`) and a gitignored `dendrite.yaml`, with no documented sync process. `infra/docker-compose.yml`.
- No regression test added for either bug fixed in Story 6.0's commit (env-var vs config.yaml precedence, bogus `gemma-4-12b-it` model id) — could silently regress. `harness/main_matrix.py`, `harness/config.py`.
- Malformed YAML in `config.yaml`/`bernard_voice.yaml` crashes startup uncaught instead of failing gracefully. `harness/config.py`, `harness/bernard.py`.

## Deferred from: code review of 6-4-nl-sparql-natural-language-iop-ontology (2026-06-24)

- **W1 `main_matrix.py:38-40` @bernard stub** — intercepts `@bernard` mentions before `route()` is called; NL dispatch unreachable until fixed. Self-reported by dev agent; fix = replace early-return with `route()` call stripping `@bernard` prefix.
- **W2 `complete_with_system` default `temperature=1.0`** — latent footgun; callers currently pass `0.0` explicitly so no current bug. Should default to `0.0` or remove default.
- **W3 `AsyncOpenAI` client instantiated per call** — no connection pooling; pre-existing pattern from `complete()`. Low-traffic bot tolerates it; fix if throughput becomes a concern.
- **W4 FORBIDDEN regex false positives on SPARQL string literals** — regex matches forbidden words inside quoted values (e.g., `FILTER(?x = "ADD makerspace")`). Proper fix = SPARQL AST parsing. Pre-existing limitation of the string-scan approach.
- **W5 `_ONTOLOGY_CACHE` race condition** — concurrent `dispatch()` calls before cache is warm trigger N simultaneous CONSTRUCT queries. Double-load only, no data corruption. Matrix bot is effectively single-threaded per room.

## Deferred from: code review of 6-3-read-query-command-set-isochrone-tool (2026-06-18)

- `sparql_client.run_select` uses total timeout 15s instead of read-only timeout 15s as specified in spec §3 — minor, `httpx.Timeout(15.0, connect=5.0)` vs intended `httpx.Timeout(connect=5.0, read=15.0)`. `harness/sparql_client.py:17`.
- ORS timeout is 20s in code vs 15s stated in changelog — minor inconsistency. `harness/isochrone.py`.

## Deferred from: sanity-check of PR #18's "12 pre-existing test failures" claim (2026-07-01)

Fixed as part of this investigation (not deferred): `tests/test_spaceapi_extract_e2e.py`'s materializer test was calling deleted `scripts/materialize_geojson.py` via subprocess, failing silently and falling back to stale `web/data/spaces.geojson` — repointed to the live `_rematerialize_geojson()` in `infra/link_handler/main.py`, same pattern as `test_materializer_three_tokens.py::_materialize_spaces`. Also fixed `tests/test_geocode_proxy.py`'s `BASE_URL`, which hardcoded `localhost:8000` — `mak-link-handler` only `expose`s that port internally (never `ports`-published, by design), so all 4 tests were failing on connection-refused regardless of stack state. Repointed through nginx (`GEOCODE_BASE_URL` env, default `localhost:8080` for dev). Both fixes verified live with the podman stack up.

Two real gaps surfaced, not fixed here — need their own decision/story:

- **No nginx rate-limit zone for `/api/geocode`.** `test_geocode_nginx_rate_limit` expects an `limit_req_zone`/`geocode_limit` (2r/s, burst 5, nodelay) enforcing abuse protection on the geocode proxy — grepping `infra/nginx/conf.d/*.conf` finds no such zone configured anywhere. This isn't a stale test; the feature it's asserting was apparently never implemented (or was removed without the test being updated). `/api/geocode` currently has no rate limiting at all. Needs: either add the `limit_req_zone` to nginx config, or consciously decide it's not needed yet and mark the test `xfail`/skip with a reason.
- **4 canary/materializer live tests fail for real once Oxigraph is actually up** (previously they silently skipped when Oxigraph was unreachable, masking this): `test_axis_b_ages_independently_when_content_unchanged`, `test_axis_c_flips_independently_on_open_now_change` (`tests/test_canary_three_axis_e2e.py`), `test_three_tokens_all_present`, `test_observed_at_from_sqlite_not_oxigraph` (`tests/test_materializer_three_tokens.py`). Not yet root-caused — could be genuine regressions in the three-token freshness model ([[project_three_token_freshness_model]]) or stale test fixtures/seed data. Needs investigation before Epic 6 spike work assumes these are green.
