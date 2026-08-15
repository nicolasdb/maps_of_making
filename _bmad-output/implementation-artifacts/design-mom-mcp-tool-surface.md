# Design — MoM-MCP: the data-plane tool surface

**Created:** 2026-08-15 · **Source:** roundtable (Winston, Amelia, John, Mary) · **Status:** design agreed, **open decisions listed at the end — not yet a story**
**Supersedes:** the "Fix 3" section of the original quick-dev doc, and the current scope of `13-4-tool-parity-find-read-gaps-fabrication-backstop`.

---

## The correction

Story 13.4 is currently scoped as **"tool-surface port (find/nearby/isochrone/log_gap/NL→SPARQL guard)"**. That scope is stale and contradicts the project's own strongest evidence:

> 13.1/13.2 shipped Bernardo full read parity with **zero code ported**, by pointing a shared SPARQL skill at `GRAPH_ENDPOINT=https://mapsofmaking.org/sparql`.

Porting `harness/isochrone.py` into hermes would be the first time in Epic 13 that code moves across the repo boundary instead of a contract being exposed — and it would put a MoM-owned ORS key, a 2000/day quota, and a 24h cache inside the agent plane, which the data-plane/agent-plane split exists to prevent.

**13.4 is re-scoped from *port* to *expose*.** MoM hosts the tool surface; hermes instances are clients.

## Why isochrone and not the rest — the selection rule

**A tool exists when SPARQL can't express it, or when it guards state.**

- `find`, `nearby`, `read` — expressible as SPARQL. The shared skill already covers them, and covers them well. Wrapping them as MCP tools is a **second path to the same data**, which is exactly the shadow-state pattern that has bitten this project repeatedly. They may never need to migrate.
- `travel_search` (isochrone) — genuinely different in kind. `harness/isochrone.py` is 278 lines (ORS geocode → isochrone polygon → shapely point-in-polygon over ~3193 spaces), imports `bernard` / `sparql_client` / `query_commands` so it isn't standalone today, and holds three pieces of state that cannot be re-derived from a SPARQL endpoint:
  - `ORS_API_KEY` — MoM-owned, **2000 requests/day**
  - `_polygon_cache` — 24h TTL
  - `_ors_cooldown` — per-Matrix-room, 60s
- `log_gap` — a **write**. Different auth story. Stays out; belongs with `13-4-write-command-parity-...`.

Duplicating the module gives two caches and two cooldown maps counting against **one shared quota** — a rate-limit incident that cannot be reproduced locally. Centralising is not just tidier, it's the only correct answer.

## Verified facts (checked live, 2026-08-15)

| Claim | Status |
|---|---|
| Hermes supports remote HTTP MCP servers with bearer auth | ✅ **Proven in production on this VPS** |
| `mcp_servers` config is global, not per-profile | ❌ **Docs are wrong.** It is **per-profile** |

`/home/nicolas/hermes-deploy/profiles/manny/config.yaml:62` — live, working, used by Manny:

```yaml
mcp_servers:
  context7:
    url: https://mcp.context7.com/mcp
    headers:
      Authorization: Bearer <REDACTED>
```

Only Manny has the key; `bernardo`, `joy`, `bianca` do not. **This kills the global-blast-radius concern entirely** — Bernardo can be given MoM's tools without Joy or Manny seeing them, and a future write surface can be scoped to one profile.

Also verified:
- **Topology:** `hermes` is on the `gateway` docker network; `maps-link-handler` is on `maps_of_making_internal`. Not colocated today, and MoM migrates to its own VPS later — so the call crosses the network by design. No localhost/unix-socket shortcut.
- **Profiles on the VPS:** `bernardo`, `bianca`, `joy`, `manny`, `import`. (`joy` already exists.)
- **MCP Python SDK shape:** `MCPServer(name=..., token_verifier=...)`, `.run(transport="streamable-http", streamable_http_path=...)`; auto-publishes RFC 9728 Protected Resource Metadata and returns `401` + `WWW-Authenticate` on unauthenticated requests.

