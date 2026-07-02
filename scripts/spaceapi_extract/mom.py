"""Extract MOM-namespace fields from SpaceAPI payload."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# pipeline_helpers lives in infra/link_handler/ (same dir as the running app in Docker,
# relative path outside Docker). Try direct import first; fall back to path injection.
try:
    from pipeline_helpers import _extract_open_now, _extract_last_open_change
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "link_handler"))
    from pipeline_helpers import _extract_open_now, _extract_last_open_change  # noqa: F401

from .address import parse_locality_from_free_address

# Freshness axis predicates are owned by the heartbeat writers in pipeline.py.
# extract_mom NEVER returns these — the negative unit test in test_spaceapi_extract.py
# guards this contract so a future contributor cannot accidentally add them here and
# create a write-race with the pipeline's dedicated writers.
_FRESHNESS_PREDS = frozenset({"mom:observedAt", "mom:updatedAt", "mom:openNow", "mom:lastOpenChange"})


def extract_mom(payload: dict) -> dict[str, Any]:
    """Extract mom-namespace fields from a SpaceAPI payload dict.

    Returns a CURIE-keyed dict suitable for triples_for().
    Does NOT return freshness axis predicates (observedAt, updatedAt, openNow,
    lastOpenChange) — those are exclusively owned by the heartbeat writers.

    Pure function — no HTTP, no SPARQL, no Oxigraph.
    """
    fields: dict[str, Any] = {}

    loc = payload.get("location") or {}

    addr = loc.get("address")
    if addr and isinstance(addr, str):
        fields["mom:address"] = addr
        city, _postcode, _country = parse_locality_from_free_address(addr)
        if city:
            fields["schema:addressLocality"] = city

    country_code = loc.get("country_code")
    if country_code and isinstance(country_code, str):
        fields["mom:countryCode"] = country_code

    timezone = loc.get("timezone")
    if timezone and isinstance(timezone, str):
        fields["mom:timeZone"] = timezone

    # Defensive assertion: freshness predicates must never slip into this output.
    assert not (set(fields) & _FRESHNESS_PREDS), (
        f"BUG: freshness predicate(s) in extract_mom output: {set(fields) & _FRESHNESS_PREDS}"
    )

    return fields
