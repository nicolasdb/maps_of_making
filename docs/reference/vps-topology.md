# VPS topology

Reference facts about the Hetzner VPS hosting Maps of Making — architecture, domains, and the
Makefile target inventory. For step-by-step operations (deploy, reset, diagnose 502s), see
[operate-the-vps.md](../how-to/operate-the-vps.md).

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

## Domains

| Domain | Status | Behavior |
|---|---|---|
| `mapsofmaking.org` | **Primary** | Serves the app |
| `mapsofmaking.com` | Active | 301 → `mapsofmaking.org` |
| `admin.mapsofmaking.org` | Active | Admin UI |
| `genjson.mapsofmaking.org` | Active | Bernard's Workshop JSON composer |
| `mothersands.mapsofmaking.org` | Active | Mother Sands website |

Wildcard cert lives at `/etc/letsencrypt/live/mapsofmaking.org/` and covers `.org` + `.com`.

## No named Docker volumes

All persistent state is bind-mounted from `./data/`, `./web/data/`, and `./infra/` — there are
**no named Docker volumes** for this project. Deleting the repo folder genuinely wipes everything.
Verify with `docker volume ls` (should show nothing project-related).

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
| `seed-spaceapi` `seed-bundle` `bundle-to-csv` `csv-to-bundle` | 🟢 seeding (see [import-a-space-batch.md](../how-to/import-a-space-batch.md)) |
| `load-ontology` `vps-load-ontology` | 🟢 clean mirror pair |
| `publish` `sync` `sync-app` `sync-gateway` `deploy-genjson` | 🟢 VPS deploy |
| `vps-rebuild` | 🟡 keep — `publish` minus the rsync; use only when VPS code is already current |
| `bernard-copy` | 🟡 keep — local YAML→JSON build step, dep of `deploy-genjson` (don't read its help line as a VPS op) |
| `vps-seed` `vps-seed-bundle` `vps-reset` | 🟡 keep — **merge candidates** (see above) |
| `c-*` `ca-*` `cb-*` `cc-*` `caxis-*` `c-demo*` `endpoint` | 🟢 canary local |
| `vps-c*` `vps-stage-scripts` `_vps-push` | 🟢 canary VPS twins (the good pattern) |
