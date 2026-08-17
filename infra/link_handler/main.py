import json
import logging
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, List, Union

import httpx
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from pydantic import BaseModel, Field, ConfigDict

import asyncio

# Ensure scripts/ (containing spaceapi_extract) is on the path.
# In Docker set SCRIPTS_DIR=/app/scripts via docker-compose env; locally resolved automatically.
_scripts_dir = os.environ.get("SCRIPTS_DIR") or str(Path(__file__).resolve().parents[2] / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from spaceapi_extract import escape_literal, extract_core, extract_mom, triples_for

from pipeline import run_space_pipeline
from pipeline_helpers import get_config
from snapshot_store import mint_observed_at, write_snapshot, read_last_ok_observed_at, read_snapshot
from utils import MOM, SCHEMA, _ALLOWED_SCHEMES, _sparql_str, _sparql_iri, _slug
import bot_keys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_manual_refresh_cooldowns: dict[str, datetime] = {}
COOLDOWN_SECONDS = 60

_last_heartbeat_completed: Optional[datetime] = None

OXIGRAPH_ENDPOINT = os.getenv("OXIGRAPH_ENDPOINT", "http://oxigraph:7878")
GEOJSON_OUTPUT = os.getenv("GEOJSON_OUTPUT", "/app/web_data/spaces.geojson")

_TOKEN_RE = re.compile(r'^[A-Za-z0-9_\-]{8,255}$')

_scheduler = AsyncIOScheduler()

# Geocode proxy — module-level geocoder + 1 req/s rate limiter
# Nominatim policy: max 1 req/s; descriptive user_agent required (see geopy docs)
_USER_AGENT = "mapsofmaking-genjson/1.0 (contact: nicolas.de.barquin@gmail.com)"
_geolocator = Nominatim(user_agent=_USER_AGENT)
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1, max_retries=1, swallow_exceptions=False)

async def _heartbeat_job():
    global _last_heartbeat_completed
    try:
        await run_heartbeat_tick(OXIGRAPH_ENDPOINT)
    except Exception as e:
        logger.exception("[heartbeat] tick failed: %s", e)
    _last_heartbeat_completed = datetime.now(timezone.utc)


async def _query_all_claimed_spaces(oxigraph_endpoint: str) -> list[dict]:
    """Return [{uid, endpoint_url, graph_uri, subject}, ...] for every space
    (canary + regular) that has mom:endpointUrl written.

    One SPARQL SELECT across all urn:mak:* named graphs. The seeded/unclaimed
    gate inside run_space_pipeline is still authoritative — this just prunes
    the work list early.
    """
    sparql = """PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
SELECT ?graph ?subject ?endpointUrl WHERE {
  GRAPH ?graph {
    ?subject mom:endpointUrl ?endpointUrl .
  }
  FILTER(STRSTARTS(STR(?graph), "urn:mak:"))
}"""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{oxigraph_endpoint}/query",
            content=sparql,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        resp.raise_for_status()
    rows = resp.json().get("results", {}).get("bindings", [])
    out = []
    for b in rows:
        subject = b["subject"]["value"]
        graph_uri = b["graph"]["value"]
        endpoint_url = b["endpointUrl"]["value"]
        # Derive uid from subject URI:
        #   urn:mak:canary/mother-sands  → mother-sands
        #   urn:mak:space/<slug>         → <slug>
        if "/" in subject:
            uid = subject.rsplit("/", 1)[-1]
        else:
            uid = subject
        out.append({
            "uid": uid,
            "endpoint_url": endpoint_url,
            "graph_uri": graph_uri,
            "subject": subject,
        })
    return out


async def _find_seeded_graph_by_name(oxigraph_endpoint: str, name: str) -> Optional[str]:
    """Find a bundle-seeded graph (mom:source starts with 'scraped-') matching the
    given space name (case-insensitive). Returns the graph URI or None.

    Used by register_url to claim a Path B record in place when a coordinator
    self-registers a SpaceAPI URL whose name matches a previously-seeded bundle
    entry. Same URI → grey pin upgrades to live with no orphan record.
    """
    # Escape the name for safe literal inclusion.
    safe = name.replace("\\", "\\\\").replace('"', '\\"')
    sparql = f"""PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
SELECT ?graph WHERE {{
  GRAPH ?graph {{
    ?s schema:name ?n ;
       mom:source ?src .
    FILTER(LCASE(STR(?n)) = LCASE("{safe}"))
    FILTER(STRSTARTS(STR(?src), "scraped-"))
  }}
}} LIMIT 1"""
    try:
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
    except httpx.HTTPError as e:
        logger.warning("[register] claim-merge lookup failed for %r: %s", name, e)
        return None
    rows = resp.json().get("results", {}).get("bindings", [])
    return rows[0]["graph"]["value"] if rows else None


async def _find_graph_by_endpoint(oxigraph_endpoint: str, endpoint_url: str) -> Optional[str]:
    """Return the graph URI of any existing space that already has this endpointUrl, or None.

    Prevents double-registration when a coordinator registers an endpoint that is
    already stored under a different slug (e.g. a bundle-seeded slug with a city suffix
    was claimed before the original name-only slug was confirmed, or vice versa).
    """
    safe_url = endpoint_url.strip()
    sparql = f"""PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
SELECT ?graph WHERE {{
  GRAPH ?graph {{
    ?s mom:endpointUrl <{safe_url}> .
  }}
}} LIMIT 1"""
    try:
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
    except httpx.HTTPError as e:
        logger.warning("[register] endpoint-dedup lookup failed for %r: %s", endpoint_url, e)
        return None
    rows = resp.json().get("results", {}).get("bindings", [])
    return rows[0]["graph"]["value"] if rows else None


