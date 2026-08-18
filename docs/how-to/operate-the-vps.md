# Operate the VPS

Operational recipes for the Hetzner VPS hosting Maps of Making. For the box's architecture,
domains, and Makefile target inventory, see [vps-topology.md](../reference/vps-topology.md).

## SSH login is root — `~` traps

`ssh hetzner` logs in as **root** by default (`$HOME=/root`), not `nicolas`. All project files live under `/home/nicolas/maps_of_making`, never `/root/...`.

Any `cd ~/maps_of_making` or bare relative `cd maps_of_making` run from an unexpected CWD as root resolves against `/root`, not `/home/nicolas`. This has already created an orphan `/root/maps_of_making/data/oxigraph/` (empty, unmounted by any container — harmless but confusing) after a `docker compose up` was run with CWD wrongly resolved to `/root` via `~`.

**Always use the absolute path** when operating as root on this VPS:
```
cd /home/nicolas/maps_of_making
```
Never rely on `~` or a bare relative `cd` for this repo in a root shell.

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

There are no named Docker volumes for this project (see [vps-topology.md](../reference/vps-topology.md)) — deleting the repo folder genuinely wipes everything.

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

## ⚠️ Stale doc flag — diagnose-a-broken-map.md is broken

[diagnose-a-broken-map.md](diagnose-a-broken-map.md) was written against the **old** canary target
names (`make canary-reset`, `make canary-b-aging`, …) before the rename to
`c-reset` / `cb-aging`. It also calls `make canary-report` 8+ times — a target
that **no longer exists in the Makefile at all**. Following that runbook today
fails on every line with "No rule to make target". It needs a naming sweep
(`canary-*` → `c*`/`cb-*`) and either a restored `canary-report`/`c-report`
target or removal of those calls. Tracked separately from this pass.
