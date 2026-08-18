# Mother Sands Canary — Setup Guide

Mother Sands is MoM's diagnostic canary: a synthetic space we control to test our own data
pipeline end to end. This guide covers the moving parts; `diagnose-a-broken-map.md`
covers driving it scenario by scenario.

## Quick Start

```bash
make startdev          # local stack up
make c-reset           # restore baseline → seeded, pushed to the public canary URL
make cb-aging          # author + push the "going quiet" scenario, backdate the marker
# reload the map and read the card to verify
```

There is **no coherence-report command** — verification is reloading the map, reading the
card, and (for graph leaks) the isolation SPARQL in the operator runbook.

## How It Works

The canary is a **single public JSON file**, not a local server in the request path:

- `data/canary/baseline.json` — committed canonical baseline; never mutated.
- `web/canary/mother-sands.json` — the served payload. `canary_scenarios.py` writes it via a
  safe-write protocol (temp file → `fsync` → atomic `os.rename` → invalidate the
  ETag/Last-Modified row in `heartbeat_log.db` so the next heartbeat doesn't get a stale 304).
- `make endpoint` rsyncs that file to `https://mapsofmaking.org/canary/mother-sands.json`.
- **Both** the local and VPS heartbeats fetch that one public URL (intended — it exercises
  the real fetch pipeline). See `memory/project_canary_public_url_and_vps_parity.md`.

Graph mutations (set/clear endpoint, backdate, declare-closed, heartbeat, rematerialize) run
*inside* the link-handler container via `scripts/canary_ops.py`. Authoring runs on the host
venv via `scripts/canary_scenarios.py`. The `make c*` targets orchestrate both; the `vps-c*`
twins redirect the in-container mutations to the VPS over ssh.

## HTTP Behaviour Injection (Axis A)

Because the heartbeat fetches the static public URL, a pushed payload cannot itself produce a
TCP timeout or 503. To exercise a *real* reachability fault, point the heartbeat at the
controllable local endpoint server, which honours a `MODE` env var:

| MODE | Behaviour |
|------|-----------|
| `ok` (default) | 200 with JSON body + ETag |
| `timeout` | accepts connection, never replies |
| `404` | 404 Not Found |
| `503` | 503 Service Unavailable |

```bash
MODE=timeout python3 data/canary/mother-sands-endpoint.py     # :9191
# point the canary at it explicitly (host is host.containers.internal from in-container):
podman exec maps-link-handler python3 /app/scripts/canary_ops.py \
    set-endpoint http://host.containers.internal:9191/
make heartbeat
```

See the Axis A section of the operator runbook for the full caveat and the DNS-fail variant.

## File Roles

| File | Role |
|------|------|
| `data/canary/baseline.json` | committed canonical baseline — never mutated |
| `web/canary/mother-sands.json` | served payload — written by scenarios, pushed to the public URL |
| `data/canary/mother-sands-endpoint.py` | programmable local HTTP server (Axis A reachability faults only) |
| `scripts/canary_scenarios.py` | pure scenario authoring functions (host venv) |
| `scripts/canary_ops.py` | in-container mutation primitives (local + VPS) |

## Named Graph Isolation

Canary data lives only in `urn:mak:canary` (subject `urn:mak:canary/mother-sands`) — never in
production `urn:mak:space/*` graphs. Verify with the isolation SPARQL in the operator runbook.
