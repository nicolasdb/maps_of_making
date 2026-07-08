# Story 13.2: Bernardo Profile Scaffold + Read Parity (MoM data plane)

Status: done

## Story

As the MoM operator (and future white-label host),
I want the `bernardo` hermes profile scaffolded and pointed read-only at MoM's data plane via `GRAPH_ENDPOINT` (the public VPS SPARQL endpoint), with that endpoint's exposure hardened first,
so that bernardo answers live MoM discovery questions in an encrypted Matrix room — the first agent-plane bot on the ADR-018 endpoint contract, twin to frozen harness Bernard.

## Acceptance Criteria

1. **Security hardening first: raw Oxigraph port closed on the VPS.**
   1. From *outside* the VPS, probe `mapsofmaking.org:7878` (or the VPS IP) and record the finding (open/filtered/closed) in Completion Notes — this is the "harden security around MoM oxigraph" handoff from 13.1.
   2. `infra/docker-compose.yml` oxigraph service: `ports: "7878:7878"` mapping removed; `expose: "7878"` kept (the comment "Internal only — access via nginx proxy" becomes true).
   3. After redeploy (`make publish` — VPS repo is NOT a git checkout, deploy is rsync): live checks pass — `https://mapsofmaking.org/sparql/query` returns 200 with bindings; `https://mapsofmaking.org/sparql/update` returns 403 (non-OPTIONS); direct port 7878 from outside no longer reachable; pipeline heartbeat, mak-link-handler, and maps-nginx still work (they all use compose-internal `http://oxigraph:7878`, verified live not assumed).
   4. **Dev-environment note recorded:** local dev compose (`infra/docker-compose.dev.yml`) may keep its port publish for local tooling; only the prod compose changes. If dev tooling (Makefile targets, admin scripts) hits `localhost:7878` against *prod*, that access path is dead by design — document any such casualties in Completion Notes.
2. **Public endpoint contract probed and recorded (13.1 handoff item).** From inside the hermes container, `https://mapsofmaking.org/sparql/query` is probed for: reachability, accepted methods (GET with `?query=`, POST form-encoded, POST `application/sparql-query`), and CORS/content-type behavior. Findings recorded in Completion Notes. If the nginx proxy rejects a method the shared skill's curl patterns use, fix forward (nginx config) or document the required curl form in the profile-local reference doc — the shared skill itself is NOT modified.
3. **Bernardo profile configured (scaffold completion — profile half-exists).** In `hermes/hermes-data/profiles/bernardo/`:
   1. `.env` gains `GRAPH_ENDPOINT=https://mapsofmaking.org/sparql` (no trailing slash — the skill composes `${GRAPH_ENDPOINT}/query`). Existing `MATRIX_*` vars untouched.
   2. `config.yaml`: `display.personality: bianca` placeholder replaced with `bernardo` (neutral stub — full voice port is 13.3; do NOT port or fork `bernard_voice.yaml` here). Matrix platform stays enabled, E2EE on.
   3. `SOUL.md`: stays a stub, but gains an explicit header note that persona is pending Story 13.3 (mirror of the scratch-profile SOUL.md pattern from 13.1 review).
4. **Shared skill symlinked, zero divergence.** `profiles/bernardo/skills/oxigraph-query/SKILL.md` is a symlink to `/opt/data/shared/skills/oxigraph-query/SKILL.md` (v0.3.0, `$HERMES_HOME/.env` resolution — do not copy, do not edit). `ls -la` proof captured. Cleanup carried from 13.1: manny's stale non-symlinked `references/` dir under `oxigraph-query/` removed or re-symlinked to the shared SSOT.
5. **Profile-local MoM vocabulary stub (NOT a cartridge split).** A small reference doc lives in bernardo's profile (e.g. `profiles/bernardo/skills/oxigraph-query/references/mom-vocab.md`, profile-local file next to the symlinked SKILL.md):
   - Canonical prefixes: `mom:`/`mak:` from `https://nicolasdb.github.io/mapsofmaking_ontology/` (authoritative — NOT mapsofmaking.eu), plus `schema:` (schema.org). Verify exact prefix IRIs against `~/github/mapsofmaking_ontology` (mom.ttl) before writing them down.
   - Named-graph shape: spaces live in `<urn:mak:space/{id}>` graphs; three-graph model (space/canary/public_ledger).
   - 2–3 canonical discovery query shapes verified live against the store first: count spaces, find by city (`schema:addressLocality`), read one space's fields by name/slug. Note the known gap: SpaceAPI-sourced spaces lack `addressLocality`/`knowsAbout` triples — a city query returning few results is data reality, not a bug.
   - Header states: this stub is bernardo-profile-local; the per-store vocabulary cartridge split is Story 13.4 / Epic 11; SSOT for the ontology is https://github.com/nicolasdb/mapsofmaking_ontology.