async def run_heartbeat_tick(oxigraph_endpoint: str) -> int:
    """Unified single tick: fetch every claimed space concurrently, then rematerialize once.

    Returns the number of spaces dispatched (for logs / smoke tests).
    """
    spaces = await _query_all_claimed_spaces(oxigraph_endpoint)
    if not spaces:
        logger.info("[heartbeat] no claimed spaces — skipping tick")
        await _rematerialize_geojson()
        return 0

    cfg = get_config()
    concurrency = int(cfg.get("bandwidth", {}).get("heartbeat_concurrency", 8))
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _guarded(s: dict):
        async with sem:
            try:
                return await run_space_pipeline(
                    uid=s["uid"],
                    endpoint_url=s["endpoint_url"],
                    graph_uri=s["graph_uri"],
                    subject=s["subject"],
                    oxigraph_endpoint=oxigraph_endpoint,
                )
            except Exception as e:
                logger.exception("[heartbeat] space %s failed: %s", s["uid"], e)
                return None

    logger.info("[heartbeat] dispatching %d spaces (concurrency=%d)", len(spaces), concurrency)
    await asyncio.gather(*(_guarded(s) for s in spaces))
    await _rematerialize_geojson()
    return len(spaces)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    interval = cfg.get("bandwidth", {}).get("heartbeat_interval_seconds", 600)
    try:
        _scheduler.add_job(
            _heartbeat_job,
            IntervalTrigger(seconds=interval),
            id="heartbeat",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("APScheduler started — heartbeat every %ds", interval)
    except Exception as e:
        logger.error("APScheduler failed to start: %s", e)
    yield
    try:
        _scheduler.shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(title="Maps of Making Link Handler", lifespan=lifespan)


_SPARQL_SELECT = """PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?spaceUri ?name ?latitude ?longitude
       ?geolocationFidelity ?geolocationNote
       ?street ?postcode ?city ?country ?address ?countryCode ?timeZone
       ?website ?profileUrl ?endpointUrl ?openNow ?lastOpenChange
       ?source ?openingHours ?description ?logo ?contactJson ?updatedAt
       ?subset ?nextUnlock
       (GROUP_CONCAT(DISTINCT ?specialty; separator="|") AS ?specialties)
       (GROUP_CONCAT(DISTINCT STR(?memberOf); separator="|") AS ?networkMemberships)
WHERE {
  {
    GRAPH ?spaceGraph {
      ?spaceUri a mom:Space ;
        schema:name ?name ;
        schema:geo [
          schema:latitude ?latitude ;
          schema:longitude ?longitude
        ] .
      OPTIONAL { ?spaceUri mom:geolocationFidelity ?geolocationFidelity }
      OPTIONAL { ?spaceUri mom:geolocationNote ?geolocationNote }
      OPTIONAL { ?spaceUri schema:streetAddress ?street }
      OPTIONAL { ?spaceUri schema:postalCode ?postcode }
      OPTIONAL { ?spaceUri schema:addressLocality ?city }
      OPTIONAL { ?spaceUri schema:addressCountry ?country }
      OPTIONAL { ?spaceUri mom:address ?address }
      OPTIONAL { ?spaceUri mom:countryCode ?countryCode }
      OPTIONAL { ?spaceUri mom:timeZone ?timeZone }
      OPTIONAL { ?spaceUri schema:url ?website }
      OPTIONAL { ?spaceUri mom:profileUrl ?profileUrl }
      OPTIONAL { ?spaceUri mom:endpointUrl ?endpointUrl }
      OPTIONAL { ?spaceUri schema:knowsAbout ?specialty }
      OPTIONAL { ?spaceUri mom:memberOf ?memberOf }
      OPTIONAL { ?spaceUri mom:source ?source }
      OPTIONAL { ?spaceUri schema:openingHours ?openingHours }
      OPTIONAL { ?spaceUri schema:description ?description }
      OPTIONAL { ?spaceUri schema:logo ?logo }
      OPTIONAL { ?spaceUri schema:contactJson ?contactJson }
      OPTIONAL { ?spaceUri mom:updatedAt ?updatedAt }
      OPTIONAL { ?spaceUri mom:openNow ?openNow }
      OPTIONAL { ?spaceUri mom:lastOpenChange ?lastOpenChange }
      OPTIONAL { ?spaceUri mom:subset ?subset }
      OPTIONAL { ?spaceUri mom:nextUnlock ?nextUnlock }
    }
    FILTER (STRSTARTS(STR(?spaceGraph), "urn:mak:space/"))
  }
  UNION
  {
    # Canary space (diagnostic instrument — isolated named graph, not on urn:mak:space/).
    GRAPH <urn:mak:canary> {
      ?spaceUri a mom:Space ;
        schema:name ?name ;
        schema:geo [
          schema:latitude ?latitude ;
          schema:longitude ?longitude
        ] .
      OPTIONAL { ?spaceUri mom:address ?address }
      OPTIONAL { ?spaceUri mom:countryCode ?countryCode }
      OPTIONAL { ?spaceUri mom:timeZone ?timeZone }
      OPTIONAL { ?spaceUri schema:url ?website }
      OPTIONAL { ?spaceUri schema:logo ?logo }
      OPTIONAL { ?spaceUri mom:endpointUrl ?endpointUrl }
      OPTIONAL { ?spaceUri schema:openingHours ?openingHours }
      OPTIONAL { ?spaceUri schema:description ?description }
      OPTIONAL { ?spaceUri mom:updatedAt ?updatedAt }
      OPTIONAL { ?spaceUri mom:openNow ?openNow }
      OPTIONAL { ?spaceUri mom:lastOpenChange ?lastOpenChange }
      OPTIONAL { ?spaceUri mom:source ?source }
      OPTIONAL { ?spaceUri schema:contactJson ?contactJson }
      OPTIONAL { ?spaceUri mom:memberOf ?memberOf }
    }
  }
}
GROUP BY ?spaceUri ?name ?latitude ?longitude
         ?geolocationFidelity ?geolocationNote
         ?street ?postcode ?city ?country ?address ?countryCode ?timeZone
         ?website ?profileUrl ?endpointUrl ?openNow ?lastOpenChange
         ?source ?openingHours ?description ?logo ?contactJson ?updatedAt
         ?subset ?nextUnlock
ORDER BY ?spaceUri"""

class UrlRequest(BaseModel):
    url: str
    space_id: Optional[str] = None


from schema import SpaceAPIGeo, SpaceAPILocation, SpaceAPISchema  # noqa: E402  (placed here to match original class location)


def _extract_name(data: dict) -> Optional[str]:
    return data.get("schema:name") or data.get("name")


def _extract_coords(data: dict) -> tuple[Optional[float], Optional[float]]:
    # Normalise schema:geo — may be a dict or a single-element list
    raw_geo = data.get("schema:geo")
    if isinstance(raw_geo, list):
        raw_geo = raw_geo[0] if raw_geo else {}
    geo = raw_geo if isinstance(raw_geo, dict) else {}

    # Use `is not None` throughout — lat/lon of 0 is valid (equator / prime meridian)
    lat = geo.get("schema:latitude") if geo.get("schema:latitude") is not None else geo.get("latitude")
    lon = geo.get("schema:longitude") if geo.get("schema:longitude") is not None else geo.get("longitude")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass

    # Flat-key fallback (less common encodings)
    lat = data.get("schema:latitude")
    lon = data.get("schema:longitude")
    if lat is None and lon is None:
        plain_geo = data.get("geo")
        if isinstance(plain_geo, dict):
            lat = plain_geo.get("lat")
            lon = plain_geo.get("lon")
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            pass
    return None, None


def classify_subset(schema: SpaceAPISchema) -> dict:
    """Classify the subset level reached by the endpoint data.

    api_compatibility is intentionally excluded from tier checks — it is a SpaceAPI
    interop signal with no MoM-specific feature unlock. Logo and contact are sufficient
    for the spaceapi:compatible tier on MoM.
    """
    has_required = bool(schema.resolved_name and schema.resolved_lat is not None and schema.resolved_lon is not None)
    has_card = has_required and bool(schema.resolved_url and schema.resolved_opening_hours)
    has_spaceapi = has_card and bool(schema.logo and schema.contact)

    if has_spaceapi:
        return {
            "subset": "spaceapi:compatible",
            "subset_score": 3,
            "missing_card_fields": [],
            "unlock_message": "Full SpaceAPI compatibility — interoperable with mapall.space and other SpaceAPI maps.",
            "next_subset": None,
            "next_unlock": None,
        }
    elif has_card:
        missing = []
        if not schema.logo:
            missing.append("logo")
        if not schema.contact:
            missing.append("contact")
        if not schema.logo:
            next_unlock = "Add logo to unlock SpaceAPI compatibility"
        elif not schema.contact:
            next_unlock = "Add contact to unlock SpaceAPI compatibility"
        else:
            next_unlock = None
        return {
            "subset": "mom:card",
            "subset_score": 2,
            "missing_card_fields": missing,
            "unlock_message": "Full detail card unlocked.",
            "next_subset": "spaceapi:compatible",
            "next_unlock": next_unlock,
        }
    elif has_required:
        missing = []
        if not schema.resolved_url:
            missing.append("schema:url")
        if not schema.resolved_opening_hours:
            missing.append("schema:openingHours")
        if not schema.resolved_url:
            next_unlock = "Add schema:url (website) to unlock the full detail card"
        elif not schema.resolved_opening_hours:
            next_unlock = "Add schema:openingHours to unlock the full detail card"
        else:
            next_unlock = None
        return {
            "subset": "mom:required",
            "subset_score": 1,
            "missing_card_fields": missing,
            "unlock_message": "Pin on map unlocked.",
            "next_subset": "mom:card",
            "next_unlock": next_unlock,
        }
    else:
        return {
            "subset": "none",
            "subset_score": 0,
            "missing_card_fields": [],
            "unlock_message": None,
            "next_subset": None,
            "next_unlock": None,
        }


_EMPTY_RESULT = {
    "reachable": False,
    "status_code": None,
    "schema_valid": False,
    "name_found": None,
    "coords_found": False,
    "lat": None,
    "lon": None,
}


async def _fetch_and_validate(url: str) -> dict:
    """Fetch URL and return validation result dict."""
    from urllib.parse import urlparse
    if urlparse(url).scheme not in _ALLOWED_SCHEMES:
        return {**_EMPTY_RESULT, "error": f"URL scheme not allowed; use http or https"}

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.get(url)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return {**_EMPTY_RESULT, "error": str(e)}
    except httpx.HTTPError as e:
        return {**_EMPTY_RESULT, "error": str(e)}

    if resp.status_code != 200:
        return {
            **_EMPTY_RESULT,
            "status_code": resp.status_code,
            "error": f"HTTP {resp.status_code}",
        }

    try:
        data = resp.json()
    except Exception:
        return {
            "reachable": True,
            "status_code": resp.status_code,
            "schema_valid": False,
            "error": "Response is not valid JSON",
        }

    # Validate through Pydantic schema
    try:
        schema = SpaceAPISchema.model_validate(data)
    except Exception as e:
        logger.warning("Pydantic validation failed: %s", e)
        schema = SpaceAPISchema()

    name = schema.resolved_name
    lat = schema.resolved_lat
    lon = schema.resolved_lon
    subset_info = classify_subset(schema)

    result = {
        "reachable": True,
        "status_code": resp.status_code,
        "schema_valid": bool(name),
        "name_found": name,
        "coords_found": lat is not None and lon is not None,
        "lat": lat,
        "lon": lon,
        "subset": subset_info["subset"],
        "subset_score": subset_info["subset_score"],
        "missing_card_fields": subset_info["missing_card_fields"],
        "unlock_message": subset_info["unlock_message"],
        "next_subset": subset_info["next_subset"],
        "next_unlock": subset_info["next_unlock"],
        "_data": data,  # internal — stripped before response
    }
    if not name:
        result["error"] = "Name not found — expected 'space' (SpaceAPI v13–15) or 'schema:name' / 'name'"
    elif lat is None or lon is None:
        result["coords_error"] = "Coordinates not found — expected location.lat/lon (SpaceAPI) or schema:geo (JSON-LD)"
    return result


def _build_sparql_update(graph_uri: str, space_uri: str, name: str, lat: float, lon: float,
                          endpoint_url: str, data: dict,
                          subset: str = "", next_unlock: Optional[str] = None) -> str:
    # Registration envelope — identity + metadata (not extractable from payload)
    envelope = [
        f"<{space_uri}> a <{MOM}Space> .",
        f"<{space_uri}> <{SCHEMA}name> {escape_literal(name)} .",
        f"<{space_uri}> <{SCHEMA}geo> [ <{SCHEMA}latitude> {lat} ; <{SCHEMA}longitude> {lon} ] .",
        f"<{space_uri}> <{MOM}endpointUrl> <{endpoint_url}> .",
        f'<{space_uri}> <{MOM}source> "self-registered" .',
    ]
    if subset:
        envelope.append(f"<{space_uri}> <{MOM}subset> {escape_literal(subset)} .")
    if next_unlock:
        envelope.append(f"<{space_uri}> <{MOM}nextUnlock> {escape_literal(next_unlock)} .")

    # Payload fields via extractor — skip name/geo (already in envelope)
    _ENVELOPE_SKIP = {"schema:name", "schema:geo"}
    core_fields = {k: v for k, v in extract_core(data).items() if k not in _ENVELOPE_SKIP}
    mom_fields = extract_mom(data)

    payload_triples = triples_for(space_uri, core_fields) + triples_for(space_uri, mom_fields)

    all_triples = ["  " + t for t in envelope] + ["  " + t for t in payload_triples]
    triples_str = "\n".join(all_triples)
    return f"""DROP SILENT GRAPH <{graph_uri}> ;
INSERT DATA {{
  GRAPH <{graph_uri}> {{
{triples_str}
  }}
}}"""


def _parse_contact_json(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _binding_to_feature(b: dict) -> Optional[dict]:
    space_uri = b.get("spaceUri", {}).get("value", "")
    space_id = space_uri.split("/")[-1] if "/" in space_uri else space_uri
    name = b.get("name", {}).get("value", "")
    lat_raw = b.get("latitude", {}).get("value")
    lon_raw = b.get("longitude", {}).get("value")
    if lat_raw is None or lon_raw is None:
        return None
    try:
        lat, lon = float(lat_raw), float(lon_raw)
    except (TypeError, ValueError):
        return None

    raw_specialties = b.get("specialties", {}).get("value", "")
    specialties = [s for s in raw_specialties.split("|") if s] if raw_specialties else []
    open_now_raw = b.get("openNow", {}).get("value")
    # None preserved (not coerced to False) so the browser distinguishes
    # "operator declared closed" (False) from "operator opted out / no state field" (None → opt-out).
    open_now = open_now_raw.lower() == "true" if open_now_raw is not None else None
    street = b.get("street", {}).get("value", "")
    postcode = b.get("postcode", {}).get("value", "")
    city = b.get("city", {}).get("value", "")
    raw_address = b.get("address", {}).get("value", "")
    if raw_address:
        address = raw_address
    else:
        address_parts = [p for p in [street, f"{postcode} {city}".strip()] if p]
        address = ", ".join(address_parts)

    updated_at = b.get("updatedAt", {}).get("value")
    last_open_change = b.get("lastOpenChange", {}).get("value")

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "id": space_id,
            "uri": space_uri,
            "name": name,
            "geolocationFidelity": b.get("geolocationFidelity", {}).get("value", ""),
            "geolocationNote": b.get("geolocationNote", {}).get("value", ""),
            "address": address,
            "city": city,
            "country": b.get("country", {}).get("value", ""),
            "country_code": b.get("countryCode", {}).get("value", ""),
            "timezone": b.get("timeZone", {}).get("value", ""),
            "website": b.get("website", {}).get("value", ""),
            "endpoint_url": b.get("endpointUrl", {}).get("value") or b.get("profileUrl", {}).get("value", ""),
            "specialties": specialties,
            "open_now": open_now,
            "last_open_change": last_open_change,
            "source": b.get("source", {}).get("value"),
            "opening_hours": b.get("openingHours", {}).get("value", ""),
            "description": b.get("description", {}).get("value", ""),
            "logo": b.get("logo", {}).get("value", ""),
            "contact": _parse_contact_json(b.get("contactJson", {}).get("value")),
            "subset": b.get("subset", {}).get("value", ""),
            "next_unlock": b.get("nextUnlock", {}).get("value", ""),
            "founded": "",
            "capacity": 0,
            "network_memberships": [m for m in b.get("networkMemberships", {}).get("value", "").split("|") if m],
            "open_for_hosting": False,
            # Three freshness tokens (Axis A, B, C)
            "observed_at": None,  # Filled from SQLite by _rematerialize_geojson
            "updated_at": updated_at,  # From Oxigraph mom:updatedAt; may be null for pre-3.8b spaces
            "last_fetch_status": None,  # Filled from SQLite by _rematerialize_geojson
            "last_fetch_error": None,   # Human-readable failure reason when last_fetch_status='unreachable'
        },
    }


