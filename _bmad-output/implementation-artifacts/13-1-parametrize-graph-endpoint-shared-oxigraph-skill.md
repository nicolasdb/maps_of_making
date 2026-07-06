# Story 13.1: Parametrize the Graph Endpoint (shared oxigraph-query skill)

Status: ready-for-dev

## Story

As the MoM operator (and future white-label host),
I want the shared `oxigraph-query` hermes skill to resolve its SPARQL endpoint from per-profile configuration (`GRAPH_ENDPOINT`) instead of the hardcoded `http://oxigraph:7878`,
so that one shared skill can serve bianca→OpenFab store and bernardo→MoM store (the ADR-018 endpoint-as-contract enabling change for all of Epic 13).

## Acceptance Criteria

1. **Env propagation verified first (spike gate).** It is confirmed, by a live test inside the running hermes container, whether a variable set in `profiles/<bot>/.env` (e.g. `GRAPH_ENDPOINT=...`) is visible in the terminal-toolset shell where the agent runs `curl`. The finding (yes/no + mechanism) is recorded in this story's Completion Notes. If NOT propagated, the fallback resolution mechanism in AC2 is used and documented in the skill.
2. **Skill reads `GRAPH_ENDPOINT`, never a hardcoded host.** `hermes-data/shared/skills/oxigraph-query/SKILL.md` instructs the agent to resolve the endpoint base URL in this order:
   - `$GRAPH_ENDPOINT` from the environment, if hermes propagates profile env (AC1 finding);
   - otherwise read `GRAPH_ENDPOINT=` from `/opt/data/profiles/<active-profile>/.env` (active profile name is in `/opt/data/active_profile`);
   - if neither yields a value, **STOP and tell the user `GRAPH_ENDPOINT` is unset for this profile** — no hardcoded default, no silent fallback, no guessed endpoint. The skill must never query a store the profile didn't explicitly configure (ADR-018: endpoint is per-profile env, never baked in the skill).
   All four endpoint URLs in the skill (`/query`, `/update`, `/store?default`, and the curl import example) are expressed relative to the resolved base (e.g. `${GRAPH_ENDPOINT}/query`).
