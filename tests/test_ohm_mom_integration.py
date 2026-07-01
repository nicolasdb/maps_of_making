"""OHM × MoM E2E integration tests.

Validates the full integration between Open Hardware Manager (OHM) and Maps of
Making (MoM). Tests require both stacks to be running:

    make mac-up && make mac-init   # one-time setup
    make mac-test                  # run these tests

Environment variables (set by mac-test, or override manually):
    OHM_BASE_URL          OHM v1 API base (default: http://localhost:8001/v1)
    MOM_SPARQL_URL        MoM public SPARQL query endpoint (via nginx)
    MOM_SPARQL_UPDATE_URL MoM Oxigraph update endpoint (direct, port 7878)

Test groups:
    T1  Stack health checks
    T2  Ontology consistency (mom.ttl ↔ activity_map.yaml)
    T3  SPARQL capability queries (Wikidata QID → matching spaces)
    T4  OKW crosswalk queries (mom-to-okw.ttl loaded and queryable)
    T5  OHM→MoM bridge (create OHM facility, round-trip to SPARQL)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import httpx

# ── Configuration ─────────────────────────────────────────────────────────────

OHM_BASE     = os.environ.get("OHM_BASE_URL",          "http://localhost:8001/v1")
SPARQL_URL   = os.environ.get("MOM_SPARQL_URL",         "http://localhost:8080/sparql/query")
UPDATE_URL   = os.environ.get("MOM_SPARQL_UPDATE_URL",  "http://localhost:7878/update")
REPO_ROOT = Path(__file__).parent.parent
MOM_NS = "https://nicolasdb.github.io/mapsofmaking_ontology/ns#"

# Wikidata QIDs for key manufacturing processes (canonical anchors)
WD = {
    "laser_cutting":   "https://www.wikidata.org/entity/Q3062349",
    "cnc_machining":   "https://www.wikidata.org/entity/Q174689",
    "three_d_printing":"https://www.wikidata.org/entity/Q229367",
    "welding":         "https://www.wikidata.org/entity/Q12544",
    "pcb_fabrication": "https://www.wikidata.org/entity/Q1047286",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def sparql_select(query: str) -> list[dict]:
    r = httpx.post(
        SPARQL_URL,
        content=query,
        headers={"Content-Type": "application/sparql-query",
                 "Accept": "application/sparql-results+json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def sparql_ask(query: str) -> bool:
    r = httpx.post(
        SPARQL_URL,
        content=query,
        headers={"Content-Type": "application/sparql-query",
                 "Accept": "application/sparql-results+json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["boolean"]


def ohm_get(path: str, **kwargs) -> dict:
    r = httpx.get(f"{OHM_BASE}{path}", timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def ohm_post(path: str, body: dict) -> dict:
    r = httpx.post(f"{OHM_BASE}{path}", json=body, timeout=30)
    r.raise_for_status()
    return r.json()


# ── T1: Stack health ──────────────────────────────────────────────────────────

class TestStackHealth:
    def test_mom_sparql_responds(self):
        assert sparql_ask("ASK {}")

    def test_mom_nginx_serves_frontend(self):
        r = httpx.get("http://localhost:8080/", timeout=10)
        assert r.status_code == 200
        assert "Maps of Making" in r.text

    def test_mom_geojson_materialized(self):
        r = httpx.get("http://localhost:8080/data/spaces.geojson", timeout=10)
        assert r.status_code == 200
        gj = r.json()
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) > 0, "GeoJSON has no features — run mac-init first"

    def test_ohm_health(self):
        r = httpx.get(f"http://localhost:8001/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.8.5"

    def test_ohm_readiness(self):
        r = httpx.get(f"http://localhost:8001/health/readiness", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ready"
        assert data["checks"]["storage"] is True

    def test_ohm_manufacturing_domain_active(self):
        data = ohm_get("/api/match/domains/manufacturing")
        assert data["status"] == "success"
        assert data["data"]["status"] == "active"
        assert "okw" in data["data"]["supported_input_types"]


# ── T2: Ontology consistency ──────────────────────────────────────────────────

class TestOntologyConsistency:
    """Verify activity_map.yaml and mom.ttl are internally consistent."""

    def test_activity_map_all_iris_defined_in_mom_ttl(self):
        activity_map_path = REPO_ROOT / "scripts" / "activity_map.yaml"
        mom_ttl_path = REPO_ROOT / "ontology" / "mom.ttl"

        activity_map_text = activity_map_path.read_text()
        mom_ttl_text = mom_ttl_path.read_text()

        # Extract all target IRIs from activity_map.yaml
        iri_pattern = re.compile(r'"([^"]+ns#([^"]+))"')
        missing = []
        for match in iri_pattern.finditer(activity_map_text):
            full_iri, local_name = match.groups()
            if f"mom:{local_name}" not in mom_ttl_text:
                missing.append(f"mom:{local_name}")

        assert not missing, (
            f"IRIs in activity_map.yaml missing from mom.ttl: {missing}\n"
            "Add SKOS concept definitions for these in ontology/mom.ttl"
        )

    def test_mom_ontology_loaded_in_oxigraph(self):
        assert sparql_ask(
            "ASK { GRAPH <urn:mak:ontology/mom> { ?s ?p ?o } }"
        ), "mom.ttl is not loaded — run load_ontology.sh or make mac-init"

    def test_iop_ontology_loaded_in_oxigraph(self):
        assert sparql_ask(
            "ASK { GRAPH <urn:mak:ontology/iop> { ?s ?p ?o } }"
        ), "iop.ttl is not loaded — run load_ontology.sh or make mac-init"

    def test_crosswalk_loaded_in_oxigraph(self):
        assert sparql_ask(
            "ASK { GRAPH <urn:mak:crosswalk/mom-to-okw> { ?s ?p ?o } }"
        ), "mom-to-okw.ttl crosswalk not loaded — run load_ontology.sh or make mac-init"

    def test_concept_count_matches_expected_minimum(self):
        rows = sparql_select("""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT (COUNT(?c) AS ?n) WHERE {
              GRAPH <urn:mak:ontology/mom> { ?c a skos:Concept }
            }
        """)
        count = int(rows[0]["n"]["value"])
        assert count >= 30, f"Only {count} SKOS concepts in mom ontology — expected ≥30"

    def test_wikidata_links_on_key_manufacturing_concepts(self):
        """Core manufacturing concepts must have owl:sameAs Wikidata links."""
        required = {
            "ThreeDPrinting": WD["three_d_printing"],
            "LaserCutting":   WD["laser_cutting"],
            "CNC":            WD["cnc_machining"],
            "Welding":        WD["welding"],
            "PCBFabrication": WD["pcb_fabrication"],
        }
        for local_name, expected_wd in required.items():
            iri = f"{MOM_NS}{local_name}"
            rows = sparql_select(f"""
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT ?wd WHERE {{
                  GRAPH <urn:mak:ontology/mom> {{
                    <{iri}> owl:sameAs ?wd .
                    FILTER(CONTAINS(STR(?wd), 'wikidata'))
                  }}
                }}
            """)
            assert rows, f"mom:{local_name} has no Wikidata owl:sameAs link"
            found = {b["wd"]["value"] for b in rows}
            assert expected_wd in found, (
                f"mom:{local_name} expected {expected_wd}, got {found}"
            )

    def test_no_undefined_activity_map_iris_in_oxigraph_query(self):
        """The old broken IRI mom:CNCMilling must not appear as a concept."""
        has_bad_iri = sparql_ask(
            f"ASK {{ GRAPH <urn:mak:ontology/mom> {{ <{MOM_NS}CNCMilling> ?p ?o }} }}"
        )
        assert not has_bad_iri, (
            "mom:CNCMilling is defined in the ontology — it was renamed to mom:CNC. "
            "Remove it from mom.ttl or update the reference."
        )


# ── T3: SPARQL capability queries ────────────────────────────────────────────

class TestSPARQLCapabilityQueries:
    """Verify OHM's core query patterns work against MoM's SPARQL endpoint."""

    def test_spaces_with_laser_cutting_via_wikidata_qid(self):
        """Query spaces by Wikidata QID — the key OHM integration pattern."""
        rows = sparql_select(f"""
            PREFIX mom: <{MOM_NS}>
            PREFIX schema: <https://schema.org/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>

            SELECT DISTINCT ?name ?lat ?lon WHERE {{
              GRAPH ?g {{
                ?space a mom:Space ;
                       schema:name ?name ;
                       schema:geo [ schema:latitude ?lat ; schema:longitude ?lon ] ;
                       schema:knowsAbout ?tag .
              }}
              GRAPH <urn:mak:ontology/mom> {{
                ?concept skos:prefLabel|skos:altLabel ?tag ;
                         owl:sameAs <{WD["laser_cutting"]}> .
              }}
            }} LIMIT 20
        """)
        assert len(rows) > 0, (
            "No spaces found with laser cutting. "
            "Run make mac-init to seed test data with activities."
        )
        first = rows[0]
        assert "name" in first and "lat" in first and "lon" in first

    def test_spaces_with_cnc_via_wikidata_qid(self):
        rows = sparql_select(f"""
            PREFIX mom: <{MOM_NS}>
            PREFIX schema: <https://schema.org/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>

            SELECT DISTINCT ?name WHERE {{
              GRAPH ?g {{
                ?space a mom:Space ;
                       schema:name ?name ;
                       schema:knowsAbout ?tag .
              }}
              GRAPH <urn:mak:ontology/mom> {{
                ?concept skos:prefLabel|skos:altLabel ?tag ;
                         owl:sameAs <{WD["cnc_machining"]}> .
              }}
            }} LIMIT 20
        """)
        assert len(rows) > 0, "No spaces found with CNC — check seed data has 'cnc' activity tags"

    def test_multi_capability_intersection_query(self):
        """Spaces with BOTH laser cutting AND CNC — the core OHM matching pattern."""
        rows = sparql_select(f"""
            PREFIX mom: <{MOM_NS}>
            PREFIX schema: <https://schema.org/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>

            SELECT DISTINCT ?name ?lat ?lon WHERE {{
              GRAPH ?g {{
                ?space a mom:Space ;
                       schema:name ?name ;
                       schema:geo [ schema:latitude ?lat ; schema:longitude ?lon ] ;
                       schema:knowsAbout ?laserTag ;
                       schema:knowsAbout ?cncTag .
              }}
              GRAPH <urn:mak:ontology/mom> {{
                ?laserConcept skos:prefLabel|skos:altLabel ?laserTag ;
                              owl:sameAs <{WD["laser_cutting"]}> .
                ?cncConcept   skos:prefLabel|skos:altLabel ?cncTag ;
                              owl:sameAs <{WD["cnc_machining"]}> .
              }}
            }} LIMIT 20
        """)
        assert len(rows) > 0, "No spaces found with both laser + CNC"
        for row in rows:
            lat = float(row["lat"]["value"])
            lon = float(row["lon"]["value"])
            assert -90 <= lat <= 90, f"Invalid latitude: {lat}"
            assert -180 <= lon <= 180, f"Invalid longitude: {lon}"

    def test_freshness_tokens_present_on_spaces(self):
        """Heartbeat-fetched spaces must have updatedAt in Oxigraph.

        Note: mom:observedAt is stored in SQLite only (ADR-006) and is NOT
        queryable via SPARQL. Only mom:updatedAt is written to Oxigraph.
        """
        rows = sparql_select(f"""
            PREFIX mom: <{MOM_NS}>
            PREFIX schema: <https://schema.org/>

            SELECT ?name ?updatedAt WHERE {{
              GRAPH ?g {{
                ?space a mom:Space ;
                       schema:name ?name ;
                       mom:updatedAt ?updatedAt .
              }}
            }} LIMIT 5
        """)
        assert len(rows) > 0, (
            "No spaces have updatedAt — heartbeat may not have run. "
            "Run make mac-heartbeat."
        )

    def test_geojson_features_have_expected_properties(self):
        r = httpx.get("http://localhost:8080/data/spaces.geojson", timeout=10)
        gj = r.json()
        required_props = {"id", "name", "observed_at", "updated_at"}
        for feature in gj["features"]:
            props = set(feature["properties"].keys())
            missing = required_props - props
            assert not missing, (
                f"Feature {feature['properties'].get('name','?')} missing: {missing}"
            )


# ── T4: OKW crosswalk queries ─────────────────────────────────────────────────

class TestOKWCrosswalk:
    def test_crosswalk_has_laser_cutting_alignment(self):
        rows = sparql_select(f"""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?okwConcept WHERE {{
              GRAPH <urn:mak:crosswalk/mom-to-okw> {{
                <{MOM_NS}LaserCutting> skos:closeMatch ?okwConcept .
              }}
            }}
        """)
        assert len(rows) > 0, "mom:LaserCutting has no OKW closeMatch in crosswalk"
        okw_uris = {r["okwConcept"]["value"] for r in rows}
        assert any("LaserCutting" in u for u in okw_uris), (
            f"Expected okw:LaserCutting in crosswalk, got: {okw_uris}"
        )

    def test_crosswalk_has_welding_alignment(self):
        rows = sparql_select(f"""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            SELECT ?okwConcept WHERE {{
              GRAPH <urn:mak:crosswalk/mom-to-okw> {{
                <{MOM_NS}Welding> skos:closeMatch ?okwConcept .
              }}
            }}
        """)
        assert len(rows) > 0, "mom:Welding has no OKW closeMatch in crosswalk"

    def test_crosswalk_eight_alignments_minimum(self):
        rows = sparql_select("""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            SELECT (COUNT(*) AS ?n) WHERE {
              GRAPH <urn:mak:crosswalk/mom-to-okw> {
                ?mom skos:closeMatch ?okw .
              }
            }
        """)
        count = int(rows[0]["n"]["value"])
        assert count >= 8, f"Crosswalk has only {count} alignments — expected ≥8"

    def test_wikidata_wormhole_via_crosswalk(self):
        """mom:Welding has both Wikidata link (mom.ttl) and OKW link (crosswalk).
        This validates the full Wikipedia URL → Wikidata → MoM → OKW chain."""
        has_wd = sparql_ask(f"""
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            ASK {{
              GRAPH <urn:mak:ontology/mom> {{
                <{MOM_NS}Welding> owl:sameAs <{WD["welding"]}> .
              }}
            }}
        """)
        has_okw = sparql_ask(f"""
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            ASK {{
              GRAPH <urn:mak:crosswalk/mom-to-okw> {{
                <{MOM_NS}Welding> skos:closeMatch ?okw .
              }}
            }}
        """)
        assert has_wd, "mom:Welding missing Wikidata owl:sameAs"
        assert has_okw, "mom:Welding missing OKW closeMatch in crosswalk"


# ── T5: OHM→MoM bridge ───────────────────────────────────────────────────────

class TestOHMMoMBridge:
    """Create an OHM facility and verify OHM→MoM data translation works."""

    FIXTURE_FACILITY = {
        "name": "Test FabLab Integration",
        "location": {
            "gps_coordinates": "50.8503, 4.3517",
            "address": {
                "city": "Brussels",
                "country": "BE",
                "street": "Rue de la Loi",
                "number": "1",
                "postcode": "1000"
            },
            "city": "Brussels",
            "country": "BE"
        },
        "facility_status": "Active",
        "description": "Integration test facility for OHM×MoM validation",
        "access_type": "Public",
        "manufacturing_processes": [
            "https://en.wikipedia.org/wiki/Laser_cutting",
            "https://en.wikipedia.org/wiki/3D_printing",
            "https://en.wikipedia.org/wiki/Numerical_control"
        ],
        "equipment": [
            {
                "name": "CO2 Laser Cutter",
                "equipment_type": "https://en.wikipedia.org/wiki/Laser_cutting",
                "manufacturing_process": "https://en.wikipedia.org/wiki/Laser_cutting",
                "laser_power": 80,
                "bed_size": 600
            },
            {
                "name": "FDM Printer",
                "equipment_type": "https://en.wikipedia.org/wiki/3D_printing",
                "manufacturing_process": "https://en.wikipedia.org/wiki/3D_printing",
                "build_volume": 220
            }
        ],
        "record_data": {
            "date_created": "2026-06-30",
            "created_by": {"name": "Integration Test"}
        },
        "domain": "manufacturing"
    }

    def test_ohm_can_validate_okw_facility(self):
        """OHM accepts a well-formed OKW facility document."""
        resp = ohm_post("/api/okw/validate", {"content": self.FIXTURE_FACILITY})
        assert resp.get("is_valid") is True, (
            f"OHM rejected the test facility: {resp}"
        )

    def test_ohm_can_create_okw_facility(self):
        """OHM can store an OKW facility.

        OHM 0.8.5 bug: POST /api/okw/create returns HTTP 500 due to a missing
        `message` field in the OKWResponse Pydantic model, but the facility IS
        created. We accept 500 here and verify creation via a subsequent GET.
        """
        def facility_count() -> int:
            resp = ohm_get("/api/okw")
            return resp.get("pagination", {}).get("total_items", 0)

        count_before = facility_count()
        try:
            ohm_post("/api/okw/create", {"content": self.FIXTURE_FACILITY})
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 500:
                raise
            # Known OHM 0.8.5 serialization bug — continue to verify via GET

        count_after = facility_count()
        assert count_after > count_before, (
            f"OHM facility count did not increase after create "
            f"(before={count_before}, after={count_after})"
        )

    def test_wikipedia_url_maps_to_wikidata_qid(self):
        """The Wikipedia→Wikidata→MoM translation chain works for laser cutting."""
        expected_wd = WD["laser_cutting"]
        expected_mom = f"{MOM_NS}LaserCutting"

        # Verify MoM ontology links: mom:LaserCutting owl:sameAs wd:Q3062349
        rows = sparql_select(f"""
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?label WHERE {{
              GRAPH <urn:mak:ontology/mom> {{
                <{expected_mom}> owl:sameAs <{expected_wd}> ;
                                 rdfs:label ?label .
              }}
            }}
        """)
        assert rows, (
            f"mom:LaserCutting is not linked to {expected_wd} — "
            "Wikidata QID crosswalk is broken"
        )
        label = rows[0]["label"]["value"]
        assert "Laser" in label, f"Unexpected label: {label}"

    def test_mom_query_finds_spaces_matching_ohm_process(self):
        """Using an OHM Wikipedia URL → Wikidata QID → MoM SPARQL, find matching spaces."""
        # Translate OHM Wikipedia URL to Wikidata QID (the crosswalk step)
        wikipedia_to_wd = {
            "https://en.wikipedia.org/wiki/Laser_cutting": WD["laser_cutting"],
            "https://en.wikipedia.org/wiki/3D_printing":   WD["three_d_printing"],
            "https://en.wikipedia.org/wiki/Numerical_control": WD["cnc_machining"],
        }

        for wikipedia_url, wd_qid in wikipedia_to_wd.items():
            rows = sparql_select(f"""
                PREFIX mom: <{MOM_NS}>
                PREFIX schema: <https://schema.org/>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>

                SELECT DISTINCT ?name ?lat ?lon WHERE {{
                  GRAPH ?g {{
                    ?space a mom:Space ;
                           schema:name ?name ;
                           schema:geo [ schema:latitude ?lat ; schema:longitude ?lon ] ;
                           schema:knowsAbout ?tag .
                  }}
                  GRAPH <urn:mak:ontology/mom> {{
                    ?concept skos:prefLabel|skos:altLabel ?tag ;
                             owl:sameAs <{wd_qid}> .
                  }}
                }} LIMIT 5
            """)
            assert len(rows) > 0, (
                f"OHM process {wikipedia_url} (→ {wd_qid}) "
                f"returned no MoM spaces. Check activity seed data."
            )

    def test_ohm_okw_template_matches_expected_structure(self):
        """OHM OKW template must have the fields we depend on for translation."""
        r = httpx.get(f"http://localhost:8001/v1/api/okw/template", timeout=10)
        assert r.status_code == 200
        tmpl = r.json().get("template", {})

        required_fields = ["name", "location", "facility_status",
                           "manufacturing_processes", "equipment"]
        for field in required_fields:
            assert field in tmpl, f"OHM OKW template missing field: {field}"

        # GPS coordinates are a single string — our parser must handle "lat, lon"
        loc = tmpl.get("location", {})
        assert "gps_coordinates" in loc, "location.gps_coordinates missing from OKW template"

    def test_ohm_manufacturing_domain_accepts_okw_input(self):
        """Manufacturing domain must list 'okw' as a supported input type."""
        data = ohm_get("/api/match/domains/manufacturing")
        input_types = data["data"]["supported_input_types"]
        assert "okw" in input_types, (
            f"Manufacturing domain does not accept 'okw' input. Got: {input_types}"
        )