def _load_thresholds_from_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    endpoint_health = cfg.get("endpoint_health") or {}
    operational_state = cfg.get("operational_state") or {}
    if not endpoint_health or not operational_state:
        raise RuntimeError(
            f"THRESHOLDS_MISSING: config.yaml missing endpoint_health/operational_state blocks "
            f"(endpoint_health={endpoint_health!r}, operational_state={operational_state!r}) — "
            f"materializer cannot ship a GeoJSON the browser can compute against"
        )
    return {"endpoint_health": endpoint_health, "operational_state": operational_state}


# Serializes whole-corpus rebuilds. Registration moved this off the request path into
# a BackgroundTask, which removed the de-facto serialization a single in-flight request
# provided: two registrations, or a registration racing the scheduler's heartbeat, now
# overlap freely. The temp file is per-run so a second writer cannot truncate the file
# the first is about to publish; the lock keeps N concurrent whole-corpus passes from
# piling up on Oxigraph and the snapshot store.
_rematerialize_lock = asyncio.Lock()


async def _rematerialize_geojson() -> None:
    async with _rematerialize_lock:
        await _rematerialize_geojson_locked()


async def _rematerialize_geojson_locked() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{OXIGRAPH_ENDPOINT}/query",
            content=_SPARQL_SELECT,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        resp.raise_for_status()
        bindings = resp.json().get("results", {}).get("bindings", [])

    features = [_binding_to_feature(b) for b in bindings]
    features = [f for f in features if f is not None]

    # SQLite join: fill in observed_at and last_fetch_status for each feature
    for feature in features:
        space_id = feature["properties"]["id"]
        snapshot = read_snapshot(space_id)
        if snapshot:
            # Story 3.10 Axis A: always carry observed_at, even when unreachable —
            # mark_unreachable preserves it intentionally so the card can show the
            # last-good snapshot timestamp ("fetched X ago" growing while broken).
            feature["properties"]["observed_at"] = snapshot["observed_at"]
            feature["properties"]["last_fetch_status"] = snapshot["fetch_status"]
            feature["properties"]["last_fetch_error"] = snapshot.get("fetch_error")

            # Story 3.10 B1: canary self-describes its demo mode via ext_canary.thresholdMode
            # in its own payload. When true, attach seconds-scale thresholds_override
            # so the aging→zombie→dead bucket walk is observable in ~minutes against
            # real mom:updatedAt. Source of truth lives in the canary endpoint itself.
            payload = snapshot.get("payload") or {}
            ext_canary = payload.get("ext_canary") or {}
            if ext_canary.get("thresholdMode") is True:
                feature["properties"]["thresholds_override"] = {
                    "operational_state": {
                        # fractional days = seconds (1/86400 ≈ 1 second)
                        "aging_days_threshold": 30 / 86400,
                        "zombie_days_threshold": 60 / 86400,
                        "dead_days_threshold": 120 / 86400,
                    }
                }

        # Check for missing tokens (fail-loud contract for materialization)
        has_observed = feature["properties"].get("observed_at") is not None
        has_updated = feature["properties"].get("updated_at") is not None
        has_lastchange = feature["properties"].get("last_open_change") is not None

        if not has_observed and not has_updated and not has_lastchange:
            logger.warning(
                "THREE_TOKENS_MISSING: space=%s — zero freshness tokens (data integrity)",
                feature["properties"]["uri"]
            )

    # Load thresholds and generate timestamp
    thresholds = _load_thresholds_from_config()
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    geojson = {
        "type": "FeatureCollection",
        "generated_at": generated_at,
        "thresholds": thresholds,
        "features": features,
    }

    out_path = Path(GEOJSON_OUTPUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Per-run temp name: replace() is atomic, but a shared temp path is not — a second
    # writer truncating it mid-flight would publish a torn file to the map.
    tmp_path = out_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(geojson, indent=2))
        tmp_path.replace(out_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    logger.info("rematerialized %d spaces → %s", len(features), out_path)


_SPACE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/heartbeat/run")
async def heartbeat_run():
    """Trigger an immediate full heartbeat cycle. Used by make publish after deploy."""
    global _last_heartbeat_completed
    dispatched = await run_heartbeat_tick(OXIGRAPH_ENDPOINT)
    _last_heartbeat_completed = datetime.now(timezone.utc)
    return {"status": "ok", "dispatched": dispatched}


@app.post("/api/rematerialize")
async def rematerialize_endpoint():
    """Rebuild web/data/spaces.geojson from current Oxigraph + SQLite state.

    Story 3.10: used by `make cb-aging/zombie/dead/closed` after back-dating
    mom:updatedAt — those scenarios don't need a fresh fetch, only a re-emit.
    """
    await _rematerialize_geojson()
    return {"status": "ok"}


@app.get("/api/heartbeat/last-run")
async def heartbeat_last_run():
    """Return timestamp of the last completed heartbeat cycle (UTC ISO-8601).

    Used by the browser to detect when new data is available and soft-refresh the map
    without a full page reload. Returns null on first boot before any cycle completes.
    """
    return {"last_run": _last_heartbeat_completed.isoformat() if _last_heartbeat_completed else None}


@app.post("/api/heartbeat-space/{space_id}")
async def heartbeat_space(space_id: str):
    if not _SPACE_ID_RE.match(space_id):
        raise HTTPException(status_code=400, detail={"error": "invalid_space_id"})

    now = datetime.now(timezone.utc)
    last = _manual_refresh_cooldowns.get(space_id)
    if last and (now - last) < timedelta(seconds=COOLDOWN_SECONDS):
        retry_after = COOLDOWN_SECONDS - int((now - last).total_seconds())
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after_seconds": retry_after},
        )

    # Canary lives in urn:mak:canary, regular spaces in urn:mak:space/<slug>.
    # One lookup across both graphs — same shape as the heartbeat driver.
    if space_id == "mother-sands":
        graph_uri = "urn:mak:canary"
        subject = f"urn:mak:canary/{space_id}"
    else:
        graph_uri = f"urn:mak:space/{space_id}"
        subject = graph_uri

    sparql = f"""PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
SELECT ?endpointUrl WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:endpointUrl ?endpointUrl .
  }}
}}"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{OXIGRAPH_ENDPOINT}/query",
            content=sparql,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    if not bindings:
        raise HTTPException(
            status_code=404,
            detail={"error": "no_endpoint", "message": "Space has no registered endpoint URL"},
        )

    endpoint_url = bindings[0]["endpointUrl"]["value"]
    _manual_refresh_cooldowns[space_id] = now

    observed_at = await run_space_pipeline(
        uid=space_id,
        endpoint_url=endpoint_url,
        graph_uri=graph_uri,
        subject=subject,
        oxigraph_endpoint=OXIGRAPH_ENDPOINT,
    )
    await _rematerialize_geojson()
    outcome = "ok" if observed_at else "unreachable_or_unclaimed"
    return {"status": "ok", "space_id": space_id, "outcome": outcome}


class DeployKeyRequest(BaseModel):
    room_id: Optional[str] = None


@app.post("/api/bot/deploy-key/{space_id}")
async def bot_deploy_key(
    space_id: str,
    req: Optional[DeployKeyRequest] = None,
    room_id: Optional[str] = None,
    x_bot_secret: Optional[str] = Header(None),
):
    """Generate (or reuse) a deploy key for a registered space, and — if a
    Matrix room_id is supplied — write the mom:botRoom mapping. The bot itself
    never writes to Oxigraph (NFR-S7); link_handler, the sole writer (ADR-015),
    does this write on the bot's behalf. See Story 6.1 Dev Notes "Room→space
    mapping: who writes it".

    `/api/` is proxied to the public internet (infra/nginx/conf.d/app.conf) —
    this endpoint is meant to be called only by mak-agent-bot, so it requires
    the shared X-Bot-Secret header (same value as BOT_KEY_SECRET) to prevent
    an internet caller from hijacking a space's mom:botRoom mapping (Story 6.1
    code review finding)."""
    if x_bot_secret != os.environ.get("BOT_KEY_SECRET"):
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})

    if not _SPACE_ID_RE.match(space_id):
        raise HTTPException(status_code=400, detail={"error": "invalid_space_id"})

    effective_room_id = room_id or (req.room_id if req else None)

    # Canary lives in urn:mak:canary, regular spaces in urn:mak:space/<slug> —
    # same lookup shape as heartbeat_space above.
    if space_id == "mother-sands":
        graph_uri = "urn:mak:canary"
        subject = f"urn:mak:canary/{space_id}"
    else:
        graph_uri = f"urn:mak:space/{space_id}"
        subject = graph_uri

    sparql = f"""PREFIX mom: <{MOM}>
