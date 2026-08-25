---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'edit-2026-04-29', 'step-e-01-discovery', 'step-e-02-review', 'step-e-03-edit']
lastEdited: '2026-06-16'
editSummary: '2026-06-16 sprint change proposal (sprint-change-proposal-2026-06-16.md, mom_handoff_2026-06-16.md): Epic 6 restructured to "Ask Bernard" — one channel-agnostic bot + intent router (write|query|nl_discovery|unknown), one Bernard voice; harness/ baseline (Nanobot deferred to 6.4); new stories 6.0-6.6 (infra/adapters/router → deploy-key SSH write → write skillset+permissions → read/query+isochrone → NL→SPARQL → voice pass → channel adapters). Epic 9 stories 9.6/9.7/9.9/9.10 superseded (absorbed by Epic 6.2 write skillset). New FRs FR45-FR49 + NFR-S7 added to PRD; new ADR-017 in architecture. Prior: 2026-05-29 sprint change proposal (sprint-change-proposal-2026-05-29.md): added Cleanup Story C.X (schema namespace pass: ext_mom→ext_canary, mom: horizontal fields, SDG migration); added Epic 9 — Bernard''s Workshop (assisted SpaceAPI JSON composer at genjson.mapsofmaking.org, Stories 9.1–9.11 full BDD-spec, M1/M2/M3 milestones); renamed old Epic 9 (Multi-Network Schema) to Epic 10; updated sequencing notes to reflect C.X→Epic 9→Epic 4 re-review track. Prior: 2026-05-16 reconciliation (Story 3.3 canary, 3.2c, 3.4, 3.5, Epic 8 stub).'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - web/maps-of-making.html
---

# maps_of_making - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for maps_of_making, decomposing the requirements from the PRD, UX (phase-1 prototype) and Architecture (14 ADRs) into implementable stories for Phase 2 — the Federated PoC.

Phase 1 (map SPA, deployed at mapofmaking.debarquin.eu) is shipped. The epic/story work below targets Phase 2: URL ingestion pipeline, Oxigraph SPARQL triplestore, ⚪→🔵 pin confirmation, admin health dashboard, and NL bot via Discord/Telegram. Phase-1 UI elements (filters, search, add-URL, embed, tweaks, bot teaser) are treated as **hypotheses** to validate, adjust, or prune from pilot telemetry — not as locked scope.

## Requirements Inventory

### Functional Requirements

**Map Display & Navigation (Phase 1 — shipped, reference only)**
- FR1: Fullscreen MapLibre GL JS map with Protomaps PMTiles vector tiles
- FR2: Pan, zoom, cluster expansion with pin stability at all zoom levels
- FR3: Pin states rendered visually: ⚪ seeded / 🔵 confirmed / dashed stale / 🔴 broken
- FR4: Default view centered on FR/DE pilot area with graceful fallback tiles on network failure

**Filtering & Search (Phase 1 — shipped, pilot-validation candidate)**
- FR5: Filter drawer with facets: machines/capabilities, services, open-now hours
- FR6: Text search across space name, city, tags
- FR7: Filters and search update map pins live (no reload)
- FR8: Shareable URL state encoding active filters + map bounds
- FR9: Filter state persists across drawer close/reopen in session
- FR10: Empty-state messaging when no results match
- FR11: Clear-all-filters control

**Space Detail (Phase 1 shipped + Phase 2 extension)**
- FR12: Click pin → detail drawer with space info, hours, machines, contact, links
- FR13: Detail drawer shows data provenance: endpoint URL + last-ingested timestamp
- FR14: Copy-to-clipboard for contact/address
- FR14b: Ingestion freshness visible: `observed_at` (last fetch) + `updated_at` (last content change) tokens per space. *(Epic 3.5: no per-version dated-snapshot archive; life-event history deferred to `public_ledger`.)*

**Embed & Sharing (Phase 1 shipped + Phase 2 polish)**
- FR15: Iframe embed snippet generator for any space or filter state
- FR16: Web component `<maps-of-making>` with configurable props (center, zoom, filter)
- FR17: Embeds render with attribution link back to full map (reciprocal visibility)
- FR18: Share button produces deep-link URL for current map state

**Coordinator Registration (Phase 2)**
- FR19: Coordinators register a space by submitting one JSON endpoint URL (no account)
- FR20: Registration form validates URL reachability + JSON schema compliance
- FR21: On successful registration, pin flips ⚪ seeded → 🔵 confirmed
- FR22: Coordinators receive a reciprocal embed snippet to place on their own website
- FR23: No edit UI — coordinators update their data by editing their JSON at the URL

**Endpoint Health & Ingestion (Phase 2)**
- FR24: Periodic fetch of all registered endpoints (~10-min cadence, configurable). Raw payload written to SQLite snapshot store (`observed_at`); Oxigraph triples rewritten (DROP/INSERT) only on content change.
- FR25: Three orthogonal freshness axes computed in the browser from tokens + `thresholds` header — endpoint reachability (Axis A: `observed_at` age), lifecycle freshness (Axis B: `updated_at` age → confirmed/aging/zombie/dead), operational liveness (Axis C: `open_now`). Terminal states: `closed` (declared) and `dead` (auto-inferred). *(Three-token contract — Epic 3.5 done.)*
- FR25b: Closure logic: JSON self-reports closed OR N consecutive fetch failures → PII removed, space marked closed-at-date, pin retained for historical record
- FR26: Diff detection between snapshots flags meaningful changes
- FR27: Ingestion failures logged with reason (timeout, 4xx, 5xx, schema invalid)
- FR27b: Raw payload retained verbatim in SQLite snapshot store (latest per space) as transparency receipt. Oxigraph triples rewritten only on real content change. *(Per-event immutable history = future `public_ledger`, not a per-fetch archive.)*

**Admin Dashboard (Phase 2)**
- FR28: Admin dashboard on separate subdomain showing all endpoints with current state
- FR29: Dashboard filters: all / confirmed / stale / broken / closed
- FR30: Per-endpoint detail: fetch history, last diff, error log
- FR31: Manual re-fetch trigger per endpoint
- FR32: Oxigraph sync status per endpoint
- FR33: Export endpoint registry (CSV/JSON)
- FR33b: Admin audit log: all admin actions timestamped and attributable

**Federated Query Layer (Phase 2)**
- FR34: Oxigraph SPARQL 1.1 endpoint exposes federated graph of all ingested spaces
- FR35: Queries validated against Internet of Production (IoP) ontology as guardrail
- FR35b: Lenient validation: non-compliant data ingested with warnings logged as ontology enrichment signals
- FR36: Public SPARQL endpoint (read-only) for third-party integrations

**Natural Language Bot (Phase 2)**
- FR37: "Ask the map" bot accepts natural language questions
- FR38: Nanobot agent translates NL → SPARQL using IoP ontology as prompt context (OpenRouter via LiteLLMProvider, model-agnostic)
- FR39: Bot returns results with source space links + query transparency (show SPARQL)
- FR40: Bot acknowledges gracefully when query can't be answered; offers clarification
- FR41: Failed/ambiguous queries logged as ontology gap signals
- FR42: Nanobot deployed to Discord (built-in), Telegram (built-in), then Mattermost (custom adapter at pilot)

**Auth (Phase 2)**
- FR43: Admin subdomain gated by simple shared password (PoC-grade)
- FR44: Public map and coordinator registration require no authentication

### NonFunctional Requirements

**Performance**
- NFR-P1: Map tile first paint <2s p50, <4s p95; interactive <4s p50 (measured on admin dashboard)
- NFR-P2: Filter/search updates <200ms (client-side)
- NFR-P3: Space detail drawer opens <300ms from pin click
- NFR-P4: Bot NL→SPARQL→response latency TBD from telemetry
- NFR-P5: No hardcoded SLAs until PoC baseline; all targets live on admin dashboard

**Reliability & Ingestion**
- NFR-R1: Endpoint fetch uses ETag / Last-Modified conditional requests
- NFR-R2: Fetch timeout 60s per endpoint with incremental backoff
- NFR-R3: Fetch cadence, failure thresholds, retention policy config-driven
- NFR-R4: Per-endpoint fetch latency logged (min/avg/max ms) on admin dashboard
- NFR-R5: Map remains functional when ≤50% endpoints unreachable — degrade-to-stale, never empty
- NFR-R6: Fetch worker failures never take down public map (pipeline isolation)
- NFR-R7: (scale note — future) >500 endpoints: per-domain rate limiting, jittered schedule, robots.txt, content-addressed dedup

**Security**
- NFR-S1: Admin gated by single shared password (env secret, PoC-grade); pilot adds per-user + MFA
- NFR-S2: Public map no auth; public SPARQL read-only + basic rate limiting
- NFR-S3: Coordinator URLs validated (https only), fetched server-side
- NFR-S4: Admin audit log immutable append-only
- NFR-S5: Bot SPARQL generation passes IoP ontology validation gate before execution
- NFR-S6: Admin dashboard exposes operational metrics only — no raw payloads, no coordinator identifiers beyond public map

**Data Model — Space-not-People**
- NFR-D1: JSON endpoints describe spaces only. Space-level contact only (generic email, webform, website). No personal names/emails/phones.
- NFR-D2: Ingestion validator rejects records with person-identifiable fields → quarantine queue + admin alert
- NFR-D3: SPARQL validation gate rejects triples resolving to schema:Person
- NFR-D4: Skills/capabilities modeled as properties of the space, never attached to named individuals

**Compliance (GDPR light)**
- NFR-C1: Closure removes current contact fields; historical record preserved
- NFR-C2: Data model excludes personal data by design — reduced GDPR burden
- NFR-C3: Anonymized snapshots candidates for IPFS/IPLD civic archive (Phase 3)

**Accessibility**
- NFR-A1: WCAG 2.1 AA for public map + coordinator registration; axe-core in CI
- NFR-A2: Keyboard navigation for all drawers, filters, pin selection, bot input
- NFR-A3: Screen reader announces pin state changes, filter counts, drawer content
- NFR-A4: Color never sole indicator of pin state — shape/pattern accompanies ⚪🔵 dashed 🔴
- NFR-A5: Non-map fallback: accessible list view of filtered results

**Integration**
- NFR-I1: PMTiles served from own CDN or self-hosted
- NFR-I2: Oxigraph exposes standard SPARQL 1.1 HTTP protocol
- NFR-I3: Bot adapters share a protocol-agnostic core
- NFR-I4: Embed web component works in any modern browser without framework dep
- NFR-I5: JSON endpoint schema extends SpaceAPI where compatible

**LLM / Bot Operations**
- NFR-L1: Prompt cache hit-rate tracked on admin dashboard
- NFR-L2: Max tokens capped; monthly cost ceiling enforced at infra level with alerting
- NFR-L3: Retry budget defined (max attempts, jitter, plain-language fallback on LLM unavailable)
- NFR-L4: Bot response latency SLO tracked separately from map tile SLO

**Observability (cross-cutting)**
- NFR-O1: Admin dashboard exposes: fetch latency, success rate, diff-rate, Oxigraph sync lag, bot latency + success rate, map load perf, quarantine depth
- NFR-O2: All "TBD" thresholds set in config after real telemetry — no premature optimization

### Additional Requirements

*(From Architecture ADRs — technical work items that inform stories but are not FRs/NFRs)*

**Starter / Greenfield structure (ADR, no conventional template):**
- AR-ST1: Custom Python harness built from scratch as a standalone 3-file spike (not inside a Nanobot container). First implementation story is a spike: Discord bot `/ping` that chains OpenRouter + Oxigraph health check, proving dependency surface. **[Updated Epic 1 retro 2026-04-25: `hkuds/nanobot` image is not publicly available; must be built from source. Nanobot runs as a SEPARATE Docker Compose project, not embedded in maps_of_making. Spike uses custom harness. Nanobot integration begins at Epic 6.]**

**Infrastructure & Deployment (ADR-001, ADR-011, ADR-013, ADR-014):**
- AR-INF1: Docker Compose stack named `maps_of_making` (explicit) with services: `oxigraph`, `mak-link-handler` (FastAPI), nginx reverse proxy. Internal-only networking via `expose`, not `ports`. **[Updated Epic 1 retro 2026-04-25: `mak-agent` (Nanobot) is commented out of this compose file; Nanobot runs as a SEPARATE compose project joining the internal network via `external: true`. Epic 6 activates it.]**
- AR-INF2: nginx routes: `/sparql/query` → Oxigraph public read; `/sparql/update` → deny (internal only); `/claim/*` → mak-link-handler; admin subdomain shared-password basic auth.
- AR-INF3: Host cron daily N-Quads dump of Oxigraph → `/var/backups/oxigraph/` → rsync off-host, 7-day retention. IPFS+IPLD production direction deferred to pilot.
- AR-INF4: Secrets via `.env` on VPS (gitignored), `.env.example` committed with placeholders.
- AR-INF5: Manual deploy for PoC (`git pull && docker compose up -d --build`); GitHub Actions deferred to pilot.

**Data Architecture (ADR-006, ADR-007, core decisions):**
- AR-DATA1: Oxigraph named graph topology — `<urn:mak:space/{id}>` (current per-space), `<urn:mak:canary/{id}>` (canary per-space), `<urn:mak:presence>` (webhook open-now, reserved), `<urn:mak:notifications>` (queue), `<urn:mak:ontology/iop>`, `<urn:mak:ontology/mom>`. **Epic 3.5 supersedes (2026-05-28):** `<urn:mak:status>` materialized-freshness graph was never built; freshness now lives in `snapshot_store.db` (Axis A) + per-space graphs (`mom:updatedAt` Axis B, `mom:lastOpenChange` Axis C); `<urn:mak:space/{id}/{date}>` per-date snapshot graphs were replaced by SQLite snapshot rows.
- AR-DATA2: Freshness materialization — **Epic 3.5 supersedes (2026-05-28):** storage holds raw tokens only (three-token contract); derived state (`endpointHealth`, `operationalState`, marker colour, aging/zombie/dead bucket) is computed in the browser from a `thresholds` block in the GeoJSON header. Do not reintroduce stored derived columns. Lifecycle 30d/90d/180d thresholds still configurable, now in `config.yaml.thresholds`. **LOD note:** state values are `xsd:string` literals (`"confirmed"`, `"seeded"`, etc.) — deliberate 4-star LOD choice. Earlier drafts used `mak:confirmed` etc. as RDF IRIs (5-star upgrade path, deferred). Do not reintroduce IRI-style values without first defining them as `skos:Concept` entries in `mom.ttl`.
- AR-DATA3: Presence graph reserved now for "open-now" webhook; handler implemented late Phase 2.
- AR-DATA4: MOM ontology align-and-extend — Schema.org base + IoP `skos:closeMatch` + `mom:` extensions. **Canonical namespace `https://nicolasdb.github.io/mapsofmaking_ontology/ns#` (prefix `mom:`); `mom.ttl` authoritative.** The earlier `w3id.org/maps-of-making/` IRI is not used anywhere. Layered schema model: ADR-016.
- AR-DATA5: IoP ontology loaded at harness startup into dedicated named graph; ~15–20% subset extracted via CONSTRUCT, cached in memory, injected into every NL→SPARQL prompt. `RELOAD_ONTOLOGY=1` forces reload.

**Agent Framework & Harness (ADR-008, ADR-009, ADR-013):**
- AR-AGT1: Nanobot as agent framework — LiteLLM provider over OpenRouter; CronService + HEARTBEAT.md for scheduling; Discord + Telegram adapters built-in. **[Updated Epic 1 retro 2026-04-25: image NOT `FROM hkuds/nanobot:latest` (not public). Must clone github.com/HKUDS/nanobot and build locally. Runs as separate compose project. Not needed until Epic 6.]**
- AR-AGT2: Custom `tasks/` modules invoked by Nanobot; one task = one file; all return `str`. **Note:** the *heartbeat/ingestion* is already built in the `infra/link_handler` runtime (Epic 3.5) — it is NOT a Nanobot task. Epic 6 tasks are the LLM ones: `nl_to_sparql`, `answer_format`; magic-link/`notify_dispatch` belong to Epic 4b.
- AR-AGT3: Multi-model assignments via config: Haiku for heartbeat, Sonnet (temp=0) for NL→SPARQL, Minimax for answer formatting.
- AR-AGT4: Discord defer pattern mandatory (`interaction.response.defer(thinking=True)`) on any LLM-involved command — bot timeout is 3s, LLM calls exceed this.
- AR-AGT5: Protocol-agnostic ChannelAdapter protocol — Discord first, Telegram built-in, Mattermost as custom adapter post-pilot.

**Magic Link / Notification (ADR-005, ADR-010, ADR-011):**
- AR-MLNK1: Dedicated FastAPI `mak-link-handler` container binds port 8000 internal, proxied at `/claim/*`. Discord bots cannot bind HTTP — this is separate by necessity.
- AR-MLNK2: Tokens are `base64url(HMAC-SHA256(uuid + expiry + space_id, LINK_SECRET))`. Stored as hash only, single-use, 72h TTL.
- AR-MLNK3: Notification dispatch is non-LLM for PoC — queue in Oxigraph (`<urn:mak:notifications>`), worker reads, fills template, sends, writes `mak:dispatched`. Retry 3× with backoff, escalate to network admins on failure.

**Operational Metrics (ADR-012):**
- AR-METR1: Operational data lives in SQLite, **not** Oxigraph (breaks circular dependency when Oxigraph is down). **Epic 3.5 supersedes (2026-05-28):** realised as `data/tasks/snapshot_store.db` (raw payload + `observed_at`) owned by the `link_handler` runtime, surfaced via `/api/*`. The `metrics.db` / `mak-scheduler` / `/metrics` endpoint and `llm_cost_log` table were never built — a dedicated metrics surface is Epic 4 (operator dashboard) / Epic 6 (LLM cost) scope.

**Conventions / Code Standards:**
- AR-CONV1: Naming — `urn:mak:{type}/{id}` for named graphs; `mom:camelCase` properties / `mom:PascalCase` classes; `snake_case` Python; `verb_noun()` async functions; `mak-` prefix on Docker services.
- AR-CONV2: structlog from day one with `session_id` bound at request entry. Event names `noun.verb_past`.
- AR-CONV3: SPARQL strings as `SCREAMING_SNAKE_CASE` module constants; never f-strings with user/LLM input; use `VALUES` clauses. Use `run_select()` / `run_update()` helpers only.
- AR-CONV4: Heartbeat idempotency — `ASK` before `INSERT`, never blind overwrite.
- AR-CONV5: Single `config.py` module; tasks import from it, never load `config.yaml` directly.

**Seed / Bootstrap:**
- AR-SEED1: **Build a new `moms_seed.json` from real data sources** — current phase-1 synthetic seed is demo-only. Real seed must be assembled from: (a) existing `vow_workshops.json` scrape (VOW / offene-werkstaetten.org — name, address, categories, profile URL, website) and (b) an equivalent RFF (France) source to be identified/scraped. Raw scrape → normalize to MOM ontology fields → geocode addresses → dedup → emit canonical `moms_seed.json` consumed by `scripts/seed_import.py`.
- AR-SEED2: `scripts/seed_import.py` loads canonical `moms_seed.json` → JSON-LD → Oxigraph as ⚪ seeded spaces. Retired at pilot once live endpoints dominate.
- AR-SEED3: `scripts/load_ontology.sh` POSTs `mom.ttl` + `iop.ttl` to their named graphs (idempotent — ASK first).
- AR-SEED4: Category/tag vocabulary from raw scrapes (e.g. German `Holz`, `Metall`, `3D-Druck`) mapped to canonical MOM/Schema.org/IoP predicates via a translation table — preserves provenance but normalizes the filter facets across FR+DE.

### UX Design Requirements

*(Extracted from phase-1 prototype `web/maps-of-making.html` + explicit principles confirmed with user. Phase-1 UI elements are **hypotheses under fog-of-war** — each UX-DR includes whether it is "validate/keep", "extend", "prune candidate", or "new for Phase 2".)*

**Pin visual grammar & legend (ADR-004 — extend)**
- UX-DR1: Default map view shows only four pin states: ⚪ seeded, 🔵 confirmed, 🟢 open-now (badge on blue), 🔴 error. Aging/zombie/dead pins are hidden from default view — surfaced only via admin health toggle.
- UX-DR2: Legend card (bottom-left) stays compact and always-visible, enumerating the four public pin states with both color and shape/pattern (NFR-A4). Aging/zombie/dead states documented only in admin view legend.
- UX-DR3: Space detail drawer carries an amber "quiet banner" — "Last confirmed 8 months ago. Details may be outdated." — visible even without the admin toggle. Provenance (endpoint URL + last-ingested timestamp) always displayed (FR13).

**Progressive disclosure & cognitive load (principle — validate phase-1 drawers)**
- UX-DR4: Topbar buttons (Filters, Search, Preset & embed, Add your URL, Tweaks) are phase-1 hypotheses. Each requires a pilot-validation gate before Phase 2 lock-in. Document default state = all drawers closed; map is the surface.
- UX-DR5: Drawers (left Filters, right Detail, bottom Preset, right Add-URL, right Bot) follow consistent open/close animation contract (260ms cubic-bezier, transform-based); reduced-motion media query disables transitions (already implemented).
- UX-DR6: Tweaks panel (map style dim/dark, pin density, pulse on/off) is explicitly labeled "design only" — treat as developer/designer affordance, not end-user feature. Prune candidate for production; keep for pilot iteration.
- UX-DR7: "Ask the map" bot FAB is a phase-1 teaser with `soon` label. Phase 2 removes the teaser and wires real behavior; label transition must be explicit (no silent activation) so users can distinguish placeholder from real.

**Graceful failure states (core principle — new for Phase 2)**
- UX-DR8: Coordinator "Add your URL" form produces explicit error states for: invalid URL syntax, non-https scheme, timeout, 4xx/5xx response, schema violation, PII detected, duplicate registration. Each state renders in plain language with actionable next step. No raw stack traces.
- UX-DR9: Stale endpoint detail view (dashed pin) shows: last successful fetch timestamp, error type from last attempt, one-click "try re-fetch" for coordinator (reuses magic link flow), fallback "this space may have moved — contact network admin" CTA.
- UX-DR10: Broken endpoint detail view (🔴) shows the error category (404, CORS, timeout, schema invalid) in plain language + last known good snapshot as "historical record" label, clearly distinguishing historical vs live data.
- UX-DR11: Empty-state messaging across filters, search, bot results — never show "0 results" alone; always pair with diagnostic suggestion ("Try widening your filter" / "No confirmed spaces match — try including seeded pins").
- UX-DR12: Bot "I couldn't answer" response includes: plain-language acknowledgment, suggestion to rephrase OR browse the map directly, no stack traces, logs ontology gap triple internally (FR41, NFR-L3).
- UX-DR13: Map tile load failure falls back to paper-overlay background with pins still rendered (NFR-R5 degrade-to-stale visible; graceful degradation visible to the user, not a blank screen).

**Coordinator registration flow (new for Phase 2)**
- UX-DR14: `Add your URL` drawer transitions from phase-1 "simulated" state to real validation. Progression: URL entry → "Fetch & validate" → live feedback on fetch (reachable ✓, schema valid ✓, geocoded ✓, PII check ✓, pin preview) → submit → confirmation screen showing ⚪→🔵 transition + reciprocal embed snippet for their site (FR22).
- UX-DR15: Try-a-sample button (already in phase-1 HTML) must work against a real seed endpoint to demo the happy path before coordinator commits their own URL.
- UX-DR16: Magic link YES/NO confirmation screens (served by `mak-link-handler`) follow the map's zine aesthetic and match principles: YES = single confirmation + "thanks, your pin is live"; NO = graceful closure confirmation + "we'll mark this space closed on {date}, PII will be removed". No forms, no logins.

**Admin dashboard / Network health view (extend — priority per architecture)**
- UX-DR17: Fleet health overview as default admin landing — single glance shows counts by status (confirmed / seeded / stale / broken / closed) with proportional visual weight, plus sparkline of ingestion events over last 7 days.
- UX-DR18: Per-endpoint drill-down card: fetch history timeline, last diff summary, error log (structured, not raw), manual "re-fetch now" button (FR31), "send nudge" CTA to dispatch magic link reminder, Oxigraph sync status (FR32).
- UX-DR19: Admin toggle "Health map overlay" reveals aging/zombie/dead pins on the map itself with pattern differentiation (dashed, ghost, skull badge or similar — NFR-A4 no-color-only). Second SPARQL query, no page reload (ADR-006).
- UX-DR20: Export controls (CSV / JSON) for endpoint registry (FR33). Output includes public fields only — no audit log leakage (NFR-S6).
- UX-DR21: Admin audit log visible as reverse-chronological timeline: who, what action, when, on which space (FR33b).

**Accessibility (NFR-A1–A5 — validate & extend)**
- UX-DR22: All drawers, filter chips, pin interactions keyboard-reachable with visible focus indicator (`:focus-visible 2.5px accent outline` already in phase-1 CSS). Regression-test in Phase 2.
- UX-DR23: Screen reader announcements for: pin state changes (⚪→🔵, 🔵→stale), filter result count updates (already `aria-live="polite"` on `#results-count`), drawer open/close, bot response arrival.
- UX-DR24: Non-map accessible list view (NFR-A5) — reachable from a link/button in filters drawer, renders filtered results as a semantic `<ul>` with same content as pins. New for Phase 2.
- UX-DR25: axe-core audit wired into CI (NFR-A1). First story must establish CI hook.

