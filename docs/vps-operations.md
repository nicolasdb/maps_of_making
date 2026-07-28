# VPS Operations Runbook

Operational reference for the Hetzner VPS hosting Maps of Making.

## Topology

Two-layer nginx, single host:

```
Internet ──► nginx-gateway (host: hetzner-gateway stack)
                │ TLS termination, fronts multiple unrelated services
                ▼
              maps-nginx (host: maps_of_making stack)
                │ static site + reverse proxy to mak-link-handler
                ▼
              mak-link-handler ──► oxigraph
```

- `nginx-gateway` lives in `/home/nicolas/hetzner-gateway/` and is **not** part of this repo. Its conf.d is at `/home/nicolas/hetzner-gateway/nginx/conf.d/`.
- The Maps-of-Making slices of that conf (`06-mapsofmaking.conf`, `07-admin-mapsofmaking.conf`) are version-controlled here under `infra/gateway-nginx/` and pushed with `make sync-gateway`.
- `maps-nginx` joins both the `gateway` external network (for the proxy hop) and the project-internal network (for `oxigraph` + `mak-link-handler`).

## SSH login is root — `~` traps

`ssh hetzner` logs in as **root** by default (`$HOME=/root`), not `nicolas`. All project files live under `/home/nicolas/maps_of_making`, never `/root/...`.

Any `cd ~/maps_of_making` or bare relative `cd maps_of_making` run from an unexpected CWD as root resolves against `/root`, not `/home/nicolas`. This has already created an orphan `/root/maps_of_making/data/oxigraph/` (empty, unmounted by any container — harmless but confusing) after a `docker compose up` was run with CWD wrongly resolved to `/root` via `~`.

**Always use the absolute path** when operating as root on this VPS:
```
cd /home/nicolas/maps_of_making
```
Never rely on `~` or a bare relative `cd` for this repo in a root shell.

## Domains

| Domain | Status | Behavior |
|---|---|---|
| `mapsofmaking.org` | **Primary** | Serves the app |
| `mapsofmaking.com` | Active | 301 → `mapsofmaking.org` |
| `admin.mapsofmaking.org` | Active | Admin UI |
| `genjson.mapsofmaking.org` | Active | Bernard's Workshop JSON composer |
| `mothersands.mapsofmaking.org` | Active | Mother Sands website |

Wildcard cert lives at `/etc/letsencrypt/live/mapsofmaking.org/` and covers `.org` + `.com`.

## `make publish` vs `make vps-reset`

| | `publish` | `vps-reset` |
|---|---|---|
| Intent | Push latest dev code | Factory-reset all state |
| Touches code on VPS | Yes (rsync) | No (uses whatever is there) |
| Touches `data/` | No | **Wipes** Oxigraph + SQLite + materialized GeoJSON |
| Rebuilds containers | Yes | Yes |
| Seeds canary | No | Yes (Mother Sands only) |
| Triggers heartbeat | No | No (next 10-min cycle picks it up) |
| Reloads gateway | (recommended) | Yes |

The bulk-seed path (`scripts/seed_import.py`) was deprecated in Story 3.4b. Neither target uses it.

## The 502-after-rebuild gotcha

Whenever the maps-nginx container is recreated (any `down`/`up --build`, or `vps-reset`), the **outer** `nginx-gateway` may keep returning 502 for a while even after maps-nginx is healthy.

Cause: the gateway's `proxy_pass` uses a `set $upstream http://maps-nginx:80;` variable with `resolver 127.0.0.11`. When the upstream disappears mid-flight, nginx fail-caches the resolution and doesn't recheck reliably.

Fix (idempotent, safe):

```bash
ssh hetzner 'docker exec nginx-gateway nginx -s reload'
```

This is now baked into `make vps-reset`. After `make publish`, run it manually if you see 502s — or we can fold it into `publish` once that target is rewritten.

## Clean re-deploy from scratch (when `rm -rf maps_of_making` route is taken)

There are **no named Docker volumes** for this project — all persistent state is bind-mounted from `./data/`, `./web/data/`, and `./infra/`. So deleting the repo folder genuinely wipes everything. Verify with `docker volume ls` (should show nothing project-related).

To rebuild from zero:

1. `rsync` (or `git clone`) the repo to `/home/nicolas/maps_of_making/`
2. Recreate `.env` and `infra/.env` symlink (see `infra_env_symlink` memory)
3. `make vps-reset` (runs full down → wipe → up → canary → reload)
4. Claim additional spaces via the admin UI