SELECT ?endpointUrl WHERE {{
  GRAPH <{graph_uri}> {{
    <{subject}> mom:endpointUrl ?endpointUrl .
  }}
}}"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{OXIGRAPH_ENDPOINT}/query",
            content=sparql,
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    if not bindings:
        raise HTTPException(
            status_code=404,
            detail={"error": "no_endpoint", "message": "Space has no registered endpoint URL"},
        )

    if not bot_keys.key_exists(space_id):
        public_key, tutorial = bot_keys.generate_and_store(space_id)
    else:
        public_key = bot_keys.get_public_key(space_id)
        tutorial = bot_keys.TUTORIAL_TEMPLATE.format(space_id=space_id, public_key=public_key)

    if effective_room_id:
        room_iri = _sparql_iri(f"urn:mak:room/{effective_room_id}")
        if room_iri:
            update = (
                f"PREFIX mom: <{MOM}>\n"
                f"INSERT DATA {{ <{room_iri}> mom:botRoom <{subject}> . }}"
            )
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    upd = await client.post(
                        f"{OXIGRAPH_ENDPOINT}/update",
                        content=update,
                        headers={"Content-Type": "application/sparql-update"},
                    )
                    upd.raise_for_status()
            except Exception as e:
                logger.warning("mom:botRoom write failed for %s/%s (non-fatal): %s", effective_room_id, space_id, e)

    return {"public_key": public_key, "tutorial": tutorial, "space_id": space_id}


