---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-04-22'
lastEdited: '2026-06-05'
inputDocuments: ['_bmad-output/planning-artifacts/prd.md', '_bmad-output/planning-artifacts/next-session.md', 'archive/docs/architecture/architecture.md', 'archive/docs/project-overview.md', 'archive/docs/index.md']
workflowType: 'architecture'
project_name: 'maps_of_making'
user_name: 'nicolas'
date: '2026-04-22'
editHistory:
  - date: '2026-04-29'
    changes: 'Added ADR-015 (SpaceAPI JSON → MOM JSON-LD transformation layer, raw snapshot to disk); updated Primary Users (3-way split: coordinator / network coordinator Luca / operator Nicolas); updated Data Flow (3-stage pipeline, operator inspection panel, Luca public toggle); updated FR mapping table; added /data/snapshots/ to project structure'
  - date: '2026-05-18'
    changes: 'Added ADR-016 (Layered Community Namespaces + Bundle-Loading Model) — four-layer schema, bundle = view config, schema:knowsAbout concept pivot, crosswalk.csv as living bridge registry; Story 3.5'
  - date: '2026-06-05'
    changes: 'Correct-course artifact-alignment pass. Reconciled in place to current state: ADR-004/006 rewritten to three-token computed-in-browser model; ADR-015 disk-snapshot stages removed (SpaceAPI→MOM mapping kept); ADR-008 marked superseded by ADR-013 (Nanobot); named-graph table, project structure tree, requirements map, and data-flow diagram corrected to the real runtime (infra/link_handler/, scripts/spaceapi_extract/, web/data/spaces.geojson); w3id.org IRIs corrected to canonical nicolasdb.github.io; stale superseding banners removed once their sections were corrected. Epic 6 (Nanobot/NL-bot), Epic 4b (magic link), Epic 7 (open-now) directions retained as planned-not-built.'
  - date: '2026-06-06'
    changes: 'ADR-004 updated: full state colour ladder (shut remap to dimmed-green, aging+zombie decay ramp, dead=off-ladder tombstone), continental view Overview Effect layer (label dissolve at altitude, no network/country colouring, freshness=fragility principle), reference to state-colour-ladder.html and overview-effect-north-stars.md. ADR-017 added: full-GL rendering substrate decision (DOM markers → GeoJSON source + GL layers, vanilla MapLibre no MapTiler SDK, viewport-first init for deep links/embeds with coords-in-URL pattern, optional 301-redirect upgrade for legacy embeds, DOM primitives retired).'
  - date: '2026-06-06'
    changes: 'ADR-017 reconciled: removed "status-weighted clusters" model (stale ideation caught in Story 5.0 readiness review). Continental view is NOT clustered — it is a zoom-scaled point field (every space its own ladder-coloured dot; circle-radius interpolates with zoom; field-of-light at world scale), reproducing the MapTiler helpers/point look in vanilla GL. Dropped cluster:true source config. Clarified ladder Daylight/Depth surfaces follow the tweaks-panel theme toggle, NOT zoom tier. Added symbol-layer glyphs for NFR-A4 (colour not sole state indicator).'
lastReconciled: '2026-06-05'
---

# Architecture Decision Document — maps_of_making

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

> ## Status & canonical sources (reconciled 2026-06-05)
>
> This file is the **BMAD-native detailed architecture record** — the authoritative store of architecture *decisions* for story creation. The companion onboarding abstraction (teammate-facing, diagram-level) lives in **`docs/architecture/01–09`** and must stay consistent with this file, not duplicate its depth.
>
> The Phase-2 freshness/ingestion design has been **updated in place** to the **three-token contract** (Epic 3.5, retro `_bmad-output/implementation-artifacts/epic-3.5-retro-2026-05-28.md`). Current runtime in one paragraph:
>
> - **Runtime engine:** `infra/link_handler/` — `main.py`, `pipeline.py`, `pipeline_helpers.py`, `snapshot_store.py`, `utils.py`. (Not a Discord-harness process; the NL bot in `harness/` is dormant Epic 6.)
> - **Axis A (`observed_at`)** + the **raw payload blob** live in SQLite (`data/tasks/snapshot_store.db`). There is no on-disk `/data/snapshots/*.json` artifact.
> - **Axis B (`mom:updatedAt`)** + **Axis C (`mom:lastOpenChange`)** live in per-space Oxigraph graphs `<urn:mak:space/{id}>` / `<urn:mak:canary/{id}>`.
> - **Transform** is `scripts/spaceapi_extract/` (`core`/`mom`/`sparql`) → idempotent `DELETE WHERE + INSERT DATA`, **only on a real content change**. **Materialize** is `_rematerialize_geojson` (`main.py`) → `web/data/spaces.geojson`, the map's only source.
> - **Derived state** (`endpointHealth`, `operationalState`, marker colour) is computed **in the browser** from the raw tokens + a `thresholds` block shipped in the GeoJSON header. Storage holds facts; consumption layers compute buckets.
>
> Planned-not-built directions retained below as design intent: **Epic 4b** (magic link — ADR-005/010/011), **Epic 7** (open-now presence — ADR-007). **Epic 6** ("Ask Bernard") is 🟢 live as of Story 6.9–6.11: harness baseline + deploy-key write path + isochrone + single tool-calling orchestrator — **ADR-017**; Nanobot (ADR-008/013) confirmed unneeded, not deferred.

---

## Project Context Analysis

### Project Overview

Maps of Making is federated infrastructure for the European maker ecosystem, piloting with RFF (France) and VOW (Germany). The core model: each space publishes one JSON-LD file at a URL they control; a heartbeat agent monitors those URLs for diffs; changes update an Oxigraph RDF triplestore; queries are answered via SPARQL or NL→SPARQL from the webapp or channel bots.

**Phase 1 (shipped):** MapLibre GL JS SPA + PMTiles vector tiles, filters, search, detail drawer, embed snippet. Deployed at mapofmaking.debarquin.eu.

**Phase 2 (this architecture):** Federated backend — URL ingestion pipeline, Oxigraph SPARQL triplestore, pin state confirmation, admin dashboard, NL bot via Discord.

### Primary Users

1. **Space coordinators** — submit one JSON endpoint URL (SpaceAPI-compatible), see their pin flip ⚪→🔵, get nudged if their endpoint goes stale. They own and publish their data; MOM only reads it.
2. **Network coordinators (e.g. Luca/VOW)** — use the public health map toggle (Tweaks panel) to read fleet state at a glance. No login, no admin access. Available to any interested party.
3. **MOM operator (Nicolas)** — infrastructure observability: system health (Oxigraph, ingestion process), space registry with last-probe timestamps, raw/ingested/displayed inspection panel for pipeline diagnosis. This is the `/admin` dashboard audience.
4. **Makers (secondary)** — browse confirmed spaces, use bot queries in their community channel

### Functional Requirements Summary

44 functional requirements across 2 phases. Phase 2 key areas: coordinator registration (FR19–23), endpoint health/ingestion (FR24–27b), admin dashboard (FR28–33b), federated SPARQL query (FR34–36), NL bot (FR37–42).

### Non-Functional Requirements — Architecturally Load-Bearing

- **NFR-R1** Conditional GET (ETag/Last-Modified) — heartbeat must be stateful
- **NFR-R3** All fetch thresholds config-file-driven, not hardcoded
- **NFR-R5** Map usable with 50% endpoints unreachable — degrade to stale, never empty
- **NFR-D1/D2/D3** Spaces not people — PII rejected at ingestion; SPARQL gate rejects `schema:Person`
- **NFR-A1–A5** WCAG 2.1 AA including non-map accessible list view
- **NFR-L1–L4** LLM cost ceiling enforced, prompt cache tracked, retry budget defined

### Scale & Complexity

- Phase 2 complexity: **High** — three distinct subsystems (heartbeat pipeline, admin dashboard, NL bot) sharing Oxigraph
- PoC target: 10 spaces → RFF+VOW pilot ~500 spaces → IoP horizon ~15k
- All thresholds (fetch cadence, failure counts, retention) set from real PoC telemetry — not pre-optimized

### Technical Constraints Already Decided (Pre-Architecture)

| Decision | Status |
|---|---|
| MapLibre GL JS + PMTiles | ✅ Shipped |
| Vanilla JS SPA, no framework | ✅ Shipped |
| Oxigraph RDF triplestore (SPARQL 1.1) | ✅ ADR-001 |
| JSON-LD as space endpoint format | ✅ ADR-003 |
| Docker Compose on VPS | ✅ Decided |
| MOM ontology + Schema.org + IoP vocabulary | ✅ Decided |

### Cross-Cutting Concerns

1. **Pin visual language** — must be defined before backend data model (it defines what the map endpoint serves)
2. **Ontology scope** — MOM vocab vs Schema.org vs IoP: which predicates are authoritative?
3. **LLM harness selection** — NL→SPARQL + heartbeat diff + answer formatting + notification dispatch
4. **Heartbeat agent boundary** — HTTP fetch+diff scope vs LLM interpretation scope
5. **Append-only snapshots** — named graphs in Oxigraph temporal versioning strategy

---

## Starter Template Evaluation

### Primary Technology Domain
Mixed brownfield stack — no conventional starter template applies.
- **Frontend SPA:** shipped vanilla JS prototype (Phase 1) — no changes
- **Python harness:** custom module built from scratch per ADR-008 structure
- **Infrastructure:** Docker Compose extending Phase 1 stack

### Nanobot Agent Dependencies
Nanobot includes all required dependencies:
```
nanobot              # Agent framework (Discord, Telegram, Slack adapters built-in)
litellm              # OpenRouter + multi-provider LLM support
asyncio              # Scheduling via CronService + HEARTBEAT.md
httpx                # async SPARQL client (not SPARQLWrapper — sync only)
pyyaml               # config loading for custom tasks
```
Custom tasks (heartbeat.py, nl_to_sparql.py, etc.) run inside Nanobot's executor. No custom event loop or APScheduler needed — CronService + HEARTBEAT.md handle all scheduling.

### First Implementation Story (Spike)
Build exactly three files, nothing else:
- `harness/main.py` — Discord bot connects, logs "ready"
- `harness/llm_client.py` — one `AsyncOpenAI` call to OpenRouter, returns string
- `harness/sparql_client.py` — one `httpx` query to Oxigraph health endpoint

One `/ping` slash command calls SPARQL + LLM in sequence. Proves: Discord auth, OpenRouter auth, Oxigraph reachability, async chain. That's the full dependency risk surface.

