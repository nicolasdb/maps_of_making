"""Unified heartbeat pipeline (Story 3.10 Step 2, extended Story 3.11).

Parameterized by (uid, endpoint_url, graph_uri, subject) so the same primitives
drive the canary and every registered space. The canary side is just one row in
the driver's SPARQL SELECT.

Stages per space:
  1. fetch_snapshot           — HTTP GET, mint observed_at once, persist to snapshot_store
  2. write_updated_at         — only when content_changed (Axis B)
  3. write_payload_fields     — only when content_changed: re-extract address/contact/etc.
  4. write_open_now           — Axis C, refreshed every fetch (volatile, not diff-gated)

All Oxigraph writes are idempotent (DELETE WHERE + INSERT DATA).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx

# Ensure scripts/ (containing spaceapi_extract) is on the path.
# In Docker set SCRIPTS_DIR=/app/scripts via docker-compose env; locally resolved automatically.
_scripts_dir = os.environ.get("SCRIPTS_DIR") or str(Path(__file__).resolve().parents[2] / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from spaceapi_extract import extract_core, extract_mom, triples_for

from snapshot_store import mint_observed_at, write_snapshot, read_snapshot, mark_unreachable
from pipeline_helpers import detect_diff, _extract_open_now, _extract_last_open_change

logger = logging.getLogger(__name__)

MOM_NS = "https://nicolasdb.github.io/mapsofmaking_ontology/ns#"
SCHEMA_NS = "https://schema.org/"
XSD_DT = "http://www.w3.org/2001/XMLSchema#dateTime"


async def fetch_snapshot(
    uid: str,
    endpoint_url: str,
    db_path: Optional[str] = None,
) -> tuple[Optional[dict], bool]:
    """Fetch a SpaceAPI endpoint, mint observed_at once, persist snapshot.

    Returns (snapshot_row, content_changed). On any failure path, marks the snapshot
    unreachable (preserving observed_at) and returns (None, False).
    """
    prev = read_snapshot(uid, db_path=db_path)
    prev_payload = prev["payload"] if prev else None

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "MapsOfMaking-heartbeat/1.0 (+https://mapsofmaking.org)"},
        ) as client:
            resp = await client.get(endpoint_url)
    except httpx.HTTPError as e:
        reason = f"Network error: {e.__class__.__name__}"
        logger.warning("[axis-a] %s fetch raised %s — marking unreachable", uid, e.__class__.__name__)
        mark_unreachable(uid, db_path=db_path, reason=reason)
        return None, False

    if resp.status_code != 200:
        reason = f"HTTP {resp.status_code}"
        logger.warning("[axis-a] %s fetch returned %s — marking unreachable", uid, resp.status_code)
        mark_unreachable(uid, db_path=db_path, reason=reason)
        return None, False

    observed_at = mint_observed_at()
    try:
        payload = resp.json()
    except json.JSONDecodeError as e:
        reason = f"Invalid JSON at line {e.lineno} col {e.colno}: {e.msg}"
        logger.warning("[axis-a] %s fetch returned malformed JSON — %s", uid, reason)
        mark_unreachable(uid, db_path=db_path, reason=reason)
        return None, False

    etag = resp.headers.get("etag")
    last_modified = resp.headers.get("last-modified")

    diff = detect_diff(prev_payload, payload)
    content_changed = diff is not None
    if content_changed:
        logger.info("[axis-b] %s content_changed=True diff=%s", uid, diff)
    else:
        logger.info("[axis-b] %s content_changed=False (payload unchanged)", uid)

    write_snapshot(
        uid=uid,
        observed_at=observed_at,
        payload=payload,
        etag=etag,
        last_modified=last_modified,
        db_path=db_path,
    )
    logger.info("[axis-a] %s snapshot minted observed_at=%s", uid, observed_at)
    return read_snapshot(uid, db_path=db_path), content_changed


async def _sparql_update(oxigraph_endpoint: str, sparql: str) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{oxigraph_endpoint}/update",
            content=sparql,
            headers={"Content-Type": "application/sparql-update"},
        )
        resp.raise_for_status()


async def write_observed_at(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
    observed_at: str,
) -> None:
    """Axis A: copy observed_at from snapshot store into Oxigraph."""
    sparql = f"""PREFIX mom: <{MOM_NS}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:observedAt ?t .
  }}
}} ;
INSERT DATA {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:observedAt "{observed_at}"^^xsd:string .
  }}
}}"""
    await _sparql_update(oxigraph_endpoint, sparql)
    logger.info("[axis-a] %s mom:observedAt=%s written", subject, observed_at)


async def write_updated_at(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
    updated_at: str,
) -> None:
    """Axis B: refresh mom:updatedAt — only called on content_changed=True."""
    sparql = f"""PREFIX mom: <{MOM_NS}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:updatedAt ?t .
  }}
}} ;
INSERT DATA {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:updatedAt "{updated_at}"^^xsd:dateTime .
  }}
}}"""
    await _sparql_update(oxigraph_endpoint, sparql)
    logger.info("[axis-b] %s mom:updatedAt=%s written", subject, updated_at)


async def write_open_now(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
    open_now: Optional[bool],
    last_open_change: Optional[str],
) -> None:
    """Axis C: write/refresh (or clear) mom:openNow + mom:lastOpenChange.

    open_now=None → operator opted out (state field absent/malformed) → DELETE only,
    leaving the subject without mom:openNow. The browser's computeAxisC then falls
    through to confirmed/B/A logic.
    """
    delete_block = f"""DELETE WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:openNow ?v .
  }}
}} ;
DELETE WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:lastOpenChange ?t .
  }}
}}"""

    insert_block = ""
    if open_now is not None:
        triples = [f'<{subject}> mom:openNow "{str(open_now).lower()}"^^xsd:boolean .']
        if last_open_change:
            triples.append(f'<{subject}> mom:lastOpenChange "{last_open_change}"^^xsd:dateTime .')
        insert_block = f""" ;