@app.get("/claim/{token}")
async def claim_link(token: str):
    if not _TOKEN_RE.match(token):
        logger.warning("claim attempt rejected — invalid token format: %.40s", token)
        raise HTTPException(status_code=400, detail="Invalid token format")
    logger.info("claim attempt: %s", token)
    raise HTTPException(status_code=422, detail="Not implemented yet")


@app.post("/api/validate-url")
async def validate_url(req: UrlRequest):
    result = await _fetch_and_validate(req.url)
    result.pop("_data", None)
    # Subset info already in result from _fetch_and_validate
    return result


@app.post("/api/register-url")
async def register_url(req: UrlRequest, background_tasks: BackgroundTasks):
    result = await _fetch_and_validate(req.url)
    data = result.pop("_data", {})

    if not result.get("reachable") or not result.get("schema_valid") or not result.get("coords_found"):
        raise HTTPException(status_code=422, detail={"validation": result})

    name = result["name_found"]
    lat = result["lat"]
    lon = result["lon"]

    slug = _slug(name)
    if not slug:
        raise HTTPException(status_code=422, detail={"error": "space name contains no ASCII-compatible characters; cannot generate a URI slug"})

    # Dedup by endpointUrl first: if any existing graph (seeded OR confirmed) already
    # carries this URL, reuse its URI. Prevents a duplicate graph when the same real
    # space was seeded under a compound slug (name+city) and later self-registered
    # under the name-only slug, or the coordinator registers twice.
    existing_endpoint_uri = await _find_graph_by_endpoint(OXIGRAPH_ENDPOINT, req.url)
    if existing_endpoint_uri:
        logger.info("[register] endpoint-dedup: %r already exists as %s — reusing URI", req.url, existing_endpoint_uri)
        graph_uri = existing_endpoint_uri
        space_uri = existing_endpoint_uri
        # Drop any orphaned seeded graph with the same name but a different URI
        # (e.g. compound-slug seed openfab-ixelles alongside confirmed openfab).
        orphan_uri = await _find_seeded_graph_by_name(OXIGRAPH_ENDPOINT, name)
        if orphan_uri and orphan_uri != existing_endpoint_uri:
            logger.info("[register] dropping orphaned seeded graph %s (same name, different slug)", orphan_uri)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"{OXIGRAPH_ENDPOINT}/update",
                        content=f"DROP GRAPH <{orphan_uri}>",
                        headers={"Content-Type": "application/sparql-update"},
                    )
            except httpx.HTTPError as e:
                logger.warning("[register] DROP orphan %s failed (non-fatal): %s", orphan_uri, e)
    else:
        # Claim-merge: if a bundle-seeded graph (mom:source starts with "scraped-")
        # exists with the same name, claim it in place — same URI, drop+reinsert as
        # self-registered. Handles the VOW/RFF Path B → coordinator flow without
        # needing to parse a city out of the SpaceAPI address string.
        claimed_uri = await _find_seeded_graph_by_name(OXIGRAPH_ENDPOINT, name)
        if claimed_uri:
            logger.info("[register] claim-merge: %r matches seeded graph %s", name, claimed_uri)
            graph_uri = claimed_uri
            space_uri = claimed_uri
        else:
            graph_uri = f"urn:mak:space/{slug}"
            space_uri = f"urn:mak:space/{slug}"

    cls: dict = {}
    reg_observed_at = mint_observed_at()
    try:
        schema_obj = SpaceAPISchema.model_validate(data)
        cls = classify_subset(schema_obj)
    except Exception as e:
        logger.warning("classify_subset failed for %s (non-fatal): %s", slug, e)

    sparql_update = _build_sparql_update(
        graph_uri, space_uri, name, lat, lon, req.url, data,
        subset=cls.get("subset", ""), next_unlock=cls.get("next_unlock"),
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upd = await client.post(
                f"{OXIGRAPH_ENDPOINT}/update",
                content=sparql_update,
                headers={"Content-Type": "application/sparql-update"},
            )
            upd.raise_for_status()
    except Exception as e:
        logger.error("Oxigraph UPDATE failed: %s", e)
        raise HTTPException(status_code=502, detail={"error": "triplestore_write_failed"})

    # Snapshot store gets the registration payload so heartbeat ticks can
    # diff against it. No mom:rawContent / snapshot-graph write (Story 3.10).
    try:
        write_snapshot(slug, reg_observed_at, data, fetch_status="ok")
    except Exception as snap_err:
        logger.warning("snapshot store write failed for %s: %s", slug, snap_err)

    # The response below is complete once the Oxigraph write and the snapshot land —
    # nothing the client renders depends on the tick or the rematerialize. Both are
    # slow (remote fetch; whole-corpus SPARQL + ~3k snapshot reads) and together they
    # used to push the request past nginx's proxy_read_timeout, so the coordinator was
    # told "failed" about a registration that had in fact succeeded. Defer them.
    async def _finish_registration() -> None:
        # Fire one tick so the new space lights up on the map
        # (writes mom:observedAt/updatedAt/openNow into urn:mak:space/<slug>).
        try:
            await run_space_pipeline(
                uid=slug,
                endpoint_url=req.url,
                graph_uri=graph_uri,
                subject=space_uri,
                oxigraph_endpoint=OXIGRAPH_ENDPOINT,
            )
        except Exception as e:
            logger.warning("[register] initial heartbeat for %s failed (non-fatal): %s", slug, e)

        try:
            await _rematerialize_geojson()
        except Exception as e:
            logger.error("GeoJSON rematerialization failed (non-fatal): %s", e)

    background_tasks.add_task(_finish_registration)

    logger.info("registered space: %s (%s)", name, space_uri)
    return {
        "status": "confirmed",
        "space_uri": space_uri,
        "space_name": name,
        "subset": result.get("subset"),
        "subset_score": result.get("subset_score"),
        "unlock_message": result.get("unlock_message"),
        "next_subset": result.get("next_subset"),
        "next_unlock": result.get("next_unlock"),
    }


@app.get("/api/space/{space_id}/snapshots")
async def get_space_snapshots(space_id: str):
    """Fetch ingestion history snapshots for a space."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', space_id):
        return []
    sparql_query = f"""PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>

SELECT ?graph ?snapshotDate ?snapshotSummary ?lastHttpStatus
WHERE {{
  GRAPH ?graph {{
    ?space <{MOM}snapshotDate> ?snapshotDate ;
           <{MOM}snapshotSummary> ?snapshotSummary .
    OPTIONAL {{ ?space <{MOM}lastHttpStatus> ?lastHttpStatus }}
  }}
  FILTER (STRSTARTS(STR(?graph), "urn:mak:space/{space_id}/"))
}}
ORDER BY DESC(?snapshotDate)
"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{OXIGRAPH_ENDPOINT}/query",
                content=sparql_query,
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json",
                },
            )
            resp.raise_for_status()
            bindings = resp.json().get("results", {}).get("bindings", [])
    except Exception as e:
        logger.warning("Failed to fetch snapshots for space %s: %s", space_id, e)
        return []

    snapshots = []
    for b in bindings:
        snapshot = {
            "date": b.get("snapshotDate", {}).get("value", ""),
            "summary": b.get("snapshotSummary", {}).get("value", ""),
            "http_status": int(b.get("lastHttpStatus", {}).get("value", 0)) if b.get("lastHttpStatus", {}).get("value") else 0,
        }
        snapshots.append(snapshot)

    return snapshots


