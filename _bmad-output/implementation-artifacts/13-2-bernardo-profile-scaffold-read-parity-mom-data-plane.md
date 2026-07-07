# Story 13.2: Bernardo Profile Scaffold + Read Parity (MoM data plane)

Status: ready-for-dev

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

- [ ] Task 1: Harden MoM oxigraph exposure (AC: 1)
  - [ ] Probe `mapsofmaking.org:7878` from outside VPS (e.g. `curl -m 5 http://mapsofmaking.org:7878/query` + `nc -zv`), record finding
  - [ ] Remove `ports: - "7878:7878"` from oxigraph service in `infra/docker-compose.yml` (keep `expose`), fix the stale comment if needed
  - [ ] Deploy via `make publish` + recreate stack on VPS; verify container network intact
  - [ ] Live checks: `/sparql/query` 200, `/sparql/update` 403, external 7878 closed, heartbeat/link-handler/nginx healthy
- [ ] Task 2: Probe public endpoint contract from hermes container (AC: 2)
  - [ ] GET `?query=` and POST forms against `https://mapsofmaking.org/sparql/query` from inside `openfab-hermes`
  - [ ] Record method/CORS findings; adjust nginx or document required curl form in mom-vocab.md if mismatch
- [ ] Task 3: Configure bernardo profile (AC: 3)
  - [ ] Add `GRAPH_ENDPOINT=https://mapsofmaking.org/sparql` to `profiles/bernardo/.env`
  - [ ] `config.yaml`: `personality: bernardo` (stub), confirm matrix enabled + E2EE
  - [ ] SOUL.md header note: persona pending 13.3
- [ ] Task 4: Skill symlink + vocab stub (AC: 4, 5)
  - [ ] Create `profiles/bernardo/skills/oxigraph-query/` with `SKILL.md` symlink → shared SSOT (use plain `cp`/`ln -s` semantics; restart hermes after adding files — SELinux `:Z` start-time relabel)
  - [ ] Verify live discovery queries against MoM store, then write `references/mom-vocab.md` (prefixes from mom.ttl, graph shape, 2–3 verified query shapes, cartridge-deferral header)
  - [ ] Cleanup: fix manny's stale local `references/` dir (13.1 carry-over)
  - [ ] `ls -la` proof of symlinks
- [ ] Task 5: Live done gate (AC: 6, 7, 8)
  - [ ] Encrypted-room Matrix run with `@bernardo`; if E2EE misbehaves, apply device-corruption recovery (logout+relogin+purge crypto.db — see Dev Notes) before debugging elsewhere
  - [ ] Cross-check answer vs direct Oxigraph ground-truth query; capture transcript + query
  - [ ] Negative test: `GRAPH_ENDPOINT` removed → loud STOP, no query, no fabrication
  - [ ] Spot-check frozen harness Bernard still answers on `@bernard` (untouched)
- [ ] Task 6: Documentation + handoff (AC: all)
  - [ ] Completion Notes: port-probe finding, endpoint-contract finding, dev-tooling casualties (AC 1.4), 13.3/13.4 handoffs

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

### Debug Log References

### Completion Notes List

### File List