## Quick checks

```bash
# public reachability
curl -sI https://mapsofmaking.org/ | head -3

# inner stack health (from host)
ssh hetzner 'docker ps --filter name=maps- --format "{{.Names}} {{.Status}}"'

# gateway → maps-nginx reachability (bypasses external DNS / TLS)
ssh hetzner 'docker exec nginx-gateway curl -sI http://maps-nginx/'

# count features in materialized GeoJSON
curl -s https://mapsofmaking.org/data/spaces.geojson | jq '.features | length'

# gateway error log (filter out unrelated services)
ssh hetzner 'docker logs nginx-gateway --tail 200 2>&1 | grep -i mapsofmaking'
```

## Makefile inventory & the local↔VPS mirror contract

> Honest-inventory pass, 2026-06-05. The Makefile carries ~50 targets in four
> zones. This section is the maintenance map: which targets mirror cleanly,
> which are hand-written twins that drift, and what's safe to cut.

### The two mirror patterns

**🟢 Canary — true mirror via variable override** (`Makefile` "VPS canary twins").
Each `vps-c*` twin invokes the *identical* local recipe with two variables
swapped: `CANARY_OPS` (`podman exec` → `ssh docker exec`) and `PUSH_STEP`
(local publish → publish + container-stage + clear-ETag). One recipe body, two
execution targets. This is the pattern to extend — never fork a canary recipe.

**🔴 Stack ops — hand-written parallel twins.** `seed-spaceapi`/`vps-seed`,
`seed-bundle`/`vps-seed-bundle`, `rebuild`/`vps-rebuild`, `reset`/`vps-reset`
are each ~2× copy-pasted. The asymmetry is *partly* structural — local runs on
the host venv against the published `:7878`; VPS stages scripts via `docker cp`
then runs in-container against `oxigraph:7878`. But it is collapsible to the
canary pattern: the dev compose already bind-mounts `scripts/` into the
container, so local could also run via `podman exec maps-link-handler` with no
staging, leaving `podman exec` vs `ssh docker cp + docker exec` as the only
difference — exactly one `EXEC` variable.

### Recommended merge (not yet executed — touches deploy paths)

Introduce a `COMPOSE_EXEC` / `SEED_EXEC` selector mirroring `CANARY_OPS`, then
fold each twin pair into one recipe. Removes ~100 lines. Requires a live test
run (`make seed-bundle` local, then `make vps-seed-bundle` against staging)
before trusting it on a real deploy. Until then the twins stay as-is.

### Target triage

| Target(s) | Verdict |
|---|---|
| `seed` | 🔴 **CUT (2026-06-05)** — deprecation stub (`exit 1`) since Story 3.4b |
| `startdev` `rebuild` `heartbeat` `devdeploy` `reset` | 🟢 local stack core |
| `seed-spaceapi` `seed-bundle` `bundle-to-csv` `csv-to-bundle` | 🟢 seeding (see seed-import-runbook.md) |
| `load-ontology` `vps-load-ontology` | 🟢 clean mirror pair |
| `publish` `sync` `sync-app` `sync-gateway` `deploy-genjson` | 🟢 VPS deploy |
| `vps-rebuild` | 🟡 keep — `publish` minus the rsync; use only when VPS code is already current |
| `bernard-copy` | 🟡 keep — local YAML→JSON build step, dep of `deploy-genjson` (don't read its help line as a VPS op) |
| `vps-seed` `vps-seed-bundle` `vps-reset` | 🟡 keep — **merge candidates** (see above) |
| `c-*` `ca-*` `cb-*` `cc-*` `caxis-*` `c-demo*` `endpoint` | 🟢 canary local |
| `vps-c*` `vps-stage-scripts` `_vps-push` | 🟢 canary VPS twins (the good pattern) |

### ⚠️ Stale doc flag — canary-operator-runbook.md is broken

`docs/canary-operator-runbook.md` was written against the **old** canary target
names (`make canary-reset`, `make canary-b-aging`, …) before the rename to
`c-reset` / `cb-aging`. It also calls `make canary-report` 8+ times — a target
that **no longer exists in the Makefile at all**. Following that runbook today
fails on every line with "No rule to make target". It needs a naming sweep
(`canary-*` → `c*`/`cb-*`) and either a restored `canary-report`/`c-report`
target or removal of those calls. Tracked separately from this pass.