INSERT DATA {{
  GRAPH <{graph_uri}> {{
    {chr(10).join(triples)}
  }}
}}"""

    sparql = f"""PREFIX mom: <{MOM_NS}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

{delete_block}{insert_block}"""
    await _sparql_update(oxigraph_endpoint, sparql)
    logger.info("[axis-c] %s mom:openNow=%s lastOpenChange=%s", subject, open_now, last_open_change)


def _to_iso_datetime(ts: Optional[str]) -> Optional[str]:
    """Normalize a timestamp to ISO 8601 for mom:updatedAt (xsd:dateTime).

    observed_at is already ISO. The HTTP Last-Modified header is RFC 7231 date
    format ("Thu, 11 Jun 2026 00:08:43 GMT") — NOT valid xsd:dateTime — so it must
    be converted before it lands in the graph, or the browser's ISO parser drops it
    and the card reads "updated unknown".
    """
    if not ts:
        return None
    s = ts.strip()
    # Already ISO 8601 → starts with YYYY-MM-DD. Trust it as-is.
    if len(s) >= 10 and s[:4].isdigit() and s[4] == "-" and s[7] == "-":
        return s
    # Otherwise assume an HTTP-date header ("Thu, 11 Jun 2026 00:08:43 GMT").
    try:
        return parsedate_to_datetime(s).isoformat()
    except (TypeError, ValueError):
        logger.warning("WARNING_UNPARSEABLE_TIMESTAMP: cannot normalize %r to ISO", ts)
        return None


async def _updated_at_absent(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
) -> bool:
    """True when mom:updatedAt is not yet present for this subject. Used for one-time backfill."""
    sparql = f"""PREFIX mom: <{MOM_NS}>
ASK {{ GRAPH <{graph_uri}> {{ <{subject}> mom:updatedAt ?t }} }}"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{oxigraph_endpoint}/query",
            content=sparql,
            headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
    return not bool(resp.json().get("boolean", False))


