# Field Traceability Matrix

> The net-list at field resolution. One row per JSON field, traced across the
> [main pipeline](../explanation/architecture/01-walking-skeleton.md): **JSON key → fetch → transform → store → materialize → surface.**
>
> Each cell is read from live code, not memory — refs point at the exact source.
> Freshness-token *computation* (the A/B/C axes + marker allocation) lives in its
> own doc: [03 · Freshness axes](freshness-axes.md).

## Sketch payload

```json
{"api_compatibility": ["15"],
 "space": "openfab",
 "location": {"address": "rue gray 158, Brussels, 1050",
              "country_code": "BE",
              "lat": 50.8330173,
              "lon": 4.3783785}}
```

## The trace — full payload

Fields group by **who produces them**, which is the real structure of the pipeline. Within each group: `JSON key → ontology term → GeoJSON property → surface`. All refs are live code.

### A · Identity — extracted from the payload (P2: `extract_core` / `extract_mom`)

| JSON key | Ontology term | GeoJSON property | Surfaces as | Ref |
|---|---|---|---|---|
| `space` (or `name`) | `schema:name` | `name` | pin label, card title | `core.py:19` |
| `location.lat`+`lon` | `schema:geo` (blank node) | `geometry.coordinates [lon,lat]` | pin position | `core.py:24` |
| `url` | `schema:url` | `website` | card link | `core.py:32` |
| `logo` | `schema:logo` | `logo` | card image | `core.py:36` |
| `contact` (dict) | `schema:contactJson` (JSON string) | `contact` (re-parsed) | card contact picto row | `core.py:40`, `main.py:_parse_contact_json` |
| `description` | `schema:description` | `description` | card body | `core.py:44` |
| `opening_hours` | `schema:openingHours` | `opening_hours` | card hours | `core.py:48` |
| `specialties` / `ext.tags` / `knowsAbout` | `schema:knowsAbout` | `specialties` | filter + card tags (the **wormhole** pivot; unmapped → `gap_log.txt`, never dropped) | `core.py:52`, `activity_map.yaml` |
| `location.address` | `mom:address` (xsd:string) | `address` | card address line | `mom.py:36` |
| `location.country_code` | `mom:countryCode` | `country_code` | filter / metadata | `mom.py:40` |
| `location.timezone` | `mom:timeZone` | `timezone` | metadata | `mom.py:44` |
| `mom.memberOf` / `memberOf` | `mom:memberOf` → `urn:mak:network/<slug>` | `network_memberships` | network filter chips | `core.py:72`, SELECT `main.py:223` |
| `mom.sdgs` / `ext_fab.sdgs` | `mom:sdgs` | — _(not surfaced)_ ⚠️ | nothing yet — **Finding 4** | `core.py:83` |

### B · Registration envelope — set at claim time, not from payload (`_build_sparql_update`)

| Value | Ontology term | GeoJSON property | Surfaces as | Ref |
|---|---|---|---|---|
| submitted endpoint URL | `mom:endpointUrl` | `endpoint_url` | card source link | `main.py:616` |
| constant | `mom:source = "self-registered"` | `source` | provenance label | `main.py:617` |
| `classify_subset()` | `mom:subset` | `subset` | progressive-disclosure marker | `main.py:461,620` |
| `classify_subset()` | `mom:nextUnlock` | `next_unlock` | "add X to unlock" nudge | `main.py:622` |

### C · Freshness tokens — minted by heartbeat writers, never by extractors (`pipeline.py`)

> These four are the **raw inputs** to freshness. How the browser turns them into
> the three axes (reachability · lifecycle · open/close) and a map marker is
> [03 · Freshness axes](freshness-axes.md) — not repeated here.

| Token | Ontology term | Store | GeoJSON property | Ref |
|---|---|---|---|---|
| minted once per fetch | `mom:observedAt` | **SQLite only** | `observed_at` (re-injected at P4) | `pipeline.py:43`, `main.py:761` |
| content-change gated | `mom:updatedAt` | Oxigraph | `updated_at` | `pipeline.py:140` |
| from `state.open` | `mom:openNow` | Oxigraph | `open_now` | `pipeline.py:164` |
| from `state.lastchange` | `mom:lastOpenChange` | Oxigraph | `last_open_change` | `pipeline_helpers.py` |

> `extract_mom` is **forbidden** from emitting these four (asserted at `mom.py:49`) — they belong to the heartbeat writers alone, so there's no write-race. That's a design rule, enforced in code.

