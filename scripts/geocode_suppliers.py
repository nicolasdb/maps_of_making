#!/usr/bin/env python3
"""Geocode a curated supplier CSV, honestly.

"Suppliers near me" needs coordinates, and a supplier list has addresses at best —
often just a commune, sometimes nothing. This script fills `lat`/`lon` in place and,
crucially, records HOW precisely it managed to, in `fidelity`:

    exact        full street address resolved
    approximate  partial street / postcode-level resolution
    city         fell back to the commune centroid — every supplier in that commune
                 lands on the same point
    (blank)      could not resolve at all; no coordinates emitted

That cascade is the whole point. A map that silently shows commune centroids as if they
were shopfronts is lying, and `mom:geolocationNote` carries the plain-language reason so
the UI can say so. Precedent: ~5% of the SpaceAPI directory had invalid coordinates,
caught at seed time rather than at render time.

CACHE. Results are cached to `data/supplier-lists/geocode-cache.json`, which is COMMITTED.
The API is called only for cache misses, so regenerating is reproducible and does not
hammer a free service. Nominatim's usage policy asks for ≤1 req/s and an identifying
User-Agent; both are enforced here.

Usage:
  python scripts/geocode_suppliers.py --csv data/supplier-lists/openfab.curation.csv
  python scripts/geocode_suppliers.py --csv … --offline   # cache only, no network
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("geocode_suppliers")

CACHE_PATH = Path("data/supplier-lists/geocode-cache.json")
USER_AGENT = "maps-of-making/1.0 (https://mapsofmaking.org; supplier geocoding, Story 10.1)"

# Europe bbox — the same guard seed_csv.py applies to spaces. It catches a geocoder
# confidently returning the wrong continent for an ambiguous commune name, without
# excluding the genuinely foreign suppliers these lists contain (a French warehouse or a
# German webshop with a real address is data, not an error).
BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH = -25.0, 34.0, 45.0, 72.0

# ISO alpha-2 → the country name Nominatim reads best in a free-form query.
COUNTRY_NAME = {"BE": "Belgium", "FR": "France", "DE": "Germany", "NL": "Netherlands",
                "LU": "Luxembourg", "IT": "Italy", "GB": "United Kingdom", "ES": "Spain"}

NOTE = {
    "approximate": "Street address incomplete — position resolved to postcode level.",
    "city": "No usable street address — showing the commune centroid, not the shopfront.",
}


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False,
                                     sort_keys=True) + "\n", encoding="utf-8")


def in_europe(lat: float, lon: float) -> bool:
    return BBOX_SOUTH <= lat <= BBOX_NORTH and BBOX_WEST <= lon <= BBOX_EAST


def candidates(row: dict) -> list[tuple[str, str]]:
    """Query strings to try, most precise first, each tagged with the fidelity it earns."""
    street = (row.get("street") or "").strip()
    postcode = (row.get("postcode") or "").strip()
    city = (row.get("city") or "").strip()
    cc = ((row.get("country") or "BE").strip() or "BE").upper()
    country = COUNTRY_NAME.get(cc, cc)
    out: list[tuple[str, str]] = []
    if street and (postcode or city):
        out.append((", ".join(p for p in (street, postcode, city, country) if p), "exact"))
    if postcode and city:
        out.append((f"{postcode} {city}, {country}", "approximate"))
    if city:
        out.append((f"{city}, {country}", "city"))
    elif postcode:
        out.append((f"{postcode}, {country}", "approximate"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Geocode a curated supplier CSV")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--offline", action="store_true",
                    help="Use only the committed cache; never call Nominatim")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        log.error(f"CSV not found: {csv_path}")
        return 1

    cache = load_cache()
    geocode = None
    if not args.offline:
        try:
            from geopy.extra.rate_limiter import RateLimiter
            from geopy.geocoders import Nominatim
        except ImportError:
            log.error("geopy not installed — `pip install -r scripts/requirements.txt`, "
                      "or re-run with --offline to use the committed cache only")
            return 1
        geocode = RateLimiter(Nominatim(user_agent=USER_AGENT, timeout=10).geocode,
                              min_delay_seconds=1.1)

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    stats: Counter = Counter()
    calls = 0

    for row in rows:
        slug = row.get("slug", "?")
        resolved = False

        for query, fidelity in candidates(row):
            if query in cache:
                hit = cache[query]
            elif args.offline:
                stats["cache_miss_offline"] += 1
                continue
            else:
                try:
                    cc = ((row.get("country") or "BE").strip() or "BE").lower()
                    loc = geocode(query, country_codes=cc, exactly_one=True)
                    calls += 1
                except Exception as exc:  # network, quota, malformed — all reported, none fatal
                    log.warning(f"WARNING {slug}: geocoder error on {query!r}: {exc}")
                    stats["geocoder_error"] += 1
                    continue
                hit = ({"lat": loc.latitude, "lon": loc.longitude,
                        "display_name": loc.address} if loc else None)
                cache[query] = hit
                save_cache(cache)  # incremental: an interrupted run loses nothing

            if not hit:
                stats["no_match"] += 1
                continue

            lat, lon = float(hit["lat"]), float(hit["lon"])
            if not in_europe(lat, lon):
                log.warning(f"WARNING {slug}: {query!r} resolved outside Europe "
                            f"({lat}, {lon}) — rejected, not written")
                stats["outside_bbox"] += 1
                continue

            row["lat"], row["lon"] = f"{lat:.6f}", f"{lon:.6f}"
            row["fidelity"] = fidelity
            row["geo_note"] = NOTE.get(fidelity, "")
            stats[fidelity] += 1
            resolved = True
            break

        if not resolved:
            row["lat"] = row["lon"] = row["fidelity"] = ""
            row["geo_note"] = ""
            stats["unresolved"] += 1
            log.warning(f"WARNING {slug}: no coordinates — needs a street address "
                        f"(street={row.get('street','')!r} city={row.get('city','')!r})")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    save_cache(cache)
    log.info(f"✓ geocoded {len(rows)} rows → {csv_path}  ({calls} live Nominatim calls, "
             f"{len(cache)} cache entries)")
    log.info("  fidelity distribution:")
    for k in ("exact", "approximate", "city", "unresolved"):
        if stats[k]:
            log.info(f"    {k}: {stats[k]}")
    for k, v in stats.items():
        if k not in ("exact", "approximate", "city", "unresolved"):
            log.info(f"    WARNING {k}: {v}")
    if stats["city"] > stats["exact"]:
        log.warning("WARNING more commune-centroid fallbacks than exact hits — "
                    "'suppliers near me' will rank poorly. Curate street addresses first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