async def _payload_fields_absent(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
) -> bool:
    """True when schema:addressLocality is not yet present for this subject.
    Used for a one-time payload-fields backfill (mirrors _updated_at_absent):
    seed_spaceapi.py intentionally seeds only a minimal envelope and expects
    write_payload_fields() to backfill address/specialty on the first
    confirmed fetch — but that only fires on content_changed=True, so an
    endpoint whose payload never drifts would otherwise never get these
    fields written at all, not just "until the next change" (see
    ops_payload_field_backfill)."""
    sparql = f"""PREFIX schema: <{SCHEMA_NS}>
ASK {{ GRAPH <{graph_uri}> {{ <{subject}> schema:addressLocality ?c }} }}"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{oxigraph_endpoint}/query",
            content=sparql,
            headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
    return not bool(resp.json().get("boolean", False))


async def _space_is_claimed(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
) -> bool:
    """Is mom:endpointUrl present on the subject? Without an endpoint the space is
    unclaimed and the heartbeat skips it entirely."""
    sparql = f"""PREFIX mom: <{MOM_NS}>
ASK {{ GRAPH <{graph_uri}> {{ <{subject}> mom:endpointUrl ?u }} }}"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{oxigraph_endpoint}/query",
            content=sparql,
            headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
        )
        resp.raise_for_status()
    return bool(resp.json().get("boolean", False))