## Architecture — agreed

**The core is plain functions. MCP mounts on them.** Tool logic comes out of `harness/` into a MoM-side service module: clean signatures, no Matrix types, no MCP types. MCP is a thin adapter over that. REST would be another thin adapter if a non-MCP consumer ever appears — **not built now, not deferred-with-intent, just an afternoon whenever needed.**

*(Winston initially argued REST-first so protocol work couldn't hold 13.5 hostage; he withdrew it once the transport was verified as a config block rather than an integration project. Amelia's "don't write the wrapper twice" stands.)*

**Separate process, separate port** — a new `maps-mcp` container, not mounted inside `link_handler`:
- `link_handler` serves public web traffic; MCP serves an authenticated agent. Different auth model, different failure mode, different restart blast radius. Mounting means an MCP dependency bump can take down the map.
- The agent-facing surface must be able to move independently when MoM splits VPS.
- Container→container on a shared docker network means **no nginx in the path for v1**, which defers the SSE/`proxy_buffering off` problem. Write the nginx block now as a comment; wire it when the call actually crosses nginx (post-VPS-split): `proxy_buffering off; proxy_read_timeout 3600s;`.

**Proposed layout:**
```
infra/mcp/
  server.py        # MCPServer(name="mom", ...) + .run(streamable-http)
  auth.py          # token_verifier — static bearer from env for v1
  tools/
    isochrone.py   # pure funcs, zero bernard/query_commands imports
    cache.py       # _polygon_cache + _ors_cooldown
  sparql.py        # thin client → GRAPH_ENDPOINT
```

**Auth v1:** static bearer via the SDK's pluggable `token_verifier`, `MCP_BEARER_TOKEN` in env, matching hermes' `headers.Authorization`. Not OAuth — the verifier is swappable later with no tool-code change.

