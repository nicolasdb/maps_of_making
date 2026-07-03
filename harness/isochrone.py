"""ORS isochrone + shapely point-in-polygon for !mom travel (Story 6.3).
Three-step: geocode origin → fetch ORS isochrone polygon → filter Oxigraph spaces.

Bucket snapping: arbitrary hours snap UP to nearest bucket [0.15, 0.30, 0.60, 1.0, 2.0]
so cache keys stay stable. Requests above 2h are passed through as a single ORS query
(no cache) — they signal the future regional discovery lens, logged for analysis.
"""
import asyncio
import os
import time
import structlog

import httpx

import bernard
import sparql_client
import query_commands

log = structlog.get_logger()

ORS_API_KEY = os.environ.get("ORS_API_KEY", "")
ORS_BASE_URL = "https://api.openrouteservice.org"

# Per-room ORS cooldown — only applies to live ORS calls, not cache hits.
_ors_cooldown: dict[str, float] = {}
ORS_COOLDOWN_SECONDS = 60  # 1 minute — 40 req/min ORS free tier; daily quota (2000) is the real limit

# Snap-up buckets in hours. Requests snap to the nearest bucket ≥ requested value.
# Above 2h: pass through uncached (regional discovery, logged as signal).
HOUR_BUCKETS = [0.15, 0.30, 0.60, 1.0, 2.0]

# In-memory polygon cache: (lat2dp, lon2dp, bucket_hours, mode) → (polygon_geom, expires_at)
_polygon_cache: dict[tuple, tuple[dict, float]] = {}
CACHE_TTL_SECONDS = 86400  # 24 hours

PREFIX = """\
PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
"""

ALL_SPACES_QUERY = PREFIX + """
SELECT ?name ?lat ?lon ?endpointUrl WHERE {
  GRAPH ?g {
    ?s a mom:Space ;
       schema:name ?name ;
       schema:geo [schema:latitude ?lat ; schema:longitude ?lon] .
    OPTIONAL { ?s mom:endpointUrl ?endpointUrl }
    FILTER(STRSTARTS(STR(?g), "urn:mak:"))
  }
}
"""

MODE_MAP = {
    "driving-car": "driving-car",
    "bike": "cycling-regular",
    "by bike": "cycling-regular",
    "cycling-regular": "cycling-regular",
    "foot": "foot-walking",
    "by foot": "foot-walking",
    "foot-walking": "foot-walking",
}


class IsochroneError(Exception):
    pass


class IsochroneTimeoutError(IsochroneError):
    pass


class OriginAmbiguousError(IsochroneError):
    """Raised when an origin substring-matches 2+ spaces and none is an exact
    name match — silently picking one (even a ranked one) risks resolving to
    the wrong space entirely (e.g. 'openfab' → Brussels OpenFab vs an
    unrelated 'Openfab OzU' in Istanbul). Report all candidates and ask the
    user to retry with the exact name instead of guessing."""

    def __init__(self, query: str, candidates: list[str]):
        self.query = query
        self.candidates = candidates
        super().__init__(f"'{query}' matches multiple spaces: {', '.join(candidates)}. Try again with the exact name.")


def _snap_hours(hours: float) -> float | None:
    """Snap hours up to nearest bucket. Returns None if above max bucket (pass-through)."""
    for bucket in HOUR_BUCKETS:
        if hours <= bucket:
            return bucket
    return None  # above 2h — caller handles


def _cache_key(coords: tuple[float, float], bucket: float, mode: str) -> tuple:
    return (round(coords[0], 2), round(coords[1], 2), bucket, mode)


def _cache_get(key: tuple) -> dict | None:
    entry = _polygon_cache.get(key)
    if entry is None:
        return None
    polygon, expires_at = entry
    if time.monotonic() > expires_at:
        del _polygon_cache[key]
        return None
    return polygon


def _cache_set(key: tuple, polygon: dict) -> None:
    _polygon_cache[key] = (polygon, time.monotonic() + CACHE_TTL_SECONDS)


def _check_cooldown(room_id: str) -> bool:
    last = _ors_cooldown.get(room_id)
    return last is not None and (time.monotonic() - last) < ORS_COOLDOWN_SECONDS


def _set_cooldown(room_id: str) -> None:
    _ors_cooldown[room_id] = time.monotonic()


async def travel_search(origin: str, hours: float, mode_input: str = "", room_id: str = "") -> dict:
    """
    Returns {
        "confirmed": [{"name": str}, ...],
        "seeded_count": int,
        "fallback": bool,   # True if ORS timed out / unavailable
    }
    Raises IsochroneError on hard failure (caller should degrade to !mom nearby).
    """
    mode = MODE_MAP.get(mode_input.lower().strip(), "driving-car")
    bucket = _snap_hours(hours)

    if bucket is None:
        # Above 2h — regional discovery territory, log and pass through uncached
        log.info("isochrone.above_bucket_range", hours=hours, mode=mode, origin=origin)
        bucket = hours  # use as-is, no caching

    coords = await _resolve_origin(origin)
    if coords is None:
        raise IsochroneError(f"Could not locate '{origin}'.")

    cache_key = _cache_key(coords, bucket, mode) if bucket in HOUR_BUCKETS else None
    polygon = _cache_get(cache_key) if cache_key else None

    if polygon is not None:
        log.info("isochrone.cache_hit", origin=origin, bucket=bucket, mode=mode)
    else:
        if _check_cooldown(room_id):
            raise IsochroneError(f"ORS rate limit — too many travel requests from this room, try again in {ORS_COOLDOWN_SECONDS}s.")

        if bucket != hours:
            log.info("isochrone.snapped", requested=hours, bucket=bucket, mode=mode)

        try:
            polygon = await _fetch_isochrone(coords, bucket, mode)
        except (httpx.ReadTimeout, asyncio.TimeoutError):
            log.warning("isochrone.ors_timeout", origin=origin, hours=bucket)
            if room_id:
                _set_cooldown(room_id)
            return {"confirmed": [], "seeded_count": 0, "fallback": True, "coords": coords}
        except IsochroneError:
            raise
        except Exception as e:
            log.warning("isochrone.ors_error", error=str(e))
            raise IsochroneError(str(e)) from e

        if cache_key:
            _cache_set(cache_key, polygon)
        if room_id:
            _set_cooldown(room_id)

    return await _filter_spaces(polygon, bucket)


