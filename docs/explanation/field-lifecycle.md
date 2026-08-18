# Field Lifecycle — SpaceAPI payload → map card

> One field at a time, traced through every stage. This is the document to open
> when "a field is empty on the card" or "a bucket is wrong" — it tells you which
> stage dropped it.
>
> Born out of the Story 3.11 canary regression (2026-05-22): unifying four
> hand-rolled extractors into the `core:` / `mom:` layer library changed the
> triple set, and nothing told us which downstream consumer expected the old
> shape. This document is that missing contract.

## The 8 stages

Every field crosses the same eight stages. A field is only "alive on the card"
if it survives all eight.

| # | Stage | Owner | Artifact |
|---|-------|-------|----------|
| 1 | SpaceAPI payload key | the coordinator endpoint | JSON |
| 2 | Extractor | `scripts/spaceapi_extract/{core,mom}.py` | CURIE-keyed dict |
| 3 | Triple emission | `spaceapi_extract/sparql.py` `triples_for()` | SPARQL triple string |
| 4 | Oxigraph predicate | a named graph (`urn:mak:space/*`, `urn:mak:canary`) | RDF triple |
| 5 | Materializer SELECT | `scripts/materialize_geojson.py` (+ `main.py` mirror) | SPARQL binding |
| 6 | GeoJSON property | `binding_to_space()` | `web/data/spaces.geojson` |
| 7 | Browser consumer | `web/app.js` | JS object field |
| 8 | UI surface | `web/app.js` render | marker / card |

**A field can be dropped at any stage and there is no error** — it just renders
empty. Stages 2–6 are the ones that drift; stage 1 is the coordinator's, stages
7–8 are the browser's expectation.

## The layer model

The extractor is split by ontology layer. Each layer is a drop-in module; adding
a community vocabulary is a new file, not a central edit.

| Layer | Module | Namespace | Owns |
|-------|--------|-----------|------|
| `core:` | `core.py` `extract_core()` | `schema.org` | SpaceAPI v15 spec terms |
| `mom:` | `mom.py` `extract_mom()` | mom ontology | identity extensions (address, jurisdiction) |
| `communities:` | *(future)* e.g. `community_fab.py` | per-community | domain vocabularies (fab, omt, …) |
| *freshness axes* | **not the extractor** — `pipeline.py` writers | mom ontology | observed/updated/openNow — see below |
| *envelope* | **not the extractor** — each callsite | mom ontology | identity + provenance — see below |

### Critical ownership rule

The extractor is a **pure payload→dict function**. It must NEVER emit:

- **Freshness axis predicates** — `mom:observedAt`, `mom:updatedAt`,
  `mom:openNow`, `mom:lastOpenChange`. These have dedicated writers in
  `infra/link_handler/pipeline.py` that own diff-gating and minting. A negative
  unit test (`tests/test_spaceapi_extract.py`) guards this — if the extractor
  emitted them, two writers would race.
- **Envelope predicates** — `a mom:Space`, `mom:endpointUrl`, `mom:source`,
  `mom:operationalState`, `mom:memberOf`. These are identity/provenance, decided
  by the callsite (loader / seed / registration), not derivable from payload.

## Layer `core:` — `extract_core()` → schema.org

| 1 SpaceAPI key | 2 CURIE | 3 datatype | 4 Oxigraph predicate | 5 SELECT var | 6 GeoJSON prop | 7 app.js consumer | 8 UI |
|---|---|---|---|---|---|---|---|
| `space` / `name` | `schema:name` | literal | `schema:name` | `?name` | `name` | search, card title | marker label, card |
| `location.lat/lon` | `schema:geo` | blank node `schema:latitude`/`longitude` | `schema:geo [ … ]` | `?latitude ?longitude` | `geometry.coordinates` | marker placement | map pin |
| `url` | `schema:url` | IRI | `schema:url` | `?website` | `website` | card link | card "website" |
| `logo` | `schema:logo` | IRI | `schema:logo` | `?logo` | `logo` | card header | card logo img |
| `contact` (object) | `schema:contactJson` | literal (JSON string) | `schema:contactJson` | `?contactJson` | `contact` (parsed) | card contact rows | card contacts |
| `description` | `schema:description` | literal | `schema:description` | `?description` | `description` | card body | card description |
| `opening_hours` | `schema:openingHours` | literal | `schema:openingHours` | *(not selected)* | `opening_hours` (hardcoded `""`) | — | — |
| `specialties` / `knowsAbout` / `ext.tags` | `schema:knowsAbout` | one literal per item | `schema:knowsAbout` (multi) | `?specialties` (GROUP_CONCAT `\|`) | `specialties` (list) | filter chips, search | specialty filter |

