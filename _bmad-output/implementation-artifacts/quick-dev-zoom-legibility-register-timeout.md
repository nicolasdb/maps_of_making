# Quick-Dev — Zoom Legibility · Register Timeout

**Created:** 2026-08-15 · **Owner:** quick-dev / Amelia
**Status:** 🔵 IMPLEMENTED 2026-08-15 — in working tree, **uncommitted, undeployed, pending Nicolas's review**
**Scope:** `web/app.js`, `infra/link_handler/main.py`, `infra/nginx/conf.d/app.conf`. Two independent bugs, no data-model or pipeline changes.
**Split note:** this doc originally carried a third item (isochrone → MCP). That outgrew quick-dev after the 2026-08-15 roundtable and now lives in `design-mom-mcp-tool-surface.md`. Nothing here depends on it.

---

## Fix 1 — Aging/broken glyphs pollute the continental view

**Symptom** (`screencap_0815_134602.png`, legend reads `z3.2`): at continental zoom the point field is speckled with amber `!` (aging), red `×` (broken) and grey `…`/`+` glyphs. At that scale the marks are 1–2px, unreadable as glyphs, and destroy the "field of light" read. The staleness axis is also *not decision-relevant* at continental scale — nobody picks a space from 2000km out based on how fresh its endpoint is.

**Root cause** — two layers, neither zoom-gated:

- `web/app.js` `spaces-glyph` symbol layer had **no `minzoom`**. Its only zoom response was `text-size` ramping `z6→8px`, `z12→13px`, so glyphs rendered at z1.5 as sub-pixel smudges.
- `web/app.js` `circle-color` was a single flat `colorMatchExpr(LADDER[surface])`, zoom-invariant. Axis-B colours (`aging` `#C9963F`, `broken` `#E24B4A`, `zombie`/`dead` greys) therefore fought the blue/green identity read at every zoom. `computeMarker()` deliberately ranks B **above** A/C, so any space past `aging_days_threshold: 30` lost its blue/green entirely.

**Fix — zoom-staged legibility. Same data, two altitudes.**

- **Continental (z < 9): identity only.** The ladder collapses to the identity axis — blue (claimed) / green (live) / faint grey (unclaimed), matching the depth→daylight basemap transition the zoom already drives.
- **Regional + street (z ≥ 9): full ladder.** Amber/red/grey and the `!` `×` `…` `+` glyphs return, where the pixels exist to render them and the information is actionable.

**As implemented:**

1. `LADDER_FAR` table added beside `LADDER` — `aging`/`broken` → claimed-blue `#378ADD`, `open`/`shut` → their greens, `seeded` unchanged `#555560`, `zombie`/`dead` **kept grey**.
2. `spaces-glyph` gets `minzoom: 9` plus `'text-opacity': ['interpolate',['linear'],['zoom'], 9, 0, 10, 1]` — glyphs fade in rather than pop, riding the same "detail arrives" moment as the existing `circle-stroke-opacity` z6→z9 ramp. Still inside the `if (!map.getLayer(...))` guard, so `ensureSpacesLayers()` stays idempotent across `setStyle()`.
3. New `ladderColorExpr(surface)` helper returns `['interpolate',['linear'],['zoom'], 7, colorMatchExpr(LADDER_FAR), 9, colorMatchExpr(LADDER[surface])]`, used by **both** `ensureSpacesLayers()` and `applyLadderPaint()`.

**Deviation from spec (accepted):** the spec inlined the interpolate at both call sites; the implementation factored it into `ladderColorExpr()` instead, matching how the file already handles `colorMatchExpr` / `strokeMatchExpr` / `radiusExpr` / `glyphColorExpr` and preventing the two call sites drifting.

**Deliberate call, still open to override:** `zombie` and `dead` stay **grey** at low zoom rather than collapsing to claimed-blue. They already render quietly (amber `!` was the noise complaint, not them), and painting a permanently-closed space as "claimed" at continental scale is an honesty cost the map doesn't need to pay. For a strict two-colour continental read, move them to `#378ADD` in `LADDER_FAR` — one line.

**Out of scope:** the legend chips still list all eight statuses at every zoom. Zoom-aware legend is a separate UX decision. → flag, don't fix.

**Verify on review:** at z3, only blue / green / faint-grey dots, zero glyphs; between z9 and z10 the amber/red states and glyphs fade in; no style-spec errors in console; `Find` mode (`applyLadderPaint(true)`) still paints flat 6px pins.

> ⚠️ The `['interpolate', …]` with `match` expressions as stop outputs relies on MapLibre propagating the expected `Color` type into the match's string outputs. Documented behaviour, but only a real map load confirms it — a mis-typed expression throws a style-spec validation error in the console rather than failing silently, so the z3 check catches it either way.

---

## Fix 2 — "Registration failed: JSON.parse: unexpected character" on a valid endpoint

**Symptom** (`screencap_0815_134548.png`): validation passes all four checks for `https://pod.nicolasdb.eu/hyperscope_ndb/shared/MoM/openfab.json`, then `Confirm & register` returns
`✗ Registration failed: JSON.parse: unexpected character at line 1 column 1 of the JSON data`.

**Root cause — CONFIRMED from VPS logs. The error message was a lie in two ways.**

`maps-nginx:/var/log/nginx/maps_error.log.1`:
```
2026/08/14 10:50:22 [error] 19#19: *93620 upstream timed out (110: Operation timed out)
while reading response header from upstream, client: 172.23.0.3, server: _,
request: "POST /api/register-url HTTP/1.0", upstream: "http://172.25.0.4:8000/api/register-url",
host: "mapsofmaking.org", referrer: "https://mapsofmaking.org/"
```