**State ownership:**
- `ORS_API_KEY` lives in the `maps-mcp` container env. Never in hermes config, never a tool argument. The key holder must be the rate limiter, and the rate limiter must be the process that owns the cache.
- `_polygon_cache` stays module-level, single process, single replica. **`maps-mcp` must not be scaled horizontally without externalising the cache** — document it in the compose file.
- `_ors_cooldown` **does not get ported. It gets retired and replaced by its two halves:**
  - *burst protection* is a client concern → stays agent-side (agents shouldn't spam)
  - *budget protection* is a server concern → per-token rate limiting, MoM-side
  Any tool signature carrying a Matrix room ID across this boundary is a review reject. Signature is `caller_id: str`, opaque, defaulting to the bearer identity.
- Keep a **hard global daily counter** independent of per-caller cooldown — per-caller limits don't protect a 2000/day cap from three personas in one container.

## Test plan (Amelia)

- `tests/mcp/test_isochrone.py` — pure functions, ORS mocked, no server
- `tests/mcp/test_cache.py` — TTL expiry, cooldown boundary, **daily-cap refusal**
- `tests/mcp/test_auth.py` — 401 + `WWW-Authenticate` on missing/bad bearer
- `tests/integration/test_mcp_live.py` — real `/mcp` over the wire (mock-only hides protocol bugs — Epic 6 lesson)
- **Grep assertion:** zero imports of `bernard`, `query_commands`, `sparql_client` under `infra/mcp/`, so it can't regress
- `Makefile` — `mcp-up`, `mcp-logs`, `mcp-test-live`; **`publish` must include `infra/mcp/` in the rsync set** (the VPS is not a git checkout — miss this and the deploy silently ships nothing)

**Retirement gate for 13.5:** a live parity test from Bernardo in Matrix — same query against `harness/isochrone.py` and against the MCP tool, matching polygons. The unit suite proves the port; only parity proves it's safe to delete. **13.5 must not close before the MCP tool has carried real traffic** — retiring `harness/` is a one-way door, and until then you've moved code, not proven a contract.

## The strategic frame (Mary, and Nicolas's modular vision)

Nicolas's plan: a **pre-customized, self-hostable hermes image for makerspaces** with agent archetypes; MoM running its own hermes container with **Bernardo** (ask the map) + **Manny** (dev/admin/guardian) + **Joy** (community building) across multiple platforms.

That makes this two-sided, and the sides are not equally the product:

- **The hosted MoM tool surface is the product.** It's the only asset that can't be copied by whoever downloads the image, gets more valuable as more spaces connect, and has a metered thing a price can attach to.
- **The distributable image is the funnel.** Design target: *local value standalone, network value connected.* If the archetypes are self-sufficient you've shipped free software with a support burden; if they're useless without MoM you've shipped a demo of a dependency.

Mapping to the monetization hypotheses:
- **Managed hosting** splits into "we run your hermes container" (commodity, thin margin, high support) and "we run the tool surface your self-hosted hermes calls" (non-commodity, nobody else can offer it). The second is the real one — **self-hosting the agents is not a lost sale**, it's the customer paying their own compute while still consuming the metered surface.
- **Managed ontology** gets a delivery vehicle: a community bundle becomes a schema layer MoM-side + an agent archetype hermes-side that speaks it.
- **Crosswalk cartridges** (OKW → IoP Alliance) become an MCP tool an institution can point a client at, without MoM shipping them anything. Cleanest of the three: the buyer is an org with a budget.

**Do not build the distributable image yet.** Evidence for the tool is "a few internal tries"; evidence for the image is zero. *Modularity is a property you preserve in your boundaries, not a milestone you ship.* Draw the seam — **MoM hosts the tool surface authenticated per-tenant; hermes instances are clients, whoever runs them** — and the image becomes a weekend packaging exercise whenever demand appears, because the MoM-hosted Bernardo+Manny+Joy container *is already the reference implementation*. Be your own first tenant; let the second tenant be someone who asked.

**Quota is the liability that forces auth into the same story.** The failure mode isn't abuse, it's **success**: fifty makerspaces each innocently calling isochrone a few times a day evaporates 2000/day with no per-tenant attribution and no fair way to shed load. You cannot rate-limit what you cannot identify. So the image can never ship a shared credential — not in v0, not "temporarily." And per-tenant tokens are simultaneously the quota control **and** the only honest adoption telemetry for deployments MoM doesn't operate, which is the one place a self-hosted install becomes an observable event without anything phoning home.

**Honest framing for the story:** this is infrastructure work justified by architecture, not by demand. Don't write user value into 13.4's acceptance criteria that doesn't exist yet.

---

## Open decisions — need Nicolas

1. **Network:** does `maps-mcp` join `gateway`, or does `hermes` join `maps_of_making_internal`? Amelia wants the first (keeps MoM's internal network closed, matches the future VPS split). This is the decision that ages worst if guessed.
2. **Is MoM-MCP a published, addressable endpoint** a partner can point a client at — or an internal service Bernardo happens to call? Changes the auth story, the uptime expectation, and whether the distributable image is even coherent.
3. **For the image: whose ORS key?** Makerspaces point at MoM's endpoint (MoM pays the bill, needs token issuance + per-tenant quota), or bring their own key (MoM ships the tool, they fund it)? The second is far cheaper to operate and arguably more honest with the sovereignty story. Needed before the image, not before 13.4.
4. **When does per-tenant token issuance land** — with the tool (Mary: auth and adoption analytics are the same mechanism, build once) or before the image ships (Winston)? Amelia scoped v1 as a single static `MCP_BEARER_TOKEN`. These three don't reconcile on their own.
5. **When a makerspace runs the image, what do they get that they can't get from the map?** If the answer is "a nicer way to ask the map questions," the image is a feature and this compresses to one hosted endpoint. If it's "Joy runs their community across Matrix/Discord/Telegram and Bernardo is a bonus," then the agent plane is the product and MoM is the moat — and the funnel direction above is backwards.
