"""Shared free-text address parsing — SpaceAPI's location.address is a
free-form string like "Street, PostCode City, CountryCode" with no
structured city field. Both seed_bundle.py (Path B bundle imports) and
extract_mom() (live SpaceAPI heartbeat re-extraction) need to derive a city
from it; this used to live only in seed_bundle.py, which meant SpaceAPI-
sourced spaces (as opposed to bundle-imported ones) never got
schema:addressLocality written at all — see
project_spaceapi_missing_locality_knowsabout memory.
"""
from __future__ import annotations

import re

_POSTCODE_RE = re.compile(r"^\d{4,5}[A-Z]{0,2}$")


def parse_locality_from_free_address(addr_str: str) -> tuple[str | None, str | None, str | None]:
    """Given a free-form address string, return (city, postcode, country).

    Any element not derivable is None. Handles the two shapes seen in
    SpaceAPI location.address values:
      "Street, PostCode City, CountryCode"   (3+ comma segments)
      "PostCode City, Country"               (2 comma segments)
    """
    city = postcode = country = None
    if not isinstance(addr_str, str):
        return city, postcode, country

    parts = [p.strip() for p in addr_str.split(",")]
    if len(parts) >= 3:
        # last segment is country code, second-to-last is "PostCode City"
        country = parts[-1].strip()
        postcode_city = parts[-2].strip()
        # split on first space: "9500 Geraardsbergen" → postcode + city
        pc_parts = postcode_city.split(None, 1)
        # Match "9500 Geraardsbergen" (BE) or "1217EH Hilversum" (NL) or "3901 TP Veenendaal"
        if len(pc_parts) == 2 and _POSTCODE_RE.match(pc_parts[0].upper().replace("-", "").replace(" ", "")):
            postcode = pc_parts[0]
            city = pc_parts[1]
        elif len(pc_parts) == 1 and _POSTCODE_RE.match(postcode_city.upper().replace(" ", "")[:6]):
            # "1217EH" with no space — postcode only, no city parseable
            postcode = postcode_city
        else:
            city = postcode_city
    elif len(parts) == 2:
        # e.g. "9052 Zwijnaarde, Belgium" — try to split postcode from city in parts[0]
        candidate = parts[0].strip()
        pc_parts2 = candidate.split(None, 1)
        if len(pc_parts2) == 2 and _POSTCODE_RE.match(pc_parts2[0].upper()):
            postcode = pc_parts2[0]
            city = pc_parts2[1]
        else:
            city = candidate

    return city, postcode, country