### Docker Compose Additions (Phase 2)
```yaml
name: maps_of_making    # explicit — prevents network name drift across VPS projects

services:
  oxigraph:
    image: ghcr.io/oxigraph/oxigraph:latest
    command: ["--location", "/data", "--bind", "0.0.0.0:7878"]
    volumes:
      - oxigraph_data:/data
    expose: ["7878"]          # internal only — never host-bound
    networks: [internal]

  harness:
    build: ./harness          # python:3.12-slim base
    environment:
      - ADAPTER=discord       # env var selects channel adapter
      - OXIGRAPH_ENDPOINT=http://oxigraph:7878
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
    depends_on: [oxigraph]
    networks: [internal]
```

### Port Isolation from Side Projects
`expose` (not `ports`) = no host-level port conflict. Explicit `name: maps_of_making` = separate `maps_of_making_default` Docker network. Two stacks with the same Oxigraph port are fully isolated. Verify with `docker network ls`.

### Secondary Channel Adapters (same image, planned)
| Adapter | Library | Defer/thinking pattern | Start mode |
|---|---|---|---|
| Telegram | `python-telegram-bot` | Placeholder message + `edit_message_text` | Polling (no public URL needed) |
| Mattermost | `httpx` (webhook model) | Silent or throwaway message | Outgoing + incoming webhooks |

One service per active adapter (`ADAPTER=telegram`, `ADAPTER=mattermost`). Heartbeat scheduler runs in the primary (Discord) service only.

### Backup Strategy
Host-level cron daily N-Quads dump, outside any application process — see **ADR-014** for the command and the IPFS/IPLD production direction.

---

## Architectural Decisions (Party Mode Sessions)

### ADR-004: Pin Visual Grammar

> **Updated 2026-06-06:** rendering substrate migrated to full-GL (see ADR-017). State colour remap and continental-view layer documented here; implementation detail in ADR-017.

**Decision:** Two-layer progressive disclosure. One marker per space, **allocated in the browser** by resolving three orthogonal axes — the map never reads a stored marker colour. Full axis spec + marker-allocation table: `docs/architecture/03-freshness-axes.md` and `04-design-rules.md`. Authoritative visual reference: `_bmad-output/planning-artifacts/state-colour-ladder.html`.

**The three axes (computed client-side from tokens + the GeoJSON `thresholds` header):**
1. **Endpoint health** — derived from `observed_at` age vs thresholds (responsive / warning / unreachable).
2. **Lifecycle freshness** — `seeded` (no `mom:endpointUrl`) vs `confirmed`, then content-staleness from `mom:updatedAt`. Two terminal states: **`closed`** (operator-declared retirement) and **`dead`** (auto-inferred after N failed cycles) — both render as a tombstone, provenance preserved.
3. **Open/now** — from Axis-C `mom:lastOpenChange` / current open claim.

**State colour model — the full ladder (authoritative: `state-colour-ladder.html`):**

| State | Family | Visual treatment | Zoom visibility |
|---|---|---|---|
| `seeded` | neutral | small dim outline circle | street + regional |
| `confirmed` | blue | solid blue circle, cool glow (depth surface) | street + regional |
| `shut` (live, closed now) | **green family** | dimmed/desaturated green — open's quieter twin. **Never black.** | street + regional |
| `open` | green | bright circle + pulse halo; UV cyan core (depth surface) | street + regional |
| `aging` | amber | warm amber circle, fading opacity | street + regional |
| `zombie` | grey | near-invisible ghost outline | street + regional |
| `dead` | grey tombstone | arch shape with cross-mark — **off the ladder, never just "darker"** | admin query only |
| `broken` | red | circle with × mark — same alarm on both surfaces | street + regional |

**Colour rule: darkness is reserved for absence.** `shut` (alive, door closed tonight) was previously rendered as near-black (`--ink`) — this conflated a healthy resting space with a corpse. It is remapped to dimmed-green. Only `dead` and the void earn darkness.

**Default (exploratory) layer:** seeded vs confirmed, plus an open-now accent. Clean first look — trustworthy, never alarming.

**Health (diagnostic) toggle:** overlays aging / zombie / dead and endpoint-health states for outreach triage. Never shown by default. The space detail drawer carries a quiet amber staleness banner ("Last confirmed N months ago…") even with the toggle off.

**Pin shape:** Circles only. No shape-based type differentiation for PoC or pilot — filters and bot queries handle type disambiguation (LOD approach). Revisited post-pilot if needed.

**Continental view — the Overview Effect layer** (design compass: `_bmad-output/planning-artifacts/overview-effect-north-stars.md`):
- At continental/world zoom, the individual dots shrink into a *field of light* — every space stays its own dot (no aggregation/clustering), just smaller, with density emerging through overlap (see ADR-017).
- The continental view **never colours by network or country** — those are the drawn lines MoM exists to dissolve. Spaces are kin by what they do and whether they're alive.
- **Place names and region labels dissolve at altitude** — GL label-layer symbol layers fade out below the continental zoom threshold (same zoom-interpolation machinery as the dot radius ramp). Coastlines and landmass remain. Left with geography and the breathing points.
- Freshness is fragility, not failure. Aging, zombie, dead states are the thin blue line that makes the living spaces feel precious. They are not suppressed.

Dead/closed spaces: removed from the default map view, retained in Oxigraph for admin query; significant life-events recorded in the append-only `<urn:mak:public_ledger>` graph.

**Rationale:** Storage holds facts (tokens + source claims); the consumption layer computes buckets. Keeps the first-look map clean while the diagnostic layer serves coordinators identifying spaces needing outreach.

---

### ADR-005: Space Coordinator Nudge — Magic Link

**Decision:** When a space's heartbeat goes stale, openclaw dispatches a templated email to the last known contact in Oxigraph containing a time-limited, single-use magic link.