3. **`GRAPH_ENDPOINT` set in bianca's profile env.** `profiles/bianca/.env` gains `GRAPH_ENDPOINT=http://oxigraph:7878` (explicit, even though it matches the old default). manny's profile gets the same line (it also symlinks the skill).
4. **Scratch profile hits a different store.** A scratch/test profile exists with the same shared-skill symlink and a `GRAPH_ENDPOINT` pointing at a *different* SPARQL store (see Dev Notes for the second-store options). Given the same skill file, the scratch profile's queries land on the second store, not OpenFab's.
5. **Live done gate (DoD, per Epic 6 retro discipline — green tests ≠ working bot):** in live Matrix (or hermes session) runs, bianca answers a query whose result can only come from the OpenFab store, and the scratch profile answers a query whose result can only come from the second store — same shared `SKILL.md`, zero per-profile skill divergence (symlinks intact, `ls -la` proof captured).
6. **No regression for bianca.** bianca's existing OpenFab graph workflow (FAQ/segment queries) still works after the change — verified live, not assumed.
7. **bernardo untouched.** No `oxigraph-query` symlink is added to `profiles/bernardo/` in this story (that is Story 13.2's scaffold work). Frozen harness Bernard (maps_of_making `harness/`) is not modified at all.

## Tasks / Subtasks

- [ ] Task 1: Verify env propagation (AC: 1)
  - [ ] Start/confirm hermes stack up (`podman compose up -d` in `~/github/hermes`; from distrobox prefix `distrobox-host-exec`)
  - [ ] Add `GRAPH_ENDPOINT=http://oxigraph:7878` to `profiles/bianca/.env`
  - [ ] Restart hermes (`podman compose restart hermes` — also re-applies `:Z` SELinux labels), open a bianca session, have the agent run `echo $GRAPH_ENDPOINT` via the terminal toolset
  - [ ] Record result (propagated / not propagated) — this decides which resolution branch the skill leads with
- [ ] Task 2: Rewrite endpoint sections of shared SKILL.md (AC: 2)
  - [ ] Edit `hermes-data/shared/skills/oxigraph-query/SKILL.md`: add an "Endpoint resolution" section near the top (before « Endpoints »), replace the hardcoded table + curl examples with `${GRAPH_ENDPOINT}`-relative forms
  - [ ] Update Pitfall #1 (« `localhost` ne marche pas — utiliser `oxigraph` ») → now: endpoint comes from profile env; `oxigraph` hostname only valid for stores on the same compose network
  - [ ] Loosen the frontmatter `description` and Overview so the OpenFab-specific ontology content is clearly labeled as *the OpenFab store's vocabulary* (do NOT delete it — vocabulary-cartridge split is deferred, see Dev Notes)
  - [ ] Keep file in French, keep existing structure/tone — this is bianca's working skill
- [ ] Task 3: Set profile envs (AC: 3)
  - [ ] `GRAPH_ENDPOINT=http://oxigraph:7878` in `profiles/bianca/.env` (done in Task 1) and `profiles/manny/.env`
- [ ] Task 4: Scratch profile against second store (AC: 4)
  - [ ] Stand up second SPARQL store (recommended: throwaway local oxigraph on another port — see Dev Notes; seed 2-3 distinctive triples so provenance of answers is unambiguous)
  - [ ] Create scratch profile (clone minimal profile dir or use `hermes-profile-admin` skill in manny's profile if it covers creation), symlink shared skill per `references/shared-skills-pattern.md`: `mkdir -p profiles/<scratch>/skills/oxigraph-query && ln -s /opt/data/shared/skills/oxigraph-query/SKILL.md profiles/<scratch>/skills/oxigraph-query/SKILL.md` (container-side path in the link target)
  - [ ] Set scratch `GRAPH_ENDPOINT` to the second store's URL
- [ ] Task 5: Live done gate (AC: 5, 6)
  - [ ] bianca: run an OpenFab-only query live (e.g. a `openfab:Submission` or FAQ lookup returning OpenFab-specific content — do NOT assert the exact counts written in SKILL.md ("34 soumissions", "19 questions"), those are a snapshot from skill-authoring time and bianca has imported since; provenance = content, not count)
  - [ ] scratch: run a query returning the distinctive seeded triples, confirm second store answered
  - [ ] Negative case: profile with `GRAPH_ENDPOINT` unset (scratch, line removed) → skill stops loudly and says endpoint unset; agent queries nothing, fabricates nothing
  - [ ] Capture both transcripts + `ls -la` of both skill dirs into Completion Notes
- [ ] Task 6: Documentation (AC: 2)
  - [ ] Update `shared/skills/oxigraph-query/references/shared-skills-pattern.md` with a short "per-profile env vars" section (skill shared, endpoint per-profile — the ADR-018 contract)
  - [ ] Note env-propagation finding + second-store choice in Completion Notes for 13.2 to inherit

## Dev Notes

### Where the work lives

**This story's files are in the hermes repo, NOT maps_of_making**: `/var/home/nicolas/github/hermes/` (host path). Container-side, `./hermes-data` mounts at `/opt/data`. maps_of_making repo is only the story/tracking home; do not touch `harness/`.

| Thing | Host path |
|---|---|
| Shared skill (the file to edit) | `hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md` |
| Symlink pattern doc | `.../oxigraph-query/references/shared-skills-pattern.md` |
| Profile envs | `hermes/hermes-data/profiles/{bianca,manny,bernardo}/.env` |
| Active profile marker | `hermes/hermes-data/active_profile` (currently `bianca`) |
| Hermes compose | `hermes/docker-compose.yml` (services: `oxigraph` = openfab-oxigraph, `hermes`) |

Symlink state today: bianca and manny symlink `SKILL.md → /opt/data/shared/skills/oxigraph-query/SKILL.md`; bernardo has **no** oxigraph-query dir (keep it that way, AC7).

### Current SKILL.md state (what changes, what must survive)

`SKILL.md` v0.2.0 is **prose instructions to the agent, not code** — the agent composes `curl` commands from it via the terminal toolset. "Parametrizing" means rewriting the instructions so the agent resolves the base URL before building any curl. Hardcoded `http://oxigraph:7878` appears in: the Endpoints table (3 rows: `/query`, `/update`, `/store?default`) and the Turtle-import curl example. All must become `${GRAPH_ENDPOINT}`-relative.

**Must survive unchanged:** the OpenFab ontology documentation (prefixes, segments table, FAQ/Submission shapes, requêtes types, procedure, pitfalls 2-6, verification checklist). That content is bianca's operational knowledge. Splitting vocabulary out of the skill into per-store "cartridges" is the Epic 11/13.4 track — explicitly NOT this story. Just label the ontology sections as OpenFab-store-specific.

### The env-propagation unknown (why AC1 is first)

Hermes consumes `profiles/<bot>/.env` for its own config (`MATRIX_*` vars live there — confirmed the real config path in the 2026-07-06 device-corruption fix). **Unconfirmed:** whether arbitrary vars from that file are exported into the shell the terminal toolset uses. Do not assume either way — test it (Task 1). Both branches are fine: if propagated, skill says "use `$GRAPH_ENDPOINT`"; if not, skill says "read `GRAPH_ENDPOINT` from `/opt/data/profiles/$(cat /opt/data/active_profile)/.env`". The file-read fallback works regardless, so it belongs in the skill as the robust path either way.

### Second store for the done gate — pick one

Recommended: **throwaway local oxigraph on another host port.** `podman run -d --rm -p 7879:7878 oxigraph/oxigraph:latest serve --location /tmp/scratch-graph --bind 0.0.0.0:7878` (or add a `scratch-oxigraph` service to hermes compose on the same network — then `GRAPH_ENDPOINT=http://scratch-oxigraph:7878` and no host-networking question at all; **this compose-service variant is the cleanest**). Seed it with a few distinctive triples via `curl -X POST -H 'Content-Type: text/turtle' --data-binary @seed.ttl http://localhost:7879/store?default`.

**Traps:**
- **Port collision:** MoM dev compose (`maps_of_making/infra/docker-compose.dev.yml`) also publishes `7878:7878`, same as hermes' openfab-oxigraph. Don't try to run both stacks with default ports simultaneously.
- **Reaching a host port from inside the hermes container** (rootless podman): `localhost` inside the container is the container. Use `host.containers.internal` — but the compose-network service variant avoids this entirely.
- Pointing scratch at MoM's **public VPS** `/sparql` (maps-nginx proxies to maps-oxigraph per `infra/docker-compose.yml` comments) previews the 13.2 remote-endpoint reality, but (a) its public reachability/method (GET vs POST query) is **unverified from here** — probe with curl from the hermes container before relying on it, and (b) it adds network variables to a story whose point is just "two stores, one skill." Bonus check, not the primary gate.

### Hermes operational gotchas (inherited, will bite)

- **SELinux `:Z` relabel is start-time only** (Fedora Kinoite + podman): a file `mv`/`cp -a`/drag-dropped into `hermes-data/` after container start keeps `user_home_t` and is unreadable in-container. Use plain `cp`, or `podman compose restart hermes` after adding files (scratch profile dir, seed files!).
- **`userns_mode: keep-id:uid=10000`** — never chown/chmod hermes-data to "fix" access; that's the SELinux problem above, not perms.
- Host is immutable Fedora; from distrobox, prefix podman commands with `distrobox-host-exec`.
- Shared-skill edits are visible to all profiles immediately (symlink), but hermes may cache skill listings (`.bundled_manifest`, curator state) — if `skill_view` shows stale content, restart hermes.
- Curator only manages `created_by: "agent"` skills — it won't fight these edits.

### Discipline carried from Epic 6 retro (binding on this epic)

- **Live verification is the DoD.** Every AC gate here is a live run, not a unit test. There is no pytest surface in this story — the "test suite" is the transcript evidence in Completion Notes.
- **Don't claim untaken actions:** when writing skill prose, keep the existing pattern of verification steps (HTTP 200, non-empty bindings) so the agent checks rather than fabricates over curl failures — Epic 6 had 4 recurrences of LLM-fabricates-over-tool-error; the code-level backstop is 13.4's job, but don't make it worse here.
- **Enforce supersession at build time:** the old hardcoded endpoint must not survive anywhere (the `nl_to_sparql`/`agent.py` drift lesson). Strict contract: unset `GRAPH_ENDPOINT` = loud stop, never a silent default. `http://oxigraph:7878` may appear only as an *example value* in docs, never as a resolution branch.

### Scope boundaries (do NOT)

- No bernardo profile scaffold, no MoM-store queries from bernardo (→ 13.2).
- No persona/voice work (→ 13.3), no tool-surface port (→ 13.4).
- No writes against any remote store; write endpoints stay documented but write-auth is blocked on WebID/Solid (ADR-018, Epic 10).
- No multi-tenant tooling, no `networks/*.yaml` manifests (Rule of Three — bernardo will be tenant #1, extract at #3).
- No maps_of_making code changes at all; sprint tracking + this story file are the only changes in this repo.

### Project Structure Notes

- Story artifact lives in maps_of_making `_bmad-output/implementation-artifacts/` per BMAD convention; implementation lives in the sibling `hermes` repo — first Epic 13 story establishing this cross-repo pattern. Record hermes-side file list in File List with full host paths.
- `hermes/hermes-data/shared/` is the shared-skill SSOT; `shared-skills-pattern.md` itself says shared/ should ideally be git-versioned — check `git -C ~/github/hermes status` before/after; commit only with Nicolas's explicit approval (standing rule).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 13] — story sketch + done gate wording
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-018] — endpoint-as-contract, "the landmine" paragraph, tenancy tiers, trade-offs (remote-latency / copy-into-local fallback stays per-profile reversible)
- [Source: _bmad-output/implementation-artifacts/epic-6-retro-2026-07-06.md] — build-vs-buy finding, live-DoD discipline, supersession-at-build-time lesson
- [Source: hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md] — file under change (v0.2.0)
- [Source: hermes/hermes-data/shared/skills/oxigraph-query/references/shared-skills-pattern.md] — symlink procedure to replicate for scratch profile
- [Source: hermes/docker-compose.yml] — oxigraph + hermes services, SELinux notes
- [Source: hermes/CLAUDE.md#Known gotchas] — keep-id, `:Z`, cp-vs-mv label trap

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