@app.get("/api/space/{space_id}/raw")
async def get_space_raw(space_id: str):
    """Fetch raw endpoint JSON for a space from the cached snapshot.

    Note: live re-fetch is intentionally NOT done here — endpoint freshness is
    the responsibility of the periodic heartbeat (Epic 3), which flips the space
    to broken/stale states when the endpoint stops responding.
    """
    if not re.match(r'^[a-zA-Z0-9_-]+$', space_id):
        return {"error": "no_snapshot", "message": "This space has no cached endpoint content yet."}

    # snapshot_store (SQLite) is the only raw-payload source. mom:rawContent
    # triples were retired in Story 3.10.
    snap = read_snapshot(space_id)
    if snap is None or not snap.get("payload"):
        return {"error": "no_snapshot", "message": "This space has no cached endpoint content yet."}
    return {
        "raw": snap["payload"],
        "snapshotDate": snap.get("observed_at", ""),
    }


# ── Geocode proxy (Story 9.3 / AC6) ─────────────────────────────────────────

class GeocodeRequest(BaseModel):
    address: str
    city: str
    postcode: str = ""
    # country_code is now DERIVED, not demanded (Story 9.12 §2): the wizard no
    # longer sends it. Kept optional so it still sharpens the query when present.
    country_code: str = ""


