# Mother Sands Canary — Operator Runbook

This runbook is the **manual test surface** for the Mother Sands diagnostic canary. Run it
when the public map shows something incoherent and you need to attribute the fault to a
specific layer.

See also: `set-up-mother-sands.md` (first-time setup) and `../explanation/mother-sands-concept.md`
(why the canary exists). The Makefile canary targets are the source of truth — this
runbook documents how to drive them.

---

## How the canary actually flows (read this first)

The canary is **one public JSON file**, not a local server:

```
canary_scenarios.py  ──writes──▶  web/canary/mother-sands.json
        (local authoring, host venv)              │
                                          make endpoint (rsync)
                                                   ▼
                              https://mapsofmaking.org/canary/mother-sands.json
                                                   │
                              BOTH local & VPS heartbeats fetch THIS url
                                                   ▼
                              canary_ops.py mutations (in-container) → Oxigraph → GeoJSON
```

- **Authoring** runs locally (`canary_scenarios.py`, via `make c*` targets) and writes the
  served payload. `make endpoint` rsyncs it to the public URL. git stays the single source
  of truth for the payload.
- **Mutations** (set/clear endpoint, backdate, declare-closed, heartbeat) run *inside* the
  link-handler container via `canary_ops.py` — `podman exec` locally, `ssh docker exec` on
  the VPS. The `vps-c*` targets are exact twins that redirect those mutations to the VPS.
- The canary lives only in graph `urn:mak:canary` (subject `urn:mak:canary/mother-sands`).

There is **no coherence-report command** in this generation of the tooling. Verification is:
reload the map, read the card, and (if you suspect a graph leak) run the isolation SPARQL
at the bottom of this doc.

---

## The Three Axes

| Axis | What it tests | Fault owner |
|------|--------------|-------------|
| **A** — Reachability | HTTP behaviour of the endpoint | Endpoint/network — MoM nudges coordinator |
| **B** — Lifecycle freshness | Days since last meaningful content update | MoM's pipeline responsibility |
| **C** — Open/Close boolean | `state.open` boolean propagation end-to-end | Presentational |

---

## Prerequisites

```bash
make startdev          # local stack up (rootless Podman)
make c-reset           # restore baseline → seeded, no endpointUrl, pushed to public URL
```

`make c-reset` copies `data/canary/baseline.json` → `web/canary/mother-sands.json`, pushes
it to the public endpoint, loads the canary graph, clears the endpoint URL (so it reads as
seeded), wipes the snapshot, and runs a heartbeat.

To simulate a coordinator *claiming* the space (so Axis B timestamps advance):

```bash
make c-activate        # adds mom:endpointUrl → next heartbeat runs the full fetch→diff path
```

---

## Axis B — Lifecycle Freshness  (the main, fully-wired axis)

Each target authors a scenario payload, pushes it, heartbeats, then back-dates
`mom:updatedAt` to land the marker in a specific bucket. Back-dating rewrites the timestamp
and re-materialises — no re-fetch, so the live scenario payload is preserved.

```bash
make cb-seeded         # no endpointUrl yet — alias of c-reset (clean slate, no claim)
# reload map → grey/seeded marker

make cb-confirmed      # endpointUrl + fresh content, open/close opted-out
# reload map → confirmed marker, no open/closed pill

make cb-aging          # backdates updatedAt 45 days → "Going quiet"
make cb-zombie         # backdates 120 days → zombie
make cb-dead           # backdates 365 days → dead
make cb-closed         # operator-declared closure (terminal-by-declaration)
```

Run the whole walk in one go:

```bash
make c-demo            # seeded → confirmed → aging → zombie → dead → closed
make caxis-b           # same coverage, axis-complete banner
```

**Verify each step:** reload the map and read the card. The marker and the freshness pill
should match the bucket you pinned. (New/seeded spaces are invisible if a network filter is
active — clear filters after `cb-seeded`.)

### Demo-speed thresholds

```bash
make c-demo-on         # compress thresholds to seconds (aging≈30s, zombie≈60s, dead≈120s)
make c-demo-off        # restore normal day-scale
```

With demo mode ON, after `cb-confirmed` the canary walks aging→zombie→dead in minutes against
its real recent `mom:updatedAt`, no back-dating needed. Demo mode lives in the payload itself
(`ext_canary.thresholdMode`) — single source of truth.

