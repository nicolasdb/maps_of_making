# OHM × Maps of Making — Integration Guide

**Status:** Implemented (PR ready)  
**OHM version:** `touchthesun/openhardwaremanager:0.8.5`  
**MoM changes:** `mom.ttl` v0.2 · new `mom-to-okw.ttl` crosswalk · Mac dev environment

---

## What this is

[Open Hardware Manager (OHM)](https://github.com/touchthesun/supply-graph-ai) is a manufacturing facility registry that stores spaces as [OpenKnowWhere (OKW)](https://github.com/iop-alliance/OpenKnowWhere) documents. It knows *what* a space can manufacture. MoM knows *where* spaces are and *whether* they are alive.

This integration makes MoM's SPARQL endpoint queryable by OHM using Wikidata QIDs as the shared vocabulary hub — the same anchor OHM already uses internally via Wikipedia URLs. It also adds a Mac Docker dev environment so the full stack (MoM + OHM) can be run locally without Podman or a VPS.

The planning document that preceded this work is at `docs/draft/ohm-mom-integration.md`.

---

## What changed in MoM

### `ontology/mom.ttl` — v0.1 → v0.2

The activity vocabulary was substantially expanded and grounded. Every manufacturing concept now carries an `owl:sameAs` Wikidata IRI, enabling cross-system queries without a bespoke mapping layer.

**New top-level domains** (with Wikidata links): `mom:Crafts`, `mom:Arts`, `mom:Science`, `mom:RepairAndReuse`, `mom:FoodProduction`

**New narrower concepts** (selected):

| Concept | Wikidata | Parent |
|---|---|---|
| `mom:VacuumForming` | Q1149785 | DigitalFabrication |
| `mom:Turning` | Q1260093 | DigitalFabrication |
| `mom:PCBFabrication` | Q1047286 | Electronics |
| `mom:Programming` | Q80006 | SoftwareAndAI |
| `mom:Woodworking` | Q287483 | Crafts |
| `mom:Metalworking` | Q15328133 | Crafts |
| `mom:Welding` | Q12544 | Metalworking |
| `mom:Textiles` | Q28823 | Crafts |
| `mom:Ceramics` | Q13151 | Crafts |
| `mom:Biology` | Q420 | Science |
| `mom:Photography` | Q11633 | Arts |
| `mom:Printing` | Q11060274 | Arts |
| `mom:Painting` | Q11629 | Arts |

Result: 34 SKOS concepts, 29 with Wikidata `owl:sameAs` links.

`skos:altLabel` entries were also expanded on all concepts to include common raw activity tag strings in multiple languages (EN, FR, NL, DE), so space JSON-LD tags like `"laser"` or `"decoupe laser"` resolve to the correct concept via the existing `skos:prefLabel|skos:altLabel` bridge without any pipeline changes.

### `scripts/activity_map.yaml` — bug fix + expansion

**Bug fixed:** `activity_map.yaml` referenced `mom:CNCMilling` in four places, but the concept in `mom.ttl` is `mom:CNC`. All references corrected.

Added 80 multilingual tag mappings covering 27 concept IRIs. All IRIs are verified to exist in `mom.ttl`.

### `ontology/crosswalks/mom-to-okw.ttl` — new file

Implements the planned-but-missing crosswalk between MoM activity concepts and OKW manufacturing process concepts. Loaded into Oxigraph as `<urn:mak:crosswalk/mom-to-okw>`.

Contains:
- 8 `skos:closeMatch` alignments (e.g. `mom:LaserCutting ↔ okw:LaserCutting`)
- 3 `skos:relatedMatch` alignments (approximate/broad matches)
- A translation gap register documenting concepts with no equivalent on either side

### `scripts/load_ontology.sh` — extended

Now loads the OKW crosswalk in addition to `mom.ttl` and `iop.ttl`:

```
mom.ttl         → <urn:mak:ontology/mom>
iop/iop.ttl     → <urn:mak:ontology/iop>
mom-to-okw.ttl  → <urn:mak:crosswalk/mom-to-okw>   ← new
```

### `infra/docker-compose.mac.yml` — new file

Mac Docker override for local development. Differences from the Fedora/Podman `docker-compose.dev.yml`:
- Strips SELinux `:z` volume flags (not applicable on macOS)
- Uses `docker compose` (not `podman compose`)
- Skips `dendrite`, `dendrite-postgres`, `mak-agent-bot` (no local config needed)
- Adds the OHM service (`touchthesun/openhardwaremanager:0.8.5`) on port 8001

### `Makefile` — new `mac-*` targets

Six targets for Mac local dev:

| Target | What it does |
|---|---|
| `make mac-up` | Creates data dirs, starts MoM + OHM, waits for health checks |
| `make mac-init` | Loads ontologies + crosswalk, seeds test spaces, triggers heartbeat |
| `make mac-heartbeat` | Triggers an immediate heartbeat cycle |
| `make mac-test` | Runs the OHM×MoM E2E integration test suite |
| `make mac-down` | Stops all services (data in `data/` persists) |
| `make mac-reset` | **DESTRUCTIVE** — wipes Oxigraph + OHM storage and re-inits |

### `data/seed-lists/fabnet_eu_sample.json` — new file

20 EU fabnet spaces (filtered from `fabnet_world.bundle.json`) with activity tags including laser cutting, CNC, electronics, and others. Used by `mac-init` as a stable, committed seed so the test suite always has spaces to query against.

### `tests/test_ohm_mom_integration.py` — new file

28 E2E integration tests across five groups:

| Group | Tests | What it verifies |
|---|---|---|
| T1 Stack health | 6 | MoM SPARQL, nginx, GeoJSON, OHM health/readiness, manufacturing domain |
| T2 Ontology consistency | 7 | activity_map ↔ mom.ttl consistency, all three graphs loaded, concept count, Wikidata links, no broken IRI |
| T3 SPARQL queries | 5 | Laser/CNC/multi-capability queries via Wikidata QID, freshness tokens, GeoJSON properties |
| T4 OKW crosswalk | 4 | Specific alignments queryable, minimum count, full Wikipedia→Wikidata→MoM→OKW chain |
| T5 OHM→MoM bridge | 6 | Validate + create OKW facility, Wikipedia→Wikidata chain, OHM process → MoM SPARQL, template structure |

---

## How the integration works

OHM stores `manufacturing_processes` as Wikipedia URLs (e.g. `https://en.wikipedia.org/wiki/Laser_cutting`). MoM stores activity tags as raw strings (`"laser"`, `"laserschneiden"`) via `schema:knowsAbout`.

The bridge runs through Wikidata:

```
OHM Wikipedia URL
  → Wikidata QID (e.g. wd:Q3062349)
    ← mom:LaserCutting owl:sameAs wd:Q3062349   (mom.ttl)
      ← "laser", "laserschneiden", … skos:altLabel mom:LaserCutting   (mom.ttl)
        ← schema:knowsAbout "laser" written to space graphs by extractor
```

This means OHM can query MoM's SPARQL endpoint using a Wikidata QID and get back all matching spaces, with no changes to MoM's ingestion pipeline:

```sparql
SELECT DISTINCT ?name ?lat ?lon WHERE {
  GRAPH ?g {
    ?space a mom:Space ;
           schema:name ?name ;
           schema:geo [ schema:latitude ?lat ; schema:longitude ?lon ] ;
           schema:knowsAbout ?tag .
  }
  GRAPH <urn:mak:ontology/mom> {
    ?concept skos:prefLabel|skos:altLabel ?tag ;
             owl:sameAs <https://www.wikidata.org/entity/Q3062349> .
  }
}
```

The SPARQL endpoint is public at `https://mapsofmaking.org/sparql/query` — no API key required.

---

## Local dev setup

The MoM stack (Oxigraph, nginx, link-handler) is set up the same way it always has been. OHM runs as a standalone sidecar — it does not need to join the MoM internal network, because the integration tests reach both stacks over `localhost`.

### Prerequisites (both platforms)

- Python 3.10+ with `httpx` and `pytest` installed (`pip install httpx pytest`)
- An `.env` file at the project root with `LINK_SECRET=<any-string>`

---

### Mac (Docker)

Uses the `mac-*` Makefile targets, which wrap `docker compose` with `infra/docker-compose.mac.yml` (includes OHM as a composed service alongside MoM).

```bash
# 1. Start MoM + OHM
make mac-up

# 2. Load ontologies, seed test data, trigger heartbeat (idempotent)
make mac-init

# 3. Run the integration tests
make mac-test
```

Expected: `28 passed in ~0.5s`.

---

### Fedora / Podman

OHM is **not** added to `docker-compose.dev.yml` — it is not part of the everyday MoM dev stack. Start OHM separately using the companion setup script (`ohm-dev-setup.sh`, provided alongside this document).

```bash
# 1. Start the normal MoM stack (as usual)
make startdev          # or: make rebuild

# 2. Start OHM as a sidecar (creates data/ohm/, pulls image, waits for health)
bash ohm-dev-setup.sh

# 3. Load ontologies and crosswalk into Oxigraph
make load-ontology

# 4. Seed test spaces
OXIGRAPH_ENDPOINT=http://localhost:7878 PYTHONPATH=infra/link_handler:scripts \
  python3 scripts/seed_spaceapi.py \
    --list data/seed-lists/test-batch.json --network test-batch --force

OXIGRAPH_ENDPOINT=http://localhost:7878 PYTHONPATH=infra/link_handler:scripts \
  python3 scripts/seed_bundle.py \
    --bundle data/seed-lists/fabnet_eu_sample.json \
    --network fabnet --source fabnet-world --force

# 5. Trigger heartbeat (materializes spaces.geojson)
make heartbeat

# 6. Run the integration tests
python3 -m pytest tests/test_ohm_mom_integration.py -v --tb=short
```

Expected: `28 passed in ~0.5s`.

To stop OHM when done: `podman rm -f maps-ohm`

---

### OHM endpoints (port 8001)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check — returns `{"status": "ok", "version": "0.8.5"}` |
| `/health/readiness` | GET | Readiness check — confirms storage is accessible |
| `/v1/api/okw` | GET | List OKW facilities (paginated) |
| `/v1/api/okw/template` | GET | OKW document template |
| `/v1/api/okw/validate` | POST | Validate an OKW document |
| `/v1/api/okw/create` | POST | Store an OKW facility (see known bug below) |
| `/v1/openapi.json` | GET | Full OpenAPI spec |

### Known OHM 0.8.5 bug

`POST /v1/api/okw/create` returns HTTP 500 due to a missing `message` field in the `OKWResponse` Pydantic model. The facility **is** created despite the 500 — verify by listing with `GET /v1/api/okw`. The integration test handles this gracefully by catching the 500 and confirming creation via a subsequent GET. This is a one-line fix on the OHM side.

### Stopping and resetting

```bash
make mac-down            # stop services; data persists in data/
make mac-reset           # DESTRUCTIVE: wipe data/ and re-init (prompts for confirmation)
```

---

## OHM-side changes (separate repo)

The integration described here is complete on the MoM side. These OHM-side improvements would make it fully bidirectional:

1. **Standardise `manufacturing_process` on Wikidata IRIs.** Currently Wikipedia URLs — Wikidata IRIs would make the translation layer unnecessary and enable direct SPARQL joins.

2. **Replace `has_process()` substring matching.** The current OHM matching logic does substring searches on Wikipedia URL strings. A Wikidata-anchored vocabulary would allow hierarchical matching (e.g. `mom:Metalworking` matching `okw:Welding` via `skos:broader`).

3. **Add `to_spaceapi_json()` to `ManufacturingFacility`.** OHM facilities should be publishable as SpaceAPI-compatible JSON endpoints so MoM's heartbeat can ingest them directly — the full loop.

---

## Pre-existing test failures (not caused by this PR)

Running the full MoM test suite (`pytest tests/`) will show 12 failures unrelated to this work:

| Failure | Root cause |
|---|---|
| `test_canary_three_axis_e2e` (×5), `test_materializer_three_tokens` (×2) | `apscheduler` not installed in host Python (only in container); tests import `link_handler/main.py` directly |
| `test_geocode_proxy` (×4) | `@pytest.mark.live` tests connect to `localhost:8000` (link-handler direct port), not exposed in Mac compose; designed for Fedora/Podman stack |
| `test_spaceapi_extract_e2e` (×1) | Looks for Mother Sands canary in `spaces.geojson`; `mac-init` seeds fabnet/test-batch, not the canary |

The 60 tests that were passing before this PR continue to pass.
