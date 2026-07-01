# OHM × Maps of Making — Integration Planning Document

**Date:** 2026-06-29  
**Status:** Draft 
**Author:** Nathan
**Context:** Open Hardware Manager (OHM) rests on two interlocking data standards — OpenKnowHow (OKH, representing manufacturing Requirements) and OpenKnowWhere (OKW, representing space Capabilities). OHM currently expects OKW data as discrete JSON files in cloud storage. This document assesses whether Maps of Making can serve as a live, federated OKW data feed for OHM, and how both systems might be improved in the process.

**Note on scope:** Both projects have minimal active users at this stage. The analysis is not constrained by backward-compatibility — where better architectures exist, they are named even if they require changes to current implementations.

---

## Executive Summary

Maps of Making and OHM are solving opposite halves of the same problem. MoM knows *where* spaces are and *whether* they are alive. OHM knows *what* those spaces can manufacture and *how precisely*. Neither is complete without the other.

After reviewing OHM's canonical data model (`src/core/models/okw.py`), three things are now clear:

**1. OHM's vocabulary is Wikipedia URLs, not OKW IRIs.** `Equipment.equipment_type` and `Equipment.manufacturing_process` are strings typed as Wikipedia URL references. This is pragmatic and actually superior to custom IRIs — Wikipedia URLs are universally understood and resolve to Wikidata entities, which are the best available shared vocabulary hub for manufacturing concepts.

**2. The translation path runs through Wikidata, not a custom crosswalk.** Rather than building a bespoke OHM→MoM mapping, both systems should anchor their manufacturing process vocabulary to Wikidata QIDs. Wikipedia URLs map to Wikidata via `schema:about`; MoM activity IRIs should get `owl:sameAs` links to the same Wikidata entities. The crosswalk then becomes a consequence of shared vocabulary, not a custom bridge to maintain.

**3. OHM should generate SpaceAPI endpoints, not JSON blobs.** OHM's current static-file model is exactly the problem MoM exists to solve. The most direct resolution: OHM generates or helps spaces maintain SpaceAPI-compatible JSON endpoints; MoM's heartbeat ingests them continuously. OHM's static file problem disappears; MoM gets richer capability data; no custom API integration is needed.

A fourth finding from the MoM codebase reinforces all of this: `ontology/iop/iop.ttl` explicitly stubs `iop:Equipment` with a comment pointing to `ontology/crosswalks/mom-to-okw.ttl` — a file that was planned but never built. MoM anticipated this integration; it just didn't have a partner with the OKW depth to build it.

---

## Section 1: OHM Data Model Analysis

Before answering the integration questions, it is worth mapping what OHM's `ManufacturingFacility` model actually contains and how it relates to MoM concepts.

### Top-level: ManufacturingFacility

| OHM field | Type | MoM equivalent | Notes |
|---|---|---|---|
| `name` | `str` | `schema:name` | Direct match |
| `location` | `Location` | `schema:geo` + `schema:address` | GPS coord format differs (see below) |
| `facility_status` | `FacilityStatus` enum | `mom:operationalState` | Partial — see status mapping |
| `opening_hours` | `str` | `schema:openingHours` | Direct match |
| `description` | `str` | `schema:description` | Direct match |
| `access_type` | `AccessType` enum | No equivalent | Gap — maps loosely to `mom:membershipPlans` |
| `equipment` | `List[Equipment]` | `mom:equipment` (stub) | OHM is far richer here |
| `manufacturing_processes` | `List[str]` (Wikipedia URLs) | `schema:knowsAbout` IRIs | The core vocabulary question |
| `typical_materials` | `List[Material]` | No equivalent | Gap |
| `certifications` | `List[str]` | No equivalent | Gap |
| `affiliations` | `List[Agent]` | `mom:memberOf` | Different structure (Agent vs network IRI) |
| `floor_size` | `int` (m²) | No equivalent | Gap |
| `typical_batch_size` | `BatchSize` enum | No equivalent | Gap — manufacturing-specific |
| `circular_economy` | `CircularEconomy` | No equivalent | Gap — interesting MoM extension candidate |
| `innovation_space.residencies` | `bool` | `mom:residency` | Close match |
| `record_data` | `RecordData` | MoM three-token model | Different provenance model (see below) |