**Embed & reciprocal visibility (extend)**
- UX-DR26: Embed mode (`body.embed-mode`) already hides chrome per phase-1 CSS. Phase 2 adds: visible "Last confirmed {date}" caption + attribution link back to full map (FR17). Stale-date prominently displayed so a stale embed visibly degrades the coordinator's own site (reciprocal incentive).
- UX-DR27: Web component `<maps-of-making>` with configurable props (center, zoom, filter) — same visual contract as iframe embed (FR16).

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 1 | MapLibre + PMTiles — shipped; Epic 1 wires to Oxigraph GeoJSON |
| FR2 | Epic 5 | Pan/zoom/cluster stability — polish pass |
| FR3 | Epic 1 | Pin states rendered from Oxigraph materialized status |
| FR4 | Epic 1 | Default view + graceful tile fallback |
| FR5 | Epic 5 | Filter drawer facets validated against real data |
| FR6 | Epic 5 | Text search against real space names/cities/tags |
| FR7 | Epic 5 | Live pin update on filter/search |
| FR8 | Epic 5 | Shareable URL state encoding |
| FR9 | Epic 5 | Session-persistent filter state |
| FR10 | Epic 5 | Empty-state messaging |
| FR11 | Epic 5 | Clear-all-filters control |
| FR12 | Epic 5 | Pin click → detail drawer (real federated data) |
| FR13 | Epic 2 | Detail drawer: provenance URL + last-ingested timestamp |
| FR14 | Epic 5 | Copy-to-clipboard for contact/address |
| FR14b | Epic 2 | Freshness tokens (`observed_at` / `updated_at`) surfaced in detail drawer |
| FR15 | Epic 5 | Iframe embed snippet generator |
| FR16 | Epic 5 | Web component `<maps-of-making>` |
| FR17 | Epic 5 | Embeds carry attribution + last-confirmed caption |
| FR18 | Epic 5 | Share button deep-link URL |
| FR19 | Epic 2 | Coordinator submits JSON endpoint URL (no account) |
| FR20 | Epic 2 | URL reachability + schema compliance validation |
| FR21 | Epic 2 | Pin flip ⚪ → 🔵 on successful registration |
| FR22 | Epic 2 | Reciprocal embed snippet returned to coordinator |
| FR23 | Epic 2 | No edit UI — coordinator updates JSON at source URL |
| FR24 | Epic 3 | Periodic endpoint fetch (~10min cadence, configurable); SQLite receipt + Oxigraph on diff |
| FR25 | Epic 3 | Three-axis freshness computed in browser (observed_at / updated_at / open_now) — Epic 3.5 done |
| FR25b | Epic 3 | Closure logic: PII removed, space marked closed-at-date |
| FR26 | Epic 2 | Diff detection on first ingest (seed→claim transition) |
| FR27 | Epic 3 | Ingestion failure logging (timeout / 4xx / 5xx / schema) |
| FR27b | Epic 2 | Raw payload in SQLite (latest per space); Oxigraph rewritten on diff only |
| FR28 | Epic 4 | Admin dashboard: all endpoints + current state |
| FR29 | Epic 4 | Dashboard filters: confirmed / stale / broken / closed |
| FR30 | Epic 4 | Per-endpoint: fetch history, last diff, error log |
| FR31 | Epic 4 | Manual re-fetch trigger |
| FR32 | Epic 4 | Oxigraph sync status per endpoint |
| FR33 | Epic 4 | Export endpoint registry (CSV/JSON) |
| FR33b | Epic 4 | Admin audit log (timestamped, attributable) |
| FR34 | Epic 1 | Oxigraph SPARQL 1.1 endpoint (federated graph) |
| FR35 | Epic 6 | Queries validated against IoP ontology |
| FR35b | Epic 6 | Lenient validation: non-compliant data → warning + log |
| FR36 | Epic 1 | Public SPARQL endpoint (read-only, nginx-gated) |
| FR37 | Epic 6.0 | "Ask Bernard" — one channel-agnostic bot + intent router (write\|query\|nl_discovery\|unknown) |
| FR38 | Epic 6.4→6.11 | NL → SPARQL via OpenRouter, IoP ontology context. **Mechanism unchanged, dispatch superseded 2026-07-02: now a tool (`query_sparql`) inside `agent.py`'s loop, Sonnet is Tier-2 escalation not default model — see Epic 6 supersession note.** |
| FR39 | Epic 6.4 | Bot returns results with source links + SPARQL transparency |
| FR40 | Epic 6.5 | Bot graceful failure → clarification offer (Bernard voice rules) |
| FR41 | Epic 6.4→6.11 | Failed queries logged as gap signals. **Store superseded 2026-07-02: RDF `<urn:mak:gaps>` graph retired into the existing `capability_gaps` SQLite table (Story 6.9), single mechanism.** |
| FR42 | Epic 6.6 | Matrix-first write; read/discovery on Discord/Telegram/Mattermost |
| FR43 | Epic 4 | Admin subdomain shared-password auth (PoC-grade) |
| FR44 | Epic 1 | Public map + coordinator registration: no auth |
| FR45 | Epic 6.1/6.2 | Bot write path: deploy-key JSON patch → git commit → heartbeat re-ingest (never writes triples) |
| FR46 | Epic 6.2 | Permission model: Matrix power levels + fixed member-write whitelist + `authorized_by` audit |
| FR47 | Epic 6.1 | Deploy-key provisioning & sovereignty (ed25519, Fernet-encrypted, coordinator-revocable) |
| FR48 | Epic 6.3 | Template query command set (status/hours/find/nearby/network) |
| FR49 | Epic 6.3 | Isochrone travel-time discovery (OpenRouteService + shapely point-in-polygon) |

**Epic 9 scope note:** Stories 9.1–9.11 implement the "LLM-assisted JSON generator" referenced in PRD §Vision (Post-PoC). No numbered FRs exist for this capability — approved via the 2026-05-29 sprint change proposal. The PRD requires a targeted update to add FRs for Epic 9 when it moves to active development (pre-Story 9.1 recommended).

**AR coverage summary:**
- AR-SEED1–4 → Epic 0
- AR-INF1–5, AR-DATA1,4, AR-AGT1, AR-CONV1–5, AR-ST1 → Epic 1
- AR-DATA2 (seed→claim), AR-AGT2 (heartbeat first-fetch) → Epic 2
- AR-MLNK1–3, AR-DATA2 (freshness lifecycle), AR-METR1 → Epic 3
- AR-INF2 (admin auth), AR-METR1 (/metrics read) → Epic 4
- AR-DATA5, AR-AGT3–5 → Epic 6
- AR-DATA3 (presence graph reserved) → Epic 1 (schema slot) + Epic 7 (implementation)
- AR-INF1 (nginx subdomain pattern) → Epic 9 Story 9.1
- Story C.X (schema namespace pass) → prerequisite for Epic 9 + Epic 4 re-review (no AR number — architectural cleanup)

## Epic List

### Epic 0: Pilot Seed Data Pipeline
Space coordinators, network admins, and makers see the map populated with credible real spaces from the FR+DE pilot ecosystem — not synthetic demo fixtures. A separate, clearly-isolated dataset of RFF mockup spaces provides health-state variety for the admin dashboard demo without polluting the real onboarding pool.

**Sequencing note:** Executes after Epic 1 Oxigraph is running. VOW data is real (eligible for organic ⚪→🔵 flip). RFF mockup data lives in an isolated named graph (`<urn:mak:mock/rff-health>`) with explicit `mak:source mak:mock-rff` provenance; droppable via `DROP GRAPH` before production. Belgium is intentionally left blank — demo of organic onboarding (Add your URL path in Epic 2).

**FRs:** FR3
**ARs:** AR-SEED1, AR-SEED2, AR-SEED3, AR-SEED4

---

### Epic 1: Federated Backend Foundation
The map reads live pin data from Oxigraph instead of a bundled JSON fixture. The backend stack (Oxigraph, Nanobot agent container, nginx routing, MOM + IoP ontologies loaded) runs on the VPS. A cached GeoJSON materialization means the map still loads in <2s regardless of dataset size.

**Architectural contracts reserved for future epics:**
- `<urn:mak:presence>` named graph slot + commented-out nginx webhook route (Epic 7)
- SPARQL UPDATE endpoint internal-only (security, NFR-S2)

**FRs:** FR1, FR3, FR4, FR34, FR36, FR44
**NFRs:** NFR-R6, NFR-S2, NFR-I1, NFR-I2, NFR-P1
**ARs:** AR-ST1, AR-INF1–5, AR-DATA1, AR-DATA3 (slot only), AR-DATA4, AR-AGT1, AR-CONV1–5

---

### Epic 2: Coordinator URL Onboarding — ⚪→🔵 Flip
A coordinator pastes their JSON-LD endpoint URL, sees live validation feedback (reachable, schema-valid, geocoded, PII-free), submits, watches their pin flip ⚪→🔵, and receives a reciprocal embed snippet to place on their own site. No login, no form to revisit. Detail drawer now shows provenance + ingestion history.

**Demo path:** Belgium coordinator = Openfab Brussels using this flow, not seeded.

**FRs:** FR13, FR14b, FR19, FR20, FR21, FR22, FR23, FR26, FR27b
**NFRs:** NFR-D1–D4, NFR-R1, NFR-S3, NFR-I5
**ARs:** AR-DATA2 (seed→claim), AR-AGT2 (heartbeat first-fetch)
**UX-DRs:** UX-DR8, UX-DR14, UX-DR15

---

### Epic 4: Operator Observability Dashboard
Nicolas (MOM operator) opens `/admin`, reads system health at a glance (Oxigraph status, ingestion process, spaces reachable count), scans the space registry table for failures, drills into any space for a raw/ingested/displayed side-by-side inspection panel. This is infrastructure observability for the pipeline operator — not a network coordinator view (Luca uses the public health map toggle, no auth required). **Replanned 2026-05-28 against post-Epic-3.5 data sources** (`snapshot_store.db` + per-space Oxigraph graphs + browser-computed axes); supersedes the original Story 4.1–4.4 ACs that targeted the `urn:mak:status` graph and `/data/snapshots/*.json` disk artifacts (neither of which was ever built).

**Depends on:** Epic 3.5's `snapshot_store.db` (Axis A + last payload), per-space `urn:mak:space/*` + `urn:mak:canary` Oxigraph graphs (Axes B & C), browser-side `computeAxisA/B/C/Marker` for derived state. Epic 4 is a consumer, not a builder, of the pipeline. **Blocked-by prep:** Story 4.0 (materializer consolidation + `mom:seededAt` verification + `pill_2_stalled_after_seconds` config).

**FRs:** FR28–FR33b, FR43
**NFRs:** NFR-S1, NFR-S4, NFR-S6, NFR-O1, NFR-O2, NFR-P5
**ARs:** AR-INF2 (admin subdomain + auth), AR-METR1 (/metrics endpoint read), ADR-A (ingestion-health signal), ADR-B (inspection-panel backend = DESCRIBE + snapshot blob + production renderer); supersedes ADR-015 (raw snapshot disk path — never built; snapshot blob lives in `snapshot_store.db`)

---

### Epic 4b: Magic Link Coordinator Recovery *(parallel non-blocking)*
Space coordinators receive a magic-link email when their endpoint goes stale — YES refreshes pin, NO gracefully archives with GDPR closure. Parallel to Epic 4, non-demo-blocking. Depends on Epic 3's notification queue.

**FRs:** FR25b (closure logic)
**ARs:** AR-MLNK1–3

---

### Epic 5: Map Polish, Progressive Disclosure & Accessibility
The map now runs on real federated data: filters/search/detail drawer all read live. Phase-1 UI hypotheses are validated or pruned (tweaks panel, drawer ergonomics). Provenance banners, stale amber warnings, and accessible list view are added. Embeds carry "last confirmed" captions. axe-core in CI.

**FRs:** FR2, FR5–FR12, FR14, FR15–FR18
**NFRs:** NFR-P2, NFR-P3, NFR-A1–A5, NFR-I4
**UX-DRs:** UX-DR1–7, UX-DR11, UX-DR22–27

---

### Epic 3: Ingestion Pipeline + Endpoint Health + Stale Detection *(prerequisite for Epic 4)*
The full ingestion pipeline becomes real: SpaceAPI JSON is fetched, raw snapshot written to disk, transformed to MOM JSON-LD via the ontology mapping layer (ADR-015), and ingested into Oxigraph. Heartbeat scheduler runs the full 6h cycle with aging/zombie/dead lifecycle. Epic 4 reads from this epic's outputs. Magic-link coordinator recovery is extracted to Epic 4b (parallel, non-blocking).

**FRs:** FR24, FR25, FR25b, FR26, FR27, FR27b
**NFRs:** NFR-R1, NFR-R2, NFR-R3, NFR-R5, NFR-C1
**ARs:** AR-DATA2 (freshness lifecycle), AR-METR1 (heartbeat_log writes), ADR-015 (transformation layer + snapshot path)

---

### Epic 6: "Ask Bernard" — One Bot, Two Skillsets *(parallel; non-blocker; restructured 2026-06-16)*
One channel-agnostic bot, one Bernard voice. A platform adapter normalises Matrix/Discord/Telegram/Mattermost to a `Message`; an intent classifier routes each message to `write | query | nl_discovery | unknown`; the matching skill fires and Bernard responds. **Write skillset:** a coordinator edits their *own* endpoint JSON via an SSH deploy key (JSON patch → git commit → heartbeat re-ingests) — the bot never writes Oxigraph triples; permissions follow Matrix power levels. **Discovery skillset:** template SPARQL queries (`status`/`hours`/`find`/`nearby`/`network`) + isochrone travel-time search (OpenRouteService + shapely), then full NL→SPARQL with the IoP ontology guardrail. `harness/` is the baseline (Nanobot deferred to Story 6.4). Matrix-first for write; read/discovery on all channels.

**FRs:** FR35, FR35b, FR37–FR42, FR45–FR49
**NFRs:** NFR-L1–L4, NFR-S5, NFR-S7, NFR-P4, NFR-I3
**ARs:** AR-AGT3–5, AR-DATA5; ADR-017 (Bernard bot — harness baseline, deploy-key write, isochrone)
**UX-DRs:** UX-DR12; Bernard voice rules (handoff 2026-06-16 §"Bernard voice rules" = Story 6.5 ACs)

---

### Epic 7: 🟢 "Open Now" Presence Layer *(parked indefinitely 2026-05-06 — heartbeat + SpaceAPI `state.open` cover it)*
Originally a webhook-driven presence layer. As of Story 3.2, the heartbeat polls every 10 min and honors SpaceAPI `state.open` as a lifecycle-resetting signal — coordinators with automated endpoints stay `confirmed` indefinitely without any push channel. Section retained as a design trail; do not create stories without fresh justification.

**FRs:** FR3 (🟢 state)
**ARs:** AR-DATA3 (ADR-007 presence graph — activate from slot)

---

### Epic 8: MOM as a Living Space — Mother Sands Broadcast Rig *(parallel, non-blocking; post-demo)*
Mother Sands stops being only a diagnostic canary (Story 3.3) and becomes MOM's self-representation on its own map: a public website at `mom.mapsofmaking.org`, a wiki/lore page, Bernard the hermit-crab admin persona, a curated changelog/feature "broadcast", and relocation/fort-rotation as ambient narrative. Parallel to Epic 5 polish; not on the demo critical path. Stub only — stories created post-demo. Design seeds: `mom_handoff_2026-05-16.md`, `mom_handoff_2026-05-15.md` (Bernard character bible, lore skeleton).

### Epic 9: Bernard's Workshop — Assisted SpaceAPI JSON Composer *(parallel, post-C.X; post-demo non-blocker)*
Assisted SpaceAPI JSON composer at `genjson.mapsofmaking.org` with Bernard's voice as the UX anchor. Goal: convincing, inclusive, effortless onboarding for non-technical coordinators, with data sovereignty and self-hosting as the end state. **Tier 1 first-user slice (9.1–9.5, 9.8, 9.12):** subdomain infra, drawer UX, wizard Tiers 0+1, Nominatim proxy, voice copy, GitLab raw-URL tutorial, visual design pass — compose JSON → host on GitLab → see pin on map. **Superseded by Epic 6 (2026-06-16):** 9.6 (`mom:` fields), 9.7 (`state.open` FSM), 9.9 (three-mode unification), 9.10 (Tier 3 `ext_fab`) — once a coordinator has a live file, the bot's write skillset (Epic 6.2) updates these fields conversationally, no wizard re-run. 9.11 (validator error UX) deferred, still valid. **Depends on:** Story C.X. **Defers Epic 4 re-review** until Tier 1 in flight.

---

**Testing discipline (baked into all Epic 2–4 ACs):**
- RFF mockup dataset = dev/test sandbox for onboarding flow (safe to flip, break, reset)
- VOW real data = read-only, no onboarding tests against it
- Openfab Brussels (Nicolas) = live acceptance test — real URL, real pin flip, embed on openfab.be validates end-to-end delay

**Demo critical path:** Epic 1 → Epic 0 → Epic 2 → Epic 3 → Epic 4 (+ Epic 5 as rolling polish)
**Parallel non-blocking:** Epic 4b (magic link) // Epic 6 (NL bot) // Epic 8 (Mother Sands broadcast rig) — none block demo
**Reserved post-demo side quest:** Epic 7 (🟢 open-now presence layer)
**Post-C.X parallel track:** `Story C.X → Epic 9 (Bernard's Workshop) → Epic 4 re-review`. Epic 9 is expected to surface small schema course-corrections; Epic 4 AC re-review is deferred until Epic 9 M1+ is in flight.

**Key dependency:** Epic 4 (operator dashboard) requires Epic 3.5's `snapshot_store.db` (Axis A), per-space Oxigraph graphs (Axes B & C), and browser-side `computeAxisA/B/C/Marker`. Story sequencing within Epic 3.5 must deliver these before Epic 4 stories begin. (Note: the original dependency on `/data/snapshots/{id}/latest.json` and `<urn:mak:status>` is superseded — those were never built.)

---

## Epic 0: Pilot Seed Data Pipeline

The map is populated with credible real spaces from the pilot ecosystem. VOW's 500+ German open workshops (already scraped in `vow_workshops.json`) are normalized to the MOM schema, geocoded, and loaded as ⚪ seeded pins. A separate RFF mockup dataset provides health-state variety (stale, broken, aging) for the admin dashboard demo without touching real onboarding data. Belgium is intentionally left blank — that region demonstrates organic onboarding (Epic 2).

**Depends on:** Story 1.3 (Oxigraph running) + Story 1.4 (MOM ontology loaded)

---

### Story 0.1: Normalize VOW Scrape to MOM-Compliant JSON-LD + Geocode

As a maker or coordinator,
I want the map to show real German open workshop spaces (from the VOW / offene-werkstaetten.org network) as ⚪ seeded pins,
So that the pilot map has credible density in Germany and coordinators can recognise their own space rather than seeing synthetic placeholder data.

**Acceptance Criteria:**

**Given** `web/data/vow_workshops.json` contains 500+ entries with fields: `name`, `address`, `website`, `profileUrl`, `categories` (German-language strings)
**When** `scripts/normalize_vow.py` is run
**Then** it produces `web/data/moms_seed.json` as a JSON-LD array where each entry maps to:
- `@type: mom:MakerSpace`
- `schema:name` ← `name`
- `schema:address` ← parsed from `address` string (street, postcode, city, country: DE)
- `schema:geo` ← geocoded lat/lng (using Nominatim or equivalent, with polite rate-limiting: 1 req/s, User-Agent header set)
- `schema:url` ← `website`
- `mom:profileUrl` ← `profileUrl` (provenance back to VOW directory)
- `schema:knowsAbout` ← categories translated via `scripts/category_map.yaml` (e.g. `Holz` → `wood`, `Elektronik` → `electronics`, `3D-Druck` → `3d-printing`)
- `mom:source: "scraped-vow"`
- `mom:operationalState: "seeded"`
**And** `scripts/category_map.yaml` exists mapping all unique German category strings in the source to canonical English tags; unmapped categories are logged as warnings and included verbatim (never silently dropped)
**And** entries that fail geocoding (address not found, Nominatim returns no result) are written to `web/data/moms_seed_geocode_failures.json` for manual review — not silently dropped from the output
**And** the script is idempotent: re-running it overwrites `moms_seed.json` cleanly

---

### Story 0.2: Generate RFF Mockup Dataset for Health-Layer Demo

As a network admin viewing the dashboard demo,
I want the admin dashboard to show a realistic spread of endpoint health states (confirmed, stale, broken, aging) attributed to the RFF France network,
So that the demo communicates the fleet-health value proposition without polluting the real VOW onboarding data with synthetic entries.

**Acceptance Criteria:**

**Given** the MOM ontology schema (Story 1.4) defines status lifecycle states
**When** `scripts/generate_rff_mockup.py` is run
**Then** it produces `web/data/rff_mockup.json` containing ~20–30 synthetic French maker spaces with:
- Realistic French names, cities, and addresses (Paris, Lyon, Marseille, Bordeaux, Toulouse spread)
- A deliberate mix of health states: ~10 confirmed (🔵), ~8 seeded (⚪), ~5 stale (dashed), ~4 broken (🔴), ~2 aging
- Plausible `last_fetched` timestamps that explain the health states (stale = 45 days ago, broken = 404, aging = 35 days no claim)
- `mom:source: mak:mock-rff` on every entry (explicit provenance flag)
- Named graph target: `<urn:mak:mock/rff-health>` (isolated from real data pool)
**And** the script includes a comment block: `# DEMO ONLY — drop this graph before production: docker exec oxigraph sparql --update "DROP GRAPH <urn:mak:mock/rff-health>"`
**And** the admin dashboard demo-toggle (Epic 4, Story 4.x) can include/exclude this graph via a SPARQL `FROM NAMED` clause

---

### Story 0.3: Seed Import — Load Both Datasets into Oxigraph

As a developer running the demo environment,
I want a single command that loads both the VOW real seed and the RFF mockup dataset into Oxigraph,
So that the map shows ⚪ pins for 500+ German spaces and the admin dashboard shows a realistic health spread for France — with both datasets clearly separated by provenance.

**Acceptance Criteria:**

**Given** Oxigraph is running (Story 1.3), ontologies are loaded (Story 1.4), and both `moms_seed.json` + `rff_mockup.json` exist
**When** `python scripts/seed_import.py` is run
**Then** it converts each entry in `moms_seed.json` to RDF triples and inserts them into `<urn:mak:space/{id}>` named graphs with `mom:source "scraped-vow"` and `mom:operationalState "seeded"`
**And** it converts each entry in `rff_mockup.json` to RDF triples and inserts them into `<urn:mak:mock/rff-health>` named graph with `mom:source "mock-rff"` and the appropriate health state triples
**And** the status scheduler job (`<urn:mak:status>`) is updated with materialized status triples for all imported spaces
**And** after import, running `python scripts/materialize_geojson.py` (Story 1.5) produces a `spaces.geojson` that includes all VOW spaces as ⚪ seeded pins visible on the map
**And** the script logs a summary on completion: `{n} VOW spaces loaded`, `{n} RFF mockup spaces loaded`, `{n} geocode failures skipped`
**And** the script is idempotent: re-running it checks `ASK { GRAPH <urn:mak:space/{id}> { ?s ?p ?o } }` before each insert and skips already-loaded spaces

---

## Epic 1: Federated Backend Foundation

The map reads pins from Oxigraph (not bundled JSON); the Docker stack runs on the VPS with proper security routing; MOM ontology v0 exists and both ontologies are loaded. Each story stands alone and enables the next.

---

### Story 1.1: Integration Dependency Spike

As a developer,
I want a single `/ping` slash command that chains Discord → OpenRouter LLM call → Oxigraph health check and logs each leg's result,
So that all three external dependencies are proven reachable before any feature work begins — and failures are surfaced early with clear diagnostics.

**Acceptance Criteria:**

**Given** the Openfab Brussels Discord server exists and the developer has admin rights on it
**When** setting up the Discord application (one-time prerequisite before any code runs)
**Then** the developer follows these steps in the Discord Developer Portal (discord.com/developers):
1. Create a new Application named `maps-of-making-bot`
2. Under Bot tab: enable bot, copy the bot token into `.env` as `DISCORD_BOT_TOKEN`
3. Under OAuth2 → URL Generator: select scopes `bot` + `applications.commands`; select permission `Send Messages` + `Use Slash Commands`; copy the generated URL and open it to invite the bot to the Openfab server
4. Under Bot tab: disable "Public Bot" (only Openfab server should use it)

**Given** the three files `harness/main.py`, `harness/llm_client.py`, `harness/sparql_client.py` exist and `DISCORD_BOT_TOKEN`, `OPENROUTER_API_KEY`, and `OXIGRAPH_ENDPOINT` are set in `.env`
**When** a developer runs `/ping` in the configured Openfab Discord channel
**Then** the bot defers (`thinking=True`), calls OpenRouter (one completion, any model), queries Oxigraph health endpoint (`ASK { ?s ?p ?o }`)
**And** responds with a structured message showing each leg: ✓/✗ Discord auth, ✓/✗ OpenRouter (model used, latency ms), ✓/✗ Oxigraph (latency ms)
**And** if any leg fails, the error is logged via `structlog` with `session_id` bound and a plain-language failure message shown in Discord (no stack trace to the user)
**And** slash commands are synced via `tree.sync()` in `setup_hook` (not on every message)
**And** all three files follow AR-CONV1 naming (`snake_case`, `verb_noun()`) and AR-CONV2 logging (`structlog`, event `noun.verb_past`)
**And** the spike is verified working before any Epic 1 story beyond 1.2 is started

---

### Story 1.2: Scope Basemap to Europe + Update Loader Copy

As a maker browsing the map,
I want the map to restrict panning to the Europe region and show accurate loader copy,
So that the initial tile batch is minimal (no tiles loading for unreachable world regions) and the loader text reflects the actual data being loaded rather than hardcoded synthetic copy.

**Acceptance Criteria:**

**Given** the map SPA is loading
**When** MapLibre initialises
**Then** `maxBounds` is set to approximately `[[-25, 34], [45, 72]]` (Atlantic west coast to Ural, North Africa to Scandinavia), preventing tile requests outside Europe
**And** the loader copy no longer reads "loading 40 synthetic spaces · FR + DE" — it reads a neutral variant (e.g. "unrolling the map…") that does not hardcode a space count or data description
**And** the map still centres on `[4.8, 49.5]` zoom 4.3 (FR/DE/BE pilot midpoint)
**And** the `<div class="loader">` second line is either removed or replaced with a version driven by actual data count once available
**And** the reduced-motion media query and 1500ms fallback dismissal remain untouched

---

### Story 1.3: Docker Compose Stack + Nginx Security Routing