**Note — `schema:openingHours` is a dead field today.** The extractor produces
it and `triples_for` writes it, but no materializer SELECTs it; `binding_to_space`
hardcodes `opening_hours: ""`. Stage 5 is the break. A real extension point — see
"Extension seams".

## Layer `mom:` — `extract_mom()` → mom ontology

| 1 SpaceAPI key | 2 CURIE | 3 datatype | 4 Oxigraph predicate | 5 SELECT var | 6 GeoJSON prop | 7 app.js consumer | 8 UI |
|---|---|---|---|---|---|---|---|
| `location.address` | `mom:address` | literal | `mom:address` | `?address` | `address` | card | card "address" |
| `location.country_code` | `mom:countryCode` | literal | `mom:countryCode` | `?countryCode` | `country_code` | *(none yet)* | — |
| `location.timezone` | `mom:timeZone` | literal | `mom:timeZone` | `?timeZone` | `timezone` | *(none yet)* | — |

**Note — `country_code` / `timezone` reach stage 6 but stage 7 is empty.** The
browser does not yet read them. They are plumbed end-to-end through the data
pipeline and waiting for a UI consumer. This is intentional (Story 3.11) — the
data contract ships before the UI.

**Address composition (regular spaces only).** For `urn:mak:space/*`, if
`mom:address` is absent the materializer composes `address` from
`schema:streetAddress` + `schema:postalCode` + `schema:addressLocality`. The
canary block does NOT select those — the canary's `address` is `mom:address` or
nothing.

## Freshness axes — heartbeat-owned, NOT the extractor

These three axes are the subject of Epic 3.5. They are written **only** by
`infra/link_handler/pipeline.py`, never by the extractor or the canary loader.

| Axis | Predicate | Store | Written by | SELECT var | GeoJSON prop | app.js | Bucket fn |
|------|-----------|-------|-----------|-----------|--------------|--------|-----------|
| **A** endpoint health | `mom:observedAt` | **SQLite** `snapshot_store.db` (NOT Oxigraph) | `fetch_snapshot()` mints once per fetch | — (SQLite join) | `observed_at` | `computeAxisA` | fresh/unresponsive/warning/broken |
| **A** fetch status | — | SQLite | `mark_unreachable()` / `write_snapshot()` | — (SQLite join) | `last_fetch_status` | `computeAxisA` | `unreachable` → broken |
| **B** content lifecycle | `mom:updatedAt` | Oxigraph | `write_updated_at()` — only on `content_changed=True` | `?updatedAt` | `updated_at` | `computeAxisB` | confirmed/aging/zombie/dead |
| **C** operational liveness | `mom:openNow` | Oxigraph | `write_open_now()` — every fetch (volatile) | `?openNow` | `open_now` | `computeAxisC` | open/shut/opt-out |
| **C** last state change | `mom:lastOpenChange` | Oxigraph | `write_open_now()` | `?lastOpenChange` | `last_open_change` | card | card timestamp |

**Marker precedence** (`computeMarker`, `app.js:340`):
`dead/zombie/aging (B)` → `broken (A)` → `open/shut (C)` → `confirmed` → `seeded`.

**Axis C `opt-out` rule:** `open_now` absent/null → `computeAxisC` returns
`opt-out` → C contributes nothing, marker falls through to confirmed/seeded.
`open_now: false` → `shut` (operator-declared closed). The two are NOT the same.