async def read_observed_at_from_oxigraph(
    oxigraph_endpoint: str,
    graph_uri: str,
    subject: str,
) -> Optional[str]:
    """SPARQL-SELECT mom:observedAt for a subject. Returns the string value or None."""
    sparql = f"""PREFIX mom: <{MOM_NS}>
SELECT ?t WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:observedAt ?t .
  }}
}}"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{oxigraph_endpoint}/query",
            content=sparql,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    if not bindings:
        return None
    return bindings[0].get("t", {}).get("value")


async def write_payload_fields(
    uid: str,
    payload: dict,
    graph_uri: str,
    subject: str,
    oxigraph_endpoint: str,
) -> None:
    """Re-extract payload fields (address, contact, description, …) and write to Oxigraph.

    Called only when content_changed=True so SPARQL traffic is bounded by actual changes.
    Uses per-predicate DELETE WHERE + INSERT DATA to avoid touching unrelated triples.

    Explicitly excludes freshness axis predicates — their dedicated writers own them:
      mom:observedAt   → snapshot_store (not in Oxigraph)
      mom:updatedAt    → write_updated_at()
      mom:openNow      → write_open_now()
      mom:lastOpenChange → write_open_now()
    """
    _FRESHNESS_AXIS = frozenset({
        f"{MOM_NS}observedAt", f"{MOM_NS}updatedAt",
        f"{MOM_NS}openNow", f"{MOM_NS}lastOpenChange",
    })

    core_fields = extract_core(payload)
    mom_fields = extract_mom(payload)
    # Skip name/geo — those are the registration anchor and don't drift
    _SKIP = {"schema:name", "schema:geo"}
    all_fields = {k: v for k, v in {**core_fields, **mom_fields}.items() if k not in _SKIP}

    # Build per-predicate DELETE WHERE + INSERT DATA blocks
    from spaceapi_extract.sparql import _expand  # noqa: PLC0415
    sparql_parts = []
    for curie, val in all_fields.items():
        if val is None:
            continue
        pred_uri = _expand(curie)
        if pred_uri in _FRESHNESS_AXIS:
            logger.warning("[payload-fields] %s skipped freshness predicate %s (bug guard)", uid, curie)
            continue
        triple_list = triples_for(subject, {curie: val})
        if not triple_list:
            continue
        delete_block = (
            f"DELETE WHERE {{\n"
            f"  GRAPH <{graph_uri}> {{\n"
            f"    <{subject}> <{pred_uri}> ?v .\n"
            f"  }}\n"
            f"}}"
        )
        insert_block = (
            f"INSERT DATA {{\n"
            f"  GRAPH <{graph_uri}> {{\n"
            f"    {' '.join(triple_list)}\n"
            f"  }}\n"
            f"}}"
        )
        sparql_parts.append(f"{delete_block} ;\n{insert_block}")

    if not sparql_parts:
        logger.debug("[payload-fields] %s no payload fields to write", uid)
        return

    sparql = f"PREFIX mom: <{MOM_NS}>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n\n" + \
             " ;\n".join(sparql_parts)
    await _sparql_update(oxigraph_endpoint, sparql)
    logger.info("[payload-fields] %s wrote %d predicate(s)", uid, len(sparql_parts))


async def run_space_pipeline(
    uid: str,
    endpoint_url: str,
    graph_uri: str,
    subject: str,
    oxigraph_endpoint: str,
    db_path: Optional[str] = None,
) -> Optional[str]:
    """Unified single-space pipeline. Returns observed_at or None on fetch failure.

    Gating: skipped when mom:endpointUrl is absent in `graph_uri` (seeded/unclaimed).
    Browser sees the marker with no observed_at and no updated_at — markerKind() = 'seeded'.

    Axis A: observed_at minted once in fetch, lives in snapshot_store.
    Axis B: if content_changed, write mom:updatedAt=observed_at to <graph_uri>.
    Axis C: refresh mom:openNow from payload.state every fetch (volatile).
    """
    if not await _space_is_claimed(oxigraph_endpoint, graph_uri, subject):
        logger.info("[pipeline] %s mom:endpointUrl absent — seeded/unclaimed, skipping", uid)
        return None

    snap, content_changed = await fetch_snapshot(uid, endpoint_url, db_path=db_path)
    if snap is None:
        return None

    observed_at = snap["observed_at"]
    # Note: mom:observedAt is NOT written to Oxigraph in the heartbeat path —
    # it lives in snapshot_store.db and is joined into spaces.geojson by the
    # materializer. write_observed_at() exists for the skeleton test only.

    if content_changed:
        try:
            await write_updated_at(oxigraph_endpoint, graph_uri, subject, observed_at)
        except Exception as e:
            logger.warning("[axis-b] %s mom:updatedAt write failed (non-fatal): %s", uid, e)
        try:
            await write_payload_fields(uid, snap["payload"], graph_uri, subject, oxigraph_endpoint)
        except Exception as e:
            logger.warning("[payload-fields] %s write failed (non-fatal): %s", uid, e)
    else:
        # One-time backfill: stamp mom:updatedAt from the snapshot's last_modified or
        # observed_at (never a fresh "now") for claimed spaces that pre-date Story 3.8b
        # and have never triggered a content diff.
        try:
            if await _updated_at_absent(oxigraph_endpoint, graph_uri, subject):
                # Anchor Axis B at observed_at (when we first successfully reached the
                # space), not last_modified (when the server last touched the file).
                # last_modified can be years old on static JSON that never changes —
                # stamping it would immediately bucket the space as dead/zombie even
                # though we just reached it. observed_at is always fresh and reliable.
                backfill_ts = observed_at
                if not backfill_ts:
                    logger.warning("[axis-b] %s backfill skipped: no timestamp available", uid)
                else:
                    await write_updated_at(oxigraph_endpoint, graph_uri, subject, backfill_ts)
                    logger.info("[axis-b] %s mom:updatedAt backfilled from observed_at=%s", uid, backfill_ts)
        except Exception as e:
            logger.warning("[axis-b] %s backfill check/write failed (non-fatal): %s", uid, e)

        # One-time backfill: seed_spaceapi.py deliberately seeds only a minimal
        # envelope and relies on write_payload_fields() to fill in address/
        # specialty on the first confirmed fetch — but that call is normally
        # gated on content_changed=True. An endpoint whose payload never
        # drifts would otherwise never get these fields at all (see
        # ops_payload_field_backfill memory: same gap, different field set).
        try:
            if await _payload_fields_absent(oxigraph_endpoint, graph_uri, subject):
                await write_payload_fields(uid, snap["payload"], graph_uri, subject, oxigraph_endpoint)
                logger.info("[payload-fields] %s backfilled (was absent, content unchanged)", uid)
        except Exception as e:
            logger.warning("[payload-fields] %s backfill check/write failed (non-fatal): %s", uid, e)

    state_obj = snap["payload"].get("state") if isinstance(snap.get("payload"), dict) else None
    open_now = _extract_open_now(state_obj)
    last_open_change = _extract_last_open_change(state_obj)
    try:
        await write_open_now(oxigraph_endpoint, graph_uri, subject, open_now, last_open_change)
    except Exception as e:
        logger.warning("[axis-c] %s mom:openNow write failed (non-fatal): %s", uid, e)

    return observed_at
