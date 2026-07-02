"""Three-axis live freshness propagation — gating test for Story 3.10.

Closes Epic 3.5: proves the canary endpoint, driven through unreachable /
stale-content / closed states, produces feature properties that the browser
axis-compute functions reduce to the correct buckets — and that the materializer
ships ONLY raw tokens + thresholds (no stored buckets).

Real seams: live Oxigraph + real SQLite snapshot store + real canary HTTP
subprocess. No mocked integration boundaries.

Run:
  pytest tests/test_canary_three_axis_e2e.py -v -m live_integration
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "infra" / "link_handler"))
sys.path.insert(0, str(REPO_ROOT))

OXIGRAPH_URL = os.getenv("OXIGRAPH_URL", "http://localhost:7878").rstrip("/")
if OXIGRAPH_URL.endswith("/query"):
    OXIGRAPH_URL = OXIGRAPH_URL[: -len("/query")]


# ── Compressed thresholds — same shape as config.yaml, seconds-scale ─────────
COMPRESSED_THRESHOLDS = {
    "endpoint_health": {
        "unresponsive_minutes_threshold": 1 / 60,   # 1 second
        "warning_minutes_threshold": 2 / 60,        # 2 seconds
        "broken_minutes_threshold": 3 / 60,         # 3 seconds
    },
    "operational_state": {
        "aging_days_threshold": 2 / 86400,          # 2 seconds
        "zombie_days_threshold": 4 / 86400,         # 4 seconds
        "dead_days_threshold": 8 / 86400,           # 8 seconds
    },
}


# ── Browser-equivalent axis-compute logic — kept tight; mirrors web/app.js ───
def _age_minutes(iso: str | None) -> float | None:
    if not iso:
        return None
    s = iso if iso.endswith("Z") else iso + "Z"
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 60.0


def _age_days(iso: str | None) -> float | None:
    m = _age_minutes(iso)
    return None if m is None else m / 1440.0


def compute_axis_a(props: dict, thresholds: dict) -> str:
    if props.get("last_fetch_status") == "unreachable":
        return "broken"
    obs = props.get("observed_at")
    if not obs:
        return "broken"
    t = thresholds["endpoint_health"]
    age = _age_minutes(obs)
    if age is None:
        return "broken"
    if age >= t["broken_minutes_threshold"]:
        return "broken"
    if age >= t["warning_minutes_threshold"]:
        return "warning"
    if age >= t["unresponsive_minutes_threshold"]:
        return "unresponsive"
    return "fresh"


def compute_axis_b(props: dict, thresholds: dict) -> str:
    if not props.get("updated_at"):
        return "dead"
    age = _age_days(props["updated_at"])
    if age is None:
        return "dead"
    t = thresholds["operational_state"]
    if age >= t["dead_days_threshold"]:
        return "dead"
    if age >= t["zombie_days_threshold"]:
        return "zombie"
    if age >= t["aging_days_threshold"]:
        return "aging"
    return "confirmed"


def compute_axis_c(props: dict) -> str:
    return "open" if props.get("open_now") is True else "not-open"


# ── Fixtures ──────────────────────────────────────────────────────────────────
def _oxigraph_alive() -> bool:
    try:
        r = httpx.post(
            f"{OXIGRAPH_URL}/query",
            content="ASK { ?s ?p ?o }",
            headers={"Content-Type": "application/sparql-query",
                     "Accept": "application/sparql-results+json"},
            timeout=2.0,
        )
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module")
def oxigraph_required():
    if not _oxigraph_alive():
        pytest.skip(f"Oxigraph not reachable at {OXIGRAPH_URL} — run `make up` first")


@pytest.fixture(autouse=True)
def _isolated_snapshot_db(tmp_path, monkeypatch):
    """Redirect SQLite snapshot store to a tmp file (default path is Docker-only)."""
    db = tmp_path / "snapshot_store.db"
    monkeypatch.setenv("SNAPSHOT_DB_PATH", str(db))


SPACE_ID = "test-three-axis-canary"
SPACE_URI = f"urn:mak:space/{SPACE_ID}"


def _sparql_update(query: str) -> None:
    r = httpx.post(
        f"{OXIGRAPH_URL}/update",
        content=query,
        headers={"Content-Type": "application/sparql-update"},
        timeout=10.0,
    )
    r.raise_for_status()


def _seed_space(updated_at_iso: str, open_now: bool, last_open_change: str = "1700000000") -> None:
    """Seed a single Space named graph with the three Oxigraph-side tokens."""
    _sparql_update(f"DROP SILENT GRAPH <{SPACE_URI}>")
    _sparql_update(f"""
PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
INSERT DATA {{
  GRAPH <{SPACE_URI}> {{
    <{SPACE_URI}> a mom:Space ;
      schema:name "Three-Axis Canary" ;
      schema:geo [ schema:latitude 50.0 ; schema:longitude 4.0 ] ;
      mom:updatedAt "{updated_at_iso}"^^xsd:dateTime ;
      mom:openNow "{str(open_now).lower()}"^^xsd:boolean ;
      mom:lastOpenChange "{last_open_change}"^^xsd:integer .
  }}
}}
""")


@pytest.fixture
def clean_space():
    yield
    try:
        _sparql_update(f"DROP SILENT GRAPH <{SPACE_URI}>")
    except Exception:
        pass


def _materialize_feature() -> tuple[dict, dict]:
    """Run the live materializer and return (feature_props, thresholds_block).

    scripts/materialize_geojson.py was deleted 2026-06-03 (commit 6ddf9db,
    honest-inventory triage) as a hand-synced duplicate of the live
    `_rematerialize_geojson` in infra/link_handler/main.py — this test was
    never repointed at the time. Drive the real async materializer directly,
    against a tmp GeoJSON output path, instead.
    """
    import asyncio
    import tempfile

    import main as link_handler_main

    link_handler_main.OXIGRAPH_ENDPOINT = OXIGRAPH_URL
    fd, out_path = tempfile.mkstemp(suffix=".geojson")
    os.close(fd)
    link_handler_main.GEOJSON_OUTPUT = out_path
    try:
        # asyncio.run() (not used here) closes its loop on exit, which breaks the
        # deprecated asyncio.get_event_loop() pattern other tests in this module
        # rely on (e.g. test_backfill_stamps_updated_at_once_on_unchanged_content)
        # when run later in the same session — keep a loop around instead.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(link_handler_main._rematerialize_geojson())
        geojson = json.loads(Path(out_path).read_text())
    finally:
        Path(out_path).unlink(missing_ok=True)

    feat = next((f for f in geojson["features"] if f["properties"]["id"] == SPACE_ID), None)
    assert feat is not None, f"{SPACE_ID} missing from GeoJSON"
    return feat["properties"], geojson["thresholds"]


# ── Canary HTTP subprocess ────────────────────────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def canary_endpoint():
    """Launch data/canary/mother-sands-endpoint.py, allow MODE switching."""
    port = _free_port()
    script = REPO_ROOT / "data" / "canary" / "mother-sands-endpoint.py"
    assert script.exists(), f"canary endpoint missing: {script}"

    processes: list[subprocess.Popen] = []

    def start(mode: str = "ok") -> str:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            env={**os.environ, "MODE": mode, "PORT": str(port)},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        processes.append(proc)
        # wait until the port is open (or process exits)
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return f"http://127.0.0.1:{port}/"
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError(f"canary exited prematurely (mode={mode})")
                time.sleep(0.05)
        raise RuntimeError(f"canary did not bind to {port}")

    def stop_all():
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
        processes.clear()

    yield start, stop_all
    stop_all()


# ─────────────────────────────────────────────────────────────────────────────
# AC 7 negative assertions — these are independent of the canary state and run
# against any seeded space. Closes the Story 3.9 review "never asserts the
# negative" gap explicitly.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.live_integration
def test_geojson_carries_only_raw_tokens_no_stored_buckets(oxigraph_required, clean_space):
    """The materializer ships raw tokens + thresholds — NO stored buckets."""
    from snapshot_store import write_snapshot
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _seed_space(updated_at_iso=now, open_now=True)
    write_snapshot(uid=SPACE_ID, observed_at=now, payload={"ok": True}, fetch_status="ok")

    props, thresholds = _materialize_feature()

    # Stored-bucket fields MUST be absent (dead-code sweep)
    for dead in ("status", "endpoint_health", "operational_state"):
        assert dead not in props, f"dead bucket field still in GeoJSON: {dead!r}"

    # Raw tokens MUST be present
    for token in ("observed_at", "updated_at", "last_open_change",
                  "open_now", "last_fetch_status"):
        assert token in props, f"raw token missing: {token!r}"

    # Thresholds block present + non-empty (AC 6)
    assert thresholds.get("endpoint_health"), "thresholds.endpoint_health empty"
    assert thresholds.get("operational_state"), "thresholds.operational_state empty"


# ─────────────────────────────────────────────────────────────────────────────
# AC 9 — three independent axes, driven against the real canary.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.live_integration
def test_axis_a_degrades_independently_under_unreachable(oxigraph_required, clean_space, canary_endpoint):
    """Canary unreachable → Axis A=broken, Axis B unaffected."""
    from snapshot_store import write_snapshot
    start, stop_all = canary_endpoint

    # Start canary in 503 mode and confirm it responds 503 (real seam check)
    url = start("503")
    r = httpx.get(url, timeout=2.0)
    assert r.status_code == 503

    # Token state: observed_at is recent, but fetch_status = unreachable (the
    # heartbeat would have stamped this on a 503). updated_at fresh → Axis B
    # must remain `confirmed`.
    fresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _seed_space(updated_at_iso=fresh, open_now=False)
    write_snapshot(uid=SPACE_ID, observed_at=fresh, payload={}, fetch_status="unreachable")

    props, _ = _materialize_feature()
    assert compute_axis_a(props, COMPRESSED_THRESHOLDS) == "broken"
    assert compute_axis_b(props, COMPRESSED_THRESHOLDS) == "confirmed", \
        "Axis B must not move when only Axis A degrades"


@pytest.mark.live_integration
def test_axis_b_ages_independently_when_content_unchanged(oxigraph_required, clean_space, canary_endpoint):
    """Endpoint responsive (Axis A fresh) but content not updating → Axis B ages."""
    from snapshot_store import write_snapshot
    start, _ = canary_endpoint

    url = start("ok")
    r = httpx.get(url, timeout=2.0)
    assert r.status_code == 200

    # Now is the responsive observation; updated_at is old enough to trip
    # aging/zombie/dead under the compressed thresholds.
    now = datetime.now(timezone.utc)
    observed_iso = now.isoformat().replace("+00:00", "Z")
    stale_updated = (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")  # > aging, < zombie

    _seed_space(updated_at_iso=stale_updated, open_now=False)
    write_snapshot(uid=SPACE_ID, observed_at=observed_iso, payload={}, fetch_status="ok")

    props, _ = _materialize_feature()
    assert compute_axis_a(props, COMPRESSED_THRESHOLDS) == "fresh", \
        "Axis A must be fresh — observed_at just now"
    axis_b = compute_axis_b(props, COMPRESSED_THRESHOLDS)
    assert axis_b in ("aging", "zombie"), f"Axis B should be aging/zombie, got {axis_b!r}"


@pytest.mark.live_integration
def test_axis_c_flips_independently_on_open_now_change(oxigraph_required, clean_space):
    """Flipping open_now flips Axis C without touching A or B."""
    from snapshot_store import write_snapshot
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Open
    _seed_space(updated_at_iso=now, open_now=True, last_open_change="1700000001")
    write_snapshot(uid=SPACE_ID, observed_at=now, payload={}, fetch_status="ok")
    props_open, _ = _materialize_feature()
    assert compute_axis_c(props_open) == "open"
    a_open = compute_axis_a(props_open, COMPRESSED_THRESHOLDS)
    b_open = compute_axis_b(props_open, COMPRESSED_THRESHOLDS)

    # Flip closed (re-seed with open_now=false)
    _seed_space(updated_at_iso=now, open_now=False, last_open_change="1700000002")
    props_closed, _ = _materialize_feature()
    assert compute_axis_c(props_closed) == "not-open"
    assert compute_axis_a(props_closed, COMPRESSED_THRESHOLDS) == a_open, \
        "Axis A must not move when only open_now flips"
    assert compute_axis_b(props_closed, COMPRESSED_THRESHOLDS) == b_open, \
        "Axis B must not move when only open_now flips"


@pytest.mark.live_integration
def test_axes_computed_from_header_thresholds_not_stored_buckets(oxigraph_required, clean_space):
    """Same feature, different thresholds → different Axis B. Proves the browser
    can recompute axes without re-materialization (no stored buckets)."""
    from snapshot_store import write_snapshot
    now = datetime.now(timezone.utc)
    observed_iso = now.isoformat().replace("+00:00", "Z")
    # updated_at 5s old
    updated_iso = (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    _seed_space(updated_at_iso=updated_iso, open_now=False)
    write_snapshot(uid=SPACE_ID, observed_at=observed_iso, payload={}, fetch_status="ok")

    props, _ = _materialize_feature()

    # With production thresholds (days), 5 seconds is still `confirmed`.
    prod_thresholds = {
        "endpoint_health": {"unresponsive_minutes_threshold": 10,
                            "warning_minutes_threshold": 30,
                            "broken_minutes_threshold": 60},
        "operational_state": {"aging_days_threshold": 30,
                              "zombie_days_threshold": 90,
                              "dead_days_threshold": 180},
    }
    assert compute_axis_b(props, prod_thresholds) == "confirmed"
    # With compressed thresholds the same feature ages.
    assert compute_axis_b(props, COMPRESSED_THRESHOLDS) in ("aging", "zombie")


# ── Backfill: one-time mom:updatedAt stamp for pre-3.8b claimed spaces ────────

def _seed_claimed_no_updated_at(endpoint_url: str) -> None:
    """Seed a claimed space that has mom:endpointUrl but no mom:updatedAt."""
    _sparql_update(f"DROP SILENT GRAPH <{SPACE_URI}>")
    _sparql_update(f"""
PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
INSERT DATA {{
  GRAPH <{SPACE_URI}> {{
    <{SPACE_URI}> a mom:Space ;
      schema:name "Backfill Test Space" ;
      schema:geo [ schema:latitude 50.0 ; schema:longitude 4.0 ] ;
      mom:endpointUrl "{endpoint_url}" .
  }}
}}
""")


def _read_updated_at_from_graph() -> str | None:
    """Return mom:updatedAt value from Oxigraph for SPACE_URI, or None."""
    r = httpx.post(
        f"{OXIGRAPH_URL}/query",
        content=f"""PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
SELECT ?t WHERE {{ GRAPH <{SPACE_URI}> {{ <{SPACE_URI}> mom:updatedAt ?t }} }}""",
        headers={"Content-Type": "application/sparql-query",
                 "Accept": "application/sparql-results+json"},
        timeout=5.0,
    )
    r.raise_for_status()
    bindings = r.json().get("results", {}).get("bindings", [])
    return bindings[0]["t"]["value"] if bindings else None


@pytest.mark.live_integration
def test_backfill_stamps_updated_at_once_on_unchanged_content(
    oxigraph_required, clean_space, canary_endpoint
):
    """Given a claimed space with no mom:updatedAt and unchanged content,
    when the pipeline runs, then mom:updatedAt is written exactly once
    and a second pipeline run on the same content does not move it."""
    import asyncio
    from pipeline import run_space_pipeline

    start, stop = canary_endpoint
    url = start(mode="open")
    try:
        _seed_claimed_no_updated_at(url)

        assert _read_updated_at_from_graph() is None, "precondition: no mom:updatedAt yet"

        asyncio.get_event_loop().run_until_complete(
            run_space_pipeline(SPACE_ID, url, SPACE_URI, SPACE_URI, OXIGRAPH_URL)
        )
        first_ts = _read_updated_at_from_graph()
        assert first_ts is not None, "backfill must stamp mom:updatedAt on first run"

        # Second run — same content, no diff; must not overwrite the backfilled value.
        asyncio.get_event_loop().run_until_complete(
            run_space_pipeline(SPACE_ID, url, SPACE_URI, SPACE_URI, OXIGRAPH_URL)
        )
        second_ts = _read_updated_at_from_graph()
        assert second_ts == first_ts, "backfill must not overwrite on subsequent unchanged run"
    finally:
        stop()


# ── Backfill: one-time schema:addressLocality/knowsAbout stamp (Story 6.10 follow-up) ──
# project_spaceapi_missing_locality_knowsabout: seed_spaceapi.py seeds only a
# minimal envelope; write_payload_fields() backfills address/specialty but was
# only ever called on content_changed=True — an endpoint whose payload never
# drifts never got these fields at all.

def _read_address_locality_from_graph() -> str | None:
    r = httpx.post(
        f"{OXIGRAPH_URL}/query",
        content=f"""PREFIX schema: <https://schema.org/>
