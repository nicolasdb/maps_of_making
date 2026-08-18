# Space card — where every field surfaces

> **The last hop.** [02 · Field traceability](../../reference/field-traceability.md) traces a JSON field *into
> storage*; it stops at the store. This doc closes the loop: **which field surfaces as which element
> on the space-profile card** — the panel that fills the `detail` drawer ([05](05-view-shell.md)) when
> you click a pin. One function builds it: `renderDetail` (`web/app.js:870`). All anchors are exact.

## Three zones, eight sections

The card was designed around **three conceptual zones** (the trust frame), but renders as eight
sections today. The zones still hold:

- **Zone 1 — identity & notifications:** Hero · Status bar · State banner
- **Zone 2 — visitor-actionable:** Quick Facts · Specialties · Embed CTA
- **Zone 3 — the trust receipt:** Source Data (raw JSON)

## Field → section map

| Section | Fields surfaced | Gated by | Anchor |
|---|---|---|---|
| **Hero** | `name`, `logo` (→ placeholder on error), `address` (→ *"address not provided"*), status badge (`computeMarker`), `network_memberships`, `open_for_hosting` | always | `app.js:916` |
| **Canary label** | `observed_at` | `id === 'mother-sands'` only | `app.js:929` |
| **Status bar** | status phrase (from kind), `updated_at` | non-seeded | `app.js:947` |
| **Quick Facts** | `description`, `website`, `opening_hours`, `next_event`, `contact` (→ channel buttons) | non-seeded | `app.js:1003` |
| **Specialties** | `specialties` (pills) | has any | `app.js:1011` |
| **Embed CTA** | — (opens preset for this space) | non-seeded, desktop | `app.js:1021` |
| **State banner / unlocks** | seeded → register prompt · `last_fetch_error`+`observed_at` (broken) · aging/zombie/dead notices · `subset`+`next_unlock` (confirmed unlock steps) | by kind | `app.js:1028` |
| **Source Data (Zone 3)** | `endpoint_url`, raw JSON via `/api/space/{id}/raw`, `observed_at` (timestamp), **encoding-issue flag** (`_detectEncodingIssue`) | non-seeded, **desktop only** (`innerWidth ≥ 768`) | `app.js:1096` |

## Design rules the card enforces

### Empty states are honest, not hidden
Quick-Facts rows render **even when the field is missing**, showing an em-dash placeholder
(`sp-fact-empty`, e.g. `app.js:963,971`). Address falls back to *"address not provided"*
(`app.js:921`). The gap is shown, never silently dropped — a visitor sees what the source *didn't*
publish. (Mirrors the pipeline's no-silent-drops stance at the UI layer.)

### The card is gated by lifecycle kind
`computeMarker(s)` (the [03](../../reference/freshness-axes.md) computation) decides *which* sections render, not
just the badge colour:
- **seeded** — minimal card: hero + a *"Is this your space? Register…"* banner that opens `addurl`
  (`app.js:1028`). No Quick Facts, no Zone 3 — there's no fetched data yet.
- **confirmed** — full card + *"What your data unlocks"* stepped progression (`subset`,
  `next_unlock`, `app.js:1060`).
- **broken / aging / zombie / dead** — full card + a kind-specific heads-up banner sourced from
  `last_fetch_error` / `observed_at` (`app.js:1035`).

So the same function produces a register-me stub or a rich profile depending on one token-derived
kind — no separate templates.

### Zone 3 is a trust receipt, not a debug panel
The Source Data section (`app.js:1096`) is the transparency half of the dual guarantee:
- Renders the raw endpoint JSON verbatim in a terminal frame (`jsonHighlight`, `app.js:1140`), with
  the fetch timestamp (`observed_at`) in the header and a linkable `↗ Open source` to `endpoint_url`.
- Carries an explicit trust line: *"The map only reads & enhances your data — it never edits the
  source."* (`app.js:1143`).
- Degrades loudly: `Source unavailable.` / `Source data exceeds display limit.` on error/truncation
  (`app.js:1125`) — never a blank panel.
- **Desktop-only** by deliberate design (no room on mobile; the trust-evaluator audience is at a
  desk anyway).

### Data-quality anomalies are surfaced, never repaired
When a source serves **double-encoded UTF-8** (mojibake — e.g. `Universität` arriving as
`UniversitÃ¤t`), the card flags it instead of silently cleaning it. `_detectEncodingIssue(s)`
(`app.js:835`) scans the visible text fields (`address`, then `name`/`description`/`opening_hours`/
`next_event`) for the tell-tale `Ã`/`Â`-plus-high-byte signature. On a hit, a coordinator-facing
warning row is injected at the top of the Source Data zone: *"Encoding issue in source — non-UTF-8
characters arrive corrupted … the raw response below is shown unaltered."*

This is a deliberate split: the **derived display** value and the **raw snapshot** both stay
byte-for-byte as the endpoint served them (preserving the non-alteration guarantee above), while the
anomaly is named and pointed at the space owner — turning a confusing glyph into an actionable CTA.
Detection lives purely in the view layer; no pipeline or stored data is touched. _(Scoped at first
sight to two directory spaces: `turmlabor`, `mag.lab`.)_

### The card can re-fetch on demand
Zone 3 includes a **Refresh from endpoint** button (`_makeRefreshBtn`, `app.js:1161`) that POSTs
`/api/heartbeat-space/{id}` — a single-space heartbeat run. This is the only place the *view layer*
triggers the *pipeline*: on success it re-pulls `spaces.geojson` and re-renders (`app.js:1147`);
on `429` it surfaces a rate-limit message with `retry_after_seconds` (`app.js:1180`). It respects
the same fetch cadence the cron uses — the user can't hammer the source.

## Backlog surfaced by this trace (verified against current code)

- ✅ **`open_for_hosting` is live** — renders as a hero badge (`app.js:925`). _(Earlier notes filed
  it as a dormant placeholder; correct that — it surfaces now.)_
- ⬜ **`mom:sdgs` is NOT surfaced** — extracted into storage but absent from `renderDetail`. Still
  the open "intended for the space-profile card" item.
- ⬜ **`founded` / `capacity`** — no card section yet (grant-matchmaking use case, deferred).

---

This completes the schematic set: [01](01-walking-skeleton.md) pipeline · [02](../../reference/field-traceability.md)
net-list · [03](../../reference/freshness-axes.md) marker mechanics · [04](04-design-rules.md) map visual grammar ·
[05](05-view-shell.md) drawer shell · **06 card field-surface** (this doc). A field's full life is now
traceable end to end: *endpoint JSON → store → materialize → marker → card element.*
