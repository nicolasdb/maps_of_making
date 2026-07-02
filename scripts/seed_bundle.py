#!/usr/bin/env python3
"""Seed Oxigraph from a bundle of mom:Space JSON-LD records.

Path B of the seeding model: bundle imports describe spaces that don't yet
publish a SpaceAPI endpoint (e.g. VOW, RFF). Each record becomes a seeded
mom:Space graph WITHOUT mom:endpointUrl → the heartbeat skips it → it renders
grey/seeded on the map until a coordinator claims it via the admin UI.

Claim flow: when a coordinator later registers a SpaceAPI URL matching the
slug (computed from name+city), register_url CLEARs the bundle graph and
re-INSERTs as self-registered → in-place upgrade, same URI.

Input shape: an array of objects following the data/archive/moms_seed.json
convention (JSON-LD-ish with schema:* / mom:* keys). The script is tolerant —
unknown keys are ignored, missing optional keys are skipped.

Required per record:
  - schema:name (or "name")
  - schema:geo.schema:latitude / .schema:longitude (or "location.lat"/"location.lon")

Optional but written when present:
  schema:address (street/postcode/city/country) ; schema:url ; mom:profileUrl ;
  schema:knowsAbout ; mom:geolocationFidelity ; mom:geolocationNote .

CLI:
  python scripts/seed_bundle.py --bundle data/archive/moms_seed.json \
                                --network vow --source scraped-vow --force
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from spaceapi_extract import escape_literal  # noqa: E402
from spaceapi_extract.address import parse_locality_from_free_address  # noqa: E402

OXIGRAPH_ENDPOINT = os.getenv("OXIGRAPH_ENDPOINT", "http://localhost:7878")
UPDATE_URL = f"{OXIGRAPH_ENDPOINT}/update"
QUERY_URL = f"{OXIGRAPH_ENDPOINT}/query"

MOM_NS = "https://nicolasdb.github.io/mapsofmaking_ontology/ns#"
SCHEMA_NS = "https://schema.org/"

# Europe bbox kept for seed_spaceapi.py; seed_bundle.py accepts global coordinates
BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH = -180, -90, 180, 90

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed_bundle")

import re


def slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def compound_slug(name: str, city: str | None) -> str:
    name_s = slug(name)
    city_s = slug(city) if city else ""
    if name_s and city_s:
        return f"{name_s}-{city_s}"
    return name_s or city_s


def _get(d: dict, *keys: str, default: Any = None) -> Any:
    """Return the first non-None value among d[k0], d[k1], …; supports dotted paths."""
    for k in keys:
        if "." in k:
            cur: Any = d
            for part in k.split("."):
                if not isinstance(cur, dict):
                    cur = None
                    break
                cur = cur.get(part)
            if cur is not None:
                return cur
        else:
            v = d.get(k)
            if v is not None:
                return v
    return default


def extract_record(record: dict) -> dict | None:
    """Normalize a bundle record into a flat dict. Returns None if invalid."""
    name = _get(record, "schema:name", "name", "space")
    if not isinstance(name, str) or not name.strip():
        return None

    geo = _get(record, "schema:geo", "geo", "location", default={}) or {}
    if isinstance(geo, dict):
        lat = _get(geo, "schema:latitude", "latitude", "lat")
        lon = _get(geo, "schema:longitude", "longitude", "lon")
    else:
        lat = lon = None
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        return None
    if lat is None or lon is None:
        return None
    if not (BBOX_SOUTH <= lat <= BBOX_NORTH and BBOX_WEST <= lon <= BBOX_EAST):
        return None

    addr = _get(record, "schema:address", "address", default={}) or {}
    if not isinstance(addr, dict):
        addr = {}
    street = _get(addr, "schema:streetAddress", "streetAddress", "street")
    postcode = _get(addr, "schema:postalCode", "postalCode")
    city = _get(addr, "schema:addressLocality", "addressLocality", "city")
    country = _get(addr, "schema:addressCountry", "addressCountry", "country")
    # SpaceAPI v15 also puts country_code at location level
    if not country:
        country = _get(record, "location.country_code")
    # SpaceAPI location.address is a free-form string like "Street, PostCode City, CountryCode".
    # Extract city/postcode/country from it when the structured addr fields are missing
    # (shared with the live heartbeat's extract_mom() — see spaceapi_extract/address.py).
    if not city:
        loc_addr_str = _get(geo, "address") if isinstance(geo, dict) else None
        if isinstance(loc_addr_str, str):
            parsed_city, parsed_postcode, parsed_country = parse_locality_from_free_address(loc_addr_str)
            city = city or parsed_city
            postcode = postcode or parsed_postcode
            country = country or parsed_country

    url = _get(record, "schema:url", "url", "website")
    profile_url = _get(record, "mom:profileUrl", "profileUrl")
    knows = _get(record, "schema:knowsAbout", "knowsAbout", "specialties", "tags")
    if isinstance(knows, str):
        knows = [knows]
    if not isinstance(knows, list):
        knows = []

    geo_fidelity = _get(record, "mom:geolocationFidelity", "geolocationFidelity")
    geo_note = _get(record, "mom:geolocationNote", "geolocationNote")

    return {
        "name": name.strip().lstrip("#").strip() or name.strip(),
        "lat": lat,
        "lon": lon,
        "street": street,
        "postcode": postcode,
        "city": city,
        "country_code": country,
        "url": url if isinstance(url, str) else None,
        "profile_url": profile_url if isinstance(profile_url, str) else None,
        "knows_about": [str(k) for k in knows if k],
        "geo_fidelity": geo_fidelity if isinstance(geo_fidelity, str) else None,
        "geo_note": geo_note if isinstance(geo_note, str) else None,
    }


def build_insert(r: dict, source: str, network: str) -> tuple[str, str]:
    subj = f"urn:mak:space/{compound_slug(r['name'], r.get('city'))}"
    triples = [
        f"<{subj}> a <{MOM_NS}Space> .",
        f"<{subj}> <{SCHEMA_NS}name> {escape_literal(r['name'])} .",
        f"<{subj}> <{SCHEMA_NS}geo> [ "
        f"<{SCHEMA_NS}latitude> {r['lat']} ; "
        f"<{SCHEMA_NS}longitude> {r['lon']} ] .",
        f"<{subj}> <{MOM_NS}source> {escape_literal(source)} .",
        f"<{subj}> <{MOM_NS}memberOf> <urn:mak:network/{network.lower()}> .",
    ]
    if r.get("street"):
        triples.append(f"<{subj}> <{SCHEMA_NS}streetAddress> {escape_literal(r['street'])} .")
    if r.get("postcode"):
        triples.append(f"<{subj}> <{SCHEMA_NS}postalCode> {escape_literal(str(r['postcode']))} .")
    if r.get("city"):
        triples.append(f"<{subj}> <{SCHEMA_NS}addressLocality> {escape_literal(r['city'])} .")
    if r.get("country_code"):
        triples.append(f"<{subj}> <{MOM_NS}countryCode> {escape_literal(r['country_code'])} .")
    if r.get("url"):
        triples.append(f"<{subj}> <{SCHEMA_NS}url> <{r['url']}> .")
    if r.get("profile_url"):
        triples.append(f"<{subj}> <{MOM_NS}profileUrl> <{r['profile_url']}> .")
    for tag in r.get("knows_about") or []:
        triples.append(f"<{subj}> <{SCHEMA_NS}knowsAbout> {escape_literal(tag)} .")
    if r.get("geo_fidelity"):
        triples.append(f"<{subj}> <{MOM_NS}geolocationFidelity> {escape_literal(r['geo_fidelity'])} .")
    if r.get("geo_note"):
        triples.append(f"<{subj}> <{MOM_NS}geolocationNote> {escape_literal(r['geo_note'])} .")

    body = "\n    ".join(triples)
    return subj, f"INSERT DATA {{\n  GRAPH <{subj}> {{\n    {body}\n  }}\n}}"


def graph_source(client: httpx.Client, graph_uri: str) -> str | None:
    q = (
        f"PREFIX mom: <{MOM_NS}> "
        f"SELECT ?s WHERE {{ GRAPH <{graph_uri}> {{ ?_ mom:source ?s }} }} LIMIT 1"
    )
    resp = client.post(
        QUERY_URL,
        data=q,
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json",
        },
    )
    resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    return bindings[0]["s"]["value"] if bindings else None


def load_bundle(source_arg: str) -> list[dict]:
    if source_arg.startswith(("http://", "https://")):
        log.info(f"Fetching bundle: {source_arg}")
        resp = httpx.get(source_arg, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    else:
        path = Path(source_arg)
        log.info(f"Loading bundle: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "spaces" in data:
        # Accept the {api, source_datasets, count, spaces:[...]} wrapper produced by merge tools
        log.info(f"Detected bundle wrapper — extracting .spaces array ({data.get('count', '?')} declared)")
        data = data["spaces"]
    if not isinstance(data, list):
        raise RuntimeError(f"Bundle must be a JSON array or {{spaces:[]}} wrapper, got {type(data).__name__}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Oxigraph from a mom:Space JSON-LD bundle")
    parser.add_argument("--bundle", required=True, help="Bundle source: URL or local path")
    parser.add_argument("--network", required=True, help="Network slug (e.g. vow, rff, vulca)")
    parser.add_argument("--source", default=None, help="mom:source tag (default: scraped-<network>)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing graphs with the same source-tag (still skips self-registered + other sources)")
    args = parser.parse_args()

    source_tag = args.source or f"scraped-{args.network}"

    try:
        records = load_bundle(args.bundle)
    except Exception as e:
        log.error(f"Bundle load failed: {e}")
        return 1

    log.info(f"Bundle has {len(records)} records — source={source_tag} network={args.network}")

    counters = {
        "imported": 0, "updated": 0,
        "skipped_existing": 0, "skipped_self_registered": 0, "skipped_other_source": 0,
        "no_name": 0, "no_geo": 0, "write_failed": 0,
    }

    with httpx.Client(timeout=20.0) as client:
        for i, record in enumerate(records):
            if not isinstance(record, dict):
                counters["no_name"] += 1
                continue
            r = extract_record(record)
            if r is None:
                # could be no name or no/oob geo — disambiguate with one more check
                name = _get(record, "schema:name", "name", "space")
                if not isinstance(name, str) or not name.strip():
                    counters["no_name"] += 1
                else:
                    counters["no_geo"] += 1
                continue

            subj, insert = build_insert(r, source_tag, args.network)

            try:
                existing = graph_source(client, subj)
            except httpx.HTTPError as e:
                log.error(f"SELECT failed for {subj}: {e}")
                counters["write_failed"] += 1
                continue

            if existing == "self-registered":
                counters["skipped_self_registered"] += 1
                continue

            if existing is not None and existing != source_tag:
                # Foreign source-tag — never overwrite (e.g. spaceapi-directory).
                counters["skipped_other_source"] += 1
                continue

            if existing == source_tag:
                if not args.force:
                    counters["skipped_existing"] += 1
                    continue
                clear = client.post(
                    UPDATE_URL,
                    data=f"CLEAR GRAPH <{subj}>",
                    headers={"Content-Type": "application/sparql-update"},
                )
                if clear.status_code >= 400:
                    log.error(f"CLEAR failed for {subj}: {clear.status_code}")
                    counters["write_failed"] += 1
                    continue
                counters["updated"] += 1
            else:
                counters["imported"] += 1

            try:
                resp = client.post(
                    UPDATE_URL,
                    data=insert,
                    headers={"Content-Type": "application/sparql-update"},
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                log.error(f"INSERT failed for {subj}: {e}")
                counters["write_failed"] += 1
                if existing == source_tag:
                    counters["updated"] -= 1
                else:
                    counters["imported"] -= 1

    log.info(
        "summary: "
        f"imported={counters['imported']} "
        f"updated={counters['updated']} "
        f"skipped_existing={counters['skipped_existing']} "
        f"skipped_self_registered={counters['skipped_self_registered']} "
        f"skipped_other_source={counters['skipped_other_source']} "
        f"no_name={counters['no_name']} "
        f"no_geo={counters['no_geo']} "
        f"write_failed={counters['write_failed']}"
    )
    return 0 if counters["write_failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