### Equipment (per-machine detail)

This is where OHM is dramatically richer than anything in MoM's current schema:

| OHM field | MoM equivalent | Notes |
|---|---|---|
| `equipment_type` | `schema:knowsAbout` IRI | Wikipedia URL → Wikidata → MoM IRI |
| `manufacturing_process` | `schema:knowsAbout` IRI | Same crosswalk path |
| `make`, `model` | No equivalent | Gap — manufacturer/model detail |
| `materials_worked` | No equivalent | Gap — critical for precise matching |
| `tolerance_class` (ISO 2768) | No equivalent | Gap — precision manufacturing |
| `bed_size`, `build_volume`, `x/y/z_travel` | No equivalent | Gap — dimensional constraints |
| `laser_power` (Watts) | No equivalent | Gap |
| `quantity` | No equivalent | Gap |
| `condition` | No equivalent | Gap |

### Status and lifecycle mapping

OHM's `FacilityStatus` and MoM's operational lifecycle cover the same space but with different models:

| OHM `FacilityStatus` | MoM equivalent | Fit | Notes |
|---|---|---|---|
| `ACTIVE` | `confirmed` | Good | MoM confirmed = heartbeat responsive + content fresh |
| `PLANNED` | `seeded` | Partial | MoM seeded = we know it exists but haven't verified; OHM planned = future facility |
| `TEMPORARY_CLOSURE` | No direct match | Gap | MoM has no human-declared hiatus state. Closest is `aging` but that's inferred, not declared |
| `CLOSED` | `closed` (terminal) | Good | Both mean permanent retirement |

The gap at `TEMPORARY_CLOSURE` is interesting. MoM infers staleness automatically from heartbeat data; OHM supports explicit human declaration. These are complementary — a human-declared temporary closure in OHM could write `mom:openNow: false` to the SpaceAPI endpoint, which MoM reads as the Axis C signal.

### GPS coordinate format mismatch

OHM uses: `gps_coordinates: Optional[str]  # Decimal degrees` — a single string like `"51.5074, -0.1278"`

MoM uses: `schema:geo → schema:GeoCoordinates` with separate `schema:latitude` and `schema:longitude` literals.

This needs a parser when translating OHM records to SpaceAPI format. Trivial code, but worth noting.

### Provenance models differ

OHM's `RecordData` tracks human-attested creation, update, and verification (who did what and when). MoM's three-token model tracks machine-observed freshness (when did we last reach this endpoint, when did content change, when did open/closed change). These are complementary:

- OHM: "Alice verified this equipment list on 2026-05-14"
- MoM: "We fetched this endpoint at 09:14 today and the content hasn't changed since 2026-05-14"

Both matter. The OHM attestation is a trust signal OHM could publish in the SpaceAPI endpoint metadata; MoM would ingest it as provenance data.

---

## Section 2: The Vocabulary Question — Wikipedia, Wikidata, and MoM IRIs

### What OHM actually uses

OHM's `manufacturing_processes` is a list of Wikipedia URLs. For example, a laser cutter entry might carry:

```python
manufacturing_processes=["https://en.wikipedia.org/wiki/Laser_cutting"]
equipment=[Equipment(
    equipment_type="https://en.wikipedia.org/wiki/Laser_cutting",
    manufacturing_process="https://en.wikipedia.org/wiki/Laser_cutting",
    laser_power=150,
    bed_size=600,
    ...
)]
```

The `has_process()` method on `ManufacturingFacility` currently matches these via substring search — `"laser" in url.lower()` — which is fragile and will produce false positives as the vocabulary grows.

### The Wikidata hub proposal

Wikipedia URLs and Wikidata entities are two sides of the same coin. Every Wikipedia article about a concept has a canonical Wikidata entity (`schema:about`). Wikidata entities have:

- Stable machine-readable IRIs (e.g., `http://www.wikidata.org/entity/Q332988` for laser cutting)
- Multilingual labels in 300+ languages — which directly solves MoM's `activity_map.yaml` normalization problem
- `owl:sameAs` connections to DBpedia, schema.org, and other open datasets
- Sub-class hierarchies (FDM is a subclass of 3D printing, CO2 laser is a subclass of laser cutting)

**Proposal:** Both systems adopt Wikidata QIDs as the shared canonical vocabulary for manufacturing processes and equipment types.

For OHM, this means a small change: store Wikidata IRIs (`http://www.wikidata.org/entity/Q...`) instead of Wikipedia URLs, or store both and add a `wikidata_id` field to `Equipment`. The Wikipedia URL is the human-readable link; the Wikidata IRI is the machine-readable anchor.

For MoM, this means adding `owl:sameAs` triples to existing activity IRIs:

```turtle
mom:ns#LaserCutting  owl:sameAs  <http://www.wikidata.org/entity/Q332988> .
mom:ns#ThreeDPrinting  owl:sameAs  <http://www.wikidata.org/entity/Q685> .
mom:ns#CNCMilling  owl:sameAs  <http://www.wikidata.org/entity/Q11465> .
```

MoM keeps its existing IRIs (backward compatible, no data migration), but every activity concept is now anchored to a universally agreed identifier. The crosswalk then becomes a consequence: any system using Wikidata QIDs can query MoM's triplestore, and vice versa.

More ambitiously: MoM could replace its custom activity IRIs with Wikidata IRIs entirely, using the `activity_map.yaml` multilingual labels from Wikidata directly. This would eliminate the need to maintain `activity_map.yaml` as its own translation table — Wikidata already has labels in every language MoM needs.

### Implications for the `has_process()` method

The current substring-based matching in OHM should be replaced with an IRI lookup:

```python
# Current (fragile):
if "laser" in process_url.lower(): ...

# Proposed (robust):
WIKIDATA_IRI = "http://www.wikidata.org/entity/Q332988"  # laser cutting
if any(eq_uri == WIKIDATA_IRI for eq_uri in facility.manufacturing_process_iris): ...
```

Or, if querying MoM SPARQL, the query is against a known IRI and no substring matching is involved at all.

---

## Section 3: Concrete Crosswalk Draft

This table maps OHM's Wikipedia URL vocabulary to Wikidata QIDs and MoM activity IRIs. It is the seed for `ontology/crosswalks/mom-to-okw.ttl`. QIDs marked `[verify]` should be confirmed against Wikidata before implementation.

**Format:** `skos:exactMatch` = same concept; `skos:closeMatch` = same category, precision differs; `gap` = no MoM IRI exists, one needs to be minted.

### Confirmed matches (MoM IRI exists, concept is clear)

