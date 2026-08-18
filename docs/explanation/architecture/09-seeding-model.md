# Seeding model — how spaces enter the graph

The map renders two kinds of pins: **confirmed** (live SpaceAPI endpoint, heartbeat
fetching) and **seeded** (grey, no endpoint yet). Both share the same `mom:Space` named
graph in Oxigraph; the only difference is the presence of `mom:endpointUrl`.

This document covers how a space reaches Oxigraph for the first time — the two intake
paths, the claim flow that upgrades a seeded pin to confirmed, and the dedup guards that
keep duplicate graphs from accumulating.

---

## Two intake paths

### Path A — live endpoint

A space publishes a SpaceAPI v14/v15 document at a public URL. `seed_spaceapi.py` pulls
the SpaceAPI directory (or a curated list), fetches every endpoint, and writes a minimal
seed graph tagged `mom:source "spaceapi-directory"`. The heartbeat picks it up on its next
cycle, writes `mom:endpointUrl`, and begins the confirmed fetch loop.

```
SpaceAPI directory ──seed_spaceapi.py──▶ Oxigraph (seeded, has endpointUrl)
                                              │
                                         heartbeat cycle
                                              ▼
                                         confirmed (Three Tokens live)
```

Path A graph URI: `urn:mak:space/<sha256(name|endpoint)[:12]>` — hash-stable; survives
endpoint URL changes at the same space.

### Path B — bundle import

A space has **no public endpoint** (not yet, or deliberately). Batch source: a hand-curated
CSV exported from any JSON merge output and cleaned in a spreadsheet. `seed_csv.py to-bundle`
converts it to a canonical `mom:Space` array; `seed_bundle.py` writes one named graph per
record, tagged `mom:source "scraped-<network>"`. No `mom:endpointUrl` → heartbeat skips it
→ grey/seeded pin until claimed.

```
raw source (scrape/merge) ──seed_csv.py to-csv──▶ curation.csv ──(spreadsheet cleanup)──▶
                           seed_csv.py to-bundle ──▶ bundle.json
                           seed_bundle.py ──────────▶ Oxigraph (seeded, no endpointUrl)
```

Path B graph URI: `urn:mak:space/<name-slug>-<city-slug>` — human-readable; city is
required to avoid slug collisions between two spaces with the same name in different cities.

The CSV-pivot is intentional. Scraped sources carry corrupt URLs, free-form address strings,
duplicate entries, and swapped coordinates. Auto-parsing them would silently embed the mess.
A one-time hand-clean is cheaper than a bug-prone multi-format parser, and a grey pin with
wrong data is the nudge that motivates a coordinator to publish a clean endpoint.

---

## The claim flow

When a coordinator registers a SpaceAPI URL via the admin UI (or `/api/register`), the
link handler runs `register_url()` with three dedup checks in priority order:

```
1. endpointUrl match  ──▶ reuse existing graph URI (strongest key)
2. name match on scraped graph  ──▶ claim-in-place (CLEAR + re-INSERT as self-registered)
3. no match  ──▶  mint new URI: urn:mak:space/<name-slug>
```

**Priority 1 — endpointUrl dedup** (`_find_graph_by_endpoint`):  
If Oxigraph already holds *any* graph with `mom:endpointUrl <registered-url>`, reuse that
graph URI — regardless of slug. This prevents a re-registration of an already-confirmed
space from creating a second graph. If a seeded graph with the same *name* but a *different*
URI also exists (the orphan case: `seed_bundle.py` used a compound slug while `register_url`
would have picked a different one), that orphan is `DROP GRAPH`'d in the same request.

**Priority 2 — name match** (`_find_seeded_graph_by_name`):  
If no endpointUrl match, look for a seeded graph whose `schema:name` literal equals the
registered space's name. If found, CLEAR it and re-INSERT as `self-registered` at the same
URI — same pin, same map position, now confirmed. This is the claim-in-place flow.

**Priority 3 — mint new URI**:  
No existing graph at all. A fresh `urn:mak:space/<slug>` is created as self-registered
from the start.

After any of the three, the heartbeat adds `mom:endpointUrl`, writes `mom:observedAt`
on the first confirmed fetch, and `mom:openNow` on subsequent checks — completing the
Three Tokens.

---

## Network membership

Both paths write `mom:memberOf <urn:mak:network/<slug>>` at seed time. This is the data
that drives the filter chips on the map.

The slug is always lowercased at every write path — `seed_bundle.py`, `seed_spaceapi.py`,
and `spaceapi_extract/core.py` (live endpoint ingestion) all call `.lower()` before writing.
Case variants from a live endpoint (`FabTafle` vs `fabtafle`) would create two filter chips;
the normalisation prevents it.

When a coordinator adds `ext_mom.memberOf` to their SpaceAPI document, the heartbeat
overwrites the seed-time value on the next confirmed fetch.

---

## Guard rails

| Situation | Behaviour |
|---|---|
| Graph already exists, same source tag | Skip (unless `--force`, then CLEAR + re-INSERT) |
| Graph exists, self-registered | Never touch — coordinator owns it |
| Graph exists, different source tag | Never overwrite (cross-source protection) |
| Coordinate outside Europe bbox | Drop at seed time, log as `no_geo` |
| Invalid URL (non-http/s) | Drop at CSV convert time, log as `url_dropped` |
| endpointUrl already in Oxigraph | Reuse existing URI, drop orphan if found |

---

## Where the seeded state is read

`_binding_to_feature` in `main.py` tests for the presence of `mom:endpointUrl` in the
SPARQL result to set the `seeded` flag on the GeoJSON feature. The map reads this flag to
choose the grey/seeded marker vs. the coloured/confirmed marker. No endpointUrl → heartbeat
skips the space → `THREE_TOKENS_MISSING` warning in logs — this is expected and normal for
every Path B space until claimed.

---

## Operational commands

```bash
# Path B — local seed (needs dev stack up)
make seed-bundle BUNDLE=data/seed-lists/BE.bundle.json NETWORK=fabtafle

# Path B — VPS seed
make vps-seed-bundle BUNDLE=data/seed-lists/BE.bundle.json NETWORK=fabtafle

# Path A — seed from SpaceAPI directory
make seed-spaceapi NETWORK=spaceapi

# CSV pivot — dump a JSON source to a curation CSV
source venv/bin/activate
python scripts/seed_csv.py to-csv --bundle data/seed-lists/BE.spaces.json --out /tmp/be.csv
python scripts/seed_csv.py to-bundle --csv /tmp/be-clean.csv --out data/seed-lists/BE.bundle.json
```

Full import walkthrough: [seed-import-runbook.md](../../how-to/import-a-space-batch.md).

---

This closes the input side of the trail:
**09 seeding** (how data enters) · [01](01-walking-skeleton.md) pipeline (how it flows) ·
[02](../../reference/field-traceability.md) field net-list · [08](../../reference/semantic-layer.md) triplestore ·
[03](../../reference/freshness-axes.md) freshness · [04](04-design-rules.md) map grammar ·
[05](05-view-shell.md) drawers · [06](06-space-card.md) card · [07](07-wizard-shell.md) wizard.