_RESOLVE_SPACE_QUERY = PREFIX + """
SELECT ?name ?lat ?lon WHERE {
  GRAPH ?g {
    ?s a mom:Space ;
       schema:name ?name ;
       schema:geo [schema:latitude ?lat ; schema:longitude ?lon] .
    OPTIONAL { ?s mom:endpointUrl ?e }
    FILTER(CONTAINS(LCASE(STR(?name)), LCASE("{origin}")))
    BIND(IF(LCASE(STR(?name)) = LCASE("{origin}"), 1, 0) AS ?exact)
    BIND(IF(BOUND(?e), 1, 0) AS ?confirmed)
  }
} ORDER BY DESC(?exact) DESC(?confirmed) ?name LIMIT 5
"""


async def _resolve_origin(origin: str) -> tuple[float, float] | None:
    """Resolve origin to (lat, lon): Oxigraph space name first, Nominatim city
    second. An exact (case-insensitive) name match is used immediately even
    if other spaces also substring-match — no ambiguity there. But if there's
    no exact match and 2+ spaces substring-match (e.g. 'openfab' hitting both
    Brussels 'OpenFab' and an unrelated 'Openfab OzU' in Istanbul), silently
    picking one — even the SPARQL-ranked top one — risks resolving to the
    wrong space entirely. Raise OriginAmbiguousError instead of guessing."""
    import re
    safe = re.sub(r'["{}<>\\' + r"\n\r]", "", origin)
    try:
        bindings, _ = await sparql_client.run_select(_RESOLVE_SPACE_QUERY.replace('"{origin}"', f'"{safe}"'))
    except Exception as e:
        log.warning("isochrone.origin_space_lookup_failed", origin=origin, error=str(e))
        bindings = []

    if bindings:
        exact = [b for b in bindings if b["name"]["value"].strip().lower() == origin.strip().lower()]
        if exact:
            return float(exact[0]["lat"]["value"]), float(exact[0]["lon"]["value"])
        if len(bindings) > 1:
            names = [b["name"]["value"] for b in bindings]
            log.info("isochrone.origin_ambiguous", origin=origin, candidates=names)
            raise OriginAmbiguousError(origin, names)
        return float(bindings[0]["lat"]["value"]), float(bindings[0]["lon"]["value"])

    return await query_commands.geocode_city(origin)


async def _fetch_isochrone(coords: tuple[float, float], hours: float, mode: str) -> dict:
    """Returns GeoJSON polygon geometry from ORS.
    coords = (lat, lon); ORS v2 expects [lon, lat] — inverted intentionally.
    """
    if not ORS_API_KEY:
        raise IsochroneError("ORS_API_KEY not configured")

    body = {
        "locations": [[coords[1], coords[0]]],  # ⚠️ ORS v2 is [lon, lat], our tuple is (lat, lon)
        "range": [int(hours * 3600)],            # seconds; field name is "range", NOT "ranges"
        "range_type": "time",
    }
    async with httpx.AsyncClient(
        headers={"Authorization": ORS_API_KEY},
        timeout=httpx.Timeout(20.0),
    ) as client:
        resp = await client.post(
            f"{ORS_BASE_URL}/v2/isochrones/{mode}",  # profile in URL path
            json=body,
        )
        resp.raise_for_status()

    features = resp.json().get("features", [])
    if not features:
        raise IsochroneError("ORS returned no polygon")
    return features[0]["geometry"]  # GeoJSON Polygon geometry dict


async def _filter_spaces(polygon_geom: dict, hours: float) -> dict:
    """Filter all Oxigraph spaces against the isochrone polygon using shapely."""
    try:
        from shapely.geometry import Point, shape
    except ImportError:
        raise IsochroneError("shapely not installed — travel search unavailable")

    poly = shape(polygon_geom)

    try:
        all_spaces, _ = await sparql_client.run_select(ALL_SPACES_QUERY)
    except Exception as e:
        raise IsochroneError(f"Oxigraph query failed: {e}") from e

    confirmed = []
    seeded_count = 0
    for b in all_spaces:
        try:
            lat = float(b["lat"]["value"])
            lon = float(b["lon"]["value"])
        except (KeyError, ValueError):
            continue
        if poly.contains(Point(lon, lat)):  # shapely Point is (x=lon, y=lat)
            has_endpoint = bool(b.get("endpointUrl", {}).get("value"))
            if has_endpoint:
                confirmed.append({"name": b["name"]["value"]})
            else:
                seeded_count += 1

    # Cap confirmed at 15 results
    capped = confirmed[:15]
    return {"confirmed": capped, "seeded_count": seeded_count, "fallback": False}