| Wikipedia URL | Wikidata QID | MoM IRI | Match type | Notes |
|---|---|---|---|---|
| `.../wiki/Laser_cutting` | Q332988 | `mom:ns#LaserCutting` | exactMatch | |
| `.../wiki/Laser_engraving` | Q1139986 [verify] | `mom:ns#LaserCutting` | closeMatch | Precision loss — engraving ≠ cutting |
| `.../wiki/3D_printing` | Q685 | `mom:ns#ThreeDPrinting` | closeMatch | Wikipedia article is additive mfg broadly |
| `.../wiki/Fused_deposition_modeling` | Q1122768 [verify] | `mom:ns#ThreeDPrinting` | closeMatch | FDM specifically; MoM loses this distinction |
| `.../wiki/Stereolithography` | Q466570 [verify] | `mom:ns#ThreeDPrinting` | closeMatch | SLA specifically; same MoM IRI |
| `.../wiki/Selective_laser_sintering` | Q901238 [verify] | `mom:ns#ThreeDPrinting` | closeMatch | SLS; same MoM IRI |
| `.../wiki/Numerical_control` | Q11465 | `mom:ns#CNCMilling` | closeMatch | NC is broader than CNC milling specifically |
| `.../wiki/CNC_router` | Q1142888 [verify] | `mom:ns#CNCMilling` | closeMatch | |
| `.../wiki/Milling_(machining)` | Q622529 [verify] | `mom:ns#CNCMilling` | closeMatch | Manual milling too; not just CNC |
| `.../wiki/Woodworking` | Q19557 | `mom:ns#Woodworking` | exactMatch | |
| `.../wiki/Metalworking` | Q179600 | `mom:ns#Metalworking` | exactMatch | |
| `.../wiki/Electronics` | Q11650 | `mom:ns#Electronics` | closeMatch | Broad; making/soldering is narrower |
| `.../wiki/Soldering` | Q181083 | `mom:ns#Electronics` | closeMatch | Specific process within electronics |
| `.../wiki/Textile` | Q28823 | `mom:ns#Textiles` | exactMatch | |
| `.../wiki/Sewing` | Q28472 | `mom:ns#Textiles` | closeMatch | |
| `.../wiki/Embroidery` | Q28167 | `mom:ns#Embroidery` | exactMatch | |
| `.../wiki/Ceramics` | Q25381 | `mom:ns#Ceramics` | exactMatch | |
| `.../wiki/Pottery` | Q175166 [verify] | `mom:ns#Ceramics` | closeMatch | |
| `.../wiki/Photography` | Q11633 | `mom:ns#Photography` | exactMatch | |
| `.../wiki/Printing` | Q11629 [verify] | `mom:ns#Printing` | closeMatch | Broad printing; screen/offset/inkjet all collapse |
| `.../wiki/Screen_printing` | Q211028 | `mom:ns#Printing` | closeMatch | |
| `.../wiki/Vinyl_cutter` | Q1436327 [verify] | `mom:ns#VinylCutting` | exactMatch | |
| `.../wiki/Biology` | Q420 | `mom:ns#Biology` | closeMatch | Broad; bio lab work is narrower |
| `.../wiki/Food_processing` | Q1434656 [verify] | `mom:ns#FoodProduction` | closeMatch | |
| `.../wiki/Painting` | Q11629 [verify] | `mom:ns#Painting` | exactMatch | |

### Gaps — OHM processes with no MoM IRI (new IRIs needed)

These are common in OHM's domain but absent from MoM's current activity set. MoM should mint new `mom:ns#` IRIs and add Wikidata `owl:sameAs` links.

| Wikipedia URL | Wikidata QID | Proposed MoM IRI | Priority | Notes |
|---|---|---|---|---|
| `.../wiki/Welding` | Q179577 | `mom:ns#Welding` | High | Very common in makerspaces |
| `.../wiki/Injection_moulding` | Q176215 | `mom:ns#InjectionMoulding` | Medium | More industrial; rare in community spaces |
| `.../wiki/Vacuum_forming` | Q1048484 [verify] | `mom:ns#VacuumForming` | Medium | Accessible in well-equipped fab labs |
| `.../wiki/Lathe` | Q187833 [verify] | `mom:ns#Turning` | Medium | Turning/lathing — distinct from CNC milling |
| `.../wiki/Electroplating` | Q48013 [verify] | `mom:ns#Electroplating` | Low | Specialist |
| `.../wiki/PCB_manufacturing` | Q182477 [verify] | `mom:ns#PCBFabrication` | High | Common, and distinct from general electronics |
| `.../wiki/Laser_welding` | Q588156 [verify] | `mom:ns#LaserWelding` | Low | Rare in community spaces |
| `.../wiki/Sandblasting` | Q1364322 [verify] | `mom:ns#Sandblasting` | Low | |

### Many-to-one collapses (precision currently lost in MoM)

These are cases where OHM can distinguish sub-processes that MoM collapses to a single IRI. As MoM's activity set matures, these could be split:

