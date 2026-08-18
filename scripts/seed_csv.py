#!/usr/bin/env python3
"""CSV ⇄ seed-bundle converter — the curation pivot for Path B imports.

The philosophy (see docs/how-to/import-a-space-batch.md): MoM does NOT try to parse every
messy source. You curate a clean CSV by hand (in a spreadsheet), then convert it to
a canonical bundle that `seed_bundle.py` ingests with zero guesswork. Missing or
wrong data is left missing — that's the nudge for a space to publish a real endpoint.

Two directions:

  to-csv    Dump an existing bundle (messy merged JSON, SpaceAPI-ish, or a
            {spaces:[…]} wrapper) into a CSV you can open in a spreadsheet and clean.
            Best-effort: it extracts what it can and flags the rest.

  to-bundle Convert a curated CSV into a canonical seed bundle (JSON array of
            mom:Space records, the shape data/archive/moms_seed.json uses), ready for
            `make seed-bundle BUNDLE=… NETWORK=…`.

CSV columns (header row required; order free; unknown columns ignored):

  name*        schema:name                         REQUIRED
  lat*         schema:geo latitude                 REQUIRED (decimal degrees)
  lon*         schema:geo longitude                REQUIRED (decimal degrees)
  street       schema:address streetAddress
  postcode     schema:address postalCode
  city         schema:address addressLocality
  country      schema:address addressCountry       (ISO 3166-1 alpha-2, e.g. BE)
  url          schema:url                          (http/https only; else dropped+warned)
  profile_url  mom:profileUrl                      (http/https only)
  tags         schema:knowsAbout                   (semicolon-separated: "3d-printing;laser")
  fidelity     mom:geolocationFidelity             (exact | approximate | city-level)
  note         mom:geolocationNote

Examples:
  python scripts/seed_csv.py to-csv    --bundle data/seed-lists/BE.spaces.json --out /tmp/be.csv
  python scripts/seed_csv.py to-bundle --csv /tmp/be-clean.csv --out data/seed-lists/BE.bundle.json
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed_csv")

# Same Europe bbox the seeders enforce — used here only to WARN, not to drop.
BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH = -25, 34, 45, 72

COLUMNS = [
    "name", "lat", "lon", "street", "postcode", "city", "country",
    "url", "profile_url", "tags", "fidelity", "note",
]


def valid_http_url(u: str | None) -> bool:
    if not isinstance(u, str) or not u.strip():
        return False
    try:
        p = urlparse(u.strip())
    except ValueError:
        return False
    u2 = u.strip()
    return p.scheme in ("http", "https") and bool(p.netloc) and " " not in u2


# ── to-bundle ────────────────────────────────────────────────────────────────

def row_to_record(row: dict, line: int, counters: dict) -> dict | None:
    """Convert one curated CSV row into a canonical mom:Space record (or None)."""
    name = (row.get("name") or "").strip()
    if not name:
        log.warning(f"row {line}: SKIP — no name")
        counters["no_name"] += 1
        return None

    try:
        lat = float(str(row.get("lat", "")).strip())
        lon = float(str(row.get("lon", "")).strip())
    except (TypeError, ValueError):
        log.warning(f"row {line} ({name}): SKIP — lat/lon not numeric "
                    f"(lat={row.get('lat')!r} lon={row.get('lon')!r})")
        counters["no_geo"] += 1
        return None

    if not (BBOX_SOUTH <= lat <= BBOX_NORTH and BBOX_WEST <= lon <= BBOX_EAST):
        log.warning(f"row {line} ({name}): WARN — coords outside Europe bbox "
                    f"({lat},{lon}); verify lat/lon order is correct.")
        counters["out_of_bbox"] += 1

    rec: dict = {
        "@type": "mom:Space",
        "schema:name": name,
        "schema:geo": {
            "@type": "schema:GeoCoordinates",
            "schema:latitude": lat,
            "schema:longitude": lon,
        },
    }

    addr = {}
    if (v := (row.get("street") or "").strip()):
        addr["schema:streetAddress"] = v
    if (v := (row.get("postcode") or "").strip()):
        addr["schema:postalCode"] = v
    if (v := (row.get("city") or "").strip()):
        addr["schema:addressLocality"] = v
    if (v := (row.get("country") or "").strip()):
        addr["schema:addressCountry"] = v
    if addr:
        addr["@type"] = "schema:PostalAddress"
        rec["schema:address"] = addr

    url = (row.get("url") or "").strip()
    if url:
        if valid_http_url(url):
            rec["schema:url"] = url
        else:
            log.warning(f"row {line} ({name}): WARN — dropping invalid url {url!r} "
                        f"(not http/https). Space still imports without a website link.")
            counters["url_dropped"] += 1

    profile = (row.get("profile_url") or "").strip()
    if profile:
        if valid_http_url(profile):
            rec["mom:profileUrl"] = profile
        else:
            log.warning(f"row {line} ({name}): WARN — dropping invalid profile_url {profile!r}")
            counters["profile_url_dropped"] += 1

    tags_raw = (row.get("tags") or "").strip()
    if tags_raw:
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()]
        if tags:
            rec["schema:knowsAbout"] = tags

    if (v := (row.get("fidelity") or "").strip()):
        rec["mom:geolocationFidelity"] = v
    if (v := (row.get("note") or "").strip()):
        rec["mom:geolocationNote"] = v

    counters["written"] += 1
    return rec


def to_bundle(args) -> int:
    path = Path(args.csv)
    if not path.exists():
        log.error(f"CSV not found: {path}")
        return 1

    counters = {
        "rows": 0, "written": 0, "no_name": 0, "no_geo": 0,
        "out_of_bbox": 0, "url_dropped": 0, "profile_url_dropped": 0,
    }
    records = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "name" not in reader.fieldnames:
            log.error("CSV must have a header row with at least: name, lat, lon")
            return 1
        for i, row in enumerate(reader, start=2):  # line 1 is the header
            counters["rows"] += 1
            rec = row_to_record(row, i, counters)
            if rec is not None:
                records.append(rec)

    out = Path(args.out)
    out.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    log.info(
        "summary: "
        f"rows={counters['rows']} written={counters['written']} "
        f"no_name={counters['no_name']} no_geo={counters['no_geo']} "
        f"out_of_bbox={counters['out_of_bbox']} "
        f"url_dropped={counters['url_dropped']} "
        f"profile_url_dropped={counters['profile_url_dropped']}"
    )
    log.info(f"✓ wrote {len(records)} records → {out}")
    log.info(f"  next: make seed-bundle BUNDLE={out} NETWORK=<slug>")
    return 0


# ── to-csv (bootstrap a curation sheet from a messy bundle) ───────────────────

def _get(d: dict, *keys, default=None):
    for k in keys:
        if "." in k:
            cur = d
            for part in k.split("."):
                if not isinstance(cur, dict):
                    cur = None
                    break
                cur = cur.get(part)
            if cur is not None:
                return cur
        elif d.get(k) is not None:
            return d[k]
    return default


def bundle_record_to_row(rec: dict) -> dict:
    """Best-effort flatten of one bundle record into CSV columns. Lossy by design —
    the point is to give a human a clean starting sheet, not a faithful round-trip."""
    name = _get(rec, "schema:name", "name", "space", default="")

    geo = _get(rec, "schema:geo", "geo", "location", default={}) or {}
    lat = _get(geo, "schema:latitude", "latitude", "lat", default="") if isinstance(geo, dict) else ""
    lon = _get(geo, "schema:longitude", "longitude", "lon", default="") if isinstance(geo, dict) else ""

    addr = _get(rec, "schema:address", "address", default={})
    addr = addr if isinstance(addr, dict) else {}
    # SpaceAPI free-form location.address string → dump into street for manual splitting
    loc_addr_str = geo.get("address") if isinstance(geo, dict) else None

    url = _get(rec, "schema:url", "url", "website", default="")
    url = url if (isinstance(url, str) and valid_http_url(url)) else ""

    tags = _get(rec, "schema:knowsAbout", "knowsAbout", "tags", default=[])
    if isinstance(tags, str):
        tags = [tags]
    tags_str = ";".join(str(t) for t in tags) if isinstance(tags, list) else ""

    return {
        "name": name if isinstance(name, str) else "",
        "lat": lat,
        "lon": lon,
        "street": _get(addr, "schema:streetAddress", "streetAddress", "street",
                        default=loc_addr_str or ""),
        "postcode": _get(addr, "schema:postalCode", "postalCode", default=""),
        "city": _get(addr, "schema:addressLocality", "addressLocality", "city", default=""),
        "country": _get(addr, "schema:addressCountry", "addressCountry", "country", default=""),
        "url": url,
        "profile_url": _get(rec, "mom:profileUrl", "profileUrl", default=""),
        "tags": tags_str,
        "fidelity": _get(rec, "mom:geolocationFidelity", "geolocationFidelity", default=""),
        "note": _get(rec, "mom:geolocationNote", "geolocationNote", default=""),
    }


def to_csv(args) -> int:
    path = Path(args.bundle)
    if not path.exists():
        log.error(f"Bundle not found: {path}")
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "spaces" in data:
        log.info(f"Detected bundle wrapper — extracting .spaces ({data.get('count', '?')} declared)")
        data = data["spaces"]
    if not isinstance(data, list):
        log.error(f"Bundle must be a JSON array or {{spaces:[]}} wrapper, got {type(data).__name__}")
        return 1

    out = Path(args.out)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for rec in data:
            if isinstance(rec, dict):
                writer.writerow(bundle_record_to_row(rec))
    log.info(f"✓ wrote {len(data)} rows → {out}")
    log.info("  Open it in a spreadsheet, clean it, then: "
             "python scripts/seed_csv.py to-bundle --csv <clean.csv> --out <bundle.json>")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV ⇄ seed-bundle converter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tc = sub.add_parser("to-csv", help="Dump a bundle into a curation CSV")
    p_tc.add_argument("--bundle", required=True, help="Input bundle (JSON array or {spaces:[]} wrapper)")
    p_tc.add_argument("--out", required=True, help="Output CSV path")
    p_tc.set_defaults(func=to_csv)

    p_tb = sub.add_parser("to-bundle", help="Convert a curated CSV into a seed bundle")
    p_tb.add_argument("--csv", required=True, help="Input curated CSV")
    p_tb.add_argument("--out", required=True, help="Output bundle JSON path")
    p_tb.set_defaults(func=to_bundle)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