## Envelope / provenance — callsite-owned, NOT the extractor

| Predicate | Written by | Meaning | SELECT var | GeoJSON prop |
|-----------|-----------|---------|-----------|--------------|
| `a mom:Space` | every callsite | type anchor | — (WHERE clause) | — |
| `mom:endpointUrl` | loader / seed / registration | **the heartbeat eligibility gate** | `?endpointUrl` | `endpoint_url` |
| `mom:source` | every callsite | provenance tag | `?source` | `source` |
| `mom:operationalState` | canary loader | lifecycle (`seeded`/`confirmed`/…) | — | — |
| `mom:memberOf` | seed (federation) | network membership | `?network` (GROUP_CONCAT) | `network_memberships` |
| `mom:endpointHealth`, `mom:lastFetched` | canary loader | canary skeleton fields | — | — |

**`mom:endpointUrl` is load-bearing.** The heartbeat driver
(`_query_all_claimed_spaces`, `main.py:65`) selects work with
`?subject mom:endpointUrl ?endpointUrl`. **No `mom:endpointUrl` → the space is
never fetched → axes A and C never advance.** This is the heartbeat's
seeded-vs-claimed gate.

## Known breakage class: stale graph + ownership migration

The Story 3.11 canary regression is the canonical example of a **stage-4 drift**:

1. Pre-3.11, `load_canary.py` wrote `mom:openNow` / `mom:lastOpenChange` itself.
2. Story 3.11 moved Axis C ownership to the heartbeat — the loader stopped
   writing them, and started writing `mom:endpointUrl` + the new `mom:address`
   / `mom:countryCode` / `mom:timeZone` predicates.
3. Oxigraph data **persists across container rebuilds** (volume-mounted). After
   the 3.11 rebuild, the `urn:mak:canary` graph still held the **pre-3.11 triple
   shape** — `mom:openNow` present, `mom:endpointUrl` absent.
4. No `mom:endpointUrl` → heartbeat skips the canary → Axis C never refreshes →
   the stale `openNow: false` persists → card shows "shut".
5. New predicates absent → `address` / `country_code` / `timezone` render empty.
6. Never fetched → no SQLite snapshot → "no source data" in the raw-source zone.

**The lesson:** a schema change is not done when the code is merged. It is done
when every existing graph has been re-materialized to the new shape. Migrations
of the triple set need an explicit reload step, not just a code deploy.

**Recovery for the canary:**

```bash
make c-reset      # reload urn:mak:canary with the new 3.11 triple shape
make c-activate   # add mom:endpointUrl → canary becomes heartbeat-eligible
make cc-open      # flip scenario + heartbeat → Axis C refreshes
```

`c-activate` uses `CANARY_ENDPOINT_URL` (default = the public production URL).
For a local-only demo it must point at a URL the link-handler container can
reach **and** that serves the scenario-controlled JSON.

## Extension seams

The layer model exists so new processing capabilities are drop-ins, not
rewrites. Known seams:

- **`schema:knowsAbout` (specialties)** — today only feeds the filter chip.
  It is the natural attach point for further processing: specialty-based
  clustering, capability matchmaking, cross-space "who can do X" queries. A new
  consumer reads `properties.specialties` at stage 7 — no change to stages 1–6.
- **`schema:openingHours`** — already extracted and written to Oxigraph; dead at
  stage 5. Add one SELECT var + one `binding_to_space` line to revive it.
- **`communities:` layer** — a new vocabulary (fab, omt, …) is a new
  `community_<name>.py` exposing `extract_<name>()`, composed at the callsites
  that want it. `triples_for` already dispatches by value type; new CURIE
  prefixes register in `sparql.py` `_NS`.
- **`country_code` / `timezone`** — plumbed to stage 6, awaiting a stage-7/8
  consumer (local-time display, jurisdiction grouping).

When adding a field: walk all 8 stages in this document and add a row. When a
field renders empty: walk the stages and find where the row breaks.