| OHM distinction | Current MoM IRI | Future split IRIs |
|---|---|---|
| FDM vs SLA vs SLS vs resin | `mom:ns#ThreeDPrinting` | `mom:ns#FDMPrinting`, `mom:ns#SLAPrinting`, `mom:ns#SLSPrinting` |
| CO2 laser cutting vs fiber laser | `mom:ns#LaserCutting` | `mom:ns#CO2LaserCutting`, `mom:ns#FiberLaserCutting` |
| CNC milling vs CNC routing vs CNC turning | `mom:ns#CNCMilling` | `mom:ns#CNCMilling`, `mom:ns#CNCRouting`, `mom:ns#CNCTurning` |
| PCB fabrication vs general electronics | `mom:ns#Electronics` | `mom:ns#PCBFabrication`, `mom:ns#Electronics` |

---

## Section 4: Can OHM Query MoM Directly?

**Yes. Two surfaces exist today, with different trade-offs:**

### Surface A — Public SPARQL Endpoint

**Endpoint:** `https://mapsofmaking.org/sparql/query`  
**Methods:** GET and POST  
**Format:** SPARQL 1.1 SELECT, `application/sparql-results+json`  
**Auth:** None (public, read-only)  
**CORS:** `Access-Control-Allow-Origin: *`

Once the Wikidata `owl:sameAs` links are added to MoM's activity IRIs, OHM can query by Wikidata IRI directly:

```sparql
PREFIX schema: <https://schema.org/>
PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?name ?lat ?lon ?updatedAt WHERE {
  GRAPH ?g {
    # Bind to Wikidata IRI for laser cutting
    ?activity owl:sameAs <http://www.wikidata.org/entity/Q332988> .
    ?space schema:name ?name ;
           schema:geo ?geo ;
           schema:knowsAbout ?activity ;
           mom:updatedAt ?updatedAt .
    ?geo schema:latitude ?lat ;
         schema:longitude ?lon .
    FILTER(?lat > 48.0 && ?lat < 52.0 && ?lon > 2.0 && ?lon < 8.0)
  }
}
ORDER BY DESC(?updatedAt)
```

Or more simply, once the crosswalk is in place, OHM translates its Wikipedia URL to the equivalent MoM IRI client-side and queries directly:

```sparql
# "https://en.wikipedia.org/wiki/Laser_cutting" → mom:ns#LaserCutting via crosswalk
SELECT ?name ?lat ?lon ?updatedAt WHERE {
  GRAPH ?g {
    ?space schema:name ?name ;
           schema:knowsAbout <https://nicolasdb.github.io/mapsofmaking_ontology/ns#LaserCutting> ;
           schema:geo ?geo ;
           mom:updatedAt ?updatedAt .
    ?geo schema:latitude ?lat ;
         schema:longitude ?lon .
  }
}
```

**What is queryable today:**
- Name, geo, address, website, country, timezone
- Activities/capabilities (`schema:knowsAbout`)
- Network membership (`mom:memberOf`)
- Freshness: `mom:updatedAt`, `mom:openNow`, `mom:lastOpenChange`
- Endpoint liveness: `mom:endpointUrl`

**What is not yet queryable (requires enrichment):**
- Machine-level specs (bed size, laser power, tolerances)
- Materials worked
- Certifications
- Batch size / capacity

### Surface B — Materialized GeoJSON

**Endpoint:** `https://mapsofmaking.org/data/spaces.geojson`  
Refreshed every ~10 minutes. Simpler to consume but less flexible — suited for a full-catalog sync, not per-query capability matching.

**Recommendation:** Use SPARQL for capability queries. Use GeoJSON for periodic health monitoring of the full space fleet.

---

## Section 5: How Much Translation Is Required?

### Short answer

For coarse process-category matching (does this space have X capability?), the translation is a lookup table — feasible in a day once the crosswalk is drafted. For precise matching (can this space manufacture this specific part?), the data simply doesn't exist in MoM yet, and getting it there requires OHM to help spaces publish richer endpoints.

### Vocabulary translation

With the Wikidata hub approach, the translation is:

```
OHM Wikipedia URL
    → Wikipedia article = Wikidata entity (via schema:about)
    → Wikidata QID
    → MoM activity IRI (via owl:sameAs)
```

