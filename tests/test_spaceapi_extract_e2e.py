"""Live integration tests for Story 3.11: unified payload extractor end-to-end.

Covers the four callsite migration: canary loader → Oxigraph → materializer,
and the heartbeat re-extract path (write_payload_fields).

Requires: live Oxigraph at OXIGRAPH_URL (default localhost:7878).

Run:
  pytest tests/test_spaceapi_extract_e2e.py -v -m live_integration
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
import socket
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "infra" / "link_handler"))

OXIGRAPH_URL = os.getenv("OXIGRAPH_URL", "http://localhost:7878").rstrip("/")
if OXIGRAPH_URL.endswith("/query"):
    OXIGRAPH_URL = OXIGRAPH_URL[: -len("/query")]

MOM_NS = "https://nicolasdb.github.io/mapsofmaking_ontology/ns#"
CANARY_GRAPH = "urn:mak:canary"
CANARY_SUBJECT = "urn:mak:canary/mother-sands"


def _oxigraph_reachable() -> bool:
    try:
        httpx.get(f"{OXIGRAPH_URL}/query", timeout=2.0)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.live_integration


@pytest.fixture(scope="module", autouse=True)
def require_oxigraph():
    if not _oxigraph_reachable():
        pytest.skip(f"Oxigraph not reachable at {OXIGRAPH_URL}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sparql_query(sparql: str) -> dict:
    resp = httpx.post(
        f"{OXIGRAPH_URL}/query",
        content=sparql,
        headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def _ask(sparql: str) -> bool:
    return bool(_sparql_query(sparql).get("boolean", False))


def _select_value(sparql: str, var: str) -> str | None:
    bindings = _sparql_query(sparql).get("results", {}).get("bindings", [])
    if not bindings:
        return None
    return bindings[0].get(var, {}).get("value")


def _run_load_canary(simulated_age: int | None = 0) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["OXIGRAPH_ENDPOINT"] = OXIGRAPH_URL
    payload_path = REPO_ROOT / "web" / "canary" / "mother-sands.json"
    payload = json.loads(payload_path.read_text())
    payload.setdefault("ext_mom", {})["simulatedAge"] = simulated_age
    payload_path_tmp = REPO_ROOT / "web" / "canary" / "_test_mother-sands.json"
    payload_path_tmp.write_text(json.dumps(payload))
    try:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "load_canary.py"), "--payload", str(payload_path_tmp)],
            capture_output=True, text=True, timeout=30, env=env,
        )
    finally:
        payload_path_tmp.unlink(missing_ok=True)
    return result


# ── Tests ────────────────────────────────────────────────────────────────────

class TestCanaryLoaderTripleContract:
    """AC 2, AC 9: canary loader uses spaceapi_extract; new predicates land in Oxigraph."""

    def test_mom_address_written(self):
        """mom:address extracted from location.address appears in canary graph."""
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "load_canary.py")],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "OXIGRAPH_ENDPOINT": OXIGRAPH_URL},
        )
        assert result.returncode == 0, result.stderr

        val = _select_value(
            f"""PREFIX mom: <{MOM_NS}>
SELECT ?v WHERE {{ GRAPH <{CANARY_GRAPH}> {{ <{CANARY_SUBJECT}> mom:address ?v }} }}""",
            "v",
        )
        assert val is not None, "mom:address not written to canary graph"
        assert "North Sea" in val or "Maunsell" in val, f"Unexpected address: {val!r}"

    def test_mom_country_code_written(self):
        val = _select_value(
            f"""PREFIX mom: <{MOM_NS}>
SELECT ?v WHERE {{ GRAPH <{CANARY_GRAPH}> {{ <{CANARY_SUBJECT}> mom:countryCode ?v }} }}""",
            "v",
        )
        assert val == "sol-3", f"mom:countryCode expected 'sol-3', got {val!r}"

    def test_mom_timezone_written(self):
        val = _select_value(
            f"""PREFIX mom: <{MOM_NS}>
SELECT ?v WHERE {{ GRAPH <{CANARY_GRAPH}> {{ <{CANARY_SUBJECT}> mom:timeZone ?v }} }}""",
            "v",
        )
        assert val == "UTC+0", f"mom:timeZone expected 'UTC+0', got {val!r}"

    def test_freshness_predicates_absent_from_canary_graph(self):
        """Heartbeat owns Axis C — openNow/lastOpenChange must not be seeded by loader."""
        for pred in ("openNow", "lastOpenChange", "observedAt"):
            present = _ask(
                f"""PREFIX mom: <{MOM_NS}>