1. **Not a parse error.** nginx hit `proxy_read_timeout 30s` (`location /api/`) and returned its **HTML 504 page**. The client did `reg = await resp.json()` unconditionally → `JSON.parse` choked on `<html>` → the catch block reported the parse error as if it were the server's verdict.
2. **The registration SUCCEEDED.** The request kept running server-side after nginx gave up. `maps-link-handler` heartbeat logs show, every 10 min since:
   ```
   INFO:httpx:HTTP Request: GET https://pod.nicolasdb.eu/.../openfab.json "HTTP/1.1 200 OK"
   INFO:pipeline:[axis-a] openfab snapshot minted observed_at=2026-08-15T11:46:18Z
   INFO:pipeline:[axis-c] urn:mak:space/openfab mom:openNow=True
   ```
   The user was told "failed" about a thing that worked — worst possible failure mode for the onboarding surface. A coordinator's rational next move is to retry, or to give up on a space that is already on the map.

**Why it exceeded 30s** — `register_url` did **five** sequential round-trips before responding, two of them whole-corpus:

| Step | Cost |
|---|---|
| `_fetch_and_validate` (re-fetches the endpoint — validate already did) | 1 remote fetch |
| endpoint dedup + orphan/claim-merge SPARQL | 2–3 Oxigraph queries |
| `_build_sparql_update` + UPDATE | 1 write |
| `run_space_pipeline` — full synchronous heartbeat tick | 1 remote fetch + writes |
| `_rematerialize_geojson` | **whole-corpus SPARQL (own 30s timeout) + ~3193 SQLite `read_snapshot()` calls in a Python loop** |

The last row alone can approach the nginx budget. The "fire one synchronous tick so the new space lights up immediately" comment was a sound goal with the wrong mechanism at 3193 spaces.

**As implemented — four parts:**

**2a. `infra/link_handler/main.py`** — `BackgroundTasks` added to the `fastapi` import; `register_url(req, background_tasks)`; `run_space_pipeline(...)` and `_rematerialize_geojson()` moved verbatim (same try/except, same log lines) into a local `_finish_registration()` coroutine registered via `background_tasks.add_task(...)`. The response now returns right after `write_snapshot(...)`. Nothing in the response payload depended on those two steps.

**2b. `web/app.js`** — register response read via `resp.text()` then `JSON.parse` in a nested try. 502/504/524 get:
```
✗ Registration failed: server took too long to respond (HTTP 504).
  Your space may still have been registered — reload the map before retrying.
```
Other non-JSON gets `HTTP ${resp.status}`. The `!resp.ok` detail path is unchanged. The "may still have been registered" hedge is the honest answer under a timeout, which is genuinely *unknown* from the client's side.

**2c. `web/app.js`** — the post-register geojson refetch now races the background task, so it's a 3-attempt loop, 2s apart, breaking as soon as the registered slug appears in the ingested features (or immediately if the response carried no `space_uri`). `spaceName`/`spaceId`/`hasSpace` derivation moved above the refetch since the slug is now needed by it. Filter-clearing behaviour preserved.

**2d. `infra/nginx/conf.d/app.conf`** — `proxy_read_timeout` `30s` → `60s` in `location /api/` **only**, belt-and-braces for the other `/api/` endpoints that also fan out to Oxigraph (`/api/space/{id}/raw`, `/api/heartbeat-space/{id}`). Not a substitute for 2a — a 60s spinner is still a broken UX.

**Verify on review + after deploy:** registering a fresh valid endpoint returns `status: confirmed` in well under 5s; the space appears on the map without a manual reload; a deliberately-stalled upstream produces the honest 504 copy, not a `JSON.parse` message.

---

## Test results (2026-08-15, pre-review)

- `node --check web/app.js` → OK.
- `inspect.signature(main.register_url)` → `(req: UrlRequest, background_tasks: BackgroundTasks)`, `/api/register-url` still registered — so `BackgroundTasks` resolves as a dependency, not folded into the request body.
- Offline suite (venv inside `dropbox-container`; the host venv's `python3.13` symlink is dangling since the host moved to 3.14): **61 passed, 17 skipped**.
- Full `pytest tests/`: **31 failed, 62 passed, 17 skipped**. Every failure is `httpx.ConnectError: [Errno 111] Connection refused` in `tests/test_ohm_mom_integration.py` / `tests/test_geocode_proxy.py` — the local stack isn't running. Environmental; none of those tests import `link_handler.main`.

---

## Observed, NOT in scope

- `maps-link-handler` logs `ERROR:main:[heartbeat] tick failed:` with an **empty message** plus a truncated `httpx`/`httpcore` `ConnectError` traceback on *every* tick, alongside three chronically unreachable spaces (`146b7b60f89a`, `e422f7705de2`, `89664d13c785`). Pre-existing, non-fatal, and the empty `%s` means the log line says nothing. → heartbeat-logging story.
- `maps-nginx`'s `log_format main` records only `$remote_addr`, which is always the `nginx-gateway` container IP — **every visitor logs as one IP**. `X-Forwarded-For` is set on proxy_pass but never logged. → picked up by `design-analytics-minimum-instrumentation.md`.
- The host venv's `python3.13` symlink is dangling (host moved to 3.14). Tests currently need `distrobox-enter dropbox-container`. → environment chore.