The crosswalk in Section 3 is the lookup table. It covers the ~25 most common manufacturing processes in the MoM/OHM overlap and flags ~8 gaps where MoM needs new IRIs.

### Multilingual normalization

MoM currently maintains `activity_map.yaml` to normalize German, English, and French tags to shared IRIs. If MoM adopts Wikidata QIDs as its activity anchors, this table can be deprecated — Wikidata provides multilingual labels for every entity. A space in Germany tagging their endpoint with "Laserschneiden" resolves to the same Wikidata entity as an English-speaking space tagging it "laser cutting."

This is an improvement for MoM independent of the OHM integration: the activity vocabulary becomes self-describing and extensible without manual YAML maintenance.

### Granularity gap

OHM has machine-level fields with no MoM equivalent:

| OHM precision | MoM equivalent | Status |
|---|---|---|
| Process category (laser cutting) | `schema:knowsAbout` IRI | ✅ Works today via crosswalk |
| Sub-process (CO2 vs fiber laser) | No distinction in MoM | ❌ Requires new MoM IRIs |
| Machine specs (bed size, power) | No equivalent | ❌ Requires new `mom:extended` fields |
| Materials (aluminium, PETG, etc.) | No equivalent | ❌ Requires new schema |
| Tolerances (ISO 2768) | No equivalent | ❌ Requires new schema |

The gap at machine-spec level is real but not a blocker for v1. A coarse match (does this space have a laser cutter?) is immediately useful and substantially better than OHM's current static files. The precision improves progressively as OHM helps spaces enrich their endpoints.

---

## Section 6: Can OHM Enrich MoM?

### Primary path: OHM generates SpaceAPI endpoints

The most direct and highest-value enrichment: OHM should generate or assist spaces in maintaining SpaceAPI-compatible JSON endpoints. MoM's heartbeat ingests these automatically; no custom API integration is needed.

OHM already has `ManufacturingFacility.to_dict()` and `to_toml()`. Adding `to_spaceapi_json()` is the key new method. A SpaceAPI-compatible output from OHM would:

1. Map `manufacturing_processes` (Wikipedia URLs) → SpaceAPI `ext.tags` / `mom:extended.equipment` using the crosswalk
2. Map `facility_status` → `state.open` (and use `TEMPORARY_CLOSURE` as a `state.lastchange` signal)
3. Map `location.gps_coordinates` → `location.lat` + `location.lon`
4. Map `opening_hours` → SpaceAPI `opening_hours`
5. Serialize `equipment` list → `mom:extended.equipment` with OKW field names

The space operator registers the OHM-generated endpoint URL with MoM once. After that, every OHM update propagates to MoM on the next heartbeat cycle — automatic, live, decentralized. This is OHM solving its own stale-data problem by delegating freshness to MoM's infrastructure.

**Rough sketch of `to_spaceapi_json()`:**

```python
def to_spaceapi_json(self, crosswalk: dict) -> dict:
    lat, lon = parse_gps(self.location.gps_coordinates)
    return {
        "api_compatibility": ["14", "15"],
        "space": self.name,
        "url": self.location.address.to_url() if self.location.address else "",
        "location": {"lat": lat, "lon": lon},
        "state": {
            "open": self.facility_status == FacilityStatus.ACTIVE,
        },
        "opening_hours": self.opening_hours,
        "ext": {
            "tags": [
                crosswalk.get(p, p)  # Wikipedia URL → MoM IRI or raw URL
                for p in self.manufacturing_processes
            ],
            "okw": {
                "equipment": [e.to_dict() for e in self.equipment],
                "typical_materials": [m.to_dict() for m in self.typical_materials],
                "certifications": self.certifications,
                "access_type": self.access_type.value,
                "typical_batch_size": self.typical_batch_size.value if self.typical_batch_size else None,
            }
        }
    }
```

### Secondary path: OHM as a MoM Library contributor

