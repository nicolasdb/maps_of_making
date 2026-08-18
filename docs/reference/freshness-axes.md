# Freshness axes — computed in the browser

> The pipeline ([01](../explanation/architecture/01-walking-skeleton.md)) ships **raw tokens** on the wire and
> nothing more. Lifecycle state is **never stored** — the browser computes it at
> view time from the tokens + a thresholds block, then picks one map marker.
>
> This is deliberate: `f(token, now, thresholds)` evaluated on render means the same
> stored snapshot ages correctly without any re-fetch or re-materialize. Storage holds
> facts; the map holds the *interpretation*. All logic below is in `web/app.js`
> (Story 3.10) — refs are exact.

## Inputs

| Token | From | Used by |
|---|---|---|
| `observed_at` | every fetch (SQLite → re-injected at materialize) | Axis A |
| `updated_at` | content-change only (Oxigraph) | Axis B |
| `open_now` | `state.open` in the payload | Axis C |
| `last_fetch_status` | fetch outcome (`unreachable` / http) | Axis A |

**Thresholds** are not hardcoded — they ride in the file-level `thresholds` block of
`spaces.geojson` (`ingestGeoJSON`, `app.js:108`). A per-feature `thresholds_override`
beats the global block (canary demo compresses the walk to seconds, `app.js:565`). If
the block is missing the code logs a **contract violation** and falls back to
`FALLBACK_THRESHOLDS` (`app.js:13`) — loud, never silently "everything confirmed".

## The three axes

Each axis is one pure function of a token + thresholds.

### Axis A — endpoint health (reachability) · `computeAxisA` (`app.js:523`)
From `observed_at` **age in minutes** (+ `last_fetch_status`). Answers *can we still reach it?*

| Result | When |
|---|---|
| `broken` | `last_fetch_status === 'unreachable'`, or no `observed_at`, or age ≥ `broken_minutes_threshold` |
| `warning` | age ≥ `warning_minutes_threshold` |
| `unresponsive` | age ≥ `unresponsive_minutes_threshold` |
| `fresh` | newer than all of the above |

Default thresholds: unresponsive 10 min · warning 30 min · broken 60 min.

### Axis B — content lifecycle · `computeAxisB` (`app.js:561`)
From `updated_at` **age in days**. Answers *how long since the content actually changed?*

| Result | When |
|---|---|
| `dead` | no `updated_at` (never observed to change), or age ≥ `dead_days_threshold` |
| `zombie` | age ≥ `zombie_days_threshold` |
| `aging` | age ≥ `aging_days_threshold` |
| `confirmed` | fresher than aging |

Default thresholds: aging 30 d · zombie 90 d · dead 180 d. Null `updated_at` → `dead`
(per AC: do **not** crash, do **not** silently render `confirmed`).

### Axis C — operational liveness (open/close) · `computeAxisC` (`app.js:581`)
From `open_now`. Does **not** age — it's the current source claim.

| Result | When |
|---|---|
| `open` | `open_now === true` |
| `shut` | `open_now === false` |
| `opt-out` | `open_now` absent/null → C contributes nothing |

## Marker allocation — combining the axes · `computeMarker` (`app.js:590`)

One marker per space, by **precedence** (loudest signal wins):

```
B: dead / zombie / aging   →   A: broken   →   C: open / shut   →   confirmed   →   seeded
```

Rationale (in code): long-term silence (B) is louder than a transient endpoint blip
(A); a broken endpoint is louder than the current open/shut claim, because we can't
trust a claim from a source we can't reach.

| Marker | Glyph | Shape | Means |
|---|---|---|---|
| `dead` | 🪦 | emoji only | content silent past dead threshold |
| `zombie` | 🧟 | emoji only | content silent past zombie threshold |
| `aging` | ⚠️ | emoji only | content going stale |
| `broken` | ❌ | red circle + X| endpoint unreachable / stale beyond broken |
| `open` | 🟢 | bright green circle + pulse ring | reachable, fresh, declared open |
| `shut` | 🟢 | deep green circle | reachable, fresh, declared closed-right-now |
| `confirmed` | 🔵 | blue circle | reachable, fresh, opted out of open/close |
| `seeded` | ⚪ | grey circle | known space, no tokens yet (never fetched) |

Marker rendering is **GL-native** — no DOM markers. `computeMarker` sets the `kind`
property on each GeoJSON feature; MapLibre reads it via a `match` expression to pick
the glyph character and colour for the `spaces-glyph` symbol layer (`app.js:379`).
Colour per kind is computed by `glyphColorExpr` (`app.js:335`). *Why* those glyphs and
colours (circles-vs-emoji, the riso palette, the curated legend) is
[04 · Design rules](../explanation/architecture/04-design-rules.md). The `find` drawer exposes a subset as status
chips: `seeded · confirmed · open · shut · broken` (`buildFilterChips`, `app.js:718`).
The decay markers (`aging`/`zombie`/`dead`) render on the map but are not yet
filterable.

---

## Why this lives client-side (design rule)

- **Storage is immutable interpretation-free.** A snapshot taken today reads as `aging`
  next month with no pipeline run — time passes in the browser, not the database.
- **Thresholds are tunable without a re-materialize.** Change the `thresholds` block,
  reload — every pin re-buckets. The canary demo exploits this via `thresholds_override`.
- **No write-race.** The heartbeat writers own the tokens (`extract_mom` is *forbidden*
  from emitting them, asserted at `mom.py:49`); the browser only reads. See
  [02 · Field Traceability §C](field-traceability.md).