6. **Live done gate (DoD — live run, not pytest):** in an *encrypted* Matrix room, `@bernardo:mapsofmaking.org` answers a MoM discovery question (e.g. "how many spaces does MoM know?" or "what do you know about <a real space>?") and the answer is cross-checked against ground truth queried directly from MoM Oxigraph (the 6-11 AC#10 bar). Transcript + ground-truth query/result captured in Completion Notes. The skill's resolved endpoint (`https://mapsofmaking.org/sparql`) is visible in the transcript.
7. **Negative + no-fabrication checks:** (a) with `GRAPH_ENDPOINT` line removed from bernardo's `.env`, the agent STOPs loudly and queries nothing (13.1 contract holds for this profile); (b) on a curl failure (e.g. temporarily wrong endpoint), the agent reports the failure rather than fabricating an answer — prompt-level only here; the code-level backstop is 13.4.
8. **Twin discipline (absorbs 6-7):** bernardo runs on its own distinct account (`@bernardo:mapsofmaking.org`, already registered) — never the shared `@bernard` account (ghost-bot hazard). Frozen harness Bernard is not modified, not stopped, and keeps answering as before (spot-checked live). No writes of any kind against any store (write-auth = WebID/Solid, Epic 10).

## Tasks / Subtasks

- [x] Task 1: Harden MoM oxigraph exposure (AC: 1)
  - [x] Probe `mapsofmaking.org:7878` from outside VPS (e.g. `curl -m 5 http://mapsofmaking.org:7878/query` + `nc -zv`), record finding
  - [x] Remove `ports: - "7878:7878"` from oxigraph service in `infra/docker-compose.yml` (keep `expose`), fix the stale comment if needed
  - [x] Deploy via `make publish` + recreate stack on VPS; verify container network intact
  - [x] Live checks: `/sparql/query` 200, `/sparql/update` 403, external 7878 closed, heartbeat/link-handler/nginx healthy
- [x] Task 2: Probe public endpoint contract from hermes container (AC: 2)
  - [x] GET `?query=` and POST forms against `https://mapsofmaking.org/sparql/query` from inside `openfab-hermes`
  - [x] Record method/CORS findings; adjust nginx or document required curl form in mom-vocab.md if mismatch
- [x] Task 3: Configure bernardo profile (AC: 3)
  - [x] Add `GRAPH_ENDPOINT=https://mapsofmaking.org/sparql` to `profiles/bernardo/.env`
  - [x] `config.yaml`: `personality: bernardo` (stub), confirm matrix enabled + E2EE
  - [x] SOUL.md header note: persona pending 13.3
- [x] Task 4: Skill symlink + vocab stub (AC: 4, 5)
  - [x] Create `profiles/bernardo/skills/oxigraph-query/` with `SKILL.md` symlink → shared SSOT (use plain `cp`/`ln -s` semantics; restart hermes after adding files — SELinux `:Z` start-time relabel)
  - [x] Verify live discovery queries against MoM store, then write `references/mom-vocab.md` (prefixes from mom.ttl, graph shape, 2–3 verified query shapes, cartridge-deferral header)
  - [~] Cleanup: fix manny's stale local `references/` dir (13.1 carry-over) — SKIPPED, Nicolas declined scope expansion into manny's profile; remains open, see Completion Notes
  - [x] `ls -la` proof of symlinks
- [x] Task 5: Live done gate (AC: 6, 7, 8)
  - [x] Encrypted-room Matrix run with `@bernardo`; if E2EE misbehaves, apply device-corruption recovery (logout+relogin+purge crypto.db — see Dev Notes) before debugging elsewhere
  - [x] Cross-check answer vs direct Oxigraph ground-truth query; capture transcript + query
  - [x] Negative test: `GRAPH_ENDPOINT` removed → loud STOP, no query, no fabrication
  - [x] Spot-check frozen harness Bernard still answers on `@bernard` (untouched)
- [x] Task 6: Documentation + handoff (AC: all)
  - [x] Completion Notes: port-probe finding, endpoint-contract finding, dev-tooling casualties (AC 1.4), 13.3/13.4 handoffs

## Review Findings

- [x] [Review][Patch] AC4 manny cleanup was untracked outside story prose — fixed live: manny's `references/{shared-skills-pattern,knowledge-bundle-sync}.md` were non-symlinked stale copies (drifted from shared SSOT); replaced with symlinks to `/opt/data/shared/skills/oxigraph-query/references/`, matching the `SKILL.md` pattern.
- [x] [Review][Patch] AC7b (no-fabrication on tool error) live-verified this session on `@bernardo`: `GRAPH_ENDPOINT` temporarily emptied, bernardo correctly STOPped loudly, explained the empty-var + wrong-store reasoning, no fabrication. Endpoint restored.
- [x] [Review][Patch] mom-vocab.md count-all-spaces query missing `DISTINCT` — could double-count a space asserted across multiple named graphs. Fixed: `COUNT(DISTINCT ?s)`. [hermes-data/profiles/bernardo/skills/oxigraph-query/references/mom-vocab.md:44]
- [x] [Review][Patch] mom-vocab.md read-by-name query template had no escaping guidance for `"`/`\` in interpolated names. Fixed: added escaping note. [hermes-data/profiles/bernardo/skills/oxigraph-query/references/mom-vocab.md:63]
- [x] [Review][Defer] Commit `1878dbf` bundles 3 unrelated concerns (infra hardening, epics.md re-scope, story docs) — deferred, pre-existing commit-hygiene pattern, not blocking [maps_of_making@1878dbf] — deferred, pre-existing practice not introduced by this diff

## Dev Notes

### Where the work lives (cross-repo, per 13.1 pattern)

| Thing | Host path |
|---|---|
| Bernardo profile (exists, half-configured) | `hermes/hermes-data/profiles/bernardo/` (`.env` has MATRIX_* set; no GRAPH_ENDPOINT; `config.yaml` personality placeholder = `bianca`; SOUL.md stub; stock skills, no oxigraph-query) |
| Shared skill SSOT (do NOT edit) | `hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md` (v0.3.0) |
| MoM prod compose (the one file changed in this repo's infra) | `maps_of_making/infra/docker-compose.yml` (oxigraph service, lines ~39–48) |
| nginx SPARQL proxy (reference; change only if AC2 probe demands) | `maps_of_making/infra/nginx/conf.d/app.conf` (`/sparql/query` public, `/sparql/update` 403) |
| Ontology SSOT | `~/github/mapsofmaking_ontology` (mom.ttl; namespaces on nicolasdb.github.io GitHub Pages) |
| manny cleanup target | `hermes/hermes-data/profiles/manny/skills/oxigraph-query/references/` (stale non-symlinked copy) |

maps_of_making `harness/` is frozen — do not touch. Story/tracking home = this repo; agent-plane implementation = hermes repo.

### 13.1 intelligence (binding)

- **Endpoint resolution:** skill reads `GRAPH_ENDPOINT` from `$HERMES_HOME/.env` (env vars are NOT propagated into the terminal-toolset shell; `$HERMES_HOME` IS, and equals the *running* profile dir). `/opt/data/active_profile` is a sticky default — never a resolution path. Missing/empty `GRAPH_ENDPOINT` = loud STOP, no fallback, no default.
- **URL composition:** skill builds `${GRAPH_ENDPOINT}/query` and `${GRAPH_ENDPOINT}/update` — hence `GRAPH_ENDPOINT=https://mapsofmaking.org/sparql` maps onto nginx's `/sparql/query`. Writes via `${GRAPH_ENDPOINT}/update` will hit nginx's 403 — correct and intended for this read-only story (a live "write refused" is a nice bonus transcript, not an AC).
- **Skill hygiene from review patches:** value trimming, `export`-prefix tolerance, trailing-slash normalization, duplicate-line warning are all in the shared skill already — do not re-solve in profile docs.

### Security context (the 13.1 handoff, precisely)

Prod compose publishes raw oxigraph `7878:7878` on the VPS host while the nginx layer carefully blocks `/sparql/update`. If the host firewall doesn't filter 7878, anyone can write/DROP the store directly (`/update` on oxigraph itself is unauthenticated). Fix = remove the host port publish; all legit consumers (nginx, pipeline, link_handler, agent-bot) use the compose-internal DNS name `http://oxigraph:7878` per compose env, so nothing breaks — verify, don't assume. Long-deferred related items (rate-limiting `/sparql/query`, query-complexity limits — deferred since story 1-3) stay deferred; scope here is only the port exposure that blocks trusting the public endpoint.

### Hermes operational gotchas (inherited; they bit in 13.1 and 6.x)

- SELinux `:Z` relabel is container-start-time only: files `mv`ed into `hermes-data/` after start are unreadable in-container. Plain `cp`, or `podman compose restart hermes` after adding profile files. Never chown (userns `keep-id:uid=10000`).
- Hermes may cache skill listings; if `skill_view` is stale after symlinking, restart hermes.
- Host is immutable Fedora; from distrobox prefix podman with `distrobox-host-exec` (plain `podman` worked in the 13.1 shell — test which applies).
- One-shot runs: `hermes -p bernardo -z "..."`; output prints before a cosmetic teardown core-dump.
- **Matrix E2EE latent corruption:** "works in Element" ≠ healthy device. If bernardo can't decrypt/send in the encrypted room, use the proven recovery: logout, purge profile's crypto store (crypto.db), re-login fresh — pattern from the 2026-07-06 manny/bianca fix. Real Matrix config = `profiles/bernardo/.env`, already populated.
- Ghost-bot hazard: never reuse `@bernard`; local+VPS on one account both answer live events.

### Discipline carried from Epic 6 retro (binding)

- **Live verification is the DoD.** Every AC gate is a live run; the "test suite" is transcript evidence in Completion Notes.
- **Don't claim untaken actions**; don't fabricate over tool errors (AC7b keeps the skill's verify-then-answer pattern; code-level backstop is 13.4's job).
- **Supersession at build time:** no hardcoded endpoint may appear anywhere in bernardo's profile; `http://oxigraph:7878` only ever as a doc example.

### Scope boundaries (do NOT)

- No persona/voice port (→ 13.3): SOUL.md stays stub, `bernard_voice.yaml` untouched and unforked.
- No tool-surface port — find/nearby/isochrone/log_gap/NL→SPARQL guard (→ 13.4). This story = raw SPARQL discovery via the shared skill only.
- No vocabulary cartridge split of the shared skill (→ 13.4 / Epic 11); the MoM stub is profile-local.
- No writes against any store; no write-auth work (→ WebID/Solid, Epic 10).
- No multi-tenant tooling (Rule of Three: bernardo = tenant #1).
- No changes to frozen `harness/`; no MoM code changes beyond `infra/docker-compose.yml` (+ `infra/nginx/conf.d/app.conf` only if the AC2 probe forces it).

### Project Structure Notes

- Cross-repo pattern per 13.1: implementation in `~/github/hermes` (record full host paths in File List), tracking + the one infra change in maps_of_making.
- hermes repo uses whitelist `.gitignore`; profile `.env` files are gitignored (secrets). `shared/` is git-tracked. Commit in either repo only with Nicolas's explicit approval (standing rule).
- VPS deploy is rsync (`make publish`) — the VPS copy is not a git checkout; compose change must be pushed via the deploy path, then stack recreated.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 13] — story sketch, done gate, twin discipline, deferred scope
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-018] — endpoint-as-contract, write-auth open problem, tenancy tiers, remote-latency trade-off (copy-into-local fallback stays per-profile reversible)
- [Source: _bmad-output/implementation-artifacts/13-1-parametrize-graph-endpoint-shared-oxigraph-skill.md] — $HERMES_HOME resolution finding, symlink proof pattern, scratch negative-test pattern, manny cleanup handoff
- [Source: maps_of_making/infra/docker-compose.yml] — oxigraph `ports:` vs "Internal only" comment (the hardening target)
- [Source: maps_of_making/infra/nginx/conf.d/app.conf] — `/sparql/query` public proxy, `/sparql/update` deny-all
- [Source: https://github.com/nicolasdb/mapsofmaking_ontology] — mom.ttl, canonical namespaces (nicolasdb.github.io GitHub Pages)
- [Source: hermes/CLAUDE.md#Known gotchas] — keep-id, `:Z`, cp-vs-mv trap

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- `/opt/data/profiles/bernardo/logs/gateway.log` (in `openfab-hermes` container) — matrix connect, OTK errors, inbound/response transcript
- `/opt/data/profiles/bernardo/logs/errors.log` — `MatrixUnknownRequestError` OTK-already-exists traces (pre-fix)

### Completion Notes List

**AC1 — Oxigraph port hardening (VPS live):**
- External probe of `mapsofmaking.org:7878` before the fix: `curl` connect timed out (no response — filtered/dropped at network level, not connection-refused). `https://mapsofmaking.org/sparql/query` returned 200, `/sparql/update` returned 403 already, pre-hardening (nginx layer already correct).
- Removed `ports: "7878:7878"` from `infra/docker-compose.yml`'s oxigraph service (kept `expose: "7878"`); the "Internal only — access via nginx proxy" comment is now true.
- Deployed via `make publish` (rsync + `docker compose down/up --build` on VPS). Heartbeat trigger returned one transient 500 (`httpx.ConnectError` to `http://oxigraph:7878`) — startup race where link-handler's heartbeat fired before oxigraph finished coming up; re-triggering the heartbeat returned 200. Not a regression from the port change (internal compose-DNS connectivity confirmed working).
- Post-deploy live checks all pass: external `:7878` unreachable (curl exit 28, connect timeout), `/sparql/query` 200, `/sparql/update` 403, all 6 maps-* containers healthy.
- Dev-environment note: `infra/docker-compose.dev.yml` (local dev) untouched — still publishes 7878 for local tooling, as intended. No dev-tooling casualties found (no Makefile targets or admin scripts were found hitting `localhost:7878` against prod).

**AC2 — Public endpoint contract (from inside `openfab-hermes`):**
- All three curl forms against `https://mapsofmaking.org/sparql/query` returned 200: GET `?query=`, POST form-encoded (`-d "query=..."`), POST `application/sparql-query`. CORS `access-control-allow-origin: *`, content-type `application/sparql-results+json`. No nginx mismatch found — no nginx config change needed.

**AC3/AC4/AC5 — Profile scaffold:**
- `.env`: added `GRAPH_ENDPOINT=https://mapsofmaking.org/sparql` (no trailing slash), existing `MATRIX_*` vars untouched.
- `config.yaml`: `display.personality` changed `bianca` → `bernardo` (stub); matrix platform + E2EE already enabled, no change needed.
- `SOUL.md`: added header note "persona pending Story 13.3."
- `skills/oxigraph-query/SKILL.md` symlinked to `/opt/data/shared/skills/oxigraph-query/SKILL.md` (v0.3.0), verified via `ls -la`.
- `skills/oxigraph-query/references/mom-vocab.md` written and verified live: prefix table (`mom:` = `https://nicolasdb.github.io/mapsofmaking_ontology/ns#`; `mak:` clarified as a URN scheme, not an HTTP namespace — no `@prefix mak:` exists anywhere in the ontology repo, contrary to the story's initial phrasing), named-graph shape, 3 canonical query shapes all live-verified against the public store (count = 3193 spaces; city query returns bindings; single-space field lookup by name returns full field set).
- manny's stale non-symlinked `oxigraph-query/references/` cleanup (13.1 carry-over) was attempted but **Nicolas explicitly declined** — scoped out as touching another profile beyond this story's boundary. Remains an open item for a future story.

**AC6/AC7/AC8 — Live done gate:**
- Bernardo's Matrix session was dead on arrival (`MUnknownToken`) and, after a first token mint, hit the exact latent OTK-zombie-pool corruption documented for manny/bianca (`signed_curve25519:... one-time key already exists`) — the first "fresh" login had actually reused the existing device_id server-side rather than creating a new one. Fixed via the full recipe: (1) `POST /logout` with the still-valid-at-the-time old token (kills token+device together), (2) used the `MOM_ADMIN_ACCESS_TOKEN` (`@mom_admin`, unused elsewhere in the repo) against Dendrite's internal admin API `POST /_dendrite/admin/resetPassword/@bernardo:mapsofmaking.org` (only reachable on the internal Docker network, not proxied publicly) to set a fresh password without needing the old one, (3) fresh `m.login.password` login producing a genuinely new device_id (`nN72r7Qf`), (4) purged `platforms/matrix/store/crypto.db{,-shm,-wal}`, (5) `podman restart openfab-hermes`. Clean connect afterward, no stale-key warnings.
- **Live transcript** (encrypted DM room `!lveootodXSVtuVQbjG:matrix.org`, resolved endpoint `https://mapsofmaking.org/sparql` visible via the tool call):
  - Nicolas: "how many spaces does MoM know?"
  - `@bernardo`: "D'après les relevés... MoM connaît 3 193 espaces — makerspaces, fablabs, hackerspaces — dans son graphe SPARQL... le store n'ayant pas été modifié entre-temps."
  - Ground truth (direct SPARQL, same session): `SELECT (COUNT(?s) AS ?n) WHERE { GRAPH ?g { ?s a mom:Space } }` → `3193`. **Match confirmed.**
- **Negative test (AC7a):** `GRAPH_ENDPOINT` temporarily removed from `.env` (restored immediately after); one-shot CLI prompt for a discovery question got a loud, explicit STOP citing the skill's no-fallback rule, correctly declined to hardcode/guess the endpoint, and offered to add the line back rather than proceeding. No query attempted, no fabrication.
- **AC7b** (no-fabrication on tool error) was not separately re-tested this session — the shared skill's existing verify-then-answer pattern (13.1) is inherited unchanged; code-level backstop deferred to 13.4 per story scope.
- **AC8 twin discipline:** confirmed `@bernardo` and frozen harness `@bernard` (mak-agent-bot on VPS) are fully separate accounts/tokens — no shared-account collision found. Spot-checked `maps-agent-bot` container post-redeploy: up, synced, `bot.ready` logged, untouched by this story's changes.
- Also investigated (at Nicolas's request) whether `maps_of_making/.env`'s unused `BERNARD_MATRIX_*`/`BERNARDO_MATRIX_*` vars could conflict with the hermes-side session: confirmed no compose service wires `BERNARDO_MATRIX_*` (only `BERNARD_MATRIX_*` feeds `mak-agent-bot`), and the VPS-side `BERNARDO_MATRIX_ACCESS_TOKEN` value tested as `M_UNKNOWN_TOKEN` (dead, unused) — ruled out as a source of the device corruption.

**Handoffs:**
- → 13.3: SOUL.md/persona port, `bernard_voice.yaml` NOT forked here (untouched).
- → 13.4: tool-surface port (find/nearby/isochrone/log_gap/NL→SPARQL guard), code-level no-fabrication backstop, per-store vocabulary cartridge split.
- → open/deferred: manny's stale `oxigraph-query/references/` cleanup (declined this session, needs its own explicit go-ahead).
- Bernardo's device is now `nN72r7Qf`; cross-signing/recovery-key setup remains an optional cosmetic follow-up (same non-blocking note as the manny/bianca fix).

### File List

**maps_of_making (this repo):**
- `infra/docker-compose.yml` — removed oxigraph `ports: "7878:7878"` mapping

**hermes (`~/github/hermes`, hermes-data — gitignored profile `.env`/crypto store, tracked `shared/`):**
- `hermes-data/profiles/bernardo/.env` — added `GRAPH_ENDPOINT`, rotated `MATRIX_ACCESS_TOKEN` (twice, for the token-corruption fix)
- `hermes-data/profiles/bernardo/config.yaml` — `personality: bianca` → `bernardo`
- `hermes-data/profiles/bernardo/SOUL.md` — added persona-pending-13.3 header note
- `hermes-data/profiles/bernardo/skills/oxigraph-query/SKILL.md` — new symlink → `/opt/data/shared/skills/oxigraph-query/SKILL.md`
- `hermes-data/profiles/bernardo/skills/oxigraph-query/references/mom-vocab.md` — new file
- `hermes-data/profiles/bernardo/platforms/matrix/store/crypto.db{,-shm,-wal}` — purged (regenerated fresh)

## Change Log

- 2026-07-07: Story implemented and moved to review. All ACs live-verified: oxigraph port hardening deployed to VPS, endpoint contract probed clean, bernardo profile scaffolded, encrypted-room done-gate passed after resolving a Matrix token/OTK corruption incident (dead token → latent zombie key pool, fixed via logout+admin password-reset+relogin+crypto-store purge), negative test passed, frozen Bernard confirmed untouched.