MoM's Library vision (`docs/draft/community_library_of_tools_structured.md`) describes an "app store for structured space data" where contributors add field definitions + bot query functions. The Library explicitly cites open hardware as an example entry:

> *"A Library field for 'devices built here' lets anyone find where to buy an already-built device, where to get hands-on help, where to join a build session."*

OHM is the natural contributor for the manufacturing capability Library entry:
- Define the `okw:` field schema for equipment specs
- Build the Bernard bot function: `!mom find spaces near Lyon that can laser-cut 5mm acrylic`
- Contribute back `crosswalk.csv` rows for `okw:` community namespace
- The key principle: **a field that answers real questions gives spaces a reason to keep it current**

### Tertiary path: Attestation as a trust signal

OHM's `RecordData` (who created/verified the record and when) is a trust signal MoM currently lacks. A space's self-reported SpaceAPI endpoint has no attestation; an OHM-generated endpoint that carries `record_data.verified_by` in its `ext` block gives MoM a way to distinguish independently-verified capability data from self-declared data.

This is low-friction: OHM already tracks this data; it just needs to be included in the SpaceAPI output. MoM can ingest it as a new predicate (`mom:verifiedBy`, `mom:verifiedAt`) and surface it in the space card's trust receipt.

---

## Section 7: Proposed Integration Architecture

```
OHM (requirement + inventory side)
─────────────────────────────────────────────────────
OKH file describes hardware project requirements
  → parse manufacturing_processes (Wikidata IRIs)
  → match against MoM SPARQL endpoint
  → filter by geo bounding box + freshness threshold
  ← candidate spaces with capability + freshness data
  → rank by freshness, proximity, spec match depth
  → display on OHM UI with live MoM freshness badge

OHM also manages equipment inventory for spaces
  → ManufacturingFacility.to_spaceapi_json()
  → space hosts JSON at URL they control
  → space registers URL with MoM once
                         ↓
MoM (aggregation + discovery side)
─────────────────────────────────────────────────────
Heartbeat fetches SpaceAPI endpoint every ~10min
  → detect content change → transform → ingest
  → mom:updatedAt minted on change (Axis B)
  → spaces.geojson rematerialized

Oxigraph triplestore holds:
  → mom:ns#LaserCutting owl:sameAs wd:Q332988
  → all capability data queryable by Wikidata IRI
  → three freshness tokens per space

Bernard bot (Matrix / Discord)
  → "!mom find CNC milling near Brussels"
  → same SPARQL query OHM uses
  → Bernard-voice answer with freshness indicators
```

One query mechanism serves OHM (programmatic) and Bernard (conversational). One data layer. One ingestion pipeline.

---

## Section 8: Proposed Roadmap

### Phase 0 — Confirm live data (½ day, no code)

Issue SPARQL queries against `https://mapsofmaking.org/sparql/query`. Confirm:
- How many confirmed spaces have `schema:knowsAbout` populated
- Which activity IRIs are most common
- Query latency for bounding-box + capability filters

**Output:** Baseline data inventory; go/no-go on SPARQL as the query surface.

### Phase 1 — Build the shared vocabulary layer (1–2 weeks, ontology work)

Two parallel tracks:

**MoM side:**
- Add `owl:sameAs` Wikidata links to existing activity IRIs in `mom.ttl`
- Mint new IRIs for the gap processes (Welding, PCBFabrication, Turning, VacuumForming)
- Create `ontology/crosswalks/mom-to-okw.ttl` with the full crosswalk table
- Update `activity_map.yaml` to include Wikidata QIDs alongside the IRI mapping (or deprecate it in favour of Wikidata labels)

**OHM side:**
- Standardize `manufacturing_process` and `equipment_type` storage on Wikidata IRIs (with Wikipedia URL as `rdfs:seeAlso`)
- Replace `has_process()` substring matching with IRI equality check

**Output:** Shared vocabulary. A Wikidata IRI in OHM maps to a MoM activity IRI with zero ambiguity.

### Phase 2 — OHM reads MoM live (2–3 weeks, OHM-side)