### D · Snapshot / trust receipt — SQLite + snapshot graph (Zone 3)

| Datum | Where | Surfaces as |
|---|---|---|
| verbatim payload (≤50 KB) | SQLite `mom:rawContent` | `/api/space/{id}/raw` — proof of non-alteration |
| `last_fetch_status` / `fetch_error` | SQLite | `last_fetch_status` / `last_fetch_error` in GeoJSON |
| http status, snapshot date/summary | snapshot named graph | admin / audit |

This is where `api_compatibility` (and every other compliance-only field) lives untouched — the raw receipt carries the *whole* payload regardless of what the mappers consume.

## Findings (honest-inventory)

> ⚠️ **Finding 1 — `crosswalk.csv` cites a deleted file.** Several rows reference `transformer.py:507`. That file no longer exists; the live transform is `spaceapi_extract/{core,mom}.py` + `pipeline.py`. The crosswalk notes are **stale** wherever they cite `transformer.py`. → `TODO: refresh crosswalk provenance notes`.

> ✅ **Finding 2 — RESOLVED (cut 2026-06-02).** `api_compatibility` is **required by the SpaceAPI schema** (so it stays in the input JSON and the SQLite raw receipt, untouched), but MoM does not consume it: no live extractor in `core.py`/`mom.py`, absent from `_binding_to_feature`. It had already been dropped from `classify_subset()` tier logic earlier (impl artifact 3-0-A) — the crosswalk row was the orphan left behind. **Removed from `crosswalk.csv`** (32 rows, `validate_crosswalk.py` green). The field still rides into SQLite as part of the verbatim payload — compliance preserved, Oxigraph kept clean.

> ✅ **Finding 3 — RESOLVED: state is client-side; the stored predicates are vestigial (cut 2026-06-02).** The GeoJSON carries **no** `operational_state` / `endpoint_health` property; the FeatureCollection ships the three freshness tokens + a `thresholds` block (+ per-feature `thresholds_override` for canary demo, `main.py:771`), and the **map JS derives** seeded/confirmed/aging/zombie/dead at render time — the three-token model, confirmed in code. Verified: **zero live producers** of `mom:operationalState` / `mom:endpointHealth` in `infra/link_handler/` or `spaceapi_extract/` (an earlier scrub removed the writers; only fixtures/archive remained). **Both rows removed from `crosswalk.csv`.** A `THREE_TOKENS_MISSING` fail-loud guard (`main.py:783`) protects the contract.

> 🟡 **Finding 4 — `mom:sdgs`: KEEP (dormant, route TBD).** A deliberate mom field: which UN Sustainable Development Goals a space aims at. Extracted (`core.py:83`, accepts `mom.sdgs` and transitional `ext_fab.sdgs`) and written to Oxigraph, but **no surface route exists yet**. Intended destination: the **space-profile card** (form TBD). Not vestigial — leave the extractor in place, wire the P4 surface when the card design lands.

> ✅ **Finding 5 — RESOLVED: `mom:networks` vestigial (cut 2026-06-02); `mom:memberOf` is the live concept.** `networks` was an early, too-narrow field (attach a space to VOW / RFF / etc.). Superseded by `mom:memberOf`, which surfaces today as the "network" header in the filter drawer and as a label on the space-profile card (good enough for now, refinement TBD). The orphan `networks → mom:networks` row had no live producer or consumer. **Removed from `crosswalk.csv`.**

> 🟡 **Finding 6 — placeholder GeoJSON fields: PARK (dormant, TBD).** `founded` (`""`), `capacity` (`0`), `open_for_hosting` (`false`) are hardcoded leftovers from a very early draft, no source field behind them. Parked — reintroduce only when a real use case exists (precursor to "Euro consortium grant matchmaking" and similar). Harmless now, but they make the GeoJSON look richer than the pipeline fills.

## The template for any future field

This is the contract you wanted — a new field is "done" when its row is filled end-to-end with no `—` that should be a value:

| JSON key | P2 maps to | P3 lands in | P4 GeoJSON property | Surfaces as | Source ref |
|---|---|---|---|---|---|
| `ext_fab.machines` | `fab:equipment` (draft ns) | Oxigraph | _add to `_binding_to_feature`_ | Bernard card "tools" list | _to wire_ |

A field with a trailing `—` in **Surfaces as** is a wire ending in open air (like `api_compatibility` today) — visible, undocumented-as-dead, never silently dropped.