ASK {{ GRAPH <{CANARY_GRAPH}> {{ <{CANARY_SUBJECT}> mom:{pred} ?v }} }}"""
            )
            assert not present, f"Freshness predicate mom:{pred} leaked into canary graph via loader"


class TestMaterializerExposesMom:
    """AC 7: materializer SELECT now includes countryCode/timeZone; feature props exposed."""

    def test_materialize_geojson_includes_country_code_and_timezone(self, monkeypatch, tmp_path):
        """Run the live materializer; check Mother Sands feature has country_code/timezone.

        Repointed 2026-07-01: scripts/materialize_geojson.py was deleted 2026-06-03
        (commit 6ddf9db, honest-inventory triage) as a hand-synced duplicate of the
        live `_rematerialize_geojson` in infra/link_handler/main.py. The subprocess
        call below was failing silently and this test was falling back to reading
        stale web/data/spaces.geojson instead of exercising the materializer at all.
        See tests/test_materializer_three_tokens.py::_materialize_spaces for the
        established repoint pattern this mirrors.
        """
        import asyncio
        import tempfile

        sys.path.insert(0, str(REPO_ROOT / "infra" / "link_handler"))
        import main as link_handler_main

        monkeypatch.setenv("SNAPSHOT_DB_PATH", str(tmp_path / "snapshot_store.db"))
        link_handler_main.OXIGRAPH_ENDPOINT = OXIGRAPH_URL
        fd, out_path = tempfile.mkstemp(suffix=".geojson")
        os.close(fd)
        link_handler_main.GEOJSON_OUTPUT = out_path
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(link_handler_main._rematerialize_geojson())
            data = json.loads(Path(out_path).read_text())
        finally:
            Path(out_path).unlink(missing_ok=True)

        features = data.get("features", [])
        canary_features = [
            f for f in features
            if "mother-sands" in f.get("properties", {}).get("uri", "").lower()
            or "Mother Sands" in f.get("properties", {}).get("name", "")
        ]
        assert canary_features, "Mother Sands not found in materialized GeoJSON"
        props = canary_features[0]["properties"]
        assert "country_code" in props, "country_code key missing from feature properties"
        assert "timezone" in props, "timezone key missing from feature properties"
        assert props["country_code"] == "sol-3", f"Expected 'sol-3', got {props['country_code']!r}"
        assert props["timezone"] == "UTC+0", f"Expected 'UTC+0', got {props['timezone']!r}"


class TestHeartbeatWritePayloadFields:
    """AC 6: heartbeat write_payload_fields re-extracts address/contact/etc. on content_changed."""

    def test_write_payload_fields_writes_mom_address(self):
        """write_payload_fields on a Mother Sands payload writes mom:address to test graph."""
        import asyncio
        from pipeline import write_payload_fields

        test_graph = "urn:mak:test/3-11-e2e"
        test_subject = f"{test_graph}/space"
        payload = {
            "space": "E2E Test Space",
            "location": {
                "lat": 51.0,
                "lon": 4.0,
                "address": "42 Pipeline Street",
                "country_code": "BE",
                "timezone": "Europe/Brussels",
            },
            "url": "https://example.org/e2e",
        }

        asyncio.run(write_payload_fields(
            uid="e2e-test",
            payload=payload,
            graph_uri=test_graph,
            subject=test_subject,
            oxigraph_endpoint=OXIGRAPH_URL,
        ))

        val = _select_value(
            f"""PREFIX mom: <{MOM_NS}>
SELECT ?v WHERE {{ GRAPH <{test_graph}> {{ <{test_subject}> mom:address ?v }} }}""",
            "v",
        )
        assert val == "42 Pipeline Street", f"mom:address not written, got {val!r}"

        cc = _select_value(
            f"""PREFIX mom: <{MOM_NS}>
SELECT ?v WHERE {{ GRAPH <{test_graph}> {{ <{test_subject}> mom:countryCode ?v }} }}""",
            "v",
        )
        assert cc == "BE", f"mom:countryCode not written, got {cc!r}"

        # Cleanup
        httpx.post(
            f"{OXIGRAPH_URL}/update",
            content=f"DROP SILENT GRAPH <{test_graph}>",
            headers={"Content-Type": "application/sparql-update"},
            timeout=10.0,
        )

    def test_write_payload_fields_does_not_write_freshness_predicates(self):
        """Belt-and-suspenders: write_payload_fields never writes Axis A/B/C predicates."""
        import asyncio
        from pipeline import write_payload_fields

        test_graph = "urn:mak:test/3-11-freshness-guard"
        test_subject = f"{test_graph}/space"
        payload = {
            "space": "Freshness Guard Test",
            "location": {"lat": 50.0, "lon": 4.0},
            "state": {"open": True, "lastchange": 1715000000},
        }

        asyncio.run(write_payload_fields(
            uid="freshness-guard",
            payload=payload,
            graph_uri=test_graph,
            subject=test_subject,
            oxigraph_endpoint=OXIGRAPH_URL,
        ))

        for pred in ("openNow", "lastOpenChange", "observedAt", "updatedAt"):
            present = _ask(
                f"""PREFIX mom: <{MOM_NS}>
ASK {{ GRAPH <{test_graph}> {{ <{test_subject}> mom:{pred} ?v }} }}"""
            )
            assert not present, f"Freshness predicate mom:{pred} leaked via write_payload_fields"

        # Cleanup
        httpx.post(
            f"{OXIGRAPH_URL}/update",
            content=f"DROP SILENT GRAPH <{test_graph}>",
            headers={"Content-Type": "application/sparql-update"},
            timeout=10.0,
        )