Replace OHM's static JSON loader with a SPARQL client:
- Translate OKH requirements (Wikidata process IRIs) to MoM query
- Filter by geo + freshness threshold
- Return ranked candidate spaces with `mom:updatedAt` as confidence signal

**Output:** OHM finds candidate spaces from live MoM data. Static files become a testing fallback only.

### Phase 3 — OHM generates SpaceAPI endpoints (3–6 weeks, OHM-side)

Add `ManufacturingFacility.to_spaceapi_json()` using the crosswalk. Provide tooling for spaces to host the generated file. Space operators register the URL with MoM once.

**Output:** OHM-managed spaces appear in MoM with machine-level capability data. The stale-file problem is eliminated by MoM's heartbeat.

### Phase 4 — Library entry + bot function (ongoing, joint)

Formalize the `okw:` namespace as a MoM Library entry. Build the Bernard bot function for capability queries. Contribute crosswalk rows to MoM's `crosswalk.csv`.

**Output:** "Find spaces that can manufacture X" is a native MoM bot command.

---

## Open Questions

1. **Which Wikidata QIDs does OHM use in practice?** The crosswalk in Section 3 is a draft based on expected coverage. Inspecting actual OHM data would confirm which Wikipedia URLs appear most frequently and whether there are any unexpected entries.

2. **OHM space identity vs MoM space identity.** OHM uses UUIDs; MoM uses `urn:mak:space/{slug}`. If a space exists in both systems, how do we link the records? Options: OHM writes its UUID into the SpaceAPI `ext` block; MoM stores it as `mom:ohmId`; or the SpaceAPI endpoint URL is the shared key (spaces register the same URL with both systems).

3. **Who hosts the OHM-generated SpaceAPI endpoint?** OHM could host it (`api.ohm.example/spaces/{id}/spaceapi.json`), or it could generate a file the space downloads and hosts themselves, or it could push to a git repo the space controls (aligning with MoM's existing deploy-key write path). Each option has sovereignty implications.

4. **SpaceAPI upstream proposal.** MoM is positioning itself as a SpaceAPI JSON-LD reference implementation. The `okw:equipment` structured field should be proposed to the SpaceAPI schema working group (the v16 draft is already expanding the schema). If it lands in the SpaceAPI spec, it becomes available to every SpaceAPI-compatible directory, not just MoM.

5. **Freshness SLA.** OHM's use case may require a fresher capability signal than MoM's ~10-minute heartbeat. How stale is too stale for OHM's matching? If near-real-time matters, OHM could query the space's SpaceAPI endpoint directly for the most current data, and use MoM only for discovery (finding candidates).

6. **Data conflicts.** A space's self-reported SpaceAPI endpoint may differ from what OHM has recorded (OHM's record is older, or more detailed, or both). Clear provenance rules are needed: MoM's heartbeat is always the authoritative freshness signal; OHM's attestation is the authoritative accuracy signal.

---

## Appendix: Relevant Code Locations

| File | Relevance |
|---|---|
| `src/core/models/okw.py` (OHM) | `ManufacturingFacility`, `Equipment`, `Material` — the OHM data model |
| `ontology/iop/iop.ttl` | `iop:Equipment` stub + OKW crosswalk reference |
| `ontology/crosswalk.csv` | MoM field bridge registry; new `okw:` rows would go here |
| `ontology/mom.ttl` | Activity IRIs that need Wikidata `owl:sameAs` links |
| `scripts/activity_map.yaml` | Multilingual tag normalization — candidate for Wikidata replacement |
| `infra/link_handler/main.py` | SPARQL queries + registration API |
| `infra/nginx/conf.d/app.conf` | `/sparql/query` public endpoint config |
| `web/data/spaces.geojson` | Materialized data — GeoJSON integration surface |
| `docs/draft/community_library_of_tools_structured.md` | Library vision — OHM as a Library contributor |
| `_bmad-output/planning-artifacts/architecture.md` | ADR-016 (ontology model), ADR-015 (ingestion pipeline) |
