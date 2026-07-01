"""test_geocode_proxy — live endpoint tests for POST /api/geocode (Story 9.3 / AC6 + AC8).

Requires the full stack running (mak-link-handler + nginx).
Run: pytest tests/test_geocode_proxy.py -v

Repointed 2026-07-01: mak-link-handler's port 8000 is `expose`d in
infra/docker-compose.yml, never `ports`-published to the host — by design, it's
only reachable via nginx's /api/ proxy_pass or `podman exec` (see Makefile's
health/heartbeat targets). BASE_URL now goes through nginx, which also fixes
test_geocode_nginx_rate_limit below: it was hardcoded to port 80 (VPS-only),
but local dev maps nginx to 8080 (docker-compose.dev.yml) — both tests now
share one configurable entry point via GEOCODE_BASE_URL.
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("GEOCODE_BASE_URL", "http://localhost:8080")  # nginx; VPS uses 80/443


@pytest.mark.live
def test_geocode_known_address():
    """Brussels city hall → lat ≈ 50.85, lon ≈ 4.36, country derived as BE (Story 9.12 §2)."""
    resp = httpx.post(
        f"{BASE_URL}/api/geocode",
        json={"address": "Rue Royale 1", "city": "Brussels", "postcode": "1000", "country_code": "BE"},
        timeout=15,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] is not None
    assert data["lon"] is not None
    assert abs(data["lat"] - 50.85) < 0.5, f"lat out of range: {data['lat']}"
    assert abs(data["lon"] - 4.36) < 0.5, f"lon out of range: {data['lon']}"
    assert data["display_name"] is not None
    assert data["country_code"] == "BE", f"expected derived country BE, got {data['country_code']!r}"
    assert data["postcode"] == "1000", f"expected derived postcode 1000, got {data['postcode']!r}"


@pytest.mark.live
def test_geocode_derives_country_and_postcode_without_input():
    """country_code AND postcode are DERIVED: omit both from the request and the
    proxy still returns them from the address (Story 9.12 §2)."""
    resp = httpx.post(
        f"{BASE_URL}/api/geocode",
        json={"address": "Rue Royale 1", "city": "Brussels"},
        timeout=15,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] is not None
    assert data["country_code"] == "BE", f"expected derived country BE, got {data['country_code']!r}"
    assert data["postcode"] == "1000", f"expected derived postcode 1000, got {data['postcode']!r}"


@pytest.mark.live
def test_geocode_no_result():
    """Unmatchable address → lat/lon/country_code/display_name all null (HTTP 200, not error)."""
    resp = httpx.post(
        f"{BASE_URL}/api/geocode",
        json={"address": "XXXXXXXXXNOTAREALPLACE99999", "city": "ZZZZZ", "postcode": "00000", "country_code": "XX"},
        timeout=15,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lat"] is None
    assert data["lon"] is None
    assert data["country_code"] is None
    assert data["postcode"] is None
    assert data["display_name"] is None


@pytest.mark.live
def test_geocode_nginx_rate_limit():
    """3 rapid POSTs through nginx → third returns 429.

    nginx limit_req_zone geocode_limit: rate=2r/s, burst=5 nodelay.
    Send 8 requests in tight succession to reliably exceed burst.
    Note: tests directly against link-handler (port 8000) bypass nginx rate-limiting;
    BASE_URL already goes through nginx (see module docstring).
    """
    nginx_url = f"{BASE_URL}/api/geocode"
    payload = {"address": "Rue Royale 1", "city": "Brussels", "postcode": "1000", "country_code": "BE"}
    statuses = []
    for _ in range(8):
        try:
            r = httpx.post(nginx_url, json=payload, timeout=5)
            statuses.append(r.status_code)
        except Exception:
            statuses.append(None)
    assert 429 in statuses, f"Expected 429 in rapid burst, got: {statuses}"