SELECT ?c WHERE {{ GRAPH <{SPACE_URI}> {{ <{SPACE_URI}> schema:addressLocality ?c }} }}""",
        headers={"Content-Type": "application/sparql-query",
                 "Accept": "application/sparql-results+json"},
        timeout=5.0,
    )
    r.raise_for_status()
    bindings = r.json().get("results", {}).get("bindings", [])
    return bindings[0]["c"]["value"] if bindings else None


@pytest.mark.live_integration
def test_backfill_writes_address_locality_once_on_unchanged_content(
    oxigraph_required, clean_space, canary_endpoint
):
    """Given a claimed space with no schema:addressLocality and unchanged
    content, when the pipeline runs, then addressLocality is backfilled from
    the payload's free-text location.address on the first run — even though
    content_changed stays False for the rest of the test."""
    import asyncio
    from pipeline import run_space_pipeline

    start, stop = canary_endpoint
    url = start(mode="open")  # baseline payload: location.address = "Maunsell Fort, North Sea"
    try:
        _seed_claimed_no_updated_at(url)

        assert _read_address_locality_from_graph() is None, "precondition: no addressLocality yet"

        asyncio.get_event_loop().run_until_complete(
            run_space_pipeline(SPACE_ID, url, SPACE_URI, SPACE_URI, OXIGRAPH_URL)
        )
        locality = _read_address_locality_from_graph()
        assert locality == "Maunsell Fort", "backfill must derive addressLocality from location.address"

        # Second run — same content, no diff; must not error or duplicate the triple.
        asyncio.get_event_loop().run_until_complete(
            run_space_pipeline(SPACE_ID, url, SPACE_URI, SPACE_URI, OXIGRAPH_URL)
        )
        assert _read_address_locality_from_graph() == locality
    finally:
        stop()