**Flow:**
1. Heartbeat scheduler detects endpoint aging threshold crossed
2. Writes `mak:pendingNotification` triple to Oxigraph notification queue
3. Dispatch worker reads queue, generates magic link token, sends email
4. **YES link** (still active) → refreshes status, resets timer, marks confirmed
5. **NO link** (we've closed) → graceful confirmation screen, space marked closed with date, PII removed per GDPR closure logic
6. **No response** → timer continues → zombie → dead by timeout
7. **Bounce/delivery failure** → retry 3× with progressive backoff → escalate to network admins listed on the space card

**Magic link properties:** Single-use, time-limited (72h), signed token. Prevents stale email chains from refreshing a closed space.

**Rationale:** Zero friction for space coordinators (one click, no login). Honest about the "no" path. Graceful degradation when contact is wrong. Network admin escalation closes the loop.

---

### ADR-006: Freshness — store tokens, compute buckets

**Decision (three-token contract, Epic 3.5):** Storage holds **facts** — raw observations and source claims. Derived freshness *buckets* (`operationalState`, `endpointHealth`) are **never stored**; they are computed at consumption time (in the browser) from the three tokens + a `thresholds` block shipped in the GeoJSON header from `config.yaml`. The only "materialization" is the GeoJSON build (see Data Flow): every claimed space's tokens are flattened into `web/data/spaces.geojson`. Full axis math: `docs/architecture/03-freshness-axes.md`.

**The three tokens:**

| Token | Minted by | Advances when | Home | Axis |
|---|---|---|---|---|
| `observed_at` (ISO-8601) | us | every responsive fetch (200 or 304) | SQLite `snapshot_store.db` ONLY | A — endpoint health |
| `mom:updatedAt` (ISO-8601) | us, on content diff | content JSON meaningfully differs | Oxigraph | B — content maintenance |
| `mom:lastOpenChange` (Unix s) | the source (SpaceAPI claim) | they flip open/closed | Oxigraph | C — operational liveness |

**Heartbeat cadence:** ~10 min cron fetch. Oxigraph is written **only on a real content change** (304 / identical-200 advance `observed_at` in SQLite and write nothing to Oxigraph).

**Seed→confirmed transition:** a seeded graph has no `mom:endpointUrl`; the heartbeat skips it. On registration/claim the link handler writes `mom:endpointUrl` (claim-in-place reuses the same graph URI — see `docs/architecture/09-seeding-model.md`), and the first confirmed fetch begins minting tokens.

**Terminal states:** `closed` (operator-declared) and `dead` (auto-inferred after N failed cycles) — both render as a tombstone, computed client-side; provenance preserved; life-events appended to `<urn:mak:public_ledger>`.

**LOD design note (still binding):** lifecycle state *values* are `xsd:string` literals (`"confirmed"`, `"seeded"`…), a deliberate 4-star LOD choice. Do not reintroduce IRI-style state values (`mak:confirmed`) without first minting those concepts in `mom.ttl` (deferred 5-star path). Predicate namespace is `mom:`, never `mak:`.

---

### ADR-007: Real-Time "Open Now" Signal

**Decision:** Webhook pings write to a separate `presence` named graph. Never coupled to heartbeat.

```turtle
GRAPH <urn:mak:presence> {
  <space-uri> mak:lastSeen "2026-04-22T14:32:00Z"^^xsd:dateTime .
  <space-uri> mak:isOpenNow true .
}
```

Heartbeat agent owns `<urn:mak:space>` graph. Webhook handler owns `<urn:mak:presence>` graph. Map query does `LEFT JOIN`. No coupling. Webhook endpoint: thin HTTP handler, validates shared secret, writes one triple, returns 200.

**Phase placement:** Data model slot reserved now. Webhook handler implemented as late Phase 2 feature — no schema changes required when added.

---

### ADR-008: LLM Harness — Custom Python over OpenRouter  ⚠️ SUPERSEDED by ADR-013

> **Superseded by ADR-013 (Nanobot).** Epic 6 uses Nanobot as a separate compose project (confirmed in `sprint-status.yaml` cross-epic handoffs). This ADR is retained for the rationale trail (the cost/lock-in analysis that ruled out other frameworks still informs the model-routing config). The `tasks/` task-module pattern below carries forward — those tasks are now invoked *from Nanobot* rather than a hand-rolled `main.py`.

**Decision (superseded):** Custom Python harness using `AsyncOpenAI` client pointed at OpenRouter. No third-party agent framework (NanoClaw disqualified on model lock-in; OpenClaw disqualified on complexity).

**Rationale:**
- NanoClaw: Anthropic SDK only — cannot use OpenRouter/Minimax/Kimi. Cost-disqualifying.
- OpenClaw: 500k lines, 70+ deps, 53 config files. Unnecessary complexity for 4 constrained tasks.
- Custom harness: ~200 lines, full control, model swap is one config line, auditable.

**Project structure:**
```
harness/
├── config.yaml              # model assignments + endpoints
├── main.py                  # Discord bot + background scheduler
├── llm_client.py            # AsyncOpenAI → OpenRouter, headers baked in
├── sparql_client.py         # httpx async SELECT + UPDATE
├── tasks/
│   ├── heartbeat.py         # diff two JSON-LD versions
│   ├── nl_to_sparql.py      # NL → SPARQL string (temp=0.0)
│   ├── answer_format.py     # SPARQL result → plain language
│   └── notify_dispatch.py   # pure logic: read queue, send, write back
└── adapters/
    └── discord_adapter.py   # slash commands + defer pattern
```

**Nanobot config.json (LiteLLM provider + multi-model):**
```json
{
  "providers": {
    "default": {
      "type": "litellm",
      "api_key": "${OPENROUTER_API_KEY}",
      "base_url": "https://openrouter.ai/api/v1",
      "models": {
        "heartbeat": { "model": "anthropic/claude-haiku-4-5", "temperature": 0.2, "max_tokens": 1024 },
        "nl_to_sparql": { "model": "anthropic/claude-sonnet-4-5", "temperature": 0.0, "max_tokens": 512 },
        "answer_format": { "model": "minimax/minimax-01", "temperature": 0.5, "max_tokens": 512 }
      }
    }
  },
  "channels": {
    "discord": { "enabled": true, "token": "${DISCORD_BOT_TOKEN}" },
    "telegram": { "enabled": true, "token": "${TELEGRAM_BOT_TOKEN}", "allowFrom": ["${ADMIN_USER_ID}"] }
  }
}
```

**Custom tasks in Nanobot:**
```python
# tasks/heartbeat.py — invoked by Nanobot's HEARTBEAT.md scheduler   # stale-ok: superseded ADR-008 sketch
async def heartbeat_task(oxigraph_endpoint: str, space_uri: str) -> str:
    # Fetch space JSON-LD, diff against snapshot, write SPARQL UPDATE
    # Returns structured message for chat or silent execution
    
# tasks/nl_to_sparql.py — invoked by Discord/Telegram slash commands
async def nl_to_sparql(user_question: str, ontology_context: str, model: str = "default") -> str:
    # Use Nanobot's LiteLLM provider to call model
```

**SPARQL client:** `httpx.AsyncClient` directly — SPARQLWrapper is synchronous, skip it.

---

### ADR-009: Channel Bot — Protocol-Agnostic Core, Discord First

**Decision:** Discord first (Nicolas is admin at Openfab Brussels). Protocol-agnostic core with thin channel adapters.

**Adapter interface:**
```python
class ChannelAdapter(Protocol):
    async def receive(self) -> Message: ...
    async def send(self, response: str, context: dict) -> None: ...
```

**Discord defer pattern** (mandatory — LLM calls exceed 3s slash command timeout):
```python
@bot.tree.command(name="ask", description="Ask a question about the map")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer(thinking=True)   # buys 15 minutes
    sparql = await nl_to_sparql.run(question)
    results = await run_select(sparql)
    answer = await answer_format.run(question, results)
    await interaction.followup.send(answer)
```

**Bot invite requirements:** `applications.commands` + `bot` scopes. Commands synced via `tree.sync()` in `setup_hook`.

**Future adapters:** Matrix, Mattermost — same `ChannelAdapter` Protocol, different transport. Docker Compose adds one service per active channel (`openclaw-discord`, `openclaw-matrix`). Core never imports from adapters.

---

### ADR-010: Notification Dispatch Architecture

**Decision:** Pending notification queue in Oxigraph. Separate dispatch worker. No LLM for PoC.

```turtle
<space:xyz> mak:pendingNotification [
  mak:recipient <coordinator:abc> ;
  mak:preferredContactChannel "email" ;
  mak:reason "unresponsive_url" ;
  mak:since "2026-04-22T..."^^xsd:dateTime ;
  mak:retryCount 0 ;
] .
```

Dispatch worker: reads queue → fills template → sends → writes `mak:dispatched` triple. Retry logic: 3× with progressive backoff on delivery failure → escalate to network admins listed on space card. LLM added to this task only if payload becomes unstructured — explicit `model: null` in config signals this is intentional.

---

### ADR-011: Magic Link HTTP Endpoint — Separate `link_handler` Service ⚠️ BLOCKER

**Decision:** The magic link YES/NO handler is a dedicated FastAPI container (`link_handler/`), proxied by nginx at `/claim/*`. It is **not** part of the Discord harness process.

**Problem:** There is no HTTP listener inside the harness process. Discord bots don't bind ports. When a space coordinator clicks the YES/NO link in their email, there's nowhere to receive it unless a separate HTTP service exists.

**Solution:**
```python
# link_handler/main.py (~50 lines)
from fastapi import FastAPI
import httpx, os, hashlib, time

app = FastAPI()
ENDPOINT = os.environ["OXIGRAPH_ENDPOINT"]
SECRET = os.environ["LINK_SECRET"]

@app.get("/claim/{token}")
async def claim(token: str, action: str):  # action = "yes" | "no"
    # 1. Validate token exists and not expired (ASK query to Oxigraph)
    # 2. Validate token not already consumed
    # 3. Execute SPARQL UPDATE: mark consumed + update space status
    # 4. Return confirmation HTML page
```

**nginx routing:**
```nginx
location /claim/ {
    proxy_pass http://mak-link-handler:8000/claim/;
}
```

**Why separate service:** FastAPI binds a port, Discord bot doesn't. Keeping them merged would require threading or an embedded ASGI server inside the bot process — unnecessary coupling and complexity.

**Implementation note:** `LINK_SECRET` is the HMAC signing key. Tokens are `base64url(HMAC-SHA256(uuid + expiry + space_id, secret))`. Never store tokens in plaintext — only the hash.

---

### ADR-012: Operational Metrics — SQLite, outside Oxigraph

> **Reconciliation (2026-06-05):** The *principle* holds and is realised — operational data lives in SQLite (`data/tasks/snapshot_store.db`), not Oxigraph. The specific `mak-scheduler` container, `metrics.db` filename, and `/metrics` REST endpoint below were **never built**; the link_handler owns the SQLite store and exposes diagnostics via `/api/*`. A dedicated metrics surface is **Epic 4** (operator dashboard) scope.

**Decision (principle — realised via `snapshot_store.db` + `/api/*`):** Keep operational data (raw payloads, `observed_at`, fetch outcomes) in SQLite, **not** Oxigraph.

**Rationale:** Storing operational metrics (heartbeat success/failure counts, response times, LLM cost per task) in Oxigraph creates a circular dependency: the heartbeat monitoring Oxigraph health cannot query Oxigraph if it's down. SQLite is a mounted file, survives container restarts, zero infrastructure overhead.

**Schema (minimal):**
```sql
CREATE TABLE heartbeat_log (
    id INTEGER PRIMARY KEY,
    space_uri TEXT,
    checked_at DATETIME,
    http_status INTEGER,
    latency_ms INTEGER,
    outcome TEXT  -- 'ok' | 'changed' | 'error' | 'timeout'
);

CREATE TABLE llm_cost_log (
    id INTEGER PRIMARY KEY,
    task TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    called_at DATETIME
);
```

**Access (superseded sketch — never built):** the original design exposed a `/metrics` endpoint on a `mak-scheduler` container. In the realised system the `link_handler` owns the SQLite store and serves diagnostics via `/api/*`; a dedicated metrics surface is Epic 4.

---

### ADR-013: Agent Framework — Nanobot with One Custom Adapter

> **Deferred to Story 6.4 (2026-06-16, sprint-change-proposal-2026-06-16.md / mom_handoff_2026-06-16.md).** Stories 6.0–6.2 extend the `harness/` baseline directly — no Nanobot. Re-evaluate Nanobot when NL→SPARQL lands (6.4). The Bernard-bot architecture (channel-agnostic core, intent router, deploy-key write path, isochrone, read-only Oxigraph) is **ADR-017**, which supersedes this for 6.0–6.3. ADR-013 retained for the framework trade-off trail.

**Decision (deferred):** Use Nanobot as the primary agent framework. Discord and Telegram adapters built-in; implement one custom Mattermost adapter if needed post-pilot.

**Rationale:**
- **OpenRouter native:** LiteLLMProvider handles `anthropic/claude-*`, `minimax/minimax-01`, OpenRouter transparently — full model-swap control via config
- **Scheduler included:** CronService + HEARTBEAT.md (30-minute polling) — heartbeat pattern ready, no custom event loop
- **Channel adapters free:** Discord (defer pattern), Telegram (polling), Slack built-in; Mattermost is the only custom adapter needed
- **Maintained project:** ~4,000 lines, high source reputation (77.6 benchmark score), active development

**Trade-off analysis:**
- Custom harness: ~200 lines base, but add Discord defer logic (~50), Telegram edit pattern (~50), scheduler loop (~100), SPARQL bindings normaliser (~50), magic link validation (~50), structured logging (~100) = **~600 lines actual**
- Nanobot: ~4,000 lines but multi-channel support + scheduling included = **less custom code overall + fewer moving parts**

**Mattermost adapter:** If needed, implement as custom extension after pilot. Nanobot's adapter protocol is straightforward (send/receive interface).

**Implementation:** Dockerfile `FROM hkuds/nanobot:latest`. Port `config.yaml` to Nanobot's `config.json` format. Keep `tasks/` directory structure for LLM tasks (heartbeat.py, nl_to_sparql.py, etc.) — they stay the same, just invoked from Nanobot instead of harness/main.py.

---

### ADR-017: "Ask Bernard" — One Voice, Two Skillsets, Deploy-Key Write Path

> **Added 2026-06-16** (sprint-change-proposal-2026-06-16.md, mom_handoff_2026-06-16.md). Supersedes ADR-008/013 for Epic 6 Stories 6.0–6.3; ADR-013 (Nanobot) deferred to Story 6.4.
>
> **Core seam and Models sub-sections below superseded 2026-07-02** (`mom_handoff_2026-07-02.md`, party-mode roundtable). Nanobot never activated — confirmed unneeded (Story 6.9: native `harness/` tool-calling agent, Gemma 4, is sufficient; no orchestration framework required). The `query | nl_discovery | unknown` three-way skill split below became, in practice, **two independently-built answer systems** (`nl_to_sparql.py` on hardcoded Sonnet vs. `agent.py`'s tool-calling loop on Gemma) that silently disagreed in production. Corrected model: **`agent.py`'s tool-calling loop is the single orchestrator** for `query`/`nl_discovery`/`unknown` — `write` alone keeps a separate dedicated skill path. NL→SPARQL generation becomes one callable tool (`query_sparql`) in the agent's catalog, not a parallel dispatch target. Sonnet is a **Tier-2 escalation inside the loop** (validation failure / empty result / detected complexity), not the default model for an entire intent class. A Tier-0 FAQ/semantic-cache check runs before the loop. See Stories 6.9, 6.10, 6.11.

**Decision:** Epic 6 ships **one channel-agnostic bot with one Bernard voice and an internal intent router**, built by extending the dormant `harness/` baseline — **not** Nanobot, and **not** two separate bots.

**Rationale:**
- **Coordinators shouldn't route themselves.** "Ask Bernard" covers both maintenance and discovery; the intent classifier (not the user) picks the skill.
- **Platform is transport, not product.** Matrix/Discord/Telegram/Mattermost are adapters behind a normalised `Message`; the skill chain never knows the transport.
- **harness/ already models the LLM call** (`harness/llm_client.py`, LiteLLMProvider over OpenRouter). 6.0–6.2 are slot-filling + formatting + git plumbing — no orchestration framework needed yet. Re-evaluate Nanobot only when free-form NL→SPARQL lands (6.4).

**Core seam (as-shipped 2026-06-16 — see supersession note above for current routing):**
```
Message(text, user_id, room_id, platform, raw)
ChannelAdapter: async receive() → Message ; async send(response, context) → None
intent classifier (Gemma 4 12B via OpenRouter, ~200-token context) → write | query | nl_discovery | unknown
skill router → response formatter (Bernard voice, platform-aware markdown) → adapter.send()
```

**Core seam (current, post-6.11):**
```
Message → intent classifier → write | (query|nl_discovery|unknown → agent.run())
agent.run(): Tier 0 FAQ-cache check (hit → matched entry injected as RAG context, NOT a bypass)
             → Tier 1 Gemma tool-calling loop
             (tools: read_space, query_map, query_sparql, log_gap, propose_write)
             → Tier 2 Sonnet retry only on validation failure/empty/complexity
→ response formatter (Bernard voice, platform-aware markdown) → adapter.send()
```

**Models:** Gemma 4 12B (OpenRouter) for classification, tool-calling, and response formatting (slot-filling, not reasoning; Haiku acceptable fallback). **Sonnet is a Tier-2 escalation inside the agent loop only** — retried with the same tools when Gemma's tool call fails validation, returns empty, or a complexity heuristic trips. Not a dedicated model for an intent class, not a blanket upgrade.

**Write path (data sovereignty — never touches Oxigraph):**
```
write command → permission check (Matrix power level) → git_ops.patch_json (schema-validate)
             → git commit + push over SSH deploy key → heartbeat re-ingests on next cycle
```
- MOM generates an ed25519 key pair per space; private key encrypted at rest (Fernet, `BOT_KEY_SECRET`), keyed to `space_uri`. Deploy-key endpoint: `POST /api/bot/deploy-key/{space_id}` in `infra/link_handler/`.
- Coordinator pastes the public key into their repo's Deploy Keys (GitLab/GitHub/Codeberg/Gitea — identical flow, Story 9.8 tutorial surface) and enables Write. Scope: **one repo, one file**. Revocation = remove the key; MOM retains no access.
- Permissions stored per room in Oxigraph (`mom:botRoom`, `mom:memberPermission`/`mom:allowedFields`). Power levels: 100 coordinator (any field + grant/revoke), 50 trusted (granted fields), 0 read-only. Fixed member whitelist (`state.open`, `contact.irc/matrix/twitter`); `space.name`/`location.*`/`url` coordinator-only. Commit message `· authorized by {matrix_user_id}` is the audit trail.

**Read/query path:** templated SPARQL (LLM only formats the answer) for `status`/`hours`/`find`/`nearby`/`network`; `infra/bot/isochrone.py` does origin-resolve → OpenRouteService isochrone polygon → `shapely` point-in-polygon over confirmed spaces, degrading to bounding-box on ORS timeout. **Bot is read-only on Oxigraph** (NFR-S7); LLM SPARQL still passes the NFR-S5 mutation gate.

**Deployment:** new `mak-agent-bot` Docker Compose service on `maps_of_making_internal` (`external: true`, `expose` not `ports`). New deps: `matrix-nio` (Matrix adapter, async), `shapely` (isochrone); `httpx`/`cryptography` already present. External: `OpenRouteService` (`ORS_API_KEY`, free tier 2000 req/day).

**Channels (Story 6.6):** Matrix ships in 6.0 and is the **only** platform with the write skillset (room power-level model has no Discord/Telegram equivalent). Discord/Telegram/Mattermost add read/discovery only; Discord uses the defer pattern for any LLM-involved command.

**Voice (Story 6.5):** Bernard voice rules (handoff §"Bernard voice rules") are hard constraints and serve as the 6.5 acceptance criteria — never raw errors/status codes; always "what I know first, then what I can't reach, then the exact path forward."

---

### ADR-018: Agent Plane / Data Plane Split — Bernardo on Hermes, Endpoint-as-Contract

> **Added 2026-07-06** (Winston architecture session + Epic 6 retrospective, `epic-6-retro-2026-07-06.md`). **Supersedes the runtime half of ADR-017**: the custom `harness/` runtime is retired as the *product* agent runtime (kept frozen as the parity benchmark). ADR-017's *behaviour* contracts (Bernard voice, deploy-key write path, confirm-by-construction, IoP-guarded NL→SPARQL, read-only-on-Oxigraph) are **carried forward unchanged** — only the runtime that hosts them moves.

**Context — the build-vs-buy finding.** Epic 6 built `harness/` from scratch and hit wall after wall: channel adapters (6-6), E2EE rooms (6-8), durable multi-turn state (flagged in 6-9 as the one thing a framework buys), thread anchoring, mention-detection fragmentation. Every one of these is solved-for-free in [NousResearch Hermes](https://hermes-agent.nousresearch.com/) — a self-hostable agent runtime with profile-per-bot, one gateway across 20+ platforms (incl. Matrix/mautrix with working E2EE), memory, skills, cron. `harness/` was the *right prototype* (it taught Matrix/E2EE/tool-calling from the inside, which is why hermes can now be adopted deliberately rather than cargo-culted) but the *wrong product*. Rule of Three / boring-technology: custom-build the differentiator (the MoM data plane — freshness, ontology, heartbeat), adopt boring infra for the commodity (the agent runtime).

**Decision — two planes, never merged, one contract between them.**

```
DATA PLANE (per community; boring, stable, the differentiator)
  oxigraph + pipeline + link_handler + web  →  exposes: SPARQL endpoint URL + vocabulary
        ▲ HTTP (SPARQL over the compose network or a public/bridged URL)
AGENT PLANE (hermes; evolves fast, commodity runtime)
  gateway + profile-per-bot (bernardo→MoM, bianca→OpenFab, manny→dev-guardian)
  each profile = persona + skills + env
```

- **The contract is a SPARQL endpoint URL + a vocabulary.** Nothing else crosses the seam. Boring, inspectable, swappable.
- **Endpoint is per-profile env, not baked in a skill.** The shared `oxigraph-query` skill currently hardcodes `http://oxigraph:7878` — the landmine. It must read `GRAPH_ENDPOINT` from `profiles/<bot>/.env`. Then bianca→OpenFab store, bernardo→MoM store, same shared skill via the symlink pattern. **This is the enabling change** (Epic 13 Story 13.1).
- **Archetype = persona + skills + env.** A white-label clone = copy a profile dir, swap env (endpoint) + persona + ontology cartridge. This is the *agent-plane* counterpart to Epic 10 (data-plane bundles) and Epic 11 (crosswalk cartridges); it reuses, not reinvents, the managed-hosting monetization already seeded there.
- **Bernardo, not Bernard.** `@bernardo:mapsofmaking.org` (registered 2026-07-06) is a distinct Matrix account, run parallel to the harness Bernard until behavioral parity — avoids the shared-account ghost-bot hazard (Epic 6 round-5) by construction. On parity, the harness Matrix side retires; the MoM data plane (pipeline/oxigraph/link_handler/admin) is untouched.

**Tenancy tiers (hybrid pattern — shared app, per-tenant data, 2026 SaaS consensus):**
| Tier | Data plane | Agent plane |
|---|---|---|
| Self-host (sovereign) | tenant's own compose + oxigraph | tenant's own hermes, cloned archetype profile |
| Managed (we host) | named-graph-per-tenant in one store, OR per-tenant store when regulatory (medical network = per-tenant, non-negotiable) | one hermes gateway, profile-per-tenant |
| White-label domain | same engine + swapped ontology cartridge + palette | same archetype + swapped persona/knowledge |

Domains this opens: makerspaces, repair-cafés, resourceries, myofunctional-therapy medical networks, Open Know-How, LGBT+ friendly-space referencing. Engine identical; **vocabulary + persona + palette are the tenant layer.**

**Open hard problem — write auth.** Today's SPARQL write endpoint is not auth-gated; a remote agent-plane bot must not write until it is. **Direction: Solid pod + WebID.** WebID = dereferenceable identity URIs for coordinators and bots → gate writes by WebID, not shared secrets. Pod = the sovereignty tier's endpoint: a space's data lives in its own pod, MoM indexes rather than owns (consistent with the no-PII-filtering / coordinator-owns-disclosure stance). RDF-native, so oxigraph and pods speak the same Turtle. Tracked in Epic 10's "node sovereignty" concern; a prerequisite for agent-plane *writes* against remote/managed data planes (reads land first).

**Rule of Three — do not build the platform yet.** Tenant #1 = bernardo→MoM. Tenant #2 = bianca→OpenFab (half-exists). Extract provisioning tooling / multi-tenant machinery only at tenant #3. Until then "archetype" is a documented profile-cloning procedure, not a product.

**Consequences for the epic map:**
- **Epic 13 (new)** owns the agent-plane migration (bernardo scaffold, endpoint parametrization, persona/tool parity, harness retirement).
- **Epic 12's** "multi-platform adapters" sub-track is **superseded on parity** — hermes ships them natively (same reason 6-6/6-8 retire).
- **Epic 10 / Epic 11** stay the data-plane white-label + cartridge track; Epic 13 is their agent-plane counterpart. Cross-referenced, not merged.

**Trade-offs (honest):** remote SPARQL from the agent plane adds latency + the write-auth gate above; a copy-into-hermes-oxigraph option (load MoM named graphs locally) trades freshness for network simplicity and stays available as a fallback. The endpoint-as-env contract keeps that choice per-profile and reversible.

---

### ADR-015: Ingestion Transformation Layer — SpaceAPI JSON → MOM JSON-LD

**Decision:** Spaces publish flat SpaceAPI-compatible JSON. MOM runs an explicit transformation layer (`scripts/spaceapi_extract/`) that converts it into MOM triples before writing to Oxigraph. The raw pre-transformation payload is persisted **first**, in SQLite (`snapshot_store.db`), as the trust receipt / Zone-3 source.

**The pipeline — three stages, content-gated:**

```
Stage 1 — FETCH  (pipeline.py / snapshot_store.py)
  Space publishes SpaceAPI JSON at their URL
  ~10-min cron does conditional GET (ETag / Last-Modified)
  Raw payload written to SQLite snapshot_store, minting observed_at
  (Zone-3 source + audit trail — SQLite, never an on-disk JSON artifact)

Stage 2 — TRANSFORM  (scripts/spaceapi_extract/: core, mom)
  Compare-gate: 304 or byte-identical content → advance observed_at only, STOP
  On real content change → SpaceAPI JSON → MOM triples (ontology applied)

Stage 3 — INGEST  (pipeline.py)
  Idempotent DELETE WHERE + INSERT DATA into <urn:mak:space/{id}>
  Set mom:updatedAt = now; log decision ("ingested" | "no_change" | "error")
```

**Why the raw payload lives in SQLite, not Oxigraph:**
It is the audit trail and the space card's Zone-3 trust receipt (`/api/space/{id}/raw`). Keeping it out of the triplestore decouples the debugging surface from the thing being diagnosed. SQLite is boring and correct.

**The ontology's role in transformation:**
The `.ttl` is the specification; `scripts/spaceapi_extract/` (`core`/`mom`) is its implementation. They are coupled. If `mom.ttl` declares `mom:MakerSpace rdfs:subClassOf schema:LocalBusiness`, the transformation must emit `@type: ["mom:MakerSpace", "schema:LocalBusiness"]`. Drift between spec and implementation means silent data errors.

**SpaceAPI → MOM field mapping (explicit contract):**

| SpaceAPI field | MOM JSON-LD mapping | Notes |
|---|---|---|
| `space` | `schema:name` | Required |
| `url` | `schema:url` | Required |
| `location.lat/lon` | `schema:geo` → `schema:GeoCoordinates` | Required |
| `location.address` | `schema:address` → `schema:PostalAddress` | Card subset |
| `contact.website` | `schema:url` (space website) | Card subset |
| `state.open` | `mom:isCurrentlyOpen` | Card subset |
| `opening_hours` | `schema:openingHoursSpecification` | Card subset |
| `linked_spaces[]` | `mom:NetworkMembership` | Extended subset |
| `membership_plans[]` | `mom:membershipPlans` | Extended subset |
| *(no SpaceAPI equivalent)* | `mom:consortium` | MOM extension |
| *(no SpaceAPI equivalent)* | `mom:residency` | MOM extension |
| *(no SpaceAPI equivalent)* | `mom:specialties`, `mom:equipment` | MOM extension |

**MOM extension fields (no SpaceAPI equivalent):** live in `mom:extended` subset. Ingested when present; never required. Progressive unlock UX signals which subset a space has reached.

**Long-term ambition:** This transformation layer is MOM's core value-add. Spaces need zero knowledge of linked data. The bridge pattern at community scale is MOM's argument for SpaceAPI adopting JSON-LD natively — making this implementation the reference.

**Raw payload storage:** SQLite `snapshot_store.db` holds the most recent raw fetch per space (keyed by graph URI), alongside `observed_at` and the conditional-GET validators (ETag / Last-Modified). No on-disk JSON artifacts; no per-date append-only file archive.

---

### ADR-016: Layered Community Namespaces + Bundle-Loading Model

**Decision:** The MOM schema is organised as four layers under the **single canonical authority** `https://nicolasdb.github.io/mapsofmaking_ontology/`. Communities are loaded as composable *bundles* — a view configuration, not a separate graph. The handoff document's `w3id.org` IRIs are illegal; the layer split is real and lives *under* the canonical authority as sub-namespaces. Operationalized by Story 3.5 (`core.ttl`, `crosswalk.csv`).

**The four layers:**

| Layer | Namespace / file | Loaded | Role |
|---|---|---|---|
| `core` | `…/ns/core#` — `ontology/core.ttl` | always | portable identity (name, logo, website, geoloc, address) + `core:relationships` |
| `mom` | `…/ns#` — `ontology/mom.ttl` | always | federation engine — `operationalState`, `endpointHealth`, `lastFetched`, `lastUpdated`, `memberOf`, `source` |
| concept commons | currently inside `mom.ttl` (`mom:ActivityScheme`); future own namespace | always (in the graph) | the SKOS concept graph `schema:knowsAbout` resolves into (CNC, 3D-printing…) — owned by nobody, traversable by everybody |
| community (`fab`/`omt`/`edu`/`agri`…) | future per-community `.ttl` | per `config.yaml` bundle | community vocabulary, fields, and CSS |

**Bundles are *view* configuration; the Oxigraph graph is universal.** A community map renders its bundle by default, but the graph holds every node. Bundle loading is analogous to `docker-compose` — the `config.yaml` composes which layers a given map surfaces; the underlying data is one shared graph.

**`schema:knowsAbout` is the concept pivot (the "wormhole hub").** Every community's specialised skill field — `fab:equipment`, `omt:treatmentFocus`, `edu:subjects` — aliases to `schema:knowsAbout` via `skos:closeMatch`. Because all of them resolve to the *same* concept IRIs, a query crossing two communities works with **zero coordination** between them: a dentist who never loaded `fab:` is still discoverable by a woodworker's "who does CNC near me" query. This is design for emergence.

**`crosswalk.csv` is a living bridge registry.** `ontology/crosswalk.csv` records, per concept, the predicate the pipeline actually emits, its SpaceAPI source, and the community fields that alias to it. It is **v1 and never "finished"** — new `skos:closeMatch` bridge rows are appended as cross-community overlaps are discovered. `scripts/validate_crosswalk.py` enforces the no-redefinition rule: an extension may alias a `core:`/`mom:` field but never redefine it.

**External concept anchors (candidates, not wired):** OpenKnowHow (OKH) and Wikidata are candidate external anchors for the concept commons — `owl:sameAs` / `skos:closeMatch` targets that would let MOM concepts align with vocabularies beyond the federation. Not implemented; noted for continuity.

**`mom.ttl` is currently impure** — it mixes the federation engine with makerspace activity concepts (`mom:ActivityScheme`). Extracting the activity scheme into a dedicated `fab.ttl` (or a standalone concept-commons namespace) is future work, tracked under the Epic 9 stub. Story 3.5 deliberately does **not** move it; `crosswalk.csv` labels those concepts "concept commons (shared layer)" so the future extraction does not mis-file them into `fab:`.

**Ontology-gap on-ramp.** `mom:OntologyGap` is declared in `mom.ttl` (added by Story 3.5). Today, unrecognised activity tags are logged to `gap_log.txt` as plain text by `transformer.py::_log_unmapped_tags` — no gap *triples* are emitted yet. Emitting `mom:OntologyGap` triples is deferred to **Story 6.3**. The gap log is intentionally the on-ramp for emergent community ontology (gap term → curation → concept minting → bridge discovery), not a janitorial dump.

**Sync model:** `ontology/mom.ttl` and `ontology/core.ttl` in this repo are the working copies. The maintainer manually syncs them to the `github.com/nicolasdb/mapsofmaking_ontology` repo (published via GitHub Pages). Ontology edits land in `ontology/` here first; nothing git-pushes to the ontology repo automatically.

---

### ADR-017: Map Rendering Substrate — Full-GL Migration (2026-06-06)

**Decision:** Migrate the map's marker layer from **individual DOM markers** (`maplibregl.Marker` per space) to a **GeoJSON source + MapLibre GL layers** — one rendering system, no DOM/GL hybrid. Implementation: vanilla MapLibre GL `addSource` / `addLayer`; no MapTiler SDK (vendor coupling, API-key dependency, conflicts with self-hosted PMTiles tile strategy).

**What this replaces:** `renderMarkers()` in `web/app.js` currently creates one SVG DOM element per space on every render. At 111 spaces this is manageable; it cannot render a continuous zoom-scaled field and re-mounts all 111 nodes on every filter/style change.

**The GL source model:**
```js
map.addSource('spaces', {
  type: 'geojson',
  data: '/data/spaces.geojson',   // the map's existing ONLY data source — unchanged
});
// NO clustering: cluster:false. Every space is its own point at every zoom.
```
A single `circle` layer (plus a `symbol` layer for non-colour state glyphs) shares this source. The data contract (`spaces.geojson` + `thresholds` header) is **unchanged** — this is a browser rendering change only; the pipeline is untouched.

**Zoom-scaled point field — NOT clustering:**

The continental view is a *field of individually-coloured dots*, not aggregated clusters. Visual reference: the MapTiler `helpers/point` example (`docs.maptiler.com/leaflet/examples/helpers-point/`) — every point rendered individually, sized/coloured by a data value, density emerging through overlap. We reproduce that *look* in vanilla GL `circle-*` expressions (the helper is a thin wrapper over them — no SDK).

| Zoom | What the viewer sees |
|---|---|
| ≤ 5 (world) | Small ladder-coloured dots — the "field of light"; dense regions read through overlapping/additive opacity |
| 5–7 (continental) | Same dots, slightly larger; place labels faded out |
| ≥ 8 (street/city) | Same dots at full radius; full colour ladder legible per-space |

The ONLY thing that changes with zoom is `circle-radius` — a single `interpolate(['linear'], ['zoom'], …)` ramp. There is no dot↔cluster swap, no aggregation, no count labels.

Label fade: MapLibre `place` symbol layer `paint['text-opacity']` interpolated to 0 below ~z6–7. Coastlines/landmass remain (Overview Effect: geography + points only at altitude).

**Colour ladder surface follows the theme toggle, not zoom:** the `state-colour-ladder` has two surfaces — Daylight (parchment) and Depth (dark) — selected by the existing tweaks-panel light/dark/grayscale toggle. The dark field in the reference screenshots is one theme, not a requirement; dots must read on whichever basemap flavour is active.

**Viewport-first init for deep links and embeds:**
Share URLs encode coordinates: `/?space=openfab&lat=51.50&lon=-0.12`. `initMap()` reads these before constructing `new maplibregl.Map()`, starting at the target viewport. First tile fetch is the local area; continental tiles only load if the viewer zooms out. No `flyTo` on cold load.

For old embed snippets (coords not in URL): optional server-side 301 redirect — if `?space=<id>` arrives without lat/lon, nginx/Flask looks up coords and redirects to the coord-enriched URL. Upgrades all legacy embeds silently. Coords are stable; redirect is cache-safe.

**What is retired:**
- `createMarkerSVG()` — DOM SVG construction per space
- `renderMarkers()` — full tear-down and re-mount on every filter/style change
- Emoji glyphs (🧟 🪦 ⚠️) and CSS `@keyframes` pulse — replaced by GL data-driven `circle-color`, `circle-radius` paint expressions and a `requestAnimationFrame`-driven opacity animation for the open-pulse. A `symbol` layer carries short text glyphs (`×` etc.) so colour is never the sole state indicator (NFR-A4).
- `maxBounds` EU constraint — dropped; world view enabled because the zoom-scaled point field keeps the world view alive (field of light) rather than empty

**What is preserved:**
- `computeMarker()` logic — ported to a JS function that maps space state → GL paint property values
- `filteredSpaces()` — drives `setFilter()` / `setData()` on the GL source instead of DOM re-mount
- `selectSpace()` / `highlightSelected()` — adapted to GL feature-state API
- All data (spaces.geojson, thresholds header, three-token model) — unchanged

**Design reference:** MapTiler `helpers/point` example (visual target; screenshots `~/Images/Screenshots/screencap_0606_151757.png`, `screencap_0606_110737.png`). Continental UX intent: `overview-effect-north-stars.md`. Authoritative colour model: `state-colour-ladder.html`.

**Rationale:** DOM markers cannot render a continuous zoom-scaled field and re-mount expensively on every state change. Moving to a GL source + `circle`/`symbol` layers gives the field-of-light point field with GPU-cheap filter/re-render (repaint vs DOM churn). The data contract is unchanged — this is a pure consumption-layer decision. *(Aggregation/clustering was considered and rejected: at PoC scale every space should be individually visible; the meaning is presence, not headcount.)*

---

### ADR-014: Backup Strategy — rsync for PoC, IPFS+IPLD Direction for Production

**Decision:** PoC uses host-level rsync/cron for daily N-Quads dumps. IPFS+IPLD is the production target but not implemented at PoC.

**What's actually at risk:** Not the space data (spaces republish from their own URLs). The provenance of aggregation — named graph snapshots showing when we saw what, diff history proving our ingestion pipeline's accuracy. This is the civic record that needs immutable archival.

**PoC backup (host cron):**
```bash
# /etc/cron.daily/backup-oxigraph
curl -s "http://localhost:7878/dump?format=application/n-quads" \
  > /var/backups/oxigraph/dump-$(date +%Y%m%d).nq
rsync -az /var/backups/oxigraph/ backup-user@backup-host:/backups/maps-of-making/
find /var/backups/oxigraph -name "*.nq" -mtime +7 -delete
```

**Production direction:** IPFS+IPLD for named graph snapshots (immutable CIDs). Solid pods as W3C alternative if IPFS operational overhead is too high at pilot. Decision deferred to pilot — requires real PoC telemetry on snapshot size and frequency.

---

### Epic 3.5 Transition State — Three-Token Freshness Model (2026-05-19 correct-course)

**Decision:** Dual-pipeline transition from legacy `heartbeat_log` pipeline to clean snapshot pipeline,
further correct-coursed from a single `observed_at` token to **three tokens on three axes**.

**The three tokens:**

| Token | Minted by | Advances when | Home | Axis |
|---|---|---|---|---|
| `observed_at` (ISO-8601) | us | every responsive fetch (200 or 304) | SQLite `snapshot_store.db` ONLY | A — endpoint health |
| `updated_at` (ISO-8601) | us, on content diff | content JSON meaningfully differs | Oxigraph `mom:updatedAt` | B — content maintenance |
| `state.lastchange` (Unix s) | the source (SpaceAPI claim) | they flip open/closed | Oxigraph `mom:lastOpenChange` | C — operational liveness |

**Governing principle:** storage holds facts (observations + source claims), never derived buckets.
`operationalState` and `endpointHealth` are computed at consumption time (browser) from the three
tokens + a `thresholds` block shipped in the GeoJSON header from `config.yaml`.

**Ingestion rule:**

| Fetch outcome | `observed_at` (SQLite) | Oxigraph write | `updated_at` |
|---|---|---|---|
| 304 | advance | **none** | unchanged |
| 200, content identical | advance | **none** | unchanged |
| 200, content changed | advance | DROP+INSERT | set to now |

Oxigraph written ONLY on a real content change. `build_state_only_update` (304→Oxigraph path) deleted.
`state` block added to `_IGNORED` diff set — open/closed flips count toward Axis C, not Axis B.

**Migration sequence — COMPLETE (Epic 3.5 done, retro 2026-05-28):**
- 3.7 ✅: Fetch seam — snapshot store + 304/unreachable rules; deleted `heartbeat_log` noise columns
- 3.8 ✅: Transform seam (old model) — wrote `mom:observedAt`; superseded by 3.8b
- 3.8b ✅: Correct transformer — stopped writing `mom:observedAt`; `mom:updatedAt` on content-changed path only; deleted `build_state_only_update` and derived bucket triples
- 3.9 ✅: Materializer joins SQLite+Oxigraph — three tokens per GeoJSON feature + `thresholds` block at file level
- 3.10 ✅: Browser computes all three axes live from tokens + thresholds header

**End state (achieved):** One clean pipeline. `heartbeat_log.db` and legacy transformer code deleted.
`mom:operationalState` and `mom:endpointHealth` are absent from Oxigraph — computed live in the browser. This is the live model, no longer a transition.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical (block implementation):**
- MOM ontology strategy — align-and-extend (decided)
- `@context` IRI stability — canonical `nicolasdb.github.io/mapsofmaking_ontology` GitHub Pages (decided)
- IoP integration pattern — named graph + cached prompt slice (decided)
- Logging — structlog from day one (decided)

**Deferred (post-PoC):**
- CI/CD pipeline — manual deploy for PoC; GitHub Actions at pilot
- Advanced ontology governance — MOM namespace versioning strategy

### Data Architecture

**Oxigraph named graph structure:**

Three live graph families (`space`, `canary`, `public_ledger`) plus read-only ontology graphs. No materialized-status graph — derived buckets are computed in the browser, not stored.

| Named graph | Owner | Contents |
|---|---|---|
| `<urn:mak:space/{id}>` | Ingestion pipeline (`infra/link_handler`) | Current space triples + tokens `mom:updatedAt`, `mom:lastOpenChange`, `mom:endpointUrl`. `{id}` = `sha256(name\|endpoint)[:12]` (Path A) or `name-slug-city-slug` (Path B) |
| `<urn:mak:canary/{id}>` | Canary tools (`scripts/canary_*.py`) | Synthetic "Mother Sands" diagnostic space — isolated from real-space graphs |
| `<urn:mak:public_ledger>` | Ledger writer *(future epic)* | Append-only, immutable, IPFS/IPLD-anchored space life-events (registration, relocation, schema upgrade, `closed`, `dead`). Name + append-only principle locked 2026-05-16; event schema deferred. **Never DROP.** |
| `<urn:mak:presence>` | Webhook handler *(Epic 7, parked)* | Ephemeral open-now signals — schema slot reserved, not implemented |
| `<urn:mak:notifications>` | Dispatch worker *(Epic 4b, planned)* | Pending notification queue |
| `<urn:mak:ontology/iop>` | Init script (`load_ontology.sh`) | IoP ontology (read-only) |
| `<urn:mak:ontology/mom>` | Init script (`load_ontology.sh`) | MOM vocabulary (read-only) |

Note: `observed_at` (Axis A) and the raw payload are authoritative in **SQLite `snapshot_store.db`** only — never an Oxigraph graph.

**MOM ontology strategy — align-and-extend** (authoritative layered model: **ADR-016**):
- Base: `schema:LocalBusiness`, `schema:openingHours`, `schema:geo` (Schema.org)
- Equipment/capabilities: `skos:closeMatch` to IoP classes — reference without hard dependency
- Maker-specific: `mom:` classes/properties (e.g. `mom:memberOf`, `mom:operationalState`, `mom:endpointUrl`)
- **Canonical namespace: `https://nicolasdb.github.io/mapsofmaking_ontology/ns#` (prefix `mom:`)** — `mom.ttl` is authoritative. The earlier `w3id.org/maps-of-making/` IRI is **not used** anywhere in code, queries, or `.ttl`.
- Working copies live in repo at `ontology/mom.ttl` + `ontology/core.ttl`, manually synced to `github.com/nicolasdb/mapsofmaking_ontology` (GitHub Pages). Nothing git-pushes to the ontology repo automatically.

**IoP integration in Oxigraph:**
- Loaded at harness startup into `<urn:mak:ontology/iop>` via idempotent `ASK` check
- Full ontology stored, ~15-20% relevant subset extracted via SPARQL CONSTRUCT at init
- Subset serialized as compact text block, cached in memory, injected into every NL→SPARQL prompt
- `RELOAD_ONTOLOGY=1` env var forces reload on update
- Load command: `curl -X POST -H 'Content-Type: text/turtle' -G 'http://oxigraph:7878/store' --data-urlencode 'graph=urn:mak:ontology/iop' --data-binary @ontology/iop.ttl`

### Authentication & Security

| Surface | Auth method |
|---|---|
| Public map SPA | None — fully open |
| Public SPARQL query endpoint (`/sparql/query`) | None — read-only, rate-limited by nginx |
| SPARQL update endpoint (`/sparql/update`) | Blocked at nginx — internal Docker network only |
| Admin dashboard | Shared password, env-var secret (PoC); per-user accounts at pilot |
| Magic link tokens | Single-use, 72h TTL, signed |
| OpenRouter / Discord / Telegram tokens | `.env` file on VPS, never committed |

### API & Communication Patterns

**SPARQL endpoint routing (nginx):**
- `GET|POST /sparql/query` → `http://oxigraph:7878/query` (public)
- `POST /sparql/update` → `deny all` (internal Docker only)
- CORS: `Access-Control-Allow-Origin: *` on query endpoint (browser clients)

**Bot command response contract:**
- Defer immediately on all LLM-involved commands (`interaction.response.defer(thinking=True)`)
- On success: `interaction.followup.send(answer)`
- On LLM failure: user-facing — "I couldn't answer that, try rephrasing or browse the map directly"
- On LLM failure: internal — log structured event + write ontology gap triple to Oxigraph (FR41)
- Error responses always via `followup.send()` after defer — never `response.send_message()`

**SPARQL result binding normalisation:**
```python
# Always flatten SPARQL JSON bindings before passing to LLM tasks
[{k: v["value"] for k, v in row.items()} for row in data["results"]["bindings"]]
```

### Infrastructure & Deployment

**Deploy for PoC — manual:**
```bash
git pull
docker compose pull
docker compose up -d --build harness
```

No CI/CD pipeline for PoC. GitHub Actions at pilot stage.

**Secrets management:** `.env` file on VPS, gitignored. `.env.example` committed with placeholder values. All secret vars scoped to the services that need them.

**Backup:** Host cron daily, 7-day retention. Outside Docker — host-level cron calls `GET /dump?format=application/n-quads`.

---

## Implementation Patterns & Consistency Rules

### Naming Patterns

**RDF / Named graphs:** `urn:mak:{type}/{id}` — lowercase, colon-separated. Never use hash URIs for named graphs.

**MOM vocabulary predicates:** `mom:camelCase` for properties, `mom:PascalCase` for classes.
Examples: `mom:freshnessStatus`, `mom:NetworkMembership`, `mom:SpaceType`

**Python — harness files:** `snake_case` throughout. Module names match their task name exactly.
- `tasks/nl_to_sparql.py` not `tasks/nlToSparql.py`
- `adapters/discord_adapter.py` not `adapters/DiscordAdapter.py`

**Python — functions:** `async def verb_noun()` — verb first, noun second.
- `run_select()`, `run_update()`, `complete()`, `handle_ask()`

**Config keys:** `snake_case` in `config.yaml`. Match the Python variable they configure.

**Discord slash commands:** lowercase, underscore-separated. `/ask_map` not `/askMap`.

**Docker service names:** hyphen-separated, prefixed with `mak-` for maps-of-making services.
- `mak-harness`, `mak-oxigraph` — avoids collision with side project services.

### Structure Patterns

**One task = one file in `tasks/`.** No shared task logic files. If two tasks share utility code, it goes in a `utils/` module, not in either task file.

**Tests:** `tests/` directory at harness root, mirroring the module structure.
- `tests/tasks/test_nl_to_sparql.py` mirrors `tasks/nl_to_sparql.py`

**Config access:** Always via a single `config.py` module that loads `config.yaml` once. Tasks import from `config`, never load YAML directly.

### Format Patterns

**Structured logs — always via structlog, always with session context:**
```python
log = structlog.get_logger()
log = log.bind(session_id=sid, adapter="discord")
log.info("query.received", query=q)
log.error("sparql.generation_failed", error=str(e), raw_output=llm_output)
```
Log event names: `noun.verb_past` — `query.received`, `sparql.generated`, `dispatch.sent`

**LLM task return contract:** All tasks return `str`. No task returns a dict or structured object. Formatting is the task's responsibility.

**SPARQL strings:** Always defined as module-level constants with `SCREAMING_SNAKE_CASE` names.
```python
PENDING_NOTIFICATIONS_QUERY = """
SELECT ?id ?type ?contact ...
"""
```
Never build SPARQL strings with f-strings containing user input — always parameterise via `VALUES` clauses.

**Error ontology gap triples format:**
```turtle
<urn:mak:gap/{uuid}> a mom:OntologyGap ;
  mom:rawQuery "{escaped query text}" ;
  mom:rawLLMOutput "{escaped output}" ;
  mom:timestamp "{ISO datetime}"^^xsd:dateTime .
```

### Process Patterns

**Heartbeat idempotency:** Every write operation checks current state before writing. No blind overwrites. Use `ASK` queries before `INSERT`.

**Magic link token lifecycle:** Generate UUID → store hash in Oxigraph with TTL → validate on click → mark consumed immediately → reject any second click. Tokens never stored in plaintext.

**All agents MUST:**
- Import config from `config.py`, never load `config.yaml` directly
- Use `structlog` for all log output, never `print()`
- Bind `session_id` at request entry before any log calls
- Use `run_select()` / `run_update()` from `sparql_client.py` — never call Oxigraph HTTP directly
- Never build SPARQL with f-strings containing user or LLM-generated content
- Return `str` from all task functions
- Defer Discord interactions before any `await` that touches LLM or SPARQL

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
maps_of_making/                          # 🟢 live · 🟡 dormant (planned) · 🔵 planned, not built
├── Makefile                             # 🟢 dev + VPS ops: seed-*, vps-*, canary, clear-etag
├── README.md
│
├── web/                                 # 🟢 static front-ends (one index.html per sub-app)
│   ├── maps-of-making.html              # main map SPA entry point
│   ├── app.js                           # map logic, filters, drawers, freshness axes (browser-computed)
│   ├── data/
│   │   ├── spaces.geojson               # the map's ONLY data source — materialized from Oxigraph
│   │   └── vow_workshops.json           # VOW seed reference
│   ├── admin/index.html                 # operator dashboard (Epic 4)
│   ├── genjson/                         # Bernard wizard / SpaceAPI composer (Epic 9) — index.html + genjson.js
│   ├── mothersands/                     # MOM-as-a-space broadcast (Epic 8) — index.html + mothersands.js
│   ├── canary/mother-sands.json         # served canary endpoint
│   └── test-fixtures/                   # SpaceAPI/JSON-LD validation fixtures
│
├── infra/                               # 🟢 the deployed stack
│   ├── docker-compose.yml               # base stack (name: maps_of_making; no :z)
│   ├── docker-compose.dev.yml           # Fedora/local overrides (:z SELinux, port maps)
│   ├── link_handler/                    # 🟢 THE RUNTIME ENGINE (FastAPI; ingestion + register + API)
│   │   ├── main.py                      # routes, /api/*, _rematerialize_geojson → spaces.geojson
│   │   ├── pipeline.py                  # fetch → transform → ingest (content-gated)
│   │   ├── pipeline_helpers.py
│   │   ├── snapshot_store.py            # SQLite raw payload + observed_at (Axis A)
│   │   ├── utils.py
│   │   ├── config.yaml                  # thresholds, cadence
│   │   ├── Dockerfile · requirements.txt · conftest.py · test_*.py
│   ├── nanobot-config/config.json       # 🟡 Nanobot agent config (Epic 6)
│   ├── nginx/                           # 🟢 app-layer nginx (.htpasswd, conf.d)
│   └── gateway-nginx/                   # 🟢 VPS gateway vhosts (06–09: map/admin/genjson/mothersands)
│
├── ontology/                            # 🟢 MOM vocabulary + IoP reference (working copies)
│   ├── mom.ttl                          # canonical: nicolasdb.github.io/mapsofmaking_ontology/ns#
│   ├── core.ttl                         # portable identity layer (ADR-016)
│   ├── crosswalk.csv · crosswalk.md     # living SpaceAPI↔mom bridge registry
│   └── iop/iop.ttl                      # IoP ontology snapshot
│
├── scripts/                             # 🟢 seeding, canary, ontology, transform lib
│   ├── spaceapi_extract/                # 🟢 TRANSFORM lib: core.py, mom.py, sparql.py (imported by pipeline + seeders)
│   ├── seed_spaceapi.py                 # Path A — live-endpoint seed from SpaceAPI directory
│   ├── seed_csv.py · seed_bundle.py     # Path B — CSV-pivot bundle import
│   ├── canary_ops.py · canary_scenarios.py · load_canary.py   # canary track
│   ├── load_ontology.sh                 # POST mom.ttl + iop.ttl to Oxigraph (⚠️ manual, not wired into Makefile)
│   └── validate_crosswalk.py            # crosswalk integrity DRC
│
├── data/                               # 🟢 runtime data (gitkept dirs)
│   ├── tasks/snapshot_store.db          # SQLite snapshot store (raw payload + observed_at)
│   ├── oxigraph/                        # triplestore volume
│   ├── seed-lists/                      # *.bundle.json + curation CSVs
│   └── archive/moms_seed.json           # frozen Epic-0 VOW seed (still served via vps-seed-bundle)
│
├── harness/                            # 🟡 Epic 6 NL bot baseline (Discord) — DORMANT
│   ├── main.py · llm_client.py · sparql_client.py   # Epic 1 integration spike
│   └── (Epic 6 target: Nanobot + tasks/ for nl_to_sparql, answer_format, notify_dispatch — ADR-009/010/013)
│
├── tests/                              # 🟢 repo-level pytest (live e2e + unit; tests/archive/ = retired)
│
├── docs/                               # 🟢 onboarding ABSTRACTION layer (teammate-facing)
│   ├── architecture/01–09 + main-pipeline.png   # the high-altitude companion to THIS file
│   └── *-runbook.md · host-your-space.md · gitlab_tuto/
│
└── _bmad-output/planning-artifacts/    # 🟢 BMAD-native DETAIL layer
    ├── prd.md · epics.md · architecture.md (this file) · ux-bernard-wizard-spec.md
    └── archive/                         # consumed handoffs + applied change-proposals
```

### Docker Compose — Full Service Topology

Current stack (`infra/docker-compose.yml`, name `maps_of_making`) — three live services + one Epic-6 placeholder:

```yaml
name: maps_of_making
services:
  maps-nginx:          # 🟢 serves web/ static front-ends, proxies /sparql → oxigraph
    image: nginx:alpine
    networks: [gateway, internal]      # gateway = shared hetzner-gateway net (external)
    volumes: [../web:…ro, ../web/data, ./nginx/conf.d:…ro, ./nginx/.htpasswd:…ro]

  oxigraph:            # 🟢 SPARQL 1.1 triplestore
    image: ghcr.io/oxigraph/oxigraph:latest
    command: serve --location /data --bind 0.0.0.0:7878
    volumes: [../data/oxigraph:/data]
    networks: [internal]

  mak-link-handler:    # 🟢 THE RUNTIME ENGINE — FastAPI ingestion + register + /api/*
    build: ./link_handler
    expose: ["8000"]
    volumes:
      - ../web/data:/app/web_data              # writes spaces.geojson
      - ../scripts/spaceapi_extract:…ro        # transform lib
      - ../data/tasks:/app/tasks               # snapshot_store.db persists here
    environment: [OXIGRAPH_ENDPOINT, LINK_SECRET, GEOJSON_OUTPUT, SCRIPTS_DIR]
    networks: [internal]

  # mak-agent:         # 🟡 Epic 6 — Nanobot NL bot, commented out. Built from
  #   image: hkuds/nanobot:local                # HKUDS/nanobot; run as a SEPARATE
  #   …                                          # compose project joining maps_of_making_internal

networks:
  gateway: { external: true }          # shared with hetzner-gateway (see infra/gateway-nginx/)
  internal: { driver: bridge }
```

**Two-layer nginx:** `infra/nginx/` is the app-layer vhost inside this stack; `infra/gateway-nginx/` (06–09) are the VPS gateway vhosts for map/admin/genjson/mothersands. **Nanobot (Epic 6)** is deliberately a *separate* compose project (the `hkuds/nanobot` image is built from source, not embedded here) — kept isolated; its CronService + tasks join `maps_of_making_internal` when Epic 6 lands.

---

### Architectural Boundaries

| Boundary | Owner | Transport |
|---|---|---|
| SPA ↔ Oxigraph | SPA reads via nginx `/sparql/query` | SPARQL SELECT → GeoJSON |
| Harness ↔ Oxigraph | Direct `http://oxigraph:7878` (Docker network) | httpx async |
| Harness ↔ OpenRouter | `AsyncOpenAI(base_url=...)` | HTTPS |
| Harness ↔ Discord | `discord.py` WebSocket | Bot gateway |
| Harness ↔ Telegram | `python-telegram-bot` polling | HTTPS |
| Admin ↔ Oxigraph | Via nginx (shared-password auth) | SPARQL SELECT |
| Magic link ↔ link_handler | HTTP GET signed token | nginx → mak-link-handler:8000/claim/ |
| Scheduler ↔ Oxigraph | Direct Docker network | httpx async SPARQL UPDATE |
| Admin ↔ Scheduler metrics | Internal Docker network | REST GET /metrics JSON |
| Heartbeat ↔ Space endpoints | Direct HTTP GET (conditional, ETag) | httpx |

### Requirements to Structure Mapping

| FR group | Location |
|---|---|
| FR1–11 Map display, filters, search | `web/app.js` (freshness axes computed here) |
| FR12–14b Space detail drawer | `web/app.js` + `/api/space/{id}/raw` (Zone-3 receipt) |
| FR15–18 Embed & sharing | `web/app.js` + nginx iframe headers |
| FR19–23 Coordinator registration | `infra/link_handler/main.py` `register_url()` (claim/dedup — see seeding doc 09) |
| FR24–27b Endpoint health / ingestion | `infra/link_handler/pipeline.py` (fetch+gate) + `scripts/spaceapi_extract/` (transform) + `snapshot_store.py` (raw + `observed_at`) |
| FR28–33b Operator dashboard | `web/admin/index.html` + `/api/*` status endpoints in `infra/link_handler/main.py` |
| FR34–36 SPARQL federated query | Oxigraph service + nginx routing |
| FR37–42, FR45–49 "Ask Bernard" bot | 🟢 Epic 6 — `harness/` (agent.py/agent_tools.py/router.py, adapters, `git_ops.py`, `isochrone.py`); deploy-key endpoint in `infra/link_handler/`; `mak-agent-bot` compose service. **ADR-017** — Nanobot confirmed unneeded (6.9), routing collapsed onto one tool-calling orchestrator (6.9–6.11) |
| FR43–44 Auth | nginx (shared-password basic auth header) |

## External Schema References

### SpaceAPI Compatibility

Maps of Making aims for interoperability with the SpaceAPI ecosystem so that a hackerspace can register the same endpoint with both MoM and SpaceAPI-compatible services (e.g. [mapall.space](https://mapall.space/)).

**Authoritative schema:** https://github.com/SpaceApi/schema
- Current stable: `14.json` / `15.json`
- Active draft: `16-draft.json` (most detailed — use as design reference)
- Migration guide: `MIGRATION.md` in same repo

**SpaceAPI v14 required fields** (minimum a space endpoint must contain):
`api_compatibility`, `space` (name), `logo`, `url`, `location` (lat+lon), `contact`

**SpaceAPI v16 required fields** (draft): same core set; `location` demoted to optional (≥1 property required if present); `linked_spaces` added for federation.

**Key v16 additions relevant to MoM:**
- `linked_spaces[]` — array of related spaces with `endpoint` or `website` URL → maps to consortium/network membership
- `membership_plans[]` — pricing/access tiers → useful for long-term membership discovery ("I want to join a space near me") and newcomer onboarding queries; residency matchmaking is separate (EU-grant-financed programs, not membership subscriptions) and lives in `mom:extended`
- `location.areas[]` — named zones with `square_meters` → equipment/workshop areas
- `state.lastchange` — Unix timestamp of last open/closed change → freshness signal (Epic 7)
- `spacefed.spacenet` / `spacefed.spacesaml` — federation auth → long-term interop

**SpaceAPI has no native tags/specialties/equipment fields.** These are MoM extensions and must live in `mom:extended` subset. When publishing alongside SpaceAPI fields, extra JSON-LD properties are allowed by SpaceAPI validators — no breakage.

**MoM schema subset model** (enforced via Pydantic in `link_handler/main.py` from Story 2.7):

| Subset | Fields | Gate behaviour | Unlocks |
|---|---|---|---|
| `mom:required` | `space`, `url`, `location.lat/lon` | Hard reject if missing | Pin on map |
| `mom:card` | `+location.address`, `contact.website`, `state.open`, `schema:openingHours` | Ingest with warning if missing | Full detail card |
| `spaceapi:compatible` | Full SpaceAPI v14+ field set | Ingest; surface compatibility score | Interop with mapall.space etc. |
| `mom:extended` | `mom:specialties`, `mom:equipment`, `mom:consortium`, `mom:residency`, `mom:membershipPlans` | Ingest; unlock advanced features | Consortium queries, residency matchmaking, membership discovery |
| `mom:live` | `state.open` + presence webhook TTL | Epic 7 — schema slot reserved | "Open now" badge |

**Progressive unlock UX (Story 2.7):** After ingestion, the validation response tells the coordinator which subset they've reached and what completing the next subset unlocks — fog-of-war incentive to enrich their endpoint over time.

**`mom:extended` field definitions** (agreed 2026-04-27 — implemented from Epic 4+):

```json
"legal": { "type": "non-profit", "country": "BE", "founded": 2011 },
"outward": {
  "grant_experience": ["Erasmus+ KA210", "NLnet NGI"],
  "partnership_scale": ["local", "national", "european"],
  "working_languages": ["fr", "en", "nl"],
  "thematic_areas": ["education", "neurodiversity", "open-hardware"],
  "seeking_partners": true,
  "grant_programme": "Erasmus+ KA220",
  "seeking_description": "digital fabrication + youth, 2027 call"
},
"inward": {
  "residency_open": true,
  "residency_duration_weeks": { "min": 2, "max": 8 },
  "residency_support": ["workspace", "materials"],
  "residency_deadline": "2026-09-01",
  "residency_profile": "Makers with textile or biofab background"
}
```

Note: `seeking_partners_for` is split into structured `grant_programme` + free `seeking_description` for queryability. `residency` ≠ `membership_plans` (SpaceAPI): residency is project-based/EU-grant-funded; membership is local subscription/newcomer discovery. The maker schema (consent-gated individual layer) is future scope — see memory file for full field definitions.

**Conceptual model:** Cell (maker) → Organ (space) → Organism (network) → Ecosystem (network of networks). Space schema = organ's public signal. Maker schema = cell's consented output. Nobody owns the cell.

**Success metric:** A hackerspace registers one JSON endpoint and appears correctly on Maps of Making AND mapall.space AND any future SpaceAPI-compatible service. One endpoint, multiple maps, multiple publics.

---

### Data Flow

```
Space publishes SpaceAPI JSON at their URL
  ↓ (~10-min cron, conditional GET — ETag/Last-Modified)
infra/link_handler/pipeline.py — STAGE 1: FETCH
  → raw payload + ETag/Last-Modified written to SQLite snapshot_store.db
  → mint observed_at (Axis A — endpoint health, SQLite ONLY)
  → content-gate:
      304 or byte-identical 200 → advance observed_at, log "no_change", STOP
      changed → proceed to Stage 2

scripts/spaceapi_extract/ (core, mom) — STAGE 2: TRANSFORM  (ADR-015)
  → SpaceAPI JSON → MOM triples (ontology applied; mom:required hard-gate, mom:card warn)

infra/link_handler/pipeline.py — STAGE 3: INGEST
  → idempotent DELETE WHERE + INSERT DATA → <urn:mak:space/{id}> (current triples)
  → set mom:updatedAt = now (Axis B); mom:lastOpenChange from source claim (Axis C)
  → log decision: "ingested" | "no_change" | "error"

MATERIALIZE  (main.py: _rematerialize_geojson)
  → SPARQL SELECT over claimed spaces → _binding_to_feature
  → write web/data/spaces.geojson (3 tokens per feature + file-level `thresholds` header)
  → this GeoJSON is the map's ONLY data source

Registration / claim
  ↓ (admin UI or POST /api/register)
infra/link_handler/main.py — register_url()
  → endpointUrl dedup → name-match claim-in-place → else mint new URI (seeding doc 09)
  → write mom:endpointUrl; heartbeat begins minting tokens on next cycle

Public map (network coordinator / maker)
  ↓
web/app.js
  → fetch spaces.geojson
  → compute all three axes + marker IN THE BROWSER from tokens + thresholds header
  → health toggle overlays aging/zombie/dead — no auth, no admin access
  → space card: GET /api/space/{id}/raw → SQLite raw payload (Zone-3 trust receipt)

"Ask Bernard" bot  🟢 Epic 6 (live — harness/ agent.py/agent_tools.py/router.py; ADR-017 supersession note)
  ↓
channel adapter → Message → intent classifier (write|query|nl_discovery|unknown)
  ├── write                       → permission check → git_ops.patch_json → git commit (SSH deploy key) → heartbeat re-ingests
  └── query|nl_discovery|unknown  → agent.run() tool-calling loop (Gemma 4, single orchestrator, post-6.11)
        Tier 0: FAQ/semantic cache hit → matched entry injected as RAG context, model call still runs
        Tier 1: Gemma picks a tool — query_map (templates), query_sparql (IoP-guarded NL→SPARQL,
                folded from nl_to_sparql.py), read_space, log_gap, propose_write
                (isochrone: ORS polygon → shapely point-in-polygon filter, inside query_map)
        Tier 2: Sonnet retry, same tools, only on validation failure/empty/complexity heuristic
  → Bernard-voice answer
```