@app.post("/api/geocode")
async def geocode(req: GeocodeRequest):
    """Proxy Nominatim geocoding for the wizard — 1 req/s rate-limited (RateLimiter).

    Returns {lat, lon, country_code, display_name} on success, nulls on no-result,
    503 on error. country_code is DERIVED from Nominatim address components (Story
    9.12 §2: "ask the address, derive the rest") so the wizard need not demand it.
    nginx enforces an additional 2 req/s/IP hard cap (limit_req_zone) upstream.
    """
    # Drop empty parts so a missing postcode/country doesn't poison the query.
    query = ", ".join(p for p in (req.address, req.city, req.postcode, req.country_code) if p)
    try:
        location = await asyncio.get_running_loop().run_in_executor(
            None, lambda: _geocode(query, addressdetails=True)
        )
    except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError) as exc:
        logger.warning("Nominatim unavailable for query %r: %s", query, exc)
        raise HTTPException(status_code=503, detail={"error": "geocoding_unavailable"})
    except Exception as exc:
        logger.warning("Nominatim unexpected error for query %r: %s", query, exc)
        raise HTTPException(status_code=503, detail={"error": "geocoding_unavailable"})

    if location is None:
        return {"lat": None, "lon": None, "country_code": None, "postcode": None, "display_name": None}

    # Derive what Bernard pulls from the address (Story 9.12 §2): ISO country code
    # (uppercased to match the wizard) and postcode. Either may be absent for some
    # results → None, and the wizard handles the gap (manual country fallback;
    # postcode simply stays empty).
    addr = location.raw.get("address", {}) or {}
    cc = addr.get("country_code", "")
    return {
        "lat": location.latitude,
        "lon": location.longitude,
        "country_code": cc.upper() if cc else None,
        "postcode": addr.get("postcode") or None,
        "display_name": location.address,
    }