---

## Axis C — Open/Close Boolean

```bash
make cc-open           # state.open = true   → open pill in drawer
make cc-shut           # state.open = false  → no open pill, still "Confirmed" (not closed)
make caxis-c           # both
```

`shut` (not `close`) is deliberate — it avoids colliding with Axis B's `closed` lifecycle
state. **Absence test:** the `c-no-open-field` scenario removes `state.open` entirely;
absence must read as "no live signal", *not* "closed".

---

## Axis A — Reachability  (partial — read the caveat)

```bash
make ca-reachable      # healthy baseline
make ca-timeout        # authors timeout scenario + pushes + heartbeat
make ca-http-error     # 503 scenario
make ca-dns-fail       # manual only — see below
make caxis-a           # run the set
```

⚠️ **Caveat:** because the heartbeat fetches the *public static URL*, pushing a payload there
cannot itself produce a real TCP timeout or 503 — the scenario only prints a `MODE=…` hint.
To exercise a genuine reachability fault you must point the heartbeat at a misbehaving
endpoint:

- **timeout / 503:** run the controllable local endpoint server with the matching mode, then
  point the canary's `mom:endpointUrl` at it directly (the `make c*` targets always use the
  public URL default, so set it via `canary_ops.py` explicitly). From inside the container the
  host is `host.containers.internal`, not `localhost`:
  ```bash
  MODE=timeout python3 data/canary/mother-sands-endpoint.py   # :9191, or MODE=503
  podman exec maps-link-handler python3 /app/scripts/canary_ops.py \
      set-endpoint http://host.containers.internal:9191/
  make heartbeat
  ```
- **DNS fail:** set the endpoint to an unresolvable URL and heartbeat; expect `ConnectError`
  in the link-handler logs and health degrading to `broken` over successive cycles:
  ```bash
  podman exec maps-link-handler python3 /app/scripts/canary_ops.py \
      set-endpoint http://unresolvable.invalid/
  make heartbeat
  ```

Run `make c-reset` afterwards to restore the canary to the public URL.

**Expected card** for all Axis A faults: an "Endpoint issue" pill; the fetch timestamp stalls
as retries fail; the marker goes `broken` once failures pass the threshold.

---

## Driving the canary on the VPS

Every local `c*` target has a `vps-c*` twin that runs the identical recipe but directs the
Oxigraph/snapshot/API mutations at the VPS container over ssh, and stages + ETag-clears the
pushed JSON there:

```bash
make vps-c-reset  vps-c-activate  vps-cb-confirmed  vps-cb-aging  vps-cb-zombie
make vps-cb-dead  vps-cb-closed   vps-cc-open       vps-cc-shut
make vps-c-demo-on  vps-c-demo-off
```

Authoring still runs locally; only the mutation target changes. See
`memory/project_canary_public_url_and_vps_parity.md` and the "Makefile inventory" section of
`operate-the-vps.md`.

---

## Named-Graph Isolation

Canary data must live **only** in `urn:mak:canary`. Verify manually against Oxigraph:

```sparql
# Should return 0 — no canary subjects leaked into production space graphs
SELECT (COUNT(?s) AS ?count) WHERE {
  GRAPH ?g { ?s ?p ?o . FILTER(CONTAINS(STR(?s), "canary")) }
  FILTER(STRSTARTS(STR(?g), "urn:mak:space/"))
}

# Should return the canary data intact
SELECT * WHERE { GRAPH <urn:mak:canary> { ?s ?p ?o } }
```

---

## When the map shows something incoherent

Walk the pipeline layer by layer (the canary's whole purpose):

1. **Endpoint payload ≠ heartbeat behaviour** — the heartbeat didn't pick up the mutation.
   Check the ETag was invalidated (`canary_ops.py clear-etag`) and that `make endpoint`
   actually pushed the new file.
2. **Heartbeat ≠ Oxigraph** — transformer write failed. Check link-handler logs and the
   SPARQL update.
3. **Oxigraph ≠ GeoJSON** — the materialiser didn't run or used stale data. Re-run
   `make heartbeat` (or `canary_ops.py rematerialize`).
4. **GeoJSON ≠ card** — front-end rendering bug. Check the marker/pill logic in `app.js`.

---

## Resetting

```bash
make c-reset           # restore baseline (seeded, no endpointUrl), re-pushed to public URL
```