As a network admin and developer,
I want the full Phase 2 service topology running on the VPS (Oxigraph, Nanobot agent, link-handler, nginx) with public SPARQL read-only and update blocked,
So that the backend is reachable, secure, and ready for ontology loading and ingestion wiring in subsequent stories.

**Acceptance Criteria:**

**Given** the VPS has Docker + Docker Compose installed and `.env` is populated from `.env.example`
**When** `docker compose up -d` is run from the project root
**Then** all four services start without error: `oxigraph`, `mak-agent` (Nanobot), `mak-link-handler`, `nginx`
**And** `docker network ls` shows a `maps_of_making_internal` network; no host-level port conflicts with other projects (all services use `expose`, not `ports`, except nginx)
**And** `GET /sparql/query` with a valid SPARQL SELECT returns 200 from the public internet
**And** `POST /sparql/update` returns 403 or connection refused from outside the Docker network (nginx deny rule verified)
**And** `/claim/test` routes to `mak-link-handler:8000/claim/test` (nginx proxy rule present, 404 or 422 from FastAPI is acceptable — route exists)
**And** the presence webhook nginx route is present but commented out (Epic 7 slot reserved)
**And** `admin.*` subdomain returns 401 without credentials and 200 with the shared password from `.env` (basic auth configured)
**And** `.env.example` is committed with all required variable names and placeholder values; `.env` is gitignored

---

### Story 1.4: Author MOM Ontology v0 + Load MOM & IoP into Oxigraph

As a developer and SPARQL client,
I want a versioned MOM ontology v0 file and both MOM + IoP ontologies loaded as named graphs in Oxigraph,
So that all downstream heartbeat, ingestion, and query stories can use stable semantic predicates without redefining vocabulary ad-hoc.

**Acceptance Criteria:**

**Given** Oxigraph is running (Story 1.3 done)
**When** `scripts/load_ontology.sh` is run
**Then** `ontology/mom.ttl` exists and declares at minimum:
- Namespace `mom:` at `https://w3id.org/maps-of-making/`
- Classes: `mom:MakerSpace`, `mom:NetworkMembership`, `mom:SpaceType`
- Properties: `mom:freshnessStatus`, `mom:healthStatus`, `mom:visibility`, `mom:operationalState`, `mom:lastChecked`, `mom:consecutiveFailures`, `mom:source`, `mom:pendingNotification`, `mom:dispatched`, `mom:retryCount`
- A `mom:OntologyGap` class for query-failure logging (FR41)
- A `@version` annotation (e.g. `owl:versionInfo "0.1.0-poc"`)
**And** `ontology/context/space.jsonld` exists providing the `@context` for coordinator JSON-LD endpoint files, mapping `mom:` and `schema:` prefixes
**And** `scripts/load_ontology.sh` is idempotent — it runs an `ASK` query before each POST and skips if already loaded
**And** after running the script, `ASK { GRAPH <urn:mak:ontology/mom> { ?s ?p ?o } }` returns `true`
**And** after running the script, `ASK { GRAPH <urn:mak:ontology/iop> { ?s ?p ?o } }` returns `true`
**And** ontology evolution (additional classes, alignment with full IoP, w3id.org registration) is explicitly noted as deferred to pilot in a `## Roadmap` comment block in `mom.ttl`
**And** `scripts/load_ontology.sh` is called in the Docker Compose startup sequence (or documented as a manual post-deploy step) so a fresh VPS install is ready after one command

---

### Story 1.5: Map Reads from Oxigraph GeoJSON Materialization

As a maker browsing the map,
I want the map to show spaces fetched from the Oxigraph-backed federated dataset (not `data/moms_seed.json`),
So that what I see on the map reflects the live system state — and the switch from bundled JSON to backend-served data is transparent to me (same load time, same pin rendering).

**Acceptance Criteria:**

**Data flow for this story:**
```
Ingestion (Epic 2/3): coordinator URL → fetch JSON-LD → parse → Oxigraph (write path)
Materialization (this story): Oxigraph → SPARQL SELECT → spaces.geojson (static file) → nginx → SPA fetch (read path)
```
The SPA never queries SPARQL directly. It fetches one pre-baked static GeoJSON file served by nginx. `materialize_geojson.py` re-bakes this file on demand; the scheduler (Epic 3) will call it after each ingest cycle. For demo: run manually once after seeding.

**Given** Oxigraph is running (Story 1.3) with ontologies loaded (Story 1.4) and at least one space triple exists in `<urn:mak:space/{id}>`
**When** `python scripts/materialize_geojson.py` is run
**Then** it executes a SPARQL SELECT against `<urn:mak:status>` and `<urn:mak:space/*>` named graphs and writes the result to `web/data/spaces.geojson` as a valid GeoJSON `FeatureCollection`
**And** each feature contains: `geometry.coordinates [lng, lat]`, `properties.name`, `properties.status` (seeded / confirmed / stale / broken), `properties.uri`, `properties.last_fetched`
**And** the query includes a `LEFT JOIN` against `<urn:mak:presence>` returning `null` for all spaces now (Epic 7 presence slot wired but inactive)
**And** nginx serves `web/data/spaces.geojson` as a static file

**Given** `spaces.geojson` is served at `/data/spaces.geojson`
**When** the map SPA boots
**Then** `app.js` fetches `/data/spaces.geojson` instead of `data/moms_seed.json` — same fetch call, different source file
**And** pin rendering, filter chips, and search work identically to phase-1 behaviour
**And** if the fetch returns non-200, the map degrades gracefully: paper-overlay background, zero pins rendered, inline banner "Map data temporarily unavailable — try refreshing" (no raw error, no blank screen)

---

## Epic 2: Coordinator URL Onboarding — ⚪→🔵 Flip

A coordinator pastes their JSON-LD endpoint URL, sees live validation feedback (reachable, schema-valid, geocoded, PII-free), submits, watches their pin flip ⚪→🔵, and receives a reciprocal embed snippet — all within a single flow, no login required.

**Testing strategy:** All development and demo testing uses RFF mockup space entries (safe to reset). VOW data is read-only and never used for onboarding tests. Openfab Brussels (Nicolas) is the live acceptance test for the full flow end-to-end, including embedding the map on openfab.be to validate the ⚪→🔵 feedback delay.

**Architecture decisions locked for Epic 2 [2026-04-25 retro]:**
- **Registration path: web drawer only.** The "Add your URL" drawer is already present in the phase-1 UI (not wired). Epic 2 wires it. Alternative registration paths (GitHub PR to ontology repo, Discord `/add` command, CI/CD cron trigger) are backlogged pending traction signal.
- **Coordinator JSON hosting:** Epic 2 accepts any valid https URL. Documentation of hosting options (GitHub Gist, Google Drive, Nextcloud, institutional IT) and a JSON generator tool are workshop content, not Epic 2 scope. Backlogged.
- **Final acceptance test:** Nicolas submits Openfab Brussels as a live coordinator. This is the Epic 2 done gate — not just RFF mockup validation.

**Story restructure [2026-04-26]:** Original stories 2.1–2.4 merged into a single vertical slice (2.1); original 2.5 renumbered to 2.2; 2.6 kept. Rationale: the coordinator gesture is atomic from UX perspective; embed was already implemented in phase-1; PII hard-rejection deferred to a future "hardening PII & GDPR compliance" story.

---

### Story 2.1: Coordinator URL Onboarding — E2E (submit → validate → ingest → flip → embed)

*Merges original stories 2.1 + 2.2 + 2.3 + 2.4. Implementation file: `_bmad-output/implementation-artifacts/2-1-coordinator-url-onboarding-e2e.md`*

As a space coordinator,
I want to paste my JSON-LD endpoint URL, see it validated live, and watch my pin flip from ⚪ to 🔵 with a ready-to-copy embed snippet —
so that I can register my space on the map without creating an account or contacting anyone.

**Acceptance Criteria (summary — see implementation story for full BDD spec):**

**Given** the "Add your URL" drawer is open
**When** a coordinator pastes a URL and clicks "Fetch & validate"
**Then** `POST /api/validate-url` is called and a live checklist renders: reachable ✓, JSON-LD valid ✓, name found ✓, coordinates found ✓, (soft PII warning if personal fields present — non-blocking)

**And** on all blocking checks passing, a "Confirm & register your space →" button appears

**And** clicking confirm calls `POST /api/register-url`, which: re-validates, writes SPARQL UPDATE to Oxigraph (`mom:operationalState "confirmed"`, `mom:endpointUrl`, `mom:lastFetched`), writes a snapshot named graph `<urn:mak:space/{slug}/{date}>`, rematerializes `web/data/spaces.geojson` inline

**And** the drawer shows a confirmation screen: space name, "Embed this space →" (calls existing `embedSpace()`), "View on map →" (calls `selectSpace()`)

**And** the map markers re-render to show the 🔵 pin

**And** a `scripts/seed_transition.py` admin utility (read-only by default, `--mark-done` opt-in) reports which seeded spaces have been confirmed — run manually for demo maintenance, isolated from the ingestion flow

**PII enforcement deferred:** Soft warning only in Epic 2 — fields detected are listed but never block registration and are silently dropped from stored triples. Hard rejection + admin alert is a future "hardening PII & GDPR compliance" story.

---

### Story 2.2: Detail Drawer — Provenance + Ingestion History

*Renumbered from original story 2.5. Implementation file: `_bmad-output/implementation-artifacts/2-2-detail-drawer-provenance-ingestion-history.md`*

As a maker or coordinator,
I want the space detail drawer to show where the data came from, when it was last fetched, and a short history of changes,
So that I can trust whether the information is current — and coordinators can verify their own endpoint is being read correctly.

**Acceptance Criteria (summary — see implementation story for full BDD spec):**

**Given** a maker clicks any pin
**When** the detail drawer opens
**Then** a "Data provenance" section shows: source label (Self-registered / VOW network / RFF network), endpoint URL (truncated, full on hover), last fetched timestamp via `timeAgo()`

**And** for ⚪ seeded spaces: a "Claim this pin" CTA appears — "Are you the coordinator? Add your URL →" (calls `setDrawer('addurl')`)

**And** for 🔴 broken spaces: freshness line replaced by amber error banner with plain-language error category (from `s.error_type`) + last known good date

**And** a "Fetch history" section shows the last 5 snapshots from `GET /api/space/{id}/snapshots` (link_handler endpoint), rendered async — shows "No fetch history yet." on empty or error

**And** `scripts/materialize_geojson.py` SPARQL query is extended to include `mom:endpointUrl`, `mom:lastFetched`, `mom:errorType` fields

**And** all existing detail drawer sections (hero, quick facts, specialties, raw JSON, embed button) are unchanged

**Depends on Story 2.1:** snapshot named graphs must be written by `POST /api/register-url` for history to populate.

---

### Story 2.6: Mobile Responsive Layout

*Added: Epic 1 retrospective 2026-04-25. Updated 2026-04-27 with mobile-first design principle and new ACs. Implementation file: `_bmad-output/implementation-artifacts/2-6-mobile-responsive-layout.md` (authoritative — supersedes this summary).*

**Mobile-first design principle:** Mobile = browsing mode (find a space, go there, share it). Coordinator onboarding, health map, and management features are desktop-only.

As a maker browsing on a phone,
I want the map to fit, be usable, and help me find spaces near me,
So that I can discover open spaces and share them with my group — without needing a desktop.

**Key ACs (see story file for full detail):**
- Topbar collapses to icon-only row (no overflow/wrap) on < 768px
- All drawers open as bottom sheets; detail drawer at ~80–85% height
- "Claim this pin" CTA suppressed on mobile — replaced with desktop whisper text
- "📍 Near me" button: geolocation → flyTo zoom 12, silent on denial
- "⎘ Copy space link" in detail drawer footer (copies `s.website || s.endpoint_url`)
- Zone 3 (raw source JSON) hidden on mobile
- Real-phone validation by Nicolas required before done
- Desktop layout unchanged (≥ 768px)

**Dev Notes:**
- CSS-only approach — no JS framework
- `prefers-reduced-motion` already covers drawers — extend to new mobile transitions
- Existing `@media (max-width: 720px)` is a partial start; this story completes it

---

### Story 2.7: Card Zones + Pydantic Schema Foundation

*Added: 2026-04-27. Addresses data flow incoherence between URL ingestion and card display. Implementation file: `_bmad-output/implementation-artifacts/2-7-card-zones-pydantic-schema-foundation.md` (authoritative).*

As a maker or coordinator viewing a space detail card,
I want to see clearly separated zones — identity, curated data, and raw source — and as a coordinator I want honest feedback about what my endpoint unlocks,
So that I can trust what the map shows me and know exactly what to improve in my data file.

**Data flow:** `URL → fetch → Pydantic validation → Oxigraph (curated fields + raw snapshot) → card (Zone 2 from Oxigraph, Zone 3 from raw snapshot)`

**Key ACs (see story file for full detail):**
- Pydantic `SpaceAPISchema` model classifies endpoints into subsets: `mom:required` → `mom:card` → `spaceapi:compatible`
- Validation response includes `subset`, `unlock_message`, `next_unlock` (progressive fog-of-war incentive)
- Raw endpoint JSON stored as `mom:rawContent` in snapshot graph (50KB cap)
- `GET /api/space/{id}/raw` returns cached snapshot JSON
- Card restructured: Zone 1 (identity/status), Zone 2 (ingested fields only — removes fake Founded/Capacity/Contact), Zone 3 (real source JSON, desktop only)
- `jsonForSpace()` deleted — it was reconstructing fake "endpoint" data from GeoJSON props
- `schema:description` surfaced in Zone 2 (was ingested but never displayed)

**SpaceAPI compatibility reference:** https://github.com/SpaceApi/schema
**Success metric:** One endpoint registers on MoM AND mapall.space without changes.

---

## Epic 3: Ingestion Pipeline + Endpoint Health + Stale Detection

*(Prerequisite for Epic 4 — must ship before operator dashboard stories begin)*

> ⚠️ **The shipped shape differs from the ACs below (Epic 3.5 correct-course, 2026-05-28).**
> Stories 3.0–3.5 shipped roughly as specified. Stories 3.6–3.12 (Epic 3.5) replaced the rest:
> - Raw snapshots live in **`infra/link_handler/snapshot_store.db`** (SQLite payload blob), not `/data/snapshots/{id}/latest.json` on disk.
> - The fetch/transform entry point is **`space_pipeline.run_space_pipeline()`** (Story 3.11 unified path). **`tasks/heartbeat.py` is deleted.**
> - There is no `<urn:mak:status>` materialized graph and no `mak:probeResult` predicate. Freshness lives in three tokens: `observed_at` (SQLite, Axis A), `mom:updatedAt` (Oxigraph, Axis B), `mom:lastOpenChange` (Oxigraph, Axis C).
> - Derived state (endpoint health buckets, marker colour) is computed in the browser, not stored.
>
> Canonical post-3.5 contract: Epic 3.5 retro (`_bmad-output/implementation-artifacts/epic-3.5-retro-2026-05-28.md`) + Epic 4 §replan above. Treat ACs in 3.0–3.4 below as historical; do not use 3.0–3.4 ACs as the spec for new code touching the ingestion pipeline.

The full ingestion pipeline becomes real: SpaceAPI JSON fetched from space endpoints, raw snapshot written to disk before any transformation, then transformed to MOM JSON-LD via the explicit ontology mapping layer (ADR-015), and ingested into Oxigraph. Heartbeat scheduler runs the full 6h cycle producing the status graph Epic 4 reads from. Magic-link coordinator recovery is a separate parallel epic (4b).

---

### Story 3.0: Ingestion Transformation Layer — SpaceAPI JSON → MOM JSON-LD

As the MOM pipeline,
I want an explicit transformation step that maps SpaceAPI JSON fields to MOM JSON-LD before anything is written to Oxigraph,
So that the boundary between "what the space published" and "what we store" is a named, auditable step — and the raw source is preserved on disk as a trust receipt.

**Acceptance Criteria:**

**Given** a registered endpoint URL exists in Oxigraph with `mom:operationalState` of `"confirmed"` or `"seeded"`
**When** `tasks/heartbeat.py` fetches the endpoint
**Then** the raw JSON response is written to `/data/snapshots/{space_id}/latest.json` immediately on receipt, before any parsing or transformation (this is the Zone 3 source and Epic 4 inspection panel source)
**And** a fetch timestamp is written alongside: `/data/snapshots/{space_id}/meta.json` with `{ fetched_at, http_status, etag, endpoint_url }`
**And** the payload is normalized before comparison: ephemeral fields (e.g. `lastchange` unix timestamps that tick every request) are stripped, arrays are sorted — this prevents false-positive "changed" detections
**And** if the normalized payload matches the stored snapshot hash: only the `fetched_at` timestamp is updated; Oxigraph is NOT touched; outcome logged as `"no_change"`
**And** if the normalized payload differs: `tasks/ingest.py` is called with the raw JSON

