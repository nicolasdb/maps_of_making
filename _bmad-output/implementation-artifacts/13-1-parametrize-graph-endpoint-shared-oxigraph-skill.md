# Story 13.1: Parametrize the Graph Endpoint (shared oxigraph-query skill)

Status: done

## Story

As the MoM operator (and future white-label host),
I want the shared `oxigraph-query` hermes skill to resolve its SPARQL endpoint from per-profile configuration (`GRAPH_ENDPOINT`) instead of the hardcoded `http://oxigraph:7878`,
so that one shared skill can serve bianca→OpenFab store and bernardo→MoM store (the ADR-018 endpoint-as-contract enabling change for all of Epic 13).

## Acceptance Criteria

1. **Env propagation verified first (spike gate).** It is confirmed, by a live test inside the running hermes container, whether a variable set in `profiles/<bot>/.env` (e.g. `GRAPH_ENDPOINT=...`) is visible in the terminal-toolset shell where the agent runs `curl`. The finding (yes/no + mechanism) is recorded in this story's Completion Notes. If NOT propagated, the fallback resolution mechanism in AC2 is used and documented in the skill.
2. **Skill reads `GRAPH_ENDPOINT`, never a hardcoded host.** `hermes-data/shared/skills/oxigraph-query/SKILL.md` instructs the agent to resolve the endpoint base URL by reading `GRAPH_ENDPOINT=` from `$HERMES_HOME/.env` (the *running session's* profile directory, confirmed propagated to the toolset shell — AC1 finding; `$HERMES_HOME` replaces the originally-planned `/opt/data/active_profile` marker, which is a sticky default and not necessarily the running profile). There is **no fallback resolution path** — `/opt/data/active_profile` is never consulted for this lookup (a fallback onto it would reproduce the exact silent-wrong-store bug this story fixes, per code review 2026-07-07). If `GRAPH_ENDPOINT` is absent, commented out, or present-but-empty, **STOP and tell the user `GRAPH_ENDPOINT` is unset for this profile** — no hardcoded default, no silent fallback, no guessed endpoint. The skill must never query a store the profile didn't explicitly configure (ADR-018: endpoint is per-profile env, never baked in the skill).
   All four endpoint URLs in the skill (`/query`, `/update`, `/store?default`, and the curl import example) are expressed relative to the resolved base (e.g. `${GRAPH_ENDPOINT}/query`).
3. **`GRAPH_ENDPOINT` set in bianca's profile env.** `profiles/bianca/.env` gains `GRAPH_ENDPOINT=http://oxigraph:7878` (explicit, even though it matches the old default). manny's profile gets the same line (it also symlinks the skill).
4. **Scratch profile hits a different store.** A scratch/test profile exists with the same shared-skill symlink and a `GRAPH_ENDPOINT` pointing at a *different* SPARQL store (see Dev Notes for the second-store options). Given the same skill file, the scratch profile's queries land on the second store, not OpenFab's.
5. **Live done gate (DoD, per Epic 6 retro discipline — green tests ≠ working bot):** in live Matrix (or hermes session) runs, bianca answers a query whose result can only come from the OpenFab store, and the scratch profile answers a query whose result can only come from the second store — same shared `SKILL.md`, zero per-profile skill divergence (symlinks intact, `ls -la` proof captured).
6. **No regression for bianca.** bianca's existing OpenFab graph workflow (FAQ/segment queries) still works after the change — verified live, not assumed.
7. **bernardo untouched.** No `oxigraph-query` symlink is added to `profiles/bernardo/` in this story (that is Story 13.2's scaffold work). Frozen harness Bernard (maps_of_making `harness/`) is not modified at all.

## Tasks / Subtasks

- [x] Task 1: Verify env propagation (AC: 1)
  - [x] Start/confirm hermes stack up (was already up: `openfab-oxigraph` + `openfab-hermes`; plain `podman` reaches them in this shell — no `distrobox-host-exec` prefix needed here)
  - [x] Add `GRAPH_ENDPOINT=http://oxigraph:7878` to `profiles/bianca/.env`
  - [x] Restart hermes, open a bianca session (`hermes -p bianca -z ...`), agent ran `echo $GRAPH_ENDPOINT` via terminal toolset → returned `[]` (empty)
  - [x] Recorded: **NOT propagated** as a shell var. But `$HERMES_HOME` (profile dir) IS propagated → skill leads with `$HERMES_HOME/.env` file-read (see Completion Notes)
- [x] Task 2: Rewrite endpoint sections of shared SKILL.md (AC: 2)
  - [x] Added "Résolution de l'endpoint (À FAIRE EN PREMIER)" section before « Endpoints »; replaced 3-row endpoint table + curl import example with `${GRAPH_ENDPOINT}`-relative forms
  - [x] Rewrote Pitfall #1 → endpoint from profile env; `oxigraph` hostname only valid same-network; empty `GRAPH_ENDPOINT` = STOP
  - [x] Relabeled frontmatter `description` + Overview as "Vocabulaire du store OpenFab" (kept intact — cartridge split deferred to 13.4)
  - [x] Kept French + structure/tone; bumped version 0.2.0 → 0.3.0
- [x] Task 3: Set profile envs (AC: 3)
  - [x] `GRAPH_ENDPOINT=http://oxigraph:7878` in `profiles/bianca/.env` (Task 1) and `profiles/manny/.env`
- [x] Task 4: Scratch profile against second store (AC: 4)
  - [x] Stood up second store as a compose service `scratch-oxigraph` (same network, no published port, ephemeral) — cleanest variant per Dev Notes; seeded 2 distinctive triples (`PURPLE-WOMBAT-42`, `GREEN-NARWHAL-99`)
  - [x] Created scratch profile via `hermes profile create scratch --clone` (from bianca), replaced cloned skill copy with symlink → `/opt/data/shared/skills/oxigraph-query/SKILL.md`
  - [x] Set scratch `GRAPH_ENDPOINT=http://scratch-oxigraph:7878`
- [x] Task 5: Live done gate (AC: 5, 6)
  - [x] bianca: segment-count query over `openfab:Submission` → resolved `http://oxigraph:7878`, returned real OpenFab content (34 submissions / 15 segments) — regression clean
  - [x] scratch: canary query → resolved `http://scratch-oxigraph:7878`, returned both seeded canaries
  - [x] Negative case: scratch with `GRAPH_ENDPOINT` line removed → agent stopped loudly, cited the skill rule, queried nothing, fabricated nothing (correctly rejected the stale `active_profile` fallback)
  - [x] Captured transcripts + `ls -la` of all three skill dirs (all symlink the one shared SSOT) into Completion Notes
- [x] Task 6: Documentation (AC: 2)
  - [x] Added "Variables d'environnement par-profile (contrat ADR-018)" section to `references/shared-skills-pattern.md`
  - [x] Recorded env-propagation finding + second-store choice below for 13.2

## Review Findings

- [x] [Review][Patch] Remove `/opt/data/active_profile` fallback entirely from SKILL.md's resolution order — `$HERMES_HOME/.env` only, STOP if absent (decision: no escape hatch, matches ADR-018 anti-guess principle strictly) [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md]
- [x] [Review][Patch] Add explicit header note to scratch profile's SOUL.md marking it as copied from Bianca for test parity only, not a real persona (decision: cheapest fix, scratch is infra not a bot) [hermes/hermes-data/profiles/scratch/SOUL.md]
- [x] [Review][Patch] Empty-but-present `GRAPH_ENDPOINT=` line vs missing line both silently yield empty string; STOP branch never mechanically triggered [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md]
- [x] [Review][Patch] `export GRAPH_ENDPOINT=...` syntax not matched by anchored grep → false-negative STOP for a validly configured profile [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md]
- [x] [Review][Patch] No trimming of inline comments / CRLF from `.env` value → malformed URL passed to curl [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md]
- [x] [Review][Patch] No trailing-slash normalization on `GRAPH_ENDPOINT` → double-slash in `${GRAPH_ENDPOINT}/query` [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md]
- [x] [Review][Patch] Duplicate `GRAPH_ENDPOINT=` lines silently resolved via `tail -1`, no warning [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md]
- [x] [Review][Patch] Story AC2 text still describes the old ($GRAPH_ENDPOINT-env-first, active_profile-second) resolution order; shipped code correctly uses $HERMES_HOME instead (live-tested) but AC2 wording was never updated to match [this story file, AC2]
- [x] [Review][Defer] scratch profile `.env` bootstrap has no validation [hermes/hermes-data/profiles/scratch/] — deferred, temporary profile, test-only, no bootstrap tooling needed
- [x] [Review][Defer] Permission-denied `.env` file indistinguishable from "missing" → misleading diagnostic message [hermes/hermes-data/shared/skills/oxigraph-query/SKILL.md] — deferred, pre-existing edge case, low priority
- [x] [Review][Defer] No automated test/CI gate for endpoint resolution [hermes repo] — deferred, by design per Epic 6 retro discipline (live verification is the DoD, not a pytest surface)

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

claude-sonnet-5 (dev-story workflow, live-driven)

### Debug Log References

- Live agent runs via `hermes -p <profile> -z "..."` inside `openfab-hermes` container (one-shot mode). `--yolo` flag intentionally avoided (blocked as unsafe-agent bypass; plain echo/curl don't hit approval gates anyway).
- Each one-shot prints its answer then the process `dumped core / Aborted` on teardown — output is captured before teardown, cosmetic only.

### Completion Notes List

**AC1 — env-propagation finding (carries into 13.2):**
- A var in `profiles/<bot>/.env` is **NOT** exported as a shell variable into the terminal-toolset shell. Live proof: bianca agent ran `echo GRAPH_ENDPOINT=[$GRAPH_ENDPOINT]` → `GRAPH_ENDPOINT=[]`. hermes reads `.env` internally for its own config but does not propagate it to tool subprocesses.
- **`$HERMES_HOME` IS propagated** and equals the *running* profile's dir (e.g. `/opt/data/profiles/scratch`). This is the reliable resolution anchor. The skill reads `$HERMES_HOME/.env`.
- **Trap corrected mid-dev:** first skill draft resolved via `/opt/data/active_profile` (per the story's AC2 wording). That marker is the *sticky default* (was `bianca`), NOT the session's profile — a `-p scratch` run has `$HERMES_HOME=scratch` but `active_profile=bianca`. First scratch run consequently hit the OpenFab store (empty bindings). Fixed skill to use `$HERMES_HOME`; `active_profile` kept only as a last-ditch fallback if `$HERMES_HOME` is absent.

**Second-store choice (carries into 13.2):** added `scratch-oxigraph` as a compose service on the default network (`http://scratch-oxigraph:7878`) — no host-port collision, no `host.containers.internal`. Ephemeral (no volume). For 13.2, bernardo→MoM will point `GRAPH_ENDPOINT` at the MoM store the same way (remote/VPS endpoint reachability still to be probed per ADR-018).

**Live done-gate transcripts (AC5/AC6):**
1. *scratch canary* → "Endpoint utilisé : `http://scratch-oxigraph:7878/query` (résolu depuis `$HERMES_HOME/.env`)" → `PURPLE-WOMBAT-42`, `GREEN-NARWHAL-99`.
2. *bianca OpenFab* → "Endpoint résolu : `http://oxigraph:7878` (depuis `$HERMES_HOME/.env` du profile bianca)" → 34 submissions across 15 segments (top: prospects_membres 7). Regression clean.
3. *scratch negative* (`GRAPH_ENDPOINT` removed) → "STOP — arrêt propre … je ne peux pas exécuter cette requête … jamais d'endpoint codé en dur, jamais de store deviné." No query issued, no fabrication, correctly declined the stale-`active_profile` fallback.

**Symlink proof (AC5):** all three profiles symlink the one shared SSOT:
```
bianca/skills/oxigraph-query/SKILL.md  -> /opt/data/shared/skills/oxigraph-query/SKILL.md
manny/skills/oxigraph-query/SKILL.md   -> /opt/data/shared/skills/oxigraph-query/SKILL.md  (+ stale local references/ dir, see below)
scratch/skills/oxigraph-query/SKILL.md -> /opt/data/shared/skills/oxigraph-query/SKILL.md
```

**Notes / follow-ups:**
- AC7 respected: no `oxigraph-query` symlink added to bernardo; maps_of_making `harness/` untouched.
- **manny divergence:** manny's `oxigraph-query/` has a real (non-symlinked) `references/` dir alongside the symlinked `SKILL.md`. SKILL.md itself is correctly shared; the stale references/ copy should be removed/symlinked in 13.2 cleanup.
- **Story AC2 wording correction:** the story said resolve via `/opt/data/active_profile`; live testing proved `$HERMES_HOME` is required instead. The shipped skill uses `$HERMES_HOME`.
- hermes repo (`~/github/hermes`) git-hygiene fixed before dev: whitelist `.gitignore` (secrets purged from the initial commit). Skill/compose changes are git-tracked in that repo — **not committed** (awaiting Nicolas's approval per standing rule).
- Two empty bind-mount dirs (`corpus/`, `faq/`) had vanished and blocked `podman compose restart`; recreated with `mkdir -p`.

### File List

**hermes repo (`/var/home/nicolas/github/hermes/`) — implementation:**
- `hermes-data/shared/skills/oxigraph-query/SKILL.md` — endpoint parametrization (v0.2.0 → 0.3.0)
- `hermes-data/shared/skills/oxigraph-query/references/shared-skills-pattern.md` — per-profile env-var contract section
- `docker-compose.yml` — added `scratch-oxigraph` service
- `hermes-data/profiles/bianca/.env` — `GRAPH_ENDPOINT` (gitignored)
- `hermes-data/profiles/manny/.env` — `GRAPH_ENDPOINT` (gitignored)
- `hermes-data/profiles/scratch/**` — new throwaway profile (gitignored; skill symlinks shared SSOT)
- `.gitignore` — whitelist model (repo hygiene, pre-dev)

**maps_of_making — tracking only:**
- `_bmad-output/implementation-artifacts/13-1-parametrize-graph-endpoint-shared-oxigraph-skill.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