**Given** `tasks/ingest.py` is called with raw SpaceAPI JSON
**When** the transformation runs
**Then** each SpaceAPI field is mapped to its MOM JSON-LD equivalent using the explicit field mapping from ADR-015 (implemented as a mapping table in `tasks/ingest.py`, not ad-hoc logic)
**And** `mom:required` fields (`space`, `url`, `location.lat/lon`) that are missing cause a hard reject with outcome `"schema_invalid"` logged — no partial ingestion
**And** `mom:card` fields that are missing are ingested with a structured warning logged: `"card_field_missing: {field}"` — never silently dropped
**And** `mom:extended` fields present in the JSON are mapped to their MOM predicates; absent fields are silently skipped (they're optional)
**And** the resulting MOM JSON-LD is written to `<urn:mak:space/{id}>` (current) and `<urn:mak:space/{id}/{date}>` (append-only snapshot) via SPARQL UPDATE
**And** every fetch decision is logged to `heartbeat_log`: `space_uri`, `checked_at`, `outcome` (`ok` / `changed` / `no_change` / `schema_invalid` / `error` / `timeout`) — never silently dropped
**And** ~~the snapshot path convention is exactly `/data/snapshots/{space_id}/latest.json` — this path is pinned here and referenced in Epic 4 stories~~ **Superseded by Epic 3.5: snapshots live in `snapshot_store.db` (see Epic 4 Story 4.3). Disk path never built.**

---

### Story 3.0-A: Space Profile Card — UX Refinement

*Added: 2026-05-04. Post-3.0 UX polish pass: profile naming, freshness signals, contact pictos, logo, share CTA, manual fetch stub, and timing fix. Implementation file: `_bmad-output/implementation-artifacts/3-0-A-space-profile-card-ux-refinement.md` (authoritative).*

As Luca (coordinator) and as a visitor,
I want the space profile to clearly reflect what the endpoint provides, let me share it easily, and signal when it was last updated,
So that the card earns trust without adding friction.

**Key ACs (see story file for full detail):**
- Drawer renamed "Space Profile" (label-only; element ids unchanged)
- Post-registration timing: 8s if unlock guidance present, 2s if none
- Zone 1: logo thumbnail inline with name; "Last updated: {timeAgo}" replaces freshness banner; share picto CTA (desktop only)
- Zone 2: contact channel pictos with click-to-copy; subset nudge ("What your data unlocks") now permanent, field-by-field; embed CTA moved here from below Zone 3
- Zone 3: raw JSON flush (no side padding); "Last fetched: {local datetime}" precise header; manual fetch button rendered disabled (endpoint ships in Story 3.1)
- Fetch history section removed
- GeoJSON surfaces: `logo`, `contact` (JSON string), `last_updated`
- `classify_subset()` updated to identify single lowest-effort next field (not a list)

**Depends on:** Story 2.7 (zones, `/raw` endpoint, Pydantic subsets)
**Deferred to Story 3.1:** `POST /api/heartbeat-space/{id}` endpoint + manual fetch button activation

---

### Story 3.1: Heartbeat Scheduler — Periodic Fetch Cycle + Manual Trigger

As the system,
I want a scheduled job that fetches all registered endpoint URLs every 10 minutes using conditional GET,
So that the federated dataset stays fresh without any manual intervention and without hammering space servers unnecessarily.

As Luca (coordinator),
I want a "Refresh from endpoint" button on the space profile,
So that I can force an immediate update after editing my JSON without waiting for the next cycle.

**Acceptance Criteria:**

**Given** Oxigraph contains at least one space with a registered endpoint URL and `mom:operationalState "confirmed"`
**When** the heartbeat scheduler fires (Nanobot CronService every 6h, configurable via `config.yaml`)
**Then** `tasks/heartbeat.py` is invoked for each confirmed space URI in sequence
**And** each fetch uses `If-None-Match` (ETag) and `If-Modified-Since` headers if the previous response provided them — only pulls full payload on actual change (NFR-R1)
**And** fetch timeout is 60s per endpoint with incremental backoff on failure: 1× immediate retry, then defer to next cycle (NFR-R2)
**And** each fetch outcome is written to `heartbeat_log` SQLite table: `space_uri`, `checked_at`, `http_status`, `latency_ms`, `outcome` (ok / changed / error / timeout) (AR-METR1)
**And** after all fetches complete, `scripts/materialize_geojson.py` is called once to refresh `spaces.geojson`
**And** fetch cadence, timeout, and retry policy are all read from `config.yaml` — never hardcoded (NFR-R3)
**And** a scheduler crash never takes down the public map — Nanobot's supervisor restarts the scheduler independently of the Discord adapter (NFR-R6)

---

### Story 3.2: Endpoint Health + Space Lifecycle + Open-Now (unified)

> **Rescoped 2026-05-06.** Original AC list (PII strip on closed) split to Story 3.2b. Open-now signal pulled in from the deferred Epic 7 entry — heartbeat already polls so it's read-side, not push-side. Epic 7 now parked indefinitely.
> **Completed 2026-05-06.** 71 unit tests + 4 live network tests (`pytest -m network`). Full ACs and dev notes live in the story file: `_bmad-output/implementation-artifacts/3-2-freshness-lifecycle-aging-zombie-dead-transitions.md`.

As MOM, I want the heartbeat to interpret each fetch into three independent truth signals — endpoint health, space lifecycle, and dynamic open/closed — and resolve them into one honest pin, so that visitors see what's actually happening and coordinators get the right freshness incentive.

**Truth model (summary):**

- **Endpoint health** (clock: minutes since last 200/304) → `healthy` < 10m, `unresponsive` 10–30m, `warning` 30–60m, `broken` ≥ 60m. Map shows red ✕ only for `broken`; Epic 4 surfaces the rest.
- **Space lifecycle** (clock: days since `mom:lastUpdated`, only resets on real content diff) → `confirmed` < 30d, `aging` 30–90d, `zombie` 90–180d, `dead` ≥ 180d. **MOM never rewrites `mom:lastUpdated` from a state-only graph write.**
- **Dynamic open/closed** — `state.open` (v15 object) or `"open"`/`"closed"` (v0.13 string) → `mom:openNow` boolean + optional `mom:lastOpenChange`. **`state.open` flips count as material content changes** — they reset the lifecycle clock. `sensors.*` flips do not. This is the designed freshness incentive.
- **Conflict resolution:** lifecycle supersedes endpoint. A dead space with vanished hosting still shows as dead, not merely broken. Resolved server-side in `transformer.effective_marker(...)`; GeoJSON exposes a single resolved `status` plus the raw signals for Epic 4.

**Story 3.2b** carries the original `mak:closed` + PII-strip flow (closed for N cycles → strip contact fields, write `mak:closedAt`, revive on next material diff). Different blast radius (triple deletion) — separate review. ✅ **Completed 2026-05-06.**

---

### Story 3.2c: Lifecycle Vocabulary Drift Fix *(pre-3.3 cleanup)*

> **Added 2026-05-16** from the Story 3.3 planning roundtable. Small cleanup story; must land **before Story 3.3** so the canary validates one coherent model rather than papering over a drift. Design record: `mom_handoff_2026-05-16.md`.

As MOM, I want the lifecycle vocabulary consistent across the ontology, the transformer code, and the planning docs, so that Story 3.3's canary tests a coherent model.

**Acceptance Criteria:**

**Given** `ontology/mom.ttl` defines `mom:operationalState`
**Then** its `rdfs:comment` enumerates exactly the lifecycle values `seeded`, `confirmed`, `aging`, `zombie`, `closed`, `dead` plus out-of-lifecycle `error`, `unlinked`
**And** the comment states the two terminal states explicitly: `closed` = operator/coordinator-declared retirement (authoritative); `dead` = auto-inferred after N failed heartbeat cycles (inferred)
**And** the comment notes the real-time open/closed boolean belongs to `mom:dynamicState`, NOT `mom:operationalState`

**Given** `transformer.effective_marker()`
**Then** it has no branch referencing a lifecycle value the ontology does not define; the stale `closed` branch is removed or remapped to the declared/inferred terminals

**Drift flagged for this story to resolve or escalate to Nicolas:**
- The `mak:` vs `mom:` predicate prefix inconsistency across `epics.md` / `architecture.md` / `mom.ttl` (e.g. `mak:operationalState` vs `mom:operationalState`).
- Story 3.2b's `mak:closed` (auto-applied after N closed-state cycles + PII strip) vs the roundtable's `closed` = operator-declared retirement — **resolved in Story 3.2c (AC#7):** both paths legitimately write `mom:operationalState "closed"`; they differ in causation (system-inferred vs. operator-declared) but share the token intentionally. If sub-distinction is needed in future, track via logs rather than a new state value.

**Dependencies:** none (pure cleanup). **Blocks Story 3.3.**

---

### Story 3.3: Mother Sands Diagnostic Canary

> **Reframed 2026-05-16** by the Story 3.3 planning roundtable. Supersedes the prior "Canary Space — Virtual Space Seed + Lifecycle Demo" scope (continuous time-bubble, fort-rotation automation — moved to Epic 8 lore / a future ledger epic). Full design record: `mom_handoff_2026-05-16.md`.

As MOM (operator), I want a programmatic way to drive a MOM-owned synthetic endpoint ("Mother Sands") through controlled states on each of the three signal axes, so that when the public map shows something incoherent I can attribute the fault to a specific layer — MOM's pipeline vs the space's own endpoint — instead of guessing.

**Single job:** a diagnostic instrument. This story is **not** "reproduce the stuck-`seeded` bug" — that bug is the motivation; pinning and fixing it is **Story 3.4**.

**Concept:**
- **Mother Sands** — the eighth Maunsell sea fort that was never built; a synthetic space MOM owns. Its drawer carries an honest "synthetic reference space" label (one-line truthfulness requirement). Lore, persona (Bernard), and the "broadcast rig" content are **Epic 8** — not this story.
- It is a **true canary**: a **programmable HTTP endpoint** the real heartbeat fetches — not a static file, not a direct store write. Axis-A faults (404/503/timeout) require the endpoint to actually misbehave.

**The three axes** (the canary perturbs exactly **one at a time** — see Story 3.2's truth model):
- **Axis A — Reachability** (`endpoint_health`). Faults → endpoint fault → MOM emits a coordinator CTA (out of MOM's hands). Insight: time-since-last-successful-fetch is itself a health signal — `n > heartbeat period` is a warning.
- **Axis B — Lifecycle freshness** (`operationalState`: seeded/confirmed/aging/zombie + terminals closed/dead). Faults → MOM's responsibility to fix. The freshness clock resets only on a **field-scoped meaningful change**; `sensors.*` churn must not reset it.
- **Axis C — open/close boolean** (`openNow`). 3.3 proves propagation when present and graceful handling of **absence** (no `open` field → "no live signal", not a false closed). Opt-out UX is **Epic 5**.

**Acceptance Criteria** — operator-framed (inject state → observe outcome), bug-independent:

**Given** the canary scenario library (Option A — code-defined pure functions, each with a 4-section docstring: INJECT / STATE / EXPECT MARKER / EXPECT CARD)
**When** the operator runs an axis-prefixed `make` target
**Then** the canary endpoint is mutated via a safe write protocol (temp file → fsync → atomic rename → ETag/Last-Modified invalidation in `heartbeat_log.db`) and the real heartbeat observes the injected state

**Axis A** — `canary-a-reachable | -a-timeout | -a-dns-fail | -a-http-error`: each resolves `endpoint_health` to the expected rung; a fetch older than the configured `heartbeat_period × multiplier` resolves to `warning` regardless of body validity (current gap: "fetched 5h ago" wrongly classifies healthy)

**Axis B** — `canary-b-seeded | -b-confirmed | -b-aging | -b-zombie | -b-closed`: each resolves `operationalState` to the expected state; a fetch whose only delta is `sensors.*` does NOT advance the lifecycle last-update timestamp, while an `openNow` flip does

**Axis C** — `canary-c-openclose-open | -c-openclose-shut`: the boolean propagates end-to-end; a payload with no `open` field does not break the pipeline and yields no false open/closed

**Given** a known injected `(endpoint_health, lifecycle, openNow)` triple
**Then** the resolved public marker equals `effective_marker(...)`, and the canary emits a **per-layer coherence-diff report** (endpoint file → heartbeat record → Oxigraph → rendered card) — not a boolean; an internally inconsistent map is a FAIL even if no single probe is red

**Given** the canary data
**Then** it lives in named graph `<urn:mak:canary>`, isolated from real-space graphs; a SPARQL `ASK` isolation test proves no canary triples leak into production queries
**And** `make canary-reset` restores the canary from the committed baseline `data/canary/baseline.json`
**And** `make canary-demo-cycle` chains scenario targets across a lifecycle (seed → … → closed/dead) for the federated PoC demo

**Given** the third Oxigraph named graph (previously conceived as a "tombstone" graph)
**Then** it is named **`public_ledger`** — an append-only, immutable, IPFS/IPLD-anchored event ledger; the name and append-only principle are locked here. (Event schema, IPFS pinning, minting authority, and relocation modelling are a **dedicated future epic** — not this story.)

**Two test surfaces:** hermetic `pytest` (mocked fetch, deterministic, CI — incl. the `<urn:mak:canary>` isolation test) **and** a live operator-poke loop (`docs/canary-operator-runbook.md`).

**Dependencies:**
- **Story 3.2c** (lifecycle vocabulary fix) — blocks this story
- Story 3.2 complete (three-axis truth model in place)
- `mom.mapsofmaking.org` subdomain configured in hetzner-gateway nginx
- `simulatedAge` lifecycle-injection seam overrides the classifier **input** (synthetic last-update), never an `if canary:` branch inside the classifier

**Deferred:**
- Relocation modelling / fort rotation U2–U7 → Epic 8 lore + the future `public_ledger` epic
- Mother Sands broadcast/comms content, Bernard activation → Epic 8
- Persisted/replayable scenario library (Option B) → Epic 4+, only if needed

---

### Story 3.4: Stuck-`seeded` Root Cause + Regression Test

> **Added 2026-05-16.** Sequenced **after Story 3.3** — the canary's diagnostic tooling pins down (and likely resolves) the root cause. Design record: `mom_handoff_2026-05-16.md`.
>
> *(The magic-link generation and coordinator-email stories formerly numbered 3.3/3.4 live in **Epic 4b** — parallel, non-blocking. They are not part of Epic 3.)*

As MOM, I want the root cause of directory-imported spaces stuck on `seeded` despite a successful fetch identified and locked by a regression test, so the recurring Epic 3 fetch/update-timer bug cannot silently return.

**Context:** some SpaceAPI-directory-imported spaces show `last-fetched ~5h ago` yet remain `seeded` with `lastUpdated unknown`, even though their JSON validates, ingests, and geolocates. Three hypotheses (see handoff brief): (a) ingestion fetched 200 but never wrote `mom:lastUpdated`; (b) it wrote it but `classify_lifecycle` misreads it during materialization; (c) first-fetch diff compares against an empty baseline and skips the write.

**Acceptance Criteria:**

**Given** the stuck-`seeded` behaviour
**Then** a failing regression test under `tests/` pins it **before** the fix — asserting the exact wrong state — and survives whoever fixes it

**Given** the Story 3.3 canary
**Then** it is used to reproduce the stuck-`seeded` state and discriminate between the three hypotheses; the confirmed root cause is documented

**Given** the fix
**Then** a freshly-fetched space transitions `seeded → confirmed` correctly and the regression test passes

**Dependencies:** Story 3.3 (diagnostic tooling).

---

### Story 3.5: `core.ttl` + `crosswalk.csv` — Operationalize the Three-Layer Schema

> **Added 2026-05-16** from the schema-architecture handoff (`mom-schema-architecture-handoff.md`). Belongs to the ingestion pipeline (it formalizes what ingestion maps *to*), so it closes Epic 3 rather than opening Epic 4. Sequenced last in Epic 3; no hard dependency on 3.3/3.4.

As MOM, I want the three-layer schema model (SpaceAPI v15 input → `core:` base → community extension namespaces) operationalized as concrete, dereferenceable artifacts, so that the SpaceAPI→`core:` mapping ingestion already performs is documented, validatable, and ready for a second community.

**Context:** ingestion already maps SpaceAPI v15 fields to MOM predicates (ADR-015), but the `core:` base vocabulary and the cross-namespace overlap rules exist only as prose in the handoff. The handoff names two missing deliverables — `core.ttl` (Layer 2 base schema) and `crosswalk.csv` (overlap-resolution table) — both needed before Article 2 publication. Canonical namespace stays the existing `https://nicolasdb.github.io/mapsofmaking_ontology/ns#` (the handoff's `w3id.org/maps-of-making/` strings are illustrative — the Claude chat that produced the handoff had an incomplete picture).

**Acceptance Criteria:**

**Given** the Layer 2 field list in the handoff
**Then** `core.ttl` exists with at minimum the identity, MOM-operational, and `core:relationships` properties, dereferenceable under the canonical namespace

**Given** the SpaceAPI v15 → MOM mapping ingestion performs
**Then** `crosswalk.csv` documents each row (SpaceAPI field, `core:` field, `fab:` field, mapping type) with `omt:`/`edu:` rows present but marked `status: draft`

**Given** the permissive-ingestion rule
**Then** the pipeline is verified to log unrecognised fields as `mom:OntologyGap` triples — never reject — and `validate_crosswalk.py` confirms no extension field redefines a `core:` field

**Dependencies:** none hard. **Not demo-blocking.** `omt:`/`edu:` namespace design is explicitly out of scope (needs community input).

---

## Epic 3.5: Freshness Propagation Contract *(pre-Epic-4 — built standalone first)*

A pre-Epic-4 slice that closes the recurring "pytest passes but the live pipeline breaks"
bug class identified in the Epic 3 retrospective (`epic-3-retro-2026-05-18.md`) and the
party-mode roundtable that followed it.

**Why this epic exists.** Epic 3 shipped a five-stage chain for one fact about a space —
endpoint JSON → `heartbeat_log.db` (SQLite) → Oxigraph named graph → `web/data/spaces.geojson`
→ browser. Every retro bug lived at a *seam* between two stages, because each stage stamped its
own "now" and `heartbeat_log.db` accumulated independently-stamped derived columns
(`last_update`, `last_fetched`, `last_content_updated`, `last_lifecycle_state`,
`last_endpoint_health`, `is_closed`…). A stale payload looked fresh whenever the stage that last
touched it ran recently.

**The model — the snapshot is the unit.** A fetch of a reachable endpoint produces one
**snapshot**: the JSON payload + the UTC instant it was observed (`observed_at`) + the space
UID. The snapshot is the single source of truth; every lifecycle fact is *derived* from it,
never independently stamped. `observed_at` is minted once, at fetch, and carried byte-identical
to the browser, which derives the lifecycle bucket from `age = now − observed_at`. This is the
propagation contract that the ontology layer and the trust-UX layer both depend on; it must
exist before either is built on.

**Clean rebuild, not a patch.** The corrected approach (operator decision, 2026-05-19) does NOT
graft `observed_at` onto the noisy `heartbeat_log` schema or the fat transformer. Story 3.6
builds a **new, clean snapshot pipeline alongside the existing one**, exercised on the Mother
Sands canary only. The old pipeline keeps serving registered spaces untouched — zero regression
risk during 3.6. Stories 3.7–3.10 migrate registered spaces onto the clean path and **delete**
the old `heartbeat_log` noise columns and old transform-time stamping wholesale — replace, never
patch. Everything is on git; a rebuild is reversible, a patched-on-noise foundation is not.

**Fetch triggers (all produce a snapshot the same way):** the coordinator registration drawer,
the cron heartbeat, and the card "refresh from endpoint" button.

**What the map carries vs. what the card loads.** The materialized GeoJSON carries only
render-critical fields — geolocation, UID, `observed_at` (age-math + marker state). All other
space fields are loaded on demand when the space-profile card opens. The canary path is minimal
from 3.6; GeoJSON slimming for *registered* spaces lands as they migrate in Story 3.9.

**The three freshness tokens (correct-course 2026-05-19):**

| Token | Minted by | Advances when | Home | Axis |
|---|---|---|---|---|
| `observed_at` (ISO-8601) | us | every responsive fetch (200 or 304) | SQLite `snapshot_store.db` only | **A — endpoint health** |
| `updated_at` (ISO-8601) | us, on content diff | content JSON meaningfully differs | Oxigraph `mom:updatedAt` | **B — content maintenance** |
| `state.lastchange` (Unix s) | the space (source claim) | they flip open/closed | Oxigraph `mom:lastOpenChange` (already exists) | **C — operational liveness** |

**Storage holds facts, never derived buckets.** `operationalState` and `endpointHealth` are
`f(token, now, thresholds)` — computed at consumption time (browser) from the three tokens plus
a `thresholds` block shipped in the GeoJSON header from `config.yaml`. They are removed from
Oxigraph entirely.

**Ingestion rule:**

| Fetch outcome | `observed_at` (SQLite) | Oxigraph write | `updated_at` |
|---|---|---|---|
| 304 | advance to now | **none** | unchanged |
| 200, content identical | advance to now | **none** | unchanged |
| 200, content changed | advance to now | DROP+INSERT | set to now |

Oxigraph is written ONLY on a real content change. The `build_state_only_update` 304→Oxigraph
path is deleted. The `state` block is added to the `_IGNORED` diff set so `updated_at` tracks
only content changes; open/closed flips count toward Axis C via `state.lastchange`.

`generated_at` (file-level, materialization time) is a separate GENERATE stamp answering
"when was this file built?" — allowed to be `now`, distinct from all three freshness tokens.

**Epic-level done-condition (acceptance test — must flip false→true, demonstrably, live):**
> An operator loads the map; a space whose endpoint has stopped updating past the staleness
> threshold visibly renders as **stale** (aging/zombie/dead), and a space still fetching fresh
> renders **confirmed** — demonstrated live against the operator-controlled Mother Sands canary,
> not a mock.

**Decisions owed before story creation:**
- Numeric staleness thresholds (confirmed→aging→zombie→dead) — in `config.yaml`, config-driven
  so the canary demo can compress them to minutes/seconds.
- Minimal snapshot metadata: UID, `observed_at`, payload (or content hash), and
  `etag`/`last_modified` for the 304 check. The derived lifecycle columns of the old
  `heartbeat_log` are NOT carried forward — they are recomputed from the snapshot.
- This epic IS the multi-cache fix named in the Epic 3 retro as "the main single epic fix" for
  demo v0.2. It is a known blocker for Epic 4 — Epic 4 mission control cannot show health data
  that does not yet propagate.

**Scope guard (do NOT pull in):** retry logic, lifecycle *policy* changes, per-stage
gatekeeping, ontology work. This epic re-architects the freshness path around the snapshot unit
and nothing else.

**Sequencing — clean skeleton first, then migrate-and-delete.** Story 3.6 builds the clean
snapshot pipeline end-to-end on the Mother Sands canary — proving the propagation contract works
*on day one* against new code, not grafted onto the old noise. Stories 3.7–3.10 then each
migrate one seam's worth of the old pipeline onto the clean path and delete the code it
replaces.

**Test gate (every story).** No story merges until its named test is green. Two non-negotiable
rules: (1) **real seams only** — real snapshot store, live Oxigraph, real fixture HTTP server,
real browser render; mocked integration seams do NOT count toward the gate. (2) **operator
visual confirmation** — every story closes with Nicolas visually confirming the behavior on the
live canary, not just a green pytest exit code. Both are required; a scripted pass alone is not
done.

### Story 3.6: Walking Skeleton — Clean Snapshot Pipeline on the Canary

Build a **new, clean snapshot pipeline end-to-end on the Mother Sands canary, alongside the
existing one**. A reachable (HTTP 200) fetch produces one snapshot — `{payload + observed_at +
UID}` — stored in a new clean snapshot store (NOT `heartbeat_log.db`), transformed to triples in
`urn:mak:canary`, materialized into a minimal GeoJSON feature, and rendered as a live age in the
browser. Happy path only, one space. The old `heartbeat_log` / fat-transformer path is NOT
touched and keeps serving registered spaces — zero regression risk. Task 1 is the
`datetime.now()` audit (inventory every stamp on the data path, classify *carry* vs. *generate*)
— it tells Stories 3.7–3.10 exactly what to delete when they migrate registered spaces onto the
clean path. The skeleton may hardcode or shortcut anything *except* the token's identity:
`observed_at` is minted exactly once and is byte-identical at every stage.

**Acceptance Criteria:**
**Given** a successful (HTTP 200) heartbeat fetch of the Mother Sands canary
**Then** one snapshot is created — JSON payload + `observed_at` (UTC, minted once at fetch) +
space UID — and stored in the new clean snapshot store
**And** `observed_at` is copied unchanged into Oxigraph as `mom:observedAt` on `urn:mak:canary`,
into the canary GeoJSON feature's `properties.observed_at`, and read by `web/app.js`
**And** the canary GeoJSON feature carries only render-critical fields — geolocation, UID,
`observed_at`
**And** the browser renders an `age = now − observed_at` value derived from that single token
**And** the existing `heartbeat_log` / transformer path for registered spaces is unchanged
**And** a `datetime.now()` carry/generate audit doc exists, listing every stamp on the
transform/heartbeat data path with a `file:line` and verdict
**Gating test** — `test_observed_at_skeleton_e2e` (full stack, live canary): run one fetch
cycle, assert the same `observed_at` value appears byte-equal in the snapshot store, in the
`mom:observedAt` triple, in `spaces.geojson`, and in the browser-read value. **+ operator visual
confirmation** the canary marker shows a live age.

### Story 3.7: Migrate the Fetch Seam — Snapshot Store + 304/Unreachable Rules

Move registered-space fetching onto the clean snapshot store built in 3.6. Each fetch produces a
snapshot; the store records `observed_at` and `fetch_status`. The old `heartbeat_log.db` noise
columns this replaces are deleted — migrate, then delete.

**Acceptance Criteria:**
**Given** the heartbeat cycle fetches a registered space
**Then** it writes a snapshot to the clean store carrying `observed_at` and `fetch_status` ∈
{`ok`,`not_modified`,`unreachable`}
**And** HTTP 200 → `fetch_status=ok`, `observed_at` = fetch time
**And** HTTP 304 → `fetch_status=not_modified`, `observed_at` ADVANCES to fetch time
**And** unreachable/error → `fetch_status=unreachable`, `observed_at` UNCHANGED from the prior
snapshot
**And** the `heartbeat_log.db` columns now superseded by the snapshot store (`last_fetched`,
`last_content_updated`, `last_endpoint_health`, `last_lifecycle_state`, `is_closed`, …) are
removed
**Gating test** — `test_heartbeat_two_cycle_temporal` (real snapshot store, no mock DB): cycle 1
against a fixture server returning 200 → capture `observed_at`=T1; cycle 2 returns 304 → assert
`observed_at` > T1; cycle 3 with the server killed → assert `observed_at` == cycle-2 value and
`fetch_status=unreachable`. **+ operator visual confirmation** on the canary (kill the endpoint,
watch the age freeze).

### Story 3.8: Migrate the Transformer Seam — `mom:observedAt`, No Re-Stamp *(done — old model)*

> **Completed 2026-05-19 under the single-token model.** `mom:observedAt` was written to Oxigraph. Superseded by Story 3.8b which corrects the transformer to the three-token model. Story 3.8's code is the starting point for 3.8b's diff.

### Story 3.8b: Correct the Transformer Seam — Three-Token Model

> **Added 2026-05-19** (correct-course from Story 3.9 architectural review). Story 3.8 wrote `mom:observedAt` to Oxigraph — wrong axis. `observed_at` belongs in SQLite only (Axis A); Oxigraph carries `mom:updatedAt` (Axis B, content diff) and `mom:lastOpenChange` (Axis C, already exists). Derived buckets removed.

**Acceptance Criteria:**
**Given** a heartbeat cycle that produces a 200 response with a content diff
**Then** `transform_to_sparql` writes `mom:updatedAt` (ISO-8601, set to now) into the space's named graph
**And** `mom:observedAt`, `mom:operationalState`, and `mom:endpointHealth` are NOT written to Oxigraph
**Given** a 304 or 200-identical response
**Then** Oxigraph receives no write at all (`build_state_only_update` is deleted; the 304 path produces zero Oxigraph operations)
**And** `observed_at` in SQLite still advances (already done by Story 3.7's snapshot store)
**And** the `state` block is added to `_IGNORED` diff set so `updated_at` tracks content only
**And** `_read_space_metadata` drops the stale `mom:lastUpdated` query
**And** the dead `content_changed` parameter is removed from `transform_to_sparql`
**Gating test** — `test_transformer_three_token` (live Oxigraph + real snapshot store):
(a) content-changed path → assert `mom:updatedAt` exists, `mom:observedAt` absent;
(b) 304 path → assert Oxigraph triple count unchanged. **+ operator visual confirmation.**

### Story 3.9: Materializer Joins SQLite+Oxigraph — Three Tokens in GeoJSON

Materializer reads `observed_at` from SQLite (Axis A), `updated_at` and `last_open_change` /
`open_now` from Oxigraph (Axes B and C), and writes all three into each GeoJSON feature.
A `thresholds` block from `config.yaml` is added to the GeoJSON header so the browser can
compute all three axes without re-reading config. `_run_clean_canary_pipeline` is removed.

**Acceptance Criteria:**
**Given** the materialization step
**Then** SPARQL drops `observedAt`/`operationalState`/`endpointHealth`/`lastUpdated`/`lastFetched` reads; adds `updatedAt`; keeps `lastOpenChange`/`openNow`
**And** the materializer joins SQLite via `snapshot_store.read_last_ok_observed_at(space_id)` for `observed_at` (Axis A — not from Oxigraph)
**And** each GeoJSON feature carries `observed_at`, `updated_at`, `last_open_change`, `open_now`, and last-fetch-status
**And** the file-level GeoJSON carries `generated_at` (materialization stamp) and a `thresholds` block copied from `config.yaml` (`endpoint_health` and `operational_state` sections)
**And** `_run_clean_canary_pipeline()` is removed from `_heartbeat_job` and `heartbeat_run`
**And** the materializer exits non-zero / logs `THREE_TOKENS_MISSING` if any feature lacks all three tokens
**Gating test** — `test_materializer_three_tokens` (live Oxigraph + real snapshot store): seed spaces, run `scripts/materialize_geojson.py`, assert `observed_at` (from SQLite), `updated_at` (from Oxigraph), and `last_open_change` land byte-correct per feature; assert `thresholds` block present at file level. **+ operator visual confirmation.**

### Story 3.10: Browser Computes Three Axes Live — Canary Demo

`web/app.js` computes all three freshness axes live from the three tokens and the `thresholds`
block in the GeoJSON header. `freshnessText()` is rewired; `effective_marker` is computed from
the three axes, not from a stored bucket.

**Acceptance Criteria:**
**Given** a GeoJSON feature with `observed_at`, `updated_at`, `last_open_change`, `open_now`
**Then** `web/app.js` computes Axis A (endpoint health) live from `observed_at` + last-fetch-status + thresholds
**And** Axis B (content lifecycle: confirmed/aging/zombie/dead) live from `updated_at` + thresholds
**And** Axis C (operational liveness) from `last_open_change` / `open_now`
**And** `effective_marker` is computed live from the three axes (not read from a stored field)
**And** `freshnessText()` is rewired to display the three-axis state; `timeAgo()` is unchanged
**And** thresholds are read from the GeoJSON header `thresholds` block — not hardcoded
**And** coordinator notification fires on bucket transition (aging→zombie→dead) — human safety net
**Gating test** — `test_canary_three_axis_e2e` (full stack, operator-controlled Mother Sands canary):
compress thresholds to seconds; make canary unreachable → Axis A degrades; leave content unchanged
→ Axis B ages independently; `open_now` flip → Axis C updates. Operator confirms all three axes
render correctly and independently. **+ operator visual confirmation** — this IS the epic
done-condition, demonstrated live to Nicolas.

**Dependencies:** 3.6 (skeleton) → 3.7 → 3.8 → 3.8b → 3.9 → 3.10. Blocks Epic 4.

---

## Cleanup Stories

Shared prerequisite stories that gate multiple epics. These are not part of any single epic's feature scope — they resolve cross-cutting schema drift or infrastructure prerequisites that would otherwise require conditional sub-columns in downstream ACs.

---

### Story C.X: Schema Namespace Pass — `ext_mom` → `ext_canary`, `mom:` horizontal fields, SDG migration

> **Added 2026-05-29** from the sprint change proposal (`_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-29.md`). **Blocks Epic 9 AND Epic 4 re-review.** Pattern: same split-out shape as the pre-Story-3.3 drift-fix cleanup Story 3.2c.

As the MOM developer,
I want the schema namespace model aligned with the four-tier architecture before Epic 9 and Epic 4 re-review begin,
So that both tracks build against a stable, correctly-partitioned vocabulary and neither accumulates `ext_mom` debt that would need a second cleanup pass.

**Context:** The current `ext_mom` namespace contains Mother-Sands-only canary fields — it should be `ext_canary`. Cross-network horizontal fields (`opening_hours`, `memberOf`, SDGs) belong in `mom:` (Tier 2), not in `ext_fab` (Tier 3 vertical). `ext_fab.sdgs` in particular is transversal across network types and must move up. The four-tier schema (locked in the 2026-05-29 sprint change proposal):

| Tier | Namespace | Scope |
|---|---|---|
| 0 | core subset | Floor: name + address → derived geolocation |
| 1 | SpaceAPI v15 core | Common to all SpaceAPI apps |
| 2 | `mom:` | Horizontal — most/all networks |
| 3 | `ext_X` | Vertical — silo-specific |

**Acceptance Criteria:**

**Given** `ontology/mom.ttl` currently defines `ext_mom:` fields used only by the Mother Sands canary
**When** Story C.X lands
**Then** `ext_mom:` is renamed to `ext_canary:` throughout `mom.ttl`, `transformer.py`, `ingest.py`, `baseline.json`, and all SPARQL strings — `grep -rn "ext_mom" infra/ scripts/ ontology/ data/` returns zero results outside `CHANGELOG` or historical comments
**And** `rdfs:comment` on the `ext_canary:` namespace reads: "Namespace for Mother Sands canary-specific fields. Not for production spaces."

**Given** `opening_hours`, `memberOf`, and `sdgs` are currently in `ext_fab:` or absent
**When** Story C.X lands
**Then** `mom:opening_hours`, `mom:memberOf`, and `mom:sdgs` are declared in `mom.ttl` as Tier 2 properties with `rdfs:domain mom:MakerSpace` and a one-line `rdfs:comment` citing the transversal rationale
**And** `ext_fab.sdgs` is removed from `mom.ttl` and from the transformer mapping table; references in `crosswalk.csv` (Story 3.5) are updated from `ext_fab.sdgs` to `mom:sdgs`
**And** the transformer maps SpaceAPI v15 source fields → `mom:opening_hours`, `mom:memberOf`, `mom:sdgs` following the same field-mapping pattern used in `ingest.py` for existing `mom:` properties

**Given** the `data/canary/baseline.json` file uses `ext_mom:` fields
**When** Story C.X lands
**Then** `baseline.json` is updated to use `ext_canary:` keys; `make canary-reset` restores correctly from the updated baseline; `test_canary_three_axis_e2e` still passes byte-identically

**Given** the existing VOW + RFF seed data in Oxigraph and `snapshot_store.db`
**When** `make wipe && make reseed` (or equivalent Makefile targets) runs after the rename
**Then** the public map renders unchanged (same pin count, same marker colours); the canary diagnostic cycle (`make canary-demo-cycle`) completes without errors
**And** the gating test `test_namespace_pass` (live Oxigraph + real snapshot store) passes: seed at least one VOW space and run one canary heartbeat cycle; assert `ext_canary:` triples exist in `<urn:mak:canary>` and zero `ext_mom:` triples exist anywhere; assert `mom:sdgs` triple present for any seeded space that had `ext_fab.sdgs` in source JSON

**+ operator visual confirmation:** map renders unchanged post-wipe-reseed.

**Dependencies:** none — this is the cleanup blocker. **Blocks Epic 9 AND Epic 4 re-review.**
Not demo-blocking on its own, but Epic 9 Story 9.2+ and Epic 4 ACs reference `mom:opening_hours` / `mom:sdgs` — must land before those stories begin.

---

## Epic 4: Operator Observability Dashboard

Nicolas (MOM infrastructure operator) opens `/admin`, reads system health at a glance (Oxigraph live, ingestion cycling, spaces reachable), scans the space registry table for failures, and drills into any space for a RAW / INGESTED / DISPLAYED inspection panel that surfaces structural mismatches between layers. This is pipeline observability — the tool that proves the system isn't lying. Luca (VOW) uses the public health map toggle; no admin access needed.

**Replanned 2026-05-28** against post-Epic-3.5 data sources. Original ACs targeted `<urn:mak:status>` + `mak:probeResult` + `/data/snapshots/{id}/latest.json` on disk + a heartbeat marker file — none of which were ever built. Epic 3.5 replaced them with `snapshot_store.db` (Axis A + last payload blob), per-space Oxigraph graphs carrying `mom:updatedAt` (Axis B) + `mom:lastOpenChange` (Axis C), and browser-side `computeAxisA/B/C/Marker` from a thresholds header. This Epic consumes those.

**Auth:** shared password from `.env` via nginx basic auth (FR43, NFR-S1). No login UI to build. Admin nginx routing (Story 4.0-foundation) is already live.

**Depends on:**
- `snapshot_store.db` — Axis A (`observed_at`), `fetch_status`, raw payload blob via `read_snapshot(uid)` (`infra/link_handler/snapshot_store.py:78`).
- Per-space Oxigraph graphs (`<urn:mak:space/{id}>`, `<urn:mak:canary/{id}>`) — Axes B & C, metadata.
- Browser `computeAxisA/B/C/Marker` from `web/app.js` — production rendering path (Story 3.10 pattern).
- `space_pipeline.run_space_pipeline()` (Story 3.11 unified path) — re-probe trigger. `tasks/heartbeat.py` is deleted.

**Blocked by prep work (Story 4.0):** materializer consolidation; `mom:seededAt` write verification; `pill_2_stalled_after_seconds` config addition. See Story 4.0 below.

**Locked principle (no PII filtering):** MoM is IPO over public coordinator endpoints. Per `[[feedback_no_pii_filtering]]` and Epic 3.5 hardening: the dashboard renders endpoint payloads verbatim. No redaction, no PII flags, no "sensitive" warnings. Coordinator authority is absolute. This is the foundation of Zone 3 trust.

---

### Story 4.0: Epic 4 Prep — Consolidate Materializers, Verify Seed Tokens, Add Stall Threshold

As the MOM developer,
I want the three blocking dependencies surfaced in the Epic 3.5 retro resolved before Story 4.1 begins,
So that Stories 4.1–4.4 can be written against a clean substrate without conditional sub-columns or precursor patches.

**Acceptance Criteria:**

**Given** the Epic 3.5 retro's critical-path #2 and three blocking dependencies
**When** Story 4.0 lands
**Then** (a) **Materializer consolidation:** `_SPARQL_SELECT` (`infra/link_handler/main.py`) and `SPARQL_QUERY` (`scripts/materialize_geojson.py`) are extracted into one shared module exporting `build_select_sparql()`, `binding_to_feature()`, `bundle_field_set()`. Both call sites import from the shared module; `grep -rn "_SPARQL_SELECT\|SPARQL_QUERY" infra/ scripts/` returns exactly one definition site.
**And** (b) **`mom:seededAt` verification:** the Story 3.12 seed pipeline (Paths A and B) writes `mom:seededAt` xsd:dateTime when seeding a space. Verified on a fresh `make publish` against `vow` and `rff` bundles by `ASK { GRAPH ?g { ?s mom:seededAt ?t } }` returning true for each seeded space. If missing, this AC adds it.
**And** (c) **`pill_2_stalled_after_seconds` config:** `config.yaml.thresholds.pill_2_stalled_after_seconds` exists with a sensible default (e.g. `heartbeat_interval × 3`). Loaded by `_load_thresholds_from_config` and surfaced in the GeoJSON header.
**And** the canary three-axis E2E test (`test_canary_three_axis_e2e`) still passes byte-identically after consolidation.

**Out of scope:** the legacy `_build_sparql_update` error-path fallback in `main.py:787` (separate deferred-work item; not blocking Epic 4).

---

### Story 4.1: System Health Strip — Three Status Pills

As the MOM operator,
I want to open `/admin` and immediately see whether Oxigraph is up, the ingestion process is cycling, and how many spaces are reachable,
So that I can read the system state in under 5 seconds and know whether anything needs attention.

**Acceptance Criteria:**

**Given** the admin subdomain is open and the shared password has been entered
**When** `admin.html` loads
**Then** a FastAPI endpoint `GET /admin/api/status` is called, assembling:
  - **Oxigraph live:** `ASK {}` query via `sparql_client.run_select()` → LIVE (green) / DOWN (red).
  - **Ingestion cycling (ADR-A):** `MAX(observed_at)` over `snapshot_store.db` vs `now − config.yaml.thresholds.pill_2_stalled_after_seconds` → RUNNING (green) / IDLE Nm (amber) / STALLED (red). **No heartbeat marker file.** The snapshot store IS the heartbeat trace.
  - **Spaces reachable:** `COUNT(fetch_status='ok') / COUNT(*)` over the latest snapshot per space in `snapshot_store.db` → "603 / 606" (green above threshold, amber otherwise). **No `urn:mak:status`, no `mak:probeResult`.** One SQL query serves Pill 2 and Pill 3.
**And** three status pills are rendered at the top of the page: `● Oxigraph LIVE · ● Ingestion RUNNING · ● Spaces reachable 603/606`
**And** a "Last checked: N minutes ago" timestamp shows when `/admin/api/status` last ran (auto-refreshes every 60s without full page reload)
**And** if Oxigraph is DOWN, its pill is red and all other data on the page shows "— unavailable" rather than stale/incorrect data
**And** all data is operational metrics only — no raw endpoint payloads (NFR-S6, aggregation-grounds defense — mass export across the registry enables surveillance the individual public endpoints don't)
**And** **diagnostic disambiguation rendered inline** (per ADR-A consequences): if Pill 3 = 0/N AND Pill 2 STALLED → strip displays "scheduler dead"; if Pill 3 = 0/N AND Pill 2 fresh → strip displays "scheduler alive, network/upstream broken". Operator distinguishes without log-diving.

---

### Story 4.2: Space Registry Table

As the MOM operator,
I want a table of all registered spaces showing freshness on two independent axes plus a combined worst-of-three badge, sortable by stalest first,
So that I can scan for failures at a glance and click into any space that needs investigation.

**Acceptance Criteria:**

**Given** the system health strip is loaded (Story 4.1) AND `snapshot_store.db` has snapshots AND per-space `urn:mak:space/{id}` graphs exist
**When** the admin page renders below the health strip
**Then** a join of `snapshot_store.db` (latest snapshot per space) ⋈ per-space Oxigraph graphs builds a table with columns:
  - Space name
  - Endpoint URL
  - `observed_at` (Axis A — last fetch time)
  - `fetch_status` (`ok` / `not_modified` / `unreachable`)
  - `updated_at` (Axis B — last content change)
  - `open_now` / `last_open_change` (Axis C — dynamic state)
  - **Browser-computed worst-of-three axis badge** per row (matches Story 3.10's `computeMarker()` pattern — single visual signal collapsing three axes)
**And** rows whose worst-of-three axis badge is `aging` / `zombie` / `dead` have a muted red background — the only colour used to signal failure
**And** **seeded-only rows** (no snapshot row exists; space entered the registry via Story 3.12 seed pipeline) show axis badge `seeded` (grey), **not** `unreachable` — these are first-class, not edge case (566+ VOW spaces and future bulk seeds)
**And** the table is sortable by `observed_at` (default: stalest first), `updated_at`, `fetch_status`, and axis badge
**And** a text filter input narrows rows by space name or endpoint URL substring (client-side, no re-query)
**And** each row is clickable, opening the inspection panel (Story 4.3)
**And** a "Re-probe now" button per row triggers `space_pipeline.run_space_pipeline()` (Story 3.11 unified path; `tasks/heartbeat.py` is deleted), shows a spinner, and refreshes the row on completion (FR31)
**And** the re-probe action is written to the operator action log: `{ action: "reprobe_triggered", space_uri, timestamp }` (FR33b)

---

### Story 4.3: Per-Space Inspection Panel — RAW / INGESTED / DISPLAYED

As the MOM operator,
I want to click a space and see three columns side-by-side — the raw snapshot payload, the ingested triples from Oxigraph, and what actually renders on the public card — with inline mismatch flags between layers,
So that I can identify exactly where a discrepancy enters the pipeline without grepping logs.

**Backend shape (ADR-B / B2):** RAW reads the snapshot store payload blob; INGESTED runs `SPARQL DESCRIBE`; DISPLAYED calls the production `_binding_to_feature()` from the consolidated materializer module (Story 4.0) plus browser `computeAxisA/B/C/Marker`. This is the only shape that gives production-rendering equivalence in DISPLAYED — the panel cannot prove the rendering pipeline isn't lying if DISPLAYED runs a parallel re-implementation.

**Acceptance Criteria:**

**Given** the space registry table is showing (Story 4.2)
**When** the operator clicks a space row
**Then** an inspection panel opens (right drawer or accordion below the row) with three columns:

**Column 1 — RAW:**
- Reads `snapshot_store.db.payload` blob via `read_snapshot(uid)` (`infra/link_handler/snapshot_store.py:78`). **No disk artifact at `/data/snapshots/{id}/latest.json`** (never built).
- Displays raw JSON in a monospaced block with `observed_at` and endpoint URL.
- **RAW status — three first-class states:** (a) `responded`; (b) `unreachable (last known {observed_at})`; (c) **`seeded-only (bundle: {name}, seeded at: {mom:seededAt})`** — depends on Story 4.0 AC (b).
- RAW renders the payload **byte-identical**. No redaction, no PII flags, no "sensitive" warnings. The panel is a window onto what the coordinator publishes. (Per `[[feedback_no_pii_filtering]]` — locked principle.)
- This is the Zone 3 source of truth — verbatim, unmodified.

**Column 2 — INGESTED:**
- Runs `SPARQL DESCRIBE <urn:mak:space/{id}>` via `/sparql/query` (schema-agnostic; grows with the bundle).
- Displays as a readable key→value list grouped by predicate prefix (`mom:` / `schema:` / `mak:` / `ext_fab:`); non-`mom:` groups collapsed by default behind a `<details>` toggle.
- Shows triple count and last-ingested timestamp (`mom:updatedAt`).

**Column 3 — DISPLAYED:**
- Calls production `_binding_to_feature()` from the consolidated materializer module (Story 4.0 critical-path #2) + browser `computeAxisA/B/C/Marker`. Production-rendering equivalence per ADR-B.
- Renders as a mini card preview: name, address, status, hours, specialties — plus the computed three-axis badges.

**Mismatch detection (six structural classes, inline ⚠ flags):**
- **(a) Serialization audit (Axis A):** snapshot row `observed_at` == GeoJSON feature `observed_at`. Catches materializer dropping/mangling the token.
- **(b) Config audit:** GeoJSON header `thresholds` == `config.yaml.thresholds`. Catches stale-config-in-shipped-file.
- **(c) Browser liveness:** displayed age tracks DB age within tolerance. The only real liveness check.
- **(d) Cross-source temporal invariant:** `mom:updatedAt` ≤ `observed_at` (Story 3.8b guarantees `updated_at` only writes on 200-with-diff; the gap is the content-stale window). Catches transformer bugs that stamp `updated_at` outside the contract.
- **(e) RAW → INGESTED gap:** payload field present, no triple in DESCRIBE → `spaceapi_extract` extractor bug (Story 3.11 unified library).
- **(f) INGESTED → DISPLAYED gap:** triple in DESCRIBE, not in `_binding_to_feature()` output → materializer drift (depends on Story 4.0 critical-path #2).

**And** the panel is the primary diagnostic tool — no raw log access, no SSH required to diagnose a pipeline discrepancy.
**And** for spaces in terminal state (`closed` / `dead`), the panel **recomputes** death classification from `mom:lastOpenChange` + threshold breach (self-validating) and shows both the derived classification AND the triggering tokens so the operator can audit the derivation. `mom:deathReason` is rendered from DESCRIBE if present. (Ledger writer for `mak:public_ledger` dag-json tombstone records remains a separate dependency — out of scope here.)
**And** **no "download as JSON" affordance** on the panel — read-only diagnostic surface (aggregation-defense + IPO principle; operators screenshot if needed).
**And** **latency budget:** INGESTED + DISPLAYED ≤ 500ms combined; RAW bounded by payload size.
**And** **seeded-only state is a first-class diagnostic surface:** when RAW state is `seeded-only`, INGESTED shows DESCRIBE of bundle metadata (no `mom:updatedAt`), DISPLAYED shows the seeded grey pin, and the panel cross-links to the Epic 4-b claim/registration flow ("awaiting claim"). Recorded as deferred-work link from Story 4.3 → Epic 4-b; B2 backend stays unchanged.
**And** (conditional, only if Story 4.0 critical-path #2 lands partial) DISPLAYED has two sub-columns "as `main.py` renders" / "as `scripts/materialize_geojson.py` renders"; byte-identical post-consolidation (hide one); divergence becomes a seventh mismatch class. **Drop this AC once Story 4.0's grep-one-definition-site check passes.**

---

### Story 4.4: Export Registry + Operator Action Log

As the MOM operator,
I want to export the space registry against the three-token shape and review a log of all operator actions taken through the dashboard,
So that I can produce a dataset snapshot a downstream consumer can replay axis computation against, and audit what was done manually.

**Acceptance Criteria:**

**Given** the admin dashboard is loaded
**When** the operator clicks "Export registry"
**Then** a join of `snapshot_store.db` ⋈ per-space Oxigraph graphs returns, per space: name, URI, endpoint URL, `observed_at`, `fetch_status`, `updated_at`, `last_open_change`, `open_now`, and the browser-computable axis-A/B/C states — exported as CSV and JSON download options (FR33). A downstream consumer carrying the thresholds header can replay axis computation deterministically.
**And** the export excludes raw endpoint payloads on **aggregation grounds** (NFR-S6 — mass export across the registry enables surveillance that the individual public endpoints, accessed one at a time, don't). **This is not a PII defense.** The "coordinator contact details not already public on the map" clause is dropped: MoM does not edit what coordinators publish; coordinator authority is absolute.

**Given** the operator action log section is open
**When** the operator views it
**Then** it displays a reverse-chronological list: timestamp, action type (`reprobe_triggered` / `export_downloaded`), space URI or "all", result (FR33b)
**And** the log is append-only — no delete, no edit (matches `[[project_three_graph_model]]` ledger pattern)
**And** the export action itself is recorded: `{ action: "export_downloaded", format, space_count, timestamp }`

---

### Story 4.5: Admin Delete Space

As the MOM operator,
I want a per-row "Delete" action in the space registry table that fully removes a space from Oxigraph and the snapshot store,
So that test fixtures, broken self-registrations, and obsolete entries can be cleaned out without SSH or hand-written SPARQL. *(Deferred from Story 2.2 — test fixtures like `herberts-lab` accumulate in Oxigraph with no removal path.)*

**Acceptance Criteria:**

**Given** the space registry table is rendered (Story 4.2) and the operator is authenticated via the shared admin password
**When** the operator clicks "Delete" on a row
**Then** a confirmation dialog displays the space name, URI, endpoint URL, and `observed_at` so the operator confirms they're targeting the right row
**And** confirming triggers `DELETE /api/admin/space/{slug}` on `mak-link-handler`, which:
  - Runs `DROP GRAPH <urn:mak:space/{slug}>` against Oxigraph.
  - Runs `DROP SILENT GRAPH <urn:mak:canary/{slug}>` (no-op for non-canary spaces; covers the Mother Sands cleanup case).
  - Deletes all rows for `{slug}` from `snapshot_store.db`.
  - Triggers a rematerialization so the public map no longer shows the pin.
**And** the deletion is written to the operator action log: `{ action: "space_deleted", space_uri, space_name, observed_at_at_deletion, timestamp }` (FR33b) — append-only per Story 4.4 (no undo through the UI; restore requires re-seeding or re-registering)
**And** **canary spaces** (Mother Sands / Unit M) are protected: the API returns `409 Conflict` if `{slug}` matches the configured canary slug, and the UI hides the Delete button for that row — the canary is operationally load-bearing
**And** **seeded-only rows** can be deleted (566+ VOW spaces include some bad-data rows the operator may want to prune); the action log captures the bundle source from `mom:seededAt` provenance so a re-seed can restore intentionally
**And** the endpoint is gated by the existing `/admin` nginx basic-auth (no separate auth layer)
**And** rate-limiting: at most one delete per second per session (defensive — prevents an accidental click-storm from cascading)

---

## Epic 4b: Magic Link Coordinator Recovery *(parallel non-blocking)*

When a space goes stale, the coordinator receives a templated email with a magic link — YES refreshes their pin, NO gracefully archives the space with GDPR closure. Parallel to Epic 4; non-demo-blocking. Depends on Epic 3's notification queue and status graph. Stories originally numbered 3.3–3.4.

**Auth:** none — magic links are publicly accessible by design (token-secured, single-use).
**Depends on:** Epic 3 (notification queue in `<urn:mak:notifications>`, status transitions from Story 3.2).

---

### Story 4b.1: Magic Link Generation + Link-Handler Validation

*(Previously Story 3.3 — content unchanged, re-sequenced to parallel epic)*

As a coordinator receiving a nudge email,
I want a single-click link that either confirms my space is still active or gracefully closes it,
So that recovery requires no login, no form, and no context-switching — just one honest click.

**Acceptance Criteria:**

**Given** `tasks/magic_link.py` exists and `LINK_SECRET` is set in `.env`
**When** a magic link is generated for a space
**Then** the token is `base64url(HMAC-SHA256(uuid + expiry + space_uri, LINK_SECRET))` — stored as hash only in Oxigraph, never in plaintext (AR-MLNK2)
**And** the token has a 72h TTL written as `mak:expiresAt` triple
**And** `GET /claim/{token}?action=yes` on `mak-link-handler`:
- Validates token exists in Oxigraph (`ASK` query)
- Validates token not expired
- Validates token not already consumed
- On valid: writes token-consumed flag (predicate TBD — `mak:consumed` vs `mom:consumed` flagged as AC#6 ambiguity → Story 4b.1 to resolve), resets timer, sets `mom:operationalState "confirmed"`, returns a confirmation HTML page ("Your space is live again 🔵")
**And** `GET /claim/{token}?action=no`:
- Same validation steps
- On valid: marks space `mak:closed`, removes PII contact fields, writes `mak:closedAt`, returns a graceful closure page
**And** a second click on any consumed token returns: "This link has already been used." — no silent failure
**And** an expired token returns: "This link expired {N} hours ago — contact your network admin for a new one."

---

### Story 4b.2: Coordinator Email Notification with Pre-filled Recovery Link

*(Previously Story 3.4 — content unchanged, re-sequenced to parallel epic)*

As a coordinator whose space endpoint has gone stale,
I want to receive an email that tells me exactly what's wrong and gives me a one-click path to fix it,
So that I can recover my pin without needing to remember what a JSON endpoint is or where to go.

**Acceptance Criteria:**

**Given** a space transitions to `mom:operationalState "aging"` or `mom:endpointHealth "broken"` (Story 3.2) and has a space-level contact address in Oxigraph
**When** the dispatch worker reads `<urn:mak:notifications>` queue
**Then** it generates a magic link token (Story 4b.1), fills the notification template, and dispatches an email containing:
- Plain-language subject: "Your space [Name] on Maps of Making needs attention"
- Error summary: what happened and when (last successful fetch date, error category)
- YES link: "My space is still active — refresh my pin" → `/claim/{token}?action=yes`
- NO link: "My space has closed — remove it from the map" → `/claim/{token}?action=no`
- Link expiry notice: "These links expire in 72 hours"
- Footer: link to the space's public map pin and the network admin contact
**And** delivery failure retries 3× with progressive backoff (1h, 6h, 24h); after 3 failures, a `mak:escalated` triple is written (AR-MLNK3)
**And** if the space has no contact address, the notification is skipped and an admin alert is written instead
**And** the dispatch action is written to the operator action log: `{ action: "notification_dispatched", space_uri, reason, timestamp }`
**And** the `mak:dispatched` triple timestamp prevents re-dispatch within 24h for the same space

---

## Epic 5: Map Polish, Progressive Disclosure & Accessibility

The map now runs on real federated data. This epic validates phase-1 UI hypotheses against actual usage, adds provenance and failure states throughout, wires the accessible list view, and gets axe-core into CI. Each story is independently shippable — polish is continuous, not a gate.

**Story 5.0 is the prerequisite foundation for this entire epic.** It migrates the rendering substrate from DOM markers to GL-native layers, unlocks the world view (drops EU `maxBounds`), remaps the colour ladder (`shut` → dimmed-green, Overview Effect continental layer), and establishes viewport-first embed init. Stories 5.1–5.5 assume 5.0 has landed.

---

### Story 5.0: GL Rendering Substrate + World View Unlock

As a map viewer anywhere in the world,
I want the map to render spaces using a GL-native layer that clusters at continental zoom and opens to the full world,
So that the map feels alive at every scale — from a maker's street corner to a continental field of light — and embeds load at the right place from the first frame.

**Acceptance Criteria:**

**Given** `spaces.geojson` is fetched on map load
**When** the map initialises
**Then** all spaces are loaded into a single MapLibre GL GeoJSON source (`map.addSource('spaces', { type: 'geojson', cluster: true, clusterMaxZoom: 7 … })`)
**And** the existing `renderMarkers()` DOM-marker loop is removed — no individual `maplibregl.Marker` elements are created for spaces
**And** `computeMarker()` logic is ported to a JS helper that maps space state → GL paint property values (circle-color, circle-radius)
**And** `filteredSpaces()` drives `map.setFilter()` on the GL source instead of DOM re-mount
**And** `selectSpace()` / `highlightSelected()` use the GL feature-state API

**Given** the map is at zoom ≤ 7 (continental / world scale)
**When** spaces are clustered
**Then** clusters render as GL circles sized by count
**And** cluster fill colour encodes the health composition of member spaces — a status-weighted blend (green-dominant = healthy region; amber/grey = decaying) derived from each member's `computeMarker()` value
**And** MapLibre place/label symbol layers fade to opacity 0 below z6 — coastlines and landmass remain, named labels dissolve (Overview Effect: geography + points only at altitude)
**And** no network or country colouring is applied to clusters — spaces are kin by aliveness, not by directory

**Given** the map is at zoom ≥ 8 (city / street scale)
**When** clusters break apart into individual spaces
**Then** each space renders as a GL circle with colour and radius driven by its `computeMarker()` state
**And** the open-pulse animation is reproduced via a `requestAnimationFrame`-driven `circle-opacity` / `circle-radius` paint update (no CSS `@keyframes`)
**And** the full colour ladder is honoured: `open` (bright algae + pulse), `shut` (dimmed green — **not black**), `confirmed` (blue), `aging` (amber), `zombie` (faint ghost), `dead` (grey, admin only), `broken` (red ×)

**Given** the EU `maxBounds` constraint currently set in `initMap()`
**When** Story 5.0 lands
**Then** `maxBounds` is removed — the map is navigable worldwide
**And** the default `center`/`zoom` is updated from the FR/DE midpoint (zoom 4.3) to a world-overview start (center [10, 20], zoom 2) so the full continental field is visible on first load
**And** at world zoom the status-weighted clusters make the map immediately legible rather than sparse

**Given** a visitor loads `/?space=openfab&lat=51.50&lon=-0.12`
**When** `initMap()` runs
**Then** the map initialises AT `[lon, lat]` zoom 13 — first tile fetch is the local area, not the world overview
**And** when data is ready, the space is selected and its drawer opens without any `flyTo` animation
**And** the share button generates URLs with coordinates appended: `/?space={id}&lat={lat}&lon={lon}`
**And** embed snippets generated by `embedSpace()` include the same coordinate params

**Given** old embed snippets arrive without coordinates (`/?space=openfab&embed=1`)
**When** the page loads
**Then** the map falls back gracefully to default zoom at the space's location once data loads (no crash, no blank map)
*(Server-side 301 redirect for legacy embeds is a follow-up task — not in this story's scope)*

**Done when:**
- `renderMarkers()` is deleted; no DOM marker SVG elements in the map
- All filter interactions use `setFilter()` — re-renders are GPU repaints, not DOM rebuilds
- Status-weighted cluster colours visible at zoom ≤ 7 on real data
- Place-name labels fade out at continental zoom
- `maxBounds` removed; world-navigable map confirmed on VPS
- Share/embed URLs include coordinates; cold load of `?space=` param starts at correct viewport
- `state-colour-ladder.html` and `overview-effect-north-stars.md` are the design reference — any visual deviation is a bug

**Architecture reference:** ADR-017 (`_bmad-output/planning-artifacts/architecture.md`). Colour model: `_bmad-output/planning-artifacts/state-colour-ladder.html`. Continental UX intent: `_bmad-output/planning-artifacts/overview-effect-north-stars.md`.

---

### Story 5.1: Filters + Search Wired to Real Federated Data

As a maker browsing the map,
I want filters and search to work against real space data from Oxigraph,
So that "electronics workshops in Hamburg" returns actual confirmed spaces, not synthetic fixtures.

**Acceptance Criteria:**

**Given** `spaces.geojson` is populated from Oxigraph (Story 1.5) with real VOW + Openfab spaces
**When** the filters drawer is opened
**Then** filter chip counts reflect the actual dataset: network chips show real network tags (`mak:scraped-vow`, confirmed, etc.), country chips show DE / BE and any others present, status chips show real counts per state
**And** specialty/category chips are built from the canonical English tags in `spaces.geojson` (mapped via `category_map.yaml` in Epic 0) — not hardcoded in JS
**And** selecting a filter updates the map pins live with no reload, and the results list in the filter drawer updates count and entries (FR7, FR9)
**And** text search across `schema:name`, city, and `schema:knowsAbout` tags is case-insensitive and accent-tolerant (e.g. "electronique" matches "électronique")
**And** when filters produce zero results, the empty state shows: "No spaces match — try widening your filters" with a "Reset filters" shortcut (FR10, UX-DR11)
**And** the shareable URL encodes active filters + map bounds so a filtered view can be bookmarked or shared (FR8)
**And** filter state persists across drawer close/reopen within the same session (FR9)

---

### Story 5.2: Stale + Broken State UI — Banners, Provenance, Empty States

As a maker clicking a stale or broken pin,
I want to understand clearly why the data may be outdated and what it means,
So that I can make an informed decision about whether to contact the space — and I don't mistake old data for live data.

**Acceptance Criteria:**

**Given** a space has status `stale` (dashed pin) and a maker clicks it
**When** the detail drawer opens
**Then** an amber quiet banner appears at the top of the drawer: "Last confirmed {N} days ago — details may be outdated" (UX-DR3)
**And** the provenance section (Story 2.2) shows the last successful fetch date and the error type from the most recent failed attempt in plain language
**And** a "contact network admin" CTA is shown below the error — links to the network's public contact (never a personal email)

**Given** a space has status `broken` (🔴 pin) and a maker clicks it
**When** the detail drawer opens
**Then** the error category is shown in plain language: "This space's data feed returned 404 (page not found)", "Connection timed out", "Data format error" — never a raw HTTP response (UX-DR10)
**And** the last known good snapshot date is shown with a "historical record" label, clearly distinguished from live data
**And** the drawer still renders all last-known fields (name, address, hours) with a "As of {date}" prefix on each section

**Given** the map has loaded but `spaces.geojson` returns an empty FeatureCollection
**When** a maker views the map
**Then** an inline banner appears: "No spaces loaded — the map data may be temporarily unavailable. Try refreshing." — never a blank map with no explanation (UX-DR13)

---

### Story 5.3: Embed Polish — "Last Confirmed" Caption + Reciprocal Visibility

As a coordinator who has embedded the map on their website,
I want the embedded map to show a visible "last confirmed" date on my space's pin,
So that visitors to my site can trust the data is fresh — and I'm motivated to keep my endpoint alive because a stale embed visibly degrades my own web presence.

**Acceptance Criteria:**

**Given** the map is loaded in embed mode (`?embed=1` or `window.self !== window.top`)
**When** a space is pre-selected via `?space={uri}`
**Then** the embed renders with the space's detail visible and a caption below the map: "Last confirmed {date} · Source: Maps of Making ↗" where the link opens the full map in a new tab (FR17, UX-DR26)
**And** if the space status is stale, the caption reads: "Last confirmed {N} days ago — data may be outdated" in amber — the degradation is visible to visitors on the coordinator's own site (reciprocal visibility incentive)
**And** the web component `<maps-of-making center="{lat},{lng}" zoom="13" space="{uri}">` produces the same output as the iframe embed with no framework dependency (FR16, NFR-I4)
**And** the embed renders correctly in all browser matrix targets (Chrome, Firefox, Safari 16+, mobile Chrome/Safari) without requiring the coordinator to tweak anything

---

### Story 5.4: Accessible List View + axe-core in CI

As a keyboard or screen reader user,
I want to browse filtered spaces as a structured list without relying on the map canvas,
So that the map's content is accessible to me regardless of how I navigate (NFR-A5).

**Acceptance Criteria:**

**Given** the filters drawer is open
**When** a user activates "View as list" (a link/button at the top of the results list in the filter drawer)
**Then** a semantic `<ul>` list renders below the filter chips showing all currently filtered spaces, each as a `<li>` with: space name (`<h3>`), city + country, status label, specialty tags, and a "View detail" button that opens the detail drawer
**And** the list is keyboard-navigable: tab moves between items, Enter on "View detail" opens the drawer, Escape closes it and returns focus to the list
**And** screen readers announce: the list item count when the list renders ("23 spaces matching your filters"), status changes when filters update (`aria-live="polite"` on result count), drawer open/close
**And** pin state changes (e.g. after a re-fetch in the admin that updates `spaces.geojson`) are announced via `aria-live` on the results count
**And** color is never the sole indicator of pin state: stale uses dashed stroke pattern, broken uses × glyph, confirmed uses solid fill — all present in phase-1 CSS and validated in list view too (NFR-A4)

**Given** the project has a CI pipeline (GitHub Actions, manual deploy for PoC)
**When** the axe-core check runs
**Then** `axe-core` is installed and a test script runs `axe` against the map SPA and admin dashboard HTML fixtures
**And** zero violations at WCAG 2.1 AA level are required for CI to pass (NFR-A1)
**And** the axe check is documented as a manual step for PoC (pre-GitHub Actions) with instructions to run locally before each demo

---

### Story 5.5: Phase-1 UI Hypothesis Validation + Tweaks Panel Decision

As a developer and product owner,
I want to review each phase-1 UI element against pilot usage and make an explicit keep/adjust/prune decision,
So that the demo map carries only UI that earns its cognitive load — nothing is present by default inertia.

**Acceptance Criteria:**

**Given** the phase-1 prototype has the following UI hypotheses: Tweaks panel (map style, pin density, pulse), "Ask the map" bot FAB (currently "soon"), Preset & embed drawer, "Add your URL" drawer (now wired in Epic 2)
**When** this story is executed (after at least one real usage session with RFF/VOW/Openfab data)
**Then** each element is reviewed against the principle "does this reduce cognitive load or add it?" and a decision is recorded:
- **Tweaks panel:** demoted from end-user feature to developer/designer tool — hidden behind a keyboard shortcut (e.g. `Shift+T`) rather than a topbar button; keeps functionality, removes topbar clutter (UX-DR6)
- **"Ask the map" bot FAB:** transitions from "soon" teaser to "active" only when Epic 6 is wired; until then remains but label updated to "Coming in Phase 2" with no interactivity change — explicit, honest (UX-DR7)
- **Preset & embed drawer:** kept but moved to a secondary affordance (share icon in detail drawer, not a topbar button) — accessed from context, not always-visible
- **"Add your URL" button:** kept in topbar (primary CTA for coordinator onboarding)
**And** each decision is implemented as a code change and the topbar renders with reduced button count for the demo
**And** the reduced-motion media query and keyboard focus styles are regression-tested after any topbar changes (NFR-A2)

---

## Epic 6: "Ask Bernard" — One Bot, Two Skillsets

*(Parallel; non-blocker for demo. Restructured 2026-06-16 — sprint-change-proposal-2026-06-16.md, mom_handoff_2026-06-16.md. Supersedes the old read-only NL-bot stories 6.1–6.6.)*

> **Superseded 2026-07-02** (`mom_handoff_2026-07-02.md`, party-mode roundtable): live testing found the diagram/model split below (a separate `nl_discovery` skill running raw NL→SPARQL on Sonnet, parallel to `query`'s templated path) had drifted into **two independently-built answer systems disagreeing in prod** — Story 6.9 built a tool-calling agent (`harness/agent.py`, Gemma-first) without retiring the original `nl_to_sparql.py` path this section describes. The handoff **replaces** the routing model below: **Bernard's tool-calling loop (`agent.py`) is the one orchestrator** for `query`/`nl_discovery`/`unknown` — it routes to tools (including a `query_sparql` tool wrapping this section's NL→SPARQL generation), checks a Tier-0 FAQ/semantic cache first, and escalates to Sonnet only as a Tier-2 fallback on validation failure/complexity — never as the default model for a whole intent class. Only `write` keeps its own dedicated skill path (Story 6.2, unchanged). See **Story 6.9** (tool-calling agent, done), **Story 6.10** (fuzzy/query folded into the agent, done), **Story 6.11** (collapses `nl_discovery` into the same agent + retires this section's standalone `nl_to_sparql` dispatch — in progress) for what's actually live. Story 6.0–6.6 below are retained as the historical design trail for the write skillset and channel-adapter work, which this supersession does **not** touch — only the discovery-side diagram/model claims are stale.

**One bot. One voice. Internal routing.** A coordinator typing "update our Tuesday hours to 10–18" and a maker typing "find laser cutters near Hamburg" both reach the same Bernard — a different skill fires, the same voice responds. The platform is transport, not product: Matrix/Discord/Telegram/Mattermost are adapters behind a normalised `Message`. An intent classifier routes to `write | query | nl_discovery | unknown`.

```
channel message → platform adapter → intent classifier → skill router
   ├── write skill                → permission check → JSON patch → git commit via SSH deploy key
   └── query | nl_discovery | unknown  →  agent.run() tool-calling loop (superseded diagram — see box above)
        ├── Tier 0: FAQ/semantic cache hit → matched entry injected as RAG context, model call still runs
        ├── Tier 1: Gemma 4 (default) picks/calls a tool (query_map, query_sparql, read_space, log_gap)
        └── Tier 2: Sonnet escalation, same tools, only on validation failure/empty/complexity heuristic
→ response formatter (Bernard voice, platform-aware) → platform adapter
```

**Framework:** extend `harness/` (🟢 live, Epic 6 baseline — `agent.py`/`agent_tools.py`/`router.py`). **No Nanobot** — deferred indefinitely, native harness confirmed sufficient (Story 6.9 spike outcome). **LLM:** Gemma 4 12B via OpenRouter (LiteLLMProvider, `harness/llm_client.py` pattern) is the default for classification, tool-calling, and formatting; Sonnet is a **Tier-2 escalation inside the agent loop only** (Story 6.11), not a dedicated model for the discovery skill. **Oxigraph is read-only from the bot** — the write path is always JSON patch → git commit → heartbeat re-ingest; the bot never writes triples (NFR-S7).

**Data sovereignty:** coordinators own their endpoint JSON. The bot edits it on their behalf via an SSH deploy key scoped to one repo, one file. MOM generates the key pair, stores the private key encrypted (Fernet), the coordinator pastes the public key into their repo's Deploy Keys (GitLab/GitHub/Codeberg/Gitea — identical flow, Story 9.8 surface), and revokes by removing it. No deploy key registered ⇒ Bernard's degraded path; read/query always works.

---

### Story 6.0: Bot Infrastructure — Adapters, Intent Router, Bernard Config

As the MOM operator,
I want a channel-agnostic bot core with a platform adapter and an intent router,
So that every later skillset plugs into one transport-independent spine with one Bernard voice.

**Depends on:** Epic 1 (Oxigraph running), `harness/` baseline exists.

**Acceptance Criteria:**

**Given** the `harness/` baseline runs cleanly (verify drift from the Epic 1 spike first) and a new `mak-agent-bot` Docker Compose service joins `maps_of_making_internal` (`external: true`, `expose` not `ports`)
**When** Story 6.0 lands
**Then** a `Message` dataclass exists with `text`, `user_id`, `room_id`, `platform`, `raw`
**And** a `ChannelAdapter` protocol is defined: `async receive() → Message`, `async send(response, context) → None`
**And** a Matrix adapter is implemented via `matrix-nio` (async Python, fits the existing stack)
**And** an intent classifier makes one compact LLM call (~200-token context) returning exactly one of `write | query | nl_discovery | unknown` (may return hardcoded `unknown` in a first pass, LLM wired second)
**And** `config.yaml` gains `bot.model`, `bot.platform_tokens`, `bot.matrix_homeserver` and the Bernard voice config is loaded at startup
**And** `!mom ping` is a smoke test: the classifier returns `unknown`, Bernard acknowledges gracefully
**And** the classifier result is logged via structlog with `session_id` bound

**Done gate (operator confirmation):** `!mom ping` in the Openfab Matrix room returns a Bernard-voice response within 5s.

---

### Story 6.1: Deploy-Key Provisioning + SSH Git Access

As a space coordinator,
I want to grant Bernard scoped write access to my endpoint JSON via a deploy key,
So that the bot can edit my data on my behalf without MOM ever hosting or owning the file.

**Depends on:** 6.0 (bot running), Epic 2 (spaces registered with endpoint URLs).

**Acceptance Criteria:**

**Given** a space is registered with an endpoint URL and a room→space mapping is stored in Oxigraph (`mom:botRoom`)
**When** a coordinator runs `!mom link` in the space's Matrix room
**Then** `link_handler` exposes `POST /api/bot/deploy-key/{space_id}` which generates an ed25519 key pair, stores the private key encrypted (Fernet, key from env `BOT_KEY_SECRET`), and returns the public key + tutorial markdown
**And** the bot presents the public key block and step-by-step tutorial in Bernard voice (GitLab → Settings → Repository → Deploy Keys → paste → enable Write access)
**And** `infra/bot/git_ops.py` provides `read_json(space_uri)`, `patch_json(space_uri, field_path, value)` (apply + schema-validate, return commit SHA), and `commit_json(...)` (commit + push) with message format `Update {field_path} for {space_name} · authorized by {matrix_user_id}`
**And** the bot checks for a stored key before any write — no deploy key ⇒ Bernard's degraded path, never a raw error

**Done gate (operator confirmation):** `!mom link` returns a public key + tutorial; after the coordinator adds it, `!mom update space.url "https://example.com"` commits the change and the heartbeat picks it up within 10 min.

---

### Story 6.2: Write Skillset — JSON Patch, Git Commit, Permission Model

As a space coordinator (or a member they trust),
I want to update my space's fields conversationally,
So that I never have to re-run the wizard or hand-edit JSON to change hours, contact, or open/close state.

**Depends on:** 6.1 (git access working). **Absorbs Epic 9 stories 9.6/9.7/9.10** — the Tier 2/3 fields are edited here conversationally, not as wizard tiers.

**Acceptance Criteria:**

**Given** a deploy key is registered and the room has a `mom:space` mapping
**When** a coordinator (Matrix power level 100) runs a write command
**Then** the bot supports: `!mom update {field.path} {value}`, `!mom open` (`state.open=true`), `!mom close` (`state.open=false`), `!mom grant @user {field}`, `!mom revoke @user {field}`, `!mom permissions`
**And** the permission model maps Matrix power levels: 100 = coordinator (any field + grant/revoke); 50 = trusted member (only coordinator-granted fields); 0 = read-only
**And** the member-writable whitelist is fixed and cannot be expanded by the coordinator: `state.open`, `contact.irc`, `contact.matrix`, `contact.twitter`; `space.name`, `location.*`, `url` are coordinator-only regardless of grant
**And** per-room permission policy is stored in Oxigraph (`mom:memberPermission` with `mom:matrixId` + `mom:allowedFields`)
**And** every commit carries `authorized_by: {matrix_user_id}` in the message — this is the audit trail, no separate log
**And** a member without the required grant receives a graceful refusal (Bernard voice, points to `!mom grant`), never "permission denied"

**Done gate (operator confirmation):** `!mom update space.contact.irc "#atelier-commun:libera.chat"` patches the JSON, commits, Bernard confirms; heartbeat re-ingests next cycle; an ungranted member is refused gracefully.

---

### Story 6.3: Read/Query Command Set + Isochrone Tool

As a maker,
I want templated discovery commands and a travel-time radius search,
So that I can find spaces fast without natural-language ambiguity (and without an LLM in the query path).

**Depends on:** 6.0 (bot running), Epic 3 (data in Oxigraph). All queries here are **templated** — the LLM only formats the Bernard-voice response.

**Acceptance Criteria:**

**Given** confirmed spaces exist in Oxigraph
**When** Story 6.3 lands
**Then** the bot supports: `!mom status` (lifecycle + last heartbeat for this room's space), `!mom hours`, `!mom find {tag} {city}`, `!mom nearby {city} {radius}` (Nominatim → bbox → SPARQL), `!mom network {network_name}` (confirmed both directions), `!mom travel {origin} {hours}`
**And** `infra/bot/isochrone.py` runs three steps: (1) resolve origin → coordinates (Oxigraph if a space name, Nominatim if a city), (2) call OpenRouteService `GET /v2/isochrones/{profile}` with `range_type: time` (`driving-car` default; `cycling-regular`/`foot-walking` via `by bike`/`by foot`) returning a GeoJSON polygon, (3) Python `shapely` point-in-polygon filter over all confirmed spaces
**And** `ORS_API_KEY` is read from `.env` (free tier, 2000 req/day); new deps `shapely` + existing `httpx`
**And** results include travel-time estimates and surface seeded-but-unregistered spaces in range as a follow-up offer (Bernard's seeded fallback)

**Done gate (operator confirmation):** `!mom travel Brussels 2h` returns confirmed spaces inside the isochrone with travel times; an ORS timeout (>5s) degrades gracefully to the `!mom nearby` bounding-box fallback.

---

### Story 6.4: NL→SPARQL — Full Natural Language with IoP Ontology Guardrail

As a community member,
I want to ask free-form questions and get grounded answers,
So that discovery isn't limited to the templated command vocabulary.

**Depends on:** 6.3 (template queries working), IoP ontology in Oxigraph (Story 1.4). This is the original Epic 6 NL→SPARQL work, now arriving on proven infrastructure.

> **Superseded 2026-07-02 — see box at top of Epic 6.** This story shipped `nl_to_sparql.py` as a *standalone dispatch path*, routed to directly by the classifier's `nl_discovery` result, always on Sonnet. Story 6.11 folds this capability into `agent.py`'s tool catalog as `query_sparql` and removes the standalone dispatch + the hardcoded Sonnet model — Sonnet becomes an agent-loop Tier-2 escalation, not this skill's default model. The ACs below describe the *mechanism* (ontology-grounded CONSTRUCT context, SPARQL validation gate, `mom:OntologyGap` logging) which Story 6.11 largely reuses; they no longer describe the *dispatch path*, which is gone.

**Acceptance Criteria:**

**Given** the IoP ontology is loaded and the classifier (6.0) routes a message to `nl_discovery` because it matches no template pattern
**When** Story 6.4 lands
**Then** an IoP ontology subset is extracted via SPARQL CONSTRUCT and cached; the model (Sonnet, `temperature=0.0`) is given it as system context and returns only a SPARQL SELECT over `<urn:mak:space/*>` / `<urn:mak:canary/*>` using only ontology predicates
**And** the SPARQL is validated before use — `DROP`/`INSERT`/`DELETE`/`UPDATE` rejected and logged as a security event (NFR-S5); the bot stays read-only on Oxigraph (NFR-S7)
**And** results are formatted in Bernard voice with source-space links + a collapsed "show how I searched" SPARQL block (FR39)
**And** invalid/empty/ambiguous queries log an `mom:OntologyGap` triple (FR41) and Bernard offers clarification, never a dead end (FR40)
**And** Gemma handles classification + formatting; Sonnet is used only for this query-generation step

**Done gate (operator confirmation):** a French / English / German free-form question returns a grounded, source-linked answer; an unanswerable one logs a gap and gets a Bernard clarification.

---

### Story 6.5: Graceful Failure + Bernard Voice Pass

As a user hitting any failure path,
I want Bernard to tell me what he knows, why something is unavailable, and the exact way forward,
So that error states build trust instead of dead-ending.

**Depends on:** 6.0–6.4 all functional. This is a retroactive pass once every failure path is observable — do **not** pre-tune voice in 6.0–6.3 (write functional responses there, polish here).

**Acceptance Criteria (the Bernard voice rules are the AC — handoff 2026-06-16 §"Bernard voice rules"):**

**Given** all 6.0–6.4 paths are functional
**When** Story 6.5 lands
**Then** Bernard **never** emits HTTP status codes, exception names, `null`/`undefined`, "I don't have permission to do that", "Your query returned no results", or "I cannot help with that" without offering what he can do
**And** Bernard **always**: states what he knows first then what he can't reach; explains *why* write is unavailable with the exact path forward (deploy-key tutorial link); for zero results offers the seeded fallback; for permission refusal points to `!mom grant`; for LLM unavailability distinguishes it from data absence and offers template queries while he recovers
**And** commit messages are in Bernard's voice (e.g. `Mark Atelier Commun open · authorized by @luca:matrix.org`)
**And** every failure path identified across 6.0–6.4 is covered by a voice-audited response

**Done gate (operator confirmation):** a walk of each failure path (no key, no grant, ORS timeout, LLM down, empty results) returns voice-compliant Bernard responses.

---

### Story 6.6: Additional Channel Adapters — Discord, Telegram, Mattermost

As a community on Discord/Telegram/Mattermost,
I want discovery and read commands on our own platform,
So that the map is usable where our community already lives (Matrix already shipped in 6.0).

**Depends on:** 6.0 (adapter protocol defined). These add channels, not features.

**Acceptance Criteria:**

**Given** the `ChannelAdapter` protocol from 6.0
**When** Story 6.6 lands
**Then** Discord and Telegram adapters implement the same protocol; Discord uses the defer pattern (`interaction.response.defer(thinking=True)`) for any LLM-involved command (3s timeout); Mattermost uses outgoing webhook → response via incoming webhook
**And** read/query/discovery commands work on all channels with platform-aware formatting (Discord markdown, Telegram `*text*`, Mattermost bare URLs)
**And** the **write skillset is explicitly Matrix-only** for the PoC — the room-based power-level permission model has no Discord/Telegram equivalent
**And** each adapter is tested with at least one real query in a live channel

**Done gate (operator confirmation):** the same discovery question answered correctly on Discord and Telegram; a write command on those channels is gracefully declined as Matrix-only.

---

### Story 6.9: Bernard Tool-Calling Agent (spike) — done

Live-verified pivot away from Nanobot/raw-SPARQL-generation-as-dispatch: `harness/agent.py` + `harness/agent_tools.py` implement a tool-calling loop (`read_space`, `query_map`, `log_gap`, `propose_write`) on Gemma 4, native SDK confirmed sufficient. Story file: `6-9-bernard-tool-calling-agent.md`. Full ACs/detail there, not duplicated here — this entry exists so Epic 6's story list isn't missing the pivot that supersedes Story 6.4's dispatch model above.

### Story 6.10: Fuzzy NL Question Routing — done, round-2 live fixes applied

Routed `unknown`-classified messages (and, discovered mid-story, the dead `query_commands.dispatch()` stub) through `agent.run()`. Live Matrix testing after deploy surfaced and fixed five real production bugs (dead query stub, LLM claiming untaken actions, false `@bernard` mention-trigger, SpaceAPI locality backfill gap) — see story file `6-10-fuzzy-nl-question-routing.md` Dev Agent Record for the full account. That same live testing is what surfaced the `nl_discovery`/`nl_to_sparql.py` divergence Story 6.11 now resolves.

### Story 6.11: Collapse NL Answer Paths — draft

Retires `nl_to_sparql.py` as a standalone dispatch path; folds its SPARQL-generation capability into `agent.py`'s tool catalog; removes the hardcoded Sonnet model; unifies gap-logging (retires the `<urn:mak:gaps>` RDF-graph writer into the existing `capability_gaps` SQLite table). This is the story that makes the diagram/model correction at the top of this epic section actually true in code, not just in docs. Story file: `6-11-collapse-nl-answer-paths.md`.

---

## Epic 7: 🟢 "Open Now" Presence Layer *(parked indefinitely — 2026-05-06)*

> **Reframed 2026-05-06.** Heartbeat (Story 3.1) + honored SpaceAPI `state.open` (Story 3.2) cover the demo's open-now needs from the read side. The push/webhook approach this epic was designed for has no remaining demo value. Section retained as a design-conversation trail — DO NOT create stories under this epic without first re-justifying why heartbeat polling + `state.open` interpretation is insufficient.

A space's 🟢 badge fires when a webhook ping hits the presence endpoint within a TTL window. The schema slot and nginx route were reserved at Epic 1 — activation cost is one handler, one task, and one nginx uncomment.

---

### Story 7.1: Webhook Presence Handler + 🟢 Badge on Map

As a maker browsing the map,
I want to see a 🟢 badge on a confirmed space's pin when that space has recently signalled it's open,
So that I can identify spaces that are live right now — not just confirmed at some point in the past.

**Acceptance Criteria:**

**Given** the `<urn:mak:presence>` named graph slot exists in Oxigraph (reserved at Story 1.4) and the nginx `/webhook/presence` route is uncommented (reserved at Story 1.3)
**When** a space sends a POST to `/webhook/presence` with `{ space_uri, shared_secret, signal_type }` (door sensor / channel activity / fridge ping / manual)
**Then** the handler validates the `shared_secret` (per-space secret stored in Oxigraph, never in the payload)
**And** writes to `<urn:mak:presence>`:
- `<space-uri> mak:lastSeen "{ISO datetime}"^^xsd:dateTime`
- `<space-uri> mak:isOpenNow true`
**And** a TTL cleanup job (runs hourly) sets `mak:isOpenNow false` for any space whose `mak:lastSeen` is older than the configured TTL (default 4h, configurable)
**And** `materialize_geojson.py` includes the `LEFT JOIN` against `<urn:mak:presence>` that was wired (but returning null) since Story 1.5 — now returns `isOpenNow: true` for signalling spaces
**And** the map renders a 🟢 pulse badge on the confirmed pin (existing `.marker-pulse` CSS animation already in phase-1 stylesheet — activate by adding `open` class)
**And** the presence handler is a separate thin FastAPI route added to `mak-link-handler` (no new container needed)
**And** the public map never shows presence for seeded/stale/broken pins — only confirmed spaces can signal open-now

---

## Epic 8: MOM as a Living Space — Mother Sands Broadcast Rig *(parallel, non-blocking; post-demo)*

> **Added 2026-05-16** from the Story 3.3 planning roundtable. **Stub only** — no stories created yet. Design seeds live in `mom_handoff_2026-05-16.md` and `mom_handoff_2026-05-15.md` (Bernard character bible, Mother Sands lore, hermit-crab lifecycle map, `mom_lore.md` skeleton).

Story 3.3 builds Mother Sands as a **diagnostic canary**. This epic gives it its **second identity**: MOM's self-representation on its own map — a meta "broadcast rig" that carries real, purposeful information (MOM's current state, new features, key changelog events, recent real-space activity) wrapped in deliberate sea-fort/pirate-radio lore.

**Scope sketch (post-demo, not on critical path):**
- Public website at `mom.mapsofmaking.org` (MOM explainer, wiki) — distinct from the SpaceAPI endpoint `mom.mapsofmaking.org/mom_v15status.json`.
- `mom_lore.md` (repo-as-source, website-as-rendered) — Bernard character bible, Mother Sands concept, hermit-crab lifecycle → MOM mechanics map.
- Bernard — the hermit-crab lead-admin persona (they/them; "Ron Swanson on a North Sea fort, with notes of *Dredge*"); voice activated gradually via curated changelog entries.
- Curated changelog / feature "broadcast" in Bernard's voice.
- Relocation / fort-rotation U2–U7 as ambient narrative (the slow lifecycle demo; the 30–60s `canary-demo-cycle` is the Story 3.3 artifact).
- Logo-click-to-drawer interaction (zoom to Mother Sands profile rather than open a page) — prototype before enshrining.

**Open product concerns carried here:** disclosed "synthetic reference space" framing (a clean one-liner ships in Story 3.3; fine-tuning is this epic); community contribution governance for Bernard's narration; possible salvage-art monetisation (Phase 3+).

**Depends on:** Story 3.3 (the canary it dresses). Parallel to Epic 5. Not demo-blocking.

---

## Epic 9: Bernard's Workshop — Assisted SpaceAPI JSON Composer *(parallel, post-C.X; post-demo non-blocker)*

> **Added 2026-05-29** from the sprint change proposal and brainstorming session (`_bmad-output/brainstorming/brainstorming-session-2026-05-29-1500.md`). **Depends on Cleanup Story C.X** (schema namespace pass). Parallel to Epic 4 re-review; not demo-blocking. Epic 9 is expected to surface small schema course-corrections before the Epic 4 re-review is finalised — defer Epic 4 re-review until Epic 9 M1+ is in flight.

An assisted SpaceAPI JSON composer at `genjson.mapsofmaking.org`, with Bernard's voice as the UX anchor. **Goal:** convincing, inclusive, effortless onboarding for non-technical space coordinators, with data sovereignty and GitLab Pages self-hosting as the end state. UX over features; minimal cognitive load.

**Bernard voice rules (locked — source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-29.md`):**
- Bernard is the **voice of the copy only** — they/them, never character imagery, no silhouette, no crab, no fort.
- Bernard names themselves **only on the wizard path**, briefly. Never in the drawer. Never in the URL shortcut.
- Forbidden patterns: "most spaces leave this blank," "keep it simple," any nudge that comforts mediocrity OR shames.
- Register: Pyramid-of-Greatness (frankness, sovereignty of choice) with a grain of salt.

**Milestone structure:**
- **M1 — Floor & Core (must-ship):** Stories 9.1–9.5
- **M2 — MoM features & pedagogy:** Stories 9.6–9.8
- **M3 — Modes & extensibility (deferrable):** Stories 9.9–9.11

**Depends on:** Story C.X (namespace pass). Parallel to Epics 5–8 and Epic 4 re-review.

---

### Story 9.1: Subdomain & Infra — `genjson.mapsofmaking.org` DNS + Nginx + Static Scaffold

As a space coordinator arriving at `genjson.mapsofmaking.org`,
I want a fast-loading, mobile-friendly page with no tracking and no login,
So that the wizard is reachable and trustworthy before any content is entered.

**Acceptance Criteria:**

**Given** the hetzner-gateway nginx config and existing cert infrastructure (see `[[infra_gateway_nginx]]`)
**When** Story 9.1 lands
**Then** DNS A-record for `genjson.mapsofmaking.org` points to the hetzner gateway IP
**And** the nginx-gateway config includes a `server` block for `genjson.mapsofmaking.org` with:
  - `ssl_certificate` / `ssl_certificate_key` paths matching the existing cert pattern (Let's Encrypt)
  - `proxy_pass` to `maps-nginx:80` (or equivalent static-file service)
  - `add_header X-Frame-Options SAMEORIGIN` and `add_header Content-Security-Policy "default-src 'self' 'unsafe-inline'"` — no third-party script CDNs
**And** a minimal `web/genjson/index.html` scaffold exists: correct `<title>` ("Bernard's Workshop — MoM"), `<meta charset>`, `<meta viewport>`, a single `<div id="wizard-root">` and a `<script src="genjson.js">` reference
**And** `GET https://genjson.mapsofmaking.org/` returns HTTP 200 with `Content-Type: text/html`
**And** `GET https://genjson.mapsofmaking.org/` over plain HTTP redirects to HTTPS (301)
**And** the page loads with no console errors and no external network requests (CSP enforced)

**Gating test** — manual: `curl -I https://genjson.mapsofmaking.org/` returns 200; `curl -I http://genjson.mapsofmaking.org/` returns 301. **+ operator visual confirmation** page loads in browser, no console errors.

**Dependencies:** hetzner-gateway nginx access (distrobox-host-exec pattern per `[[infra_gateway_nginx]]`).

---

### Story 9.2: Drawer UX on MoM Map — Bernard One-Liner + URL Input + CTA

As a space coordinator browsing the MoM map,
I want a low-friction entry point into the wizard that respects my time and doesn't assume I have a JSON endpoint already,
So that I can choose my path — paste a URL I already have, or start from scratch — in four seconds or less.

**Acceptance Criteria (locked UX decisions from sprint-change-proposal-2026-05-29.md):**

**Given** the "Add your URL" drawer is open (Epic 2 wired path)
**When** Story 9.2 lands
**Then** the drawer contains exactly three elements in order:
  1. Bernard's one-liner (copy from Story 9.5 voice artifact): *"Two ways through. [Tell me about your space]. Or paste a URL if you already have one. Either is fine."* — plain text, no character imagery
  2. An inline URL input: `placeholder="https://yourspace.org/status.json"`, `type="url"`, `id="existing-url-input"` — activates the "fetch & validate" path (Epic 2 Story 2.1 flow)
  3. A CTA button: "Tell me about your space →" — opens `genjson.mapsofmaking.org` in a new tab (or same-tab modal, see note below)
**And** every other element currently in the drawer that does not serve the "decide in 4 seconds" test is removed or moved: no instructional paragraphs, no "how it works" expansion, no sample URLs in body text
**And** the URL input + "Fetch & validate" button remain from Story 2.1 — they are not duplicated; the one-liner replaces the existing copy above them
**And** `localStorage.getItem('genjson_draft')` is checked on CTA click: if a draft exists, the tab opens to `genjson.mapsofmaking.org/?resume=1`; if not, to `genjson.mapsofmaking.org/`
**And** on mobile (`< 768px`) the drawer renders both elements without horizontal overflow and the CTA button is full-width (matches Story 2.6 mobile contract)

**Note:** Modal vs new-tab is a product decision deferred to Story 9.3 implementation; for 9.2 the CTA opens a new tab (`target="_blank" rel="noopener"`). If Story 9.3 implements a modal, 9.2 is updated accordingly.

**Gating test** — axe-core on the updated drawer HTML: zero WCAG 2.1 AA violations. **+ operator visual confirmation** drawer renders correctly on desktop and mobile with no layout overflow.

**Dependencies:** Story 2.1 (drawer exists and is wired); Story 9.5 (voice copy — draft text acceptable for 9.2 if 9.5 not yet done); Story C.X (namespace pass — for `mom:` field labels in future tiers).

---

### Story 9.3: Wizard Core — Tiers 0 + 1 (Name + Address → SpaceAPI v15 Core; localStorage; Export)

As a space coordinator using the wizard,
I want to enter my space name and address and walk through the SpaceAPI core fields at my own pace, with my progress saved automatically in the browser,
So that I can produce a valid SpaceAPI v15 JSON file without understanding the schema — and stop and resume without losing work.

**Acceptance Criteria:**

**Given** the wizard page at `genjson.mapsofmaking.org`
**When** Story 9.3 lands
**Then** the wizard renders as a single-page flow with two tier gates visible in the UI: **Tier 0** (floor) and **Tier 1** (SpaceAPI core)

**Tier 0 — Floor gate:**
**Given** the wizard is freshly loaded (no draft)
**When** the coordinator fills `space` (name) and the address block (`address`, `city`, `postcode`, `country_code`)
**Then** coordinates (`lat` / `lon`) are derived automatically via the Nominatim proxy (Story 9.4) and displayed as a preview on a mini-map tile or inline `{lat}, {lon}` string
**And** the "Continue →" button to Tier 1 is disabled until `space` + address + derived coordinates are present; if Nominatim returns no result, the coordinator can enter `lat`/`lon` manually and the floor gate still passes
**And** the Bernard floor-gate copy renders: *"Name and address. That's the floor. Everything else, I'll derive."*

**Tier 1 — SpaceAPI core:**
**Given** the floor gate has passed
**When** the coordinator is on Tier 1
**Then** the wizard presents the following SpaceAPI v15 core fields as optional progressive inputs: `logo` (URL), `url` (space website), `description`, `contact.email`, `contact.website`, `contact.mastodon`, `state.open` (deferred to Story 9.7 — renders as "skip for now" in 9.3)
**And** each field has a one-line label and a two-line hint (sourced from Story 9.5 voice artifact); no long paragraphs
**And** the Tier 1 exit banner renders: *"Core's in. Other SpaceAPI apps can read this file as-is."*
**And** an "Export JSON" button is available at any point after the floor gate passes; it produces a valid SpaceAPI v15 JSON file containing all filled fields and derived coordinates, downloadable as `{space_name_slug}.json`
**And** the export passes SpaceAPI v15 schema validation (JSON Schema, bundled client-side) — if it fails, a non-blocking inline warning lists the invalid fields; export is not blocked

**localStorage auto-save:**
**Given** the coordinator has entered any field
**When** any field value changes
**Then** `localStorage.setItem('genjson_draft', JSON.stringify(draftObject))` is called; the draft is keyed by `genjson_draft` (single slot — one wizard at a time)
**And** on page load, if `localStorage.getItem('genjson_draft')` is non-null, the wizard pre-fills all fields from the draft and shows the Bernard warning: *"Your progress is saved in this browser. Hard-refresh or clearing site data wipes it. Export at any point if you want a copy outside the browser."*
**And** a "Clear & start over" link resets the draft and the form; confirmation dialog: "This will erase your saved progress. Continue?" — no accidental wipes
**And** if `?resume=1` is present in the URL but `localStorage.getItem('genjson_draft')` is null (draft cleared or cross-device), the wizard loads at Tier 0 with no pre-fill and no error — `?resume=1` is a hint, not a requirement

**Gating test** — `test_wizard_tier0_tier1_export` (browser E2E — Playwright or Cypress; **new test infra dependency, must be set up as part of Story 9.1 or 9.3 before this test can run**): fill name + address → Nominatim call → lat/lon derived → fill two Tier 1 fields → click Export → validate downloaded JSON against SpaceAPI v15 schema → reload page → assert fields pre-filled from localStorage. **+ operator visual confirmation** export JSON validates and map registers correctly via Epic 2 Story 2.1 flow.

**Dependencies:** Story 9.1 (subdomain up); Story 9.4 (Nominatim proxy).

---

### Story 9.4: Nominatim Proxy Endpoint in `link_handler`

> **MERGED into Story 9.3 (2026-05-30).** The wizard cannot E2E-pass or demo without geocoding
> (9.3's gating test calls this proxy, and the CSP `/api/` same-origin seam lives between the two).
> Folded into 9.3 as a single demoable vertical slice. ACs below are retained as the proxy spec
> (now AC6/AC7 of Story 9.3); status `merged` in sprint-status.yaml.

As the wizard front-end,
I want a server-side Nominatim geocoding proxy at `POST /api/geocode`,
So that geocoding requests from the wizard respect Nominatim's rate-limit policy (1 req/s, identified User-Agent) without exposing coordinator IP addresses to a third-party geocoding service.

**Acceptance Criteria:**

**Given** `mak-link-handler` (FastAPI, `infra/link_handler/main.py`)
**When** Story 9.4 lands
**Then** a `POST /api/geocode` endpoint exists accepting `{ "address": str, "city": str, "postcode": str, "country_code": str }`
**And** the handler calls `geopy.Nominatim` with `user_agent="mapsofmaking-genjson/1.0 (contact: nicolas.de.barquin@gmail.com)"`, rate-limited to 1 request/second via a module-level `RateLimiter` (geopy's built-in `RateLimiter` wrapper)
**And** on success it returns `{ "lat": float, "lon": float, "display_name": str }` with HTTP 200
**And** on no-result it returns `{ "lat": null, "lon": null, "display_name": null }` with HTTP 200 (not an error — the wizard handles the null case by showing a manual lat/lon input)
**And** on Nominatim timeout or network error it returns HTTP 503 with `{ "error": "geocoding_unavailable" }` — the wizard shows "Geocoding temporarily unavailable — enter coordinates manually"
**And** the endpoint is rate-limited at the nginx level: max 2 req/s per IP (`limit_req_zone` in nginx config), returning 429 on excess — prevents wizard abuse
**And** the `geopy` dependency is added to `infra/link_handler/requirements.txt`
**And** an existing pattern (`scripts/normalize_vow.py`) uses `geopy.Nominatim` — the proxy follows the same User-Agent and rate-limit pattern (do not diverge)

**Gating test** — `test_geocode_proxy` (live endpoint, real Nominatim): POST `{ address: "Rue Royale 1", city: "Brussels", postcode: "1000", country_code: "BE" }` → assert `lat` ≈ 50.85, `lon` ≈ 4.36. POST an unmatchable address → assert `lat: null`. **+ rate-limit test:** 3 rapid POSTs → third returns 429.

**Dependencies:** Story 9.1 (subdomain infrastructure); `geopy` available in Python environment.

---

### Story 9.5: Bernard Voice Copy Pass — Curated Voice Artifact

As the MoM product,
I want all wizard copy (intro, tier gates, validation messages, sovereignty disclosure) authored in a single curated artifact before any UI story lands its final text,
So that Bernard's voice is consistent across Stories 9.2–9.8 and individual story ACs reference the artifact rather than each containing their own ad-hoc copy.

**Context:** Bernard's voice is the primary UX differentiator of the wizard — it is the mechanism by which a non-technical coordinator trusts the tool and understands what their data will unlock. Getting it wrong in individual stories creates inconsistent register and costly retro edits. This story ships the artifact first; it is a prerequisite for the final copy of Stories 9.2, 9.3, 9.6, 9.7, 9.8.

**Voice rules (locked — see sprint-change-proposal-2026-05-29.md §"Key UX decisions"):**
- Register: Pyramid-of-Greatness (frankness, sovereignty of choice) with a grain of salt
- Forbidden: "most spaces leave this blank," "keep it simple," any nudge that comforts mediocrity OR shames
- Bernard names themselves (they/them) **only on the wizard intro**, briefly
- Bernard **never appears as character imagery** — no silhouette, no crab, no fort

**Acceptance Criteria:**

**Given** the calibrated lines in the sprint change proposal and the Bernard character bible (`_bmad-output/planning-artifacts/mom_handoff_2026-05-15.md`)
**When** Story 9.5 lands
**Then** `web/genjson/bernard_copy.yaml` exists as the single source of truth for all wizard copy, structured as a YAML map keyed by moment:

```yaml
drawer_one_liner: "Two ways through. [Tell me about your space]. Or paste a URL if you already have one. Either is fine."
wizard_intro: "Hi, I'm Bernard (they/them) from 'Mother Sands'. Let's get your space on the map."
floor_gate: "Name and address. That's the floor. Everything else, I'll derive."
tier_1_exit: "Core's in. Other SpaceAPI apps can read this file as-is."
tier_2_exit: "MoM fields filled. Network features unlocked: membership, opening hours, SDGs."
tier_3_exit: "Silo fields in. Your space's vertical features active."
sovereignty_disclosure: "You publish, we make it legible. The rest is history."
localstorage_warning: "Your progress is saved in this browser. Hard-refresh or clearing site data wipes it. Export at any point if you want a copy outside the browser."
field_hints:
  space: "The name your community knows you by."
  logo: "A square image URL. Shows on your map card."
  url: "Your space's main web page."
  description: "One or two sentences. What kind of space is this?"
  contact_email: "A contact address for the space — not a personal inbox."
  opening_hours: "When are you open? We use OSM opening_hours format."
  memberOf: "Which network(s) is this space part of? URL preferred."
  sdgs: "Which UN Sustainable Development Goals does your space contribute to? Numbers only."
validation_messages:
  schema_invalid: "Something's off. Check the fields marked in red — the file isn't valid yet."
  nominatim_unavailable: "Geocoding temporarily unavailable — enter coordinates manually."
  localstorage_resume: "Continuing from where you left off."
  clear_confirm: "This will erase your saved progress. Continue?"
```

**And** `bernard_copy.yaml` is imported by the wizard JS bundle at build time (or fetched once at load and cached) — no copy is hardcoded in HTML or JS except as fallback if the YAML fetch fails
**And** Stories 9.2, 9.3, 9.6, 9.7, 9.8 ACs that reference specific copy lines cite `bernard_copy.yaml` key names rather than quoting strings inline
**And** a `test_bernard_voice_completeness` test asserts that every key referenced in the wizard JS bundle has a corresponding entry in `bernard_copy.yaml`

**Gating test** — `test_bernard_voice_completeness` passes; Nicolas reads the full artifact and approves the register (no forbidden patterns, consistent tone). **No automated tone testing** — tone approval is operator judgement, documented in Story 9.5 completion notes.

**Dependencies:** none — can land in parallel with 9.1–9.4; is a prerequisite for final copy of 9.2, 9.3, 9.6, 9.7, 9.8.

---

### Story 9.6: Wizard Tier 2 — `mom:` Fields (opening_hours, memberOf, mom:sdgs)

> **SUPERSEDED 2026-06-16** (sprint-change-proposal-2026-06-16.md) — absorbed by **Epic 6.2 write skillset**. These Tier 2 fields are better edited conversationally via Bernard once a coordinator has a live file, rather than as a wizard tier. Not built as a wizard story. Body retained as design trail.

As a space coordinator who has completed Tiers 0 + 1,
I want to fill in the MoM-specific horizontal fields that unlock network features (membership, opening hours, SDGs),
So that my space appears correctly in network filters and benefits from the cross-network features MoM provides.

**Context:** These fields are Tier 2 (`mom:` namespace) — unlocked only after SpaceAPI v15 core (Tier 1) is complete. They require Story C.X (namespace pass) to have landed, as `mom:opening_hours`, `mom:memberOf`, and `mom:sdgs` must be declared in `mom.ttl` before the transformer maps them.

**Acceptance Criteria:**

**Given** the coordinator has exported or saved a Tier 1 draft and opens Tier 2
**When** Story 9.6 lands
**Then** the Tier 2 section presents three fields in order, with copy from `bernard_copy.yaml`:
  1. **`mom:opening_hours`** — text input, placeholder `Mo-Fr 10:00-18:00`, hint: *"When are you open? We use OSM opening_hours format."* A "validate hours format" inline check highlights invalid OSM format strings without blocking
  2. **`mom:memberOf`** — URL input (or comma-separated URLs), hint: *"Which network(s) is this space part of? URL preferred."* Accepts free text if URL validation fails — logs as `mom:OntologyGap` on ingestion
  3. **`mom:sdgs`** — multi-select of SDG numbers 1–17 with short labels (e.g. "4 — Quality Education"), hint: *"Which UN Sustainable Development Goals does your space contribute to?"* Renders as a compact chip grid, not a dropdown
**And** the Tier 2 exit banner renders: *"MoM fields filled. Network features unlocked: membership, opening hours, SDGs."* (from `bernard_copy.yaml`)
**And** the export at any point after Tier 1 passes now includes `mom:opening_hours`, `mom:memberOf`, `mom:sdgs` in the output JSON if filled; unfilled Tier 2 fields are omitted entirely (not `null`)
**And** SDG chip selection state is persisted in localStorage alongside other fields

**Gating test** — `test_wizard_tier2_export`: fill Tier 2 fields → export → validate exported JSON contains `mom:opening_hours`, `mom:memberOf`, `mom:sdgs` keys → submit via Story 2.1 registration → assert triples present in Oxigraph (`ASK { ?s mom:sdgs ?o }`). **+ operator visual confirmation** SDG chips render correctly on mobile without overflow.

**Dependencies:** Story C.X (namespace pass); Stories 9.3 + 9.5.

---

### Story 9.7: Wizard `state.open` FSM — Cascading Questions + Marker Mapping + Opt-out

> **SUPERSEDED 2026-06-16** (sprint-change-proposal-2026-06-16.md) — absorbed by **Epic 6.2 write skillset** (`!mom open` / `!mom close` / `!mom update state.open`). Not built as a wizard story. Body retained as design trail; the Axis-C `state.open` semantics here still inform the bot's write behaviour.

As a space coordinator filling in the wizard,
I want to express whether my space signals open/closed status — or choose not to — without encountering jargon,
So that the map marker reflects my actual operational behaviour and Axis C (Story 3.3) propagates correctly.

**Context:** `state.open` in SpaceAPI v15 is an object with `value` (boolean), `message` (optional string), and optionally `trigger` (string). Story 3.3 Axis C semantics: field **omission** = "no live signal" (not false); presence of `value: false` = explicitly closed; presence of `value: true` = open. Opt-out is omission, not a sentinel. The wizard must not coerce the coordinator into a false open/closed signal.

**Acceptance Criteria:**

**Given** the coordinator reaches the `state.open` section of the wizard (Tier 1, after `contact.*` fields)
**When** Story 9.7 lands
**Then** the wizard presents a three-option radio group with plain-language labels — no JSON field names shown:
  - **"Yes — my space is currently open"** → sets `state.open.value = true`
  - **"No — my space is currently closed"** → sets `state.open.value = false`
  - **"Skip — I'd rather not signal this"** → omits `state.open` from the exported JSON entirely (opt-out = field omission per Axis C contract)
**And** selecting "Yes" or "No" reveals an optional `state.open.message` textarea: placeholder "e.g. Open Wednesdays for drop-in. Closed for August." — Bernard hint: *"Optional. If you add a message, it shows on your map card."*
**And** the marker preview (a small coloured dot beside the section header) updates live:
  - `value: true` → 🟢 green dot
  - `value: false` → ⚫ black dot
  - omitted → 🔵 blue dot (confirmed, no live signal)
**And** the "Skip" option is the **default** (no pre-selection of Yes/No) — the coordinator must affirmatively choose to signal open or closed; the wizard never assumes
**And** the SpaceAPI v15 `state` block in the exported JSON reflects exactly the coordinator's choice — no coercion, no defaults injected for omitted fields
**And** the `state.open` FSM propagates correctly end-to-end: a wizard export submitted via Story 2.1 registration, with `state.open.value = true`, results in `mom:openNow "true"^^xsd:boolean` in Oxigraph and a 🟢 badge on the map pin (if the space is `confirmed`)

**Gating test** — three paths: (a) select Yes → export → submit → assert `mom:openNow true` in Oxigraph; (b) select No → export → assert `mom:openNow false` in Oxigraph; (c) select Skip → export → assert `state.open` absent from JSON AND `mom:openNow` triple absent from Oxigraph. **+ operator visual confirmation** marker preview updates live on selection.

**Dependencies:** Stories 9.3 + 9.5; Story C.X (for `mom:` fields consistency).

---

### Story 9.8: GitLab Tutorial Surface — Embedded Guide + Raw URL Handoff to Register Flow

> **Spec revised 2026-06-01:** Original spec used GitLab Pages + logo pedagogy. Revised to the minimal fast path: raw file URL is live on commit, no Pages enablement needed. Logo hosting is self-directed — coordinators return to Bernard's workshop on their own terms.

As a space coordinator who has exported their JSON file but has no hosting,
I want a compact tutorial showing me how to put my file on GitLab and get a raw URL,
So that I can register as an advanced user without needing to ask anyone for help.

**Context:** Many non-technical coordinators ("Maëlle") will export a valid JSON but stall on hosting. GitLab's public repository raw file URL (`gitlab.com/{user}/{project}/-/raw/main/file.json`) is live immediately on commit — no Pages, no deploy wait, no terminal. Four screens, ~2 minutes. The raw URL feeds directly back into the "add your space" register flow (Story 9.2), completing the loop.

**Acceptance Criteria:**

**Given** the coordinator has exported a JSON file (Tier 0 or above)
**When** Story 9.8 lands
**Then** a "Publish your file" section appears below the Export button (collapsed by default, expands on click) containing:

  **Step 1 — Create a GitLab account** — link to `gitlab.com/users/sign_up`; email/SSO + email verification; one sentence.
  **Step 2 — Create a public project** — New project → Create blank project → Visibility: Public; one-sentence + screenshot from `docs/gitlab_tuto/`
  **Step 3 — Upload your JSON file** — `+` button in the repository → Upload file → drag the exported JSON → Commit changes; one-sentence + screenshot
  **Step 4 — Copy the raw URL** — open the file in GitLab → "Open raw" button → copy the URL from the browser; one-sentence + screenshot

**And** below Step 4, a text input pre-filled with `https://gitlab.com/{username}/{project}/-/raw/main/{filename}.json` prompts the coordinator to paste their actual raw URL
**And** a "**Register your space →**" CTA button submits the pasted URL to the "add your space" drawer flow (Story 9.2) — no intermediate validation step; the register flow validates on fetch as it does for any advanced user
**And** the tutorial is static HTML/CSS; only the CTA button requires JS
**And** the tutorial renders correctly on mobile

**Gating test** — manual (M2 acceptance test): Nicolas follows the tutorial with a real GitLab account, uploads a real JSON, copies the raw URL, clicks "Register your space →", confirms the space pin appears on the map. Automated test: `test_gitlabpages_register_cta` — assert CTA button passes the pasted URL into the register/drawer flow.

**Dependencies:** Stories 9.1, 9.3, 9.5; Story 2.1 (`/api/validate-url` endpoint used by register flow).

---

### Story 9.9: Three-Mode Unification — URL Fetch Pre-fill, Validator Mode, Cache Resume Reconciliation *(M3 — deferrable)*

> **SUPERSEDED 2026-06-16** (sprint-change-proposal-2026-06-16.md) — absorbed by **Epic 6**. URL-fetch reconciliation and ongoing edits move to the bot's read + write skillsets. Not built as a wizard story. Body retained as design trail.

> **M3 — deferrable.** Implement after M1 + M2 are validated with real coordinators.

As a space coordinator returning to the wizard with an existing endpoint URL,
I want the wizard to pre-fill from my live endpoint so I can see what MoM currently reads and update only what's changed,
So that maintaining my data doesn't require re-entering everything from scratch.

**Acceptance Criteria:**

**Given** a coordinator opens `genjson.mapsofmaking.org/?url=https://myspace.org/status.json`
**When** Story 9.9 lands
**Then** the wizard fetches the URL via `POST /api/validate-url` (Story 2.1 endpoint), parses the response JSON, and pre-fills all matching wizard fields from the live endpoint payload
**And** fields present in the live payload but not matching any wizard field are shown in a collapsible "Unrecognised fields (preserved)" section — they are included unchanged in the export
**And** if `localStorage.getItem('genjson_draft')` also exists for this URL, the wizard shows a conflict-resolution prompt: "You have a saved draft from {date}. Use it, or start from the live endpoint?" — coordinator chooses; no silent override

**Validator mode:** `GET genjson.mapsofmaking.org/?validate=https://myspace.org/status.json` shows a read-only validation report (checklist: reachable, schema, tiers unlocked, field-by-field annotations) without entering the edit flow.

**Cache resume reconciliation:** if the wizard detects that `localStorage` draft differs from the current live endpoint (by content hash), it shows: "Your draft and your live endpoint differ. Review before exporting." — highlights differing fields in amber.

**Gating test** — `test_url_prefill`: POST a known-valid endpoint URL → assert wizard fields pre-filled correctly; assert unrecognised fields appear in collapsed section. **+ operator visual confirmation** conflict-resolution prompt renders correctly.

**Dependencies:** Stories 9.3, 9.4; Story 2.1.

---

### Story 9.10: Wizard Tier 3 — `ext_fab` Fields (space_type Fuzzy Dropdown, equipment) *(M3 — deferrable)*

> **SUPERSEDED 2026-06-16** (sprint-change-proposal-2026-06-16.md) — absorbed by **Epic 6.2 write skillset**. Tier 3 `ext_fab` fields are edited conversationally via Bernard. Not built as a wizard story. Body retained as design trail.

> **M3 — deferrable.** Implement after M2 is validated; requires `ext_fab.ttl` extraction (Epic 10).

As a makerspace coordinator filling in silo-specific fields,
I want a fuzzy-search dropdown for space type and an equipment multi-select,
So that my space's vertical features (capabilities, equipment) are correctly tagged for maker-specific filtering.

**Acceptance Criteria:**

**Given** the coordinator has completed Tier 2 and advances to Tier 3
**When** Story 9.10 lands
**Then** the Tier 3 section presents:
  1. **`ext_fab.space_type`** — fuzzy-search single-select dropdown populated from the canonical `space_type` vocabulary in `ext_fab.ttl`; typing filters the list; "not listed" is always an option, accepting free text
  2. **`ext_fab.equipment`** — multi-select chip grid populated from the equipment vocabulary in `ext_fab.ttl`; chip selection is additive; a "custom equipment" text input appends items not in the vocabulary
**And** the Tier 3 exit banner renders: *"Silo fields in. Your space's vertical features active."* (from `bernard_copy.yaml`)
**And** selected `ext_fab.*` fields appear in the exported JSON under the `ext_fab` namespace key
**And** the vocabulary lists are bundled as a static JSON file (`web/genjson/ext_fab_vocab.json`) — no runtime SPARQL query from the wizard

**Gating test** — `test_wizard_tier3_export`: select a space type + two equipment items → export → validate exported JSON contains `ext_fab.space_type` and `ext_fab.equipment`. **+ operator visual confirmation** fuzzy search filters correctly.

**Dependencies:** Stories 9.3, 9.5; Epic 10 (`ext_fab.ttl` extraction).

---

### Story 9.11: Validator Error UX — Inline Per-field + Summary Report *(M3 — deferrable)*

> **M3 — deferrable.** Implement after M1 + M2 UX is stable; requires real coordinator usage to calibrate error messages.

As a space coordinator whose JSON failed validation,
I want inline per-field error messages and a summary report that tells me exactly what to fix and why,
So that I can resolve validation failures without asking for help.

**Acceptance Criteria:**

**Given** the coordinator clicks "Export" or "Refresh from URL" and the validation fails
**When** Story 9.11 lands
**Then** each field with a validation error shows an inline red border + one-sentence plain-language explanation (from `bernard_copy.yaml.validation_messages` — add new keys as needed)
**And** a collapsible "Validation summary" section at the bottom of the wizard lists all failing fields with their error category and a one-line fix instruction
**And** the summary distinguishes between: (a) blocking errors (export disabled until resolved), (b) non-blocking warnings (export proceeds but with a banner), and (c) schema upgrade hints (fields that would unlock the next tier)
**And** no raw JSON Schema error strings are shown to the coordinator — all errors are translated to plain language in `bernard_copy.yaml`
**And** on "Refresh from URL" failure, the validation summary matches what `POST /api/validate-url` would return — the wizard and the endpoint are consistent in their error vocabulary

**Gating test** — `test_validator_error_ux`: submit a JSON missing `space` (required) → assert inline error on `space` field + "Export" disabled; submit a JSON with invalid OSM hours format → assert non-blocking warning; assert no raw JSON Schema strings visible in DOM. **+ operator visual confirmation** error messages read naturally in Bernard's register.

**Dependencies:** Stories 9.3, 9.5.

---

### Story 9.12: Wizard Visual Design Pass — Color, Layout & Contrast *(stub)*

> **Added 2026-05-31.** Picks up the styling half of the Story 9.3 deferral (*"fine styling + tone deferred to Story 9.5"*) — Story 9.5 took the **tone + font**; this story owns the **visual design** of the wizard so it ships as its own reviewable slice. Distinct from 9.5 (voice/copy) and 9.11 (validator error UX).

As a space coordinator using the wizard at `genjson.mapsofmaking.org`,
I want the wizard to look finished and legible — coherent color scheme, comfortable spacing, clear tier hierarchy, accessible contrast,
So that the tool feels trustworthy and effortless, matching the polish of the MoM map drawer.

**Scope sketch (to be detailed at story-creation time):**
- **Color scheme** — align the wizard palette with the MoM map's semantic conventions: blue (`--accent-2`) for links/positive/confirmed, red (`--accent`) reserved for errors/broken only (mirrors the drawer `.inline-link` fix, 2026-05-31). No error-red on neutral CTAs.
- **Tier hierarchy** — Tier 0 / Tier 1 / Tier 2 gates visually distinct; hierarchy via size + color contrast, **not** font-weight (Special Elite is single-weight — see bernard-bible §4).
- **Spacing & layout** — field-row rhythm, section separation, the post-export fork-stub buttons, breathing room.
- **Contrast / accessibility** — surface/border/text/placeholder contrast meets WCAG AA; carries forward the 9.3 contrast pass and finishes it.
- **Mobile** — wizard usable on small screens (the map is already mobile-responsive per Story 2.6).
- **Consistency with drawer** — same font (Special Elite, self-hosted), same link treatment (blue + underline), so the drawer→wizard handoff feels continuous.

**Dependencies:** Stories 9.3 (wizard exists), 9.5 (font locked, `.bernard-voice` canonical, copy artifact in place). Should land after 9.5 so styling targets final copy.

**Notes:** Operator (Nicolas) reviews visually, one change at a time (per `memory/feedback_ui_iteration.md`). No automated visual testing.

---

## Epic 10: Multi-Network Schema — Bundles, Concept Commons & Emergent Ontologies *(opened 2026-08-25 — Story 10.1 in progress)*

> **Added 2026-05-18** from the schema role-play design dialogue around Story 3.5. **Stub only.** Design seeds: `schema-roleplay-personas.md`, `mom-schema-architecture-handoff.md`, ADR-016 (written in Story 3.5).

Story 3.5 ships `core.ttl` + `crosswalk.csv` — the static foundation of the three/four-layer schema. This epic *operationalizes the multi-network vision*: MOM serving health, agri, education, culture and other communities from one federated graph, where cross-silo discovery emerges without coordination.

**Scope sketch (post-demo, not on critical path):**
- **`fab.ttl` extraction** — refactor makerspace-specific vocabulary out of the impure `mom.ttl` into the `fab:` community namespace. Care required: code emits `mom:` predicates today.
- **Concept commons** — promote the activity/skill SKOS scheme into its own always-loaded namespace; anchor concepts to Wikidata and OpenKnowHow (OKH / IoP Alliance — *Internet of Production*, distinct from the repo's `iop:` *Internet of Places*).
- **Bundle-loading via `config.yaml`** — deploy a new branded map ("Maps of Healing", "Maps of Growing") by selecting ontology layers + CSS, analogous to `docker-compose`. Bundles are view config; the graph stays universal.
- **The wormhole** — cross-namespace query/traversal UX surfacing `skos:closeMatch` bridges on demand (overlaps Epic 6 "Ask the Map").
- **Emergent community ontologies** — the `gap_log` → curation → concept minting → bridge discovery pipeline. The "private joke" layer: communities grow their own vocabulary; `crosswalk.csv` becomes a living bridge registry.

**Open product concerns carried here:** managed hosting *and* managed-ontology as monetization lanes (Phase 3+ product brief); Solid-pod direction for node sovereignty; governance of concept promotion (local → commons).

> **Update 2026-07-06 (agent-plane counterpart):** this epic is the **data-plane** white-label track (bundles, cartridges, ontology layers). Its **agent-plane counterpart is Epic 13** (Bernardo on Hermes — cloneable bot archetype = profile + env + persona). The archetype and the bundle are the same white-label unit seen from two planes (ADR-018). The **Solid-pod / WebID** direction noted above is a *future, additive* storage + write-auth backend for pod-sovereign nodes — **NOT** the mechanism Epic 13 uses to land agent-plane writes (re-scoped 2026-07-07: Epic 13 writes ride the existing Matrix-power-level + git-deploy-key path; see Epic 13 Story 13.4-write). Pod-backed write-auth is not a prerequisite for retiring harness Bernard.

> **Update 2026-08-25 (epic opened — the "post-demo" framing no longer holds):** this epic was scoped as a
> stub, post-demo and off the critical path. A concrete demo need pulled it forward: MoM can only find
> makerspaces, and the next demo step is **"wood suppliers within 5 km"** — makers need materials, not just
> spaces. OpenFab has a curated Brussels supplier list (`openfab-lab/rtfm`, `faq/fournisseurs.md`, ~55 entries,
> free-form French). Ingesting it forces exactly this epic's central question, and answers it the same way MoM
> already splits spaces: **vocabulary is horizontal and lives in `ontology/` on MoM; content is per-place and
> lives with the place.** If each space minted its own "wood" concept, nothing would cross-reference and
> "suppliers near me" would only ever return the list of the space being asked — so the concept commons is not
> an aesthetic preference here, it is the feature. Suppliers are therefore the epic's first real case rather
> than a design seed. **Story 10.1** ships the shared `mom:` supplier vocabulary + OpenFab's list, geolocated
> and trilingual (FR/EN/NL). Deliberately still out of scope and unchanged by this: `fab.ttl` extraction,
> bundle-loading via `config.yaml`, wormhole traversal UX, managed-ontology monetization. The original scope
> sketch above stands; only its sequencing changed.

**Depends on:** Story 3.5 (`core.ttl`, `crosswalk.csv`, ADR-016). Parallel to Epics 5–8. **Story 10.1 is demo-driven** (the rest of the epic remains post-demo).

> **Update 2026-06-19:** the OKW/IoP-Alliance partnership (see Epic 11) makes this epic's "crosswalk cartridge" vision concrete — OKW is the first real cartridge, OSLO (Flemish education) a likely second. The parenthetical above ("OKH/IoP Alliance — Internet of Production, distinct from the repo's `iop:` Internet of Places") is **resolved**: IoP = Internet of Production Alliance, the repo will map *toward* OKW rather than mint homegrown equipment terms.

---

## Epic 11: OKW / Multi-Ontology Crosswalk Interoperability *(stub — partnership track; 2026-06-19)*

> **Added 2026-06-19** from the party-mode roundtable on Epic 6 bot UX. Triggered by a concrete adoption opportunity, not speculation: the **Internet of Production Alliance** (internetofproduction.org) supports MoM and would **replace their stale Open Know-Where (OKW) map with it**, because their map suffers the exact staleness phenomenon MoM's heartbeat/freshness model solves. Full strategic + architectural detail in `deferred-work.md` ("IoP = Internet of Production Alliance → OKW interop opportunity").

As the MoM operator pursuing network partnerships,
I want MoM to express its data in a partner's ontology (starting with OKW) via a swappable per-audience "crosswalk cartridge,"
So that established communities adopt MoM as their live, trustworthy map without MoM forking its canonical schema or becoming a spec-contractor.

**The model — "crosswalk cartridge":** `mom:` stays the canonical, audience-neutral core (freshness/heartbeat = the universal value). Each customer slots in a swappable ontology overlay — **OKW** (IoP Alliance), **OSLO** (Flemish education), per-community next. Three layers, sequenced:
1. **Crosswalk file (no code, first step):** `ontology/crosswalks/mom-to-okw.ttl` — static `skos:closeMatch`/`relatedMatch`, OKW version pinned in header. The "compliance receipt."
2. **`ext_okw` vertical:** store OKW-native fields as-is; don't coerce `mom:` fields. Additive.
3. **Export endpoint:** `infra/link_handler/routers/export_okw.py` — SPARQL → OKW JSON, explicit Python mapping, no reasoner. MVP proof-of-partnership = one GET → one space as valid OKW JSON.
- **Ingestion = separate importer** (`scripts/import_okw.py`, NOT the heartbeat); separate graph; identity reconciliation deferred.

**Two questions to resolve WITH the Alliance before building:** (1) why did their OKW map stale — heartbeat-fixable or contributor-adoption problem? (2) Who owns MoM's schema on OKW version bumps? Position as "an OKW-compliant implementation," not "the reference implementation."

**Explicitly deferred:** OKH (Open Know-How, "how to fabricate") + IoP-Ontology integration — valuable (Bernard answering "which live space can build this design?") but a separate, later track from bounded OKW compliance.

**Depends on:** Epic 3.5 (freshness contract), Story 1.4 (Oxigraph + crosswalk pattern from `crosswalk.csv`). Overlaps Epic 10's bundle vision. Partnership track — parallel, not demo-blocking.

---

## Epic 12: Bernard Everywhere — Multi-Platform Adapters + Query API *(stub; 2026-06-19)*

> **Added 2026-06-19** from the same roundtable. Forward-looking; seed-only so the intent isn't lost. Each sub-thread is triggered by a concrete demand signal, not built ahead of it.

As a makerspace community,
I want to reach Bernard where we already are (Discord, Telegram) and to embed MoM answers in non-chat surfaces (map-UI drawer, partner sites),
So that discovery isn't locked to Matrix.

**Scope sketch (sub-tracks, each demand-gated):**
- **Multi-platform adapters** — `PlatformAdapter` ABC with `normalize(raw_event) → Message`; Discord/Telegram adapters as additional consumers of the same `harness/` core. **Precondition (harden now, see deferred-work.md):** platform-specific identity must never leak past the adapter; `Message` gains sender display name + channel ID + platform enum; `router.py`/`commands.py` must have zero imports from `matrix_adapter.py`. Permission trap: `read_only_ack` is MXID-gated — decouple before a second adapter bypasses the read-only gate. *Trigger: someone asks for Bernard on an unsupported channel.*
- **Query API (mini-API)** — a thin FastAPI service (`bernard_api`) importing `harness/` core, with a `response_format: chat|json|ui` param. **Do NOT extend `link_handler`** (it already owns geocode + registration + materialization). First consumer = a map-UI drawer; this is close to Epic 4 (operator tool) — check fit there first. *Trigger: the map UI needs to answer a question Bernard already answers.*
- **ext_* feature surface** — the API + crosswalk cartridges (Epic 11) together open the "marketplace of features on new `ext_*` field sets." **Do NOT seed a plugin-execution/marketplace epic yet** — that needs a reasoner + schema registry + trust model; build only after a schema registry has real adoption data. Schema extensibility (add `ext_foo`) ≠ behavioral extensibility (auto-generated commands/cards).

**Depends on:** Epic 6 (Bernard core), the `harness/` import-boundary cleanup. Parallel, post-demo, non-blocking.

> **Update 2026-07-06 (Epic 13 supersession):** the "Multi-platform adapters" sub-track above is **superseded on parity by Epic 13** — the Hermes runtime ships 20+ platform adapters (incl. Discord/Telegram/Matrix) natively, so `PlatformAdapter`-on-`harness/` is not built by hand. The `harness/` import-boundary cleanup this sub-track required is moot once the harness Matrix side retires. The **Query API** and **ext_\* feature surface** sub-tracks survive (still demand-gated) but re-home onto the hermes agent plane rather than importing `harness/` core.

---

## Epic 13: Agent Plane — Bernardo on Hermes *(parallel, non-blocking; twin-until-parity; 2026-07-06)*

> **Added 2026-07-06** from the Winston architecture session + Epic 6 retrospective (`epic-6-retro-2026-07-06.md`). Governed by **ADR-018** (agent-plane / data-plane split, endpoint-as-contract, WebID direction). This is a **migration + parity** epic, not greenfield.

As the MoM operator (and future white-label host),
I want Bernard's behaviour to run on the Hermes agent runtime as a swappable profile pointed at MoM's data plane via a SPARQL-endpoint contract,
So that we stop maintaining a bespoke bot runtime, gain E2EE/multi-platform/durable-state for free, and get a cloneable bot archetype communities can self-host or we can host per-tenant.

**The finding driving this epic (retro):** Epic 6's custom `harness/` was the right *prototype* (it taught Matrix/E2EE/tool-calling from the inside) but the wrong *product* — every hard 6.x problem (channel adapters 6-6, E2EE 6-8, durable multi-turn state flagged in 6-9) is solved-for-free in Hermes. Custom-build the differentiator (MoM data plane: freshness/ontology/heartbeat), adopt boring infra for the commodity (agent runtime).

**The contract (ADR-018):** two planes, one seam = a SPARQL endpoint URL + vocabulary. Agent-plane bots are Hermes profiles = **persona + skills + env**. The endpoint lives in `profiles/<bot>/.env` (`GRAPH_ENDPOINT`), never hardcoded in a skill. Archetype clone = copy profile dir, swap env + persona + ontology cartridge (data-plane counterpart = Epics 10/11).

**Discipline carried from Epic 6 retro:**
- **Twin-until-parity, then explicit retirement.** `@bernardo:mapsofmaking.org` (registered 2026-07-06) runs parallel to harness Bernard on a *distinct* account (no shared-account ghost-bot, per 6-11 round 5). Freeze Bernard-on-harness as the parity benchmark — do NOT modify it during this epic. Retire the harness Matrix side only after Story 13.5 confirms parity. **Enforce supersession at build time** (the 6-4/6-9 `nl_to_sparql`/`agent.py` drift lesson).
- **Live verification is the DoD.** Green tests ≠ working bot (Epic 6's defining lesson). Every story's done-gate is a live Matrix run, not a passing suite.

> **Re-scope 2026-07-07 (WebID/Solid removed from the retirement path).** Reviewing Bernard's actual write mechanism (`harness/commands.py` `_can_write` + `link_handler /api/bot/deploy-key`) confirmed the live write auth is **Matrix power-level ≥ 100 + a git deploy key** — the coordinator (room admin) authorizes writes by adding a bot-generated deploy key to their **git repo (GitHub/GitLab/etc.)**, and the bot patches their JSON there; `link_handler` remains the sole Oxigraph writer (NFR-S7/ADR-015). **No WebID anywhere in the live system.** WebID/Solid is a *future alternative storage backend* (JSON-in-a-pod), NOT a prerequisite for the writes we already do — it was mis-scoped as a Bernard-retirement blocker. Consequences: (1) write parity is a real, scopeable story now (**Story 13.4-write**), not a wait on an unplanned epic; (2) the deploy-key + link_handler + git half is platform-neutral and reusable as-is; only the **auth half** (`power_level >= 100`) is Matrix-specific and needs a thin per-platform "is sender an admin here?" adapter — built for **Matrix, Telegram, Discord only** for now (NOT the full 20+ hermes adapter list; add others on demand). WebID/Solid pod storage stays a genuine future epic (TBD), decoupled from retiring Bernard.

**Story sketch (sequence; each demand/parity-gated):**

- **Story 13.1 — Parametrize the graph endpoint (the enabling change).** Shared `oxigraph-query` skill reads `GRAPH_ENDPOINT` from profile env instead of hardcoded `http://oxigraph:7878`. bianca→OpenFab store, bernardo→MoM store, same shared skill via the symlink pattern. *Done gate: bianca and a scratch profile hit different stores live with one shared skill.*
- **Story 13.2 — Bernardo profile scaffold + read parity against MoM's data plane.** Scaffold `profiles/bernardo/` (`.env` with `@bernardo` creds + `GRAPH_ENDPOINT`→MoM oxigraph, `config.yaml` persona=bernardo, matrix store, E2EE on). Read-only first. **Absorbs 6-7** (twin-account IS dev/prod separation). *Done gate: bernardo answers a discovery question in an encrypted Matrix room, cross-checked against MoM Oxigraph ground truth (the 6-11 AC#10 bar).*
- **Story 13.3 — Persona / voice port.** `bernard_voice.yaml` → hermes persona (SOUL.md / config personality). Resolve the copy-SSOT question (bernard_voice.yaml is SSOT — port, don't fork). *Done gate: side-by-side voice A/B vs frozen harness Bernard reads as the same character.*
- **Story 13.4 — Tool parity: find / read / gaps.** Port the read/discovery tool surface (find, nearby, network, isochrone, read_space, log_gap, IoP-guarded NL→SPARQL) as hermes skills/tools against `GRAPH_ENDPOINT`. **Carries the Epic 6 fabrication-backstop debt** — add a code-level guard (not prompt-only) for the LLM-fabricates-over-failure class (4 recurrences in Epic 6). *Done gate: discovery parity live.* (Write path split out into 13.4-write below — no longer WebID-blocked; see 2026-07-07 re-scope note above.)
- **Story 13.4-write — Write-command parity (deploy-key path, NOT WebID).** Port Bernard's write command surface (`!mom update {field.path} {value}`, `open`, `close`, `grant`, `revoke`, `permissions`, deploy-key setup/tutorial) to hermes as skills/`!mom`-style triggers, reusing the **existing** platform-neutral chain unchanged: `link_handler /api/bot/deploy-key` + git deploy key (GitHub/GitLab/…) + heartbeat re-ingest; `link_handler` stays the sole Oxigraph writer (NFR-S7/ADR-015). The one net-new piece is a thin **platform-admin adapter** feeding the existing `_can_write` gate — normalize "sender is a room/channel admin" across **Matrix (power_level ≥ 100), Telegram (chat admin), Discord (permission bits)** only; other platforms deferred to demand. WebID/Solid pod storage is explicitly out of scope (future epic). *Done gate: a room admin on each of Matrix/Telegram/Discord commits a `!mom update` via bernardo through the deploy-key path, heartbeat re-ingests, an ungranted member is refused gracefully — behavioral parity with frozen Bernard's write path.*
- **Story 13.5 — Parity evaluation + harness Matrix retirement.** Behavioral parity checklist against frozen Bernard-on-harness (built from Epic 6 done-notes = what Bernard actually does), covering **both** discovery (13.4) **and** write (13.4-write) parity. On pass: stop the mom-harness Matrix runtime, keep MoM data plane (pipeline/oxigraph/link_handler/admin) untouched. Flip Epic 6 `6-6`/`6-8` from `superseded-pending` → `superseded`. *Done gate: operator confirms bernardo is the sole @-bot answering MoM discovery **and** committing writes (deploy-key path, no WebID dependency), harness Matrix side down, no capability regression.*

**Explicitly deferred / out of scope:**
- **Multi-tenant provisioning tooling** — Rule of Three: bernardo=tenant #1, bianca=tenant #2; extract tooling only at tenant #3. "Archetype" here = a documented profile-cloning procedure, not a platform.
- **WebID/Solid pod storage + write-auth** — its own future epic (TBD, Epic 10 node-sovereignty concern). This is a *second, alternative* storage/auth backend (JSON-in-a-pod) for the day node owners want pod sovereignty instead of a git repo. **It is NOT a Bernard-retirement blocker** (re-scoped 2026-07-07): Epic 13 lands both reads (13.4) and writes (13.4-write) over the existing Matrix-power-level + git-deploy-key path. Pod-backed write-auth is purely additive, later.
- **`networks/*.yaml` manifest system, persona packs, marketplace** — same trap flagged in 6-11; not this epic.

**Depends on:** Epic 6 (frozen as parity benchmark), Hermes runtime (live locally — manny/bianca profiles exist), MoM data plane (Epic 3.5 freshness contract, oxigraph reachable). **Blocks nothing** — parallel, post-demo. **Cross-ref:** ADR-018; Epic 10 (data-plane white-label + WebID sovereignty — the latter now decoupled from Bernard retirement, see 2026-07-07 re-scope note); Epic 11 (crosswalk cartridges = the vocabulary layer of the archetype); Epic 12 (adapter sub-track superseded here).
