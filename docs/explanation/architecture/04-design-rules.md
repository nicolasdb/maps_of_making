# Design rules — the map surface

> **Why the map looks the way it does.** Companion to [03 · Freshness axes](../../reference/freshness-axes.md):
> 03 owns the *mechanics* (which token → which marker, thresholds, precedence). This doc
> owns the *decisions* — the visual grammar and the reasoning behind it. Where the two
> overlap, **03 is authoritative for the what**; this file never re-lists glyphs or thresholds,
> it explains why they were chosen. All anchors are in `web/maps-of-making.html`.

## The palette is a risograph print, not a UI kit

The whole surface is a two-ink-on-paper print (`:root`, `maps-of-making.html:23`):

| Token | Value | Role |
|---|---|---|
| `--paper` | `#f7f2e7` | ground — the unclaimed / neutral state |
| `--ink` | `#1a1a1a` | structure, and the *shut* marker |
| `--accent` | riso red `oklch(62% 0.18 25)` | alarm — broken endpoint |
| `--accent-2` | cobalt `oklch(55% 0.17 250)` | confirmed (reachable, opted out of open/close) |
| `--green` | `oklch(60% 0.14 150)` | life — open now |

**Rule:** colour carries *one* meaning each — red is always "something's wrong," green is always
"alive right now," cobalt is "known-good but quiet," paper is "nothing claimed yet." A new marker
state must reuse this vocabulary, not introduce a sixth hue. (`oklch` is deliberate: perceptual
lightness stays even across hues, so no one colour shouts louder than its meaning warrants.)

## Two visual classes: circles for live states, emoji for decay

The marker set splits in two on purpose (see 03's allocation table):

- **Live states** (`seeded · confirmed · open · shut · broken`) are **circles** — one shared shape,
  distinguished only by the palette above. They share a grammar because they're all "the endpoint
  is part of the conversation right now."
- **Decay states** (`aging · zombie · dead`) are **emoji-only** (⚠️ 🧟 🪦) — no circle, no fill.
  A gravestone needs no legend; the glyph *is* the explanation. They deliberately break the circle
  grammar because they mean "this has fallen out of the conversation."

This split is why the legend can stay short (next rule).

## The legend shows visitor states only — decay is self-explanatory

The legend (`maps-of-making.html:696`) lists exactly five rows:

```
Seeded · unclaimed   Confirmed   Open now   Closed now   Broken endpoint
```

**Rule (progressive disclosure):** the legend teaches the states a *visitor* acts on — "can I go
there, is it real, is it alive." The decay markers are intentionally **omitted**: their emoji are
self-documenting, and explaining them would surface operator-grade lifecycle nuance to an audience
that doesn't need it. Curated, not complete — completeness lives in 03 for the people who maintain
the system. (The legend also `display:none`s on mobile, `:496` — there isn't room, and the glyphs
carry on alone.)

## The open-pulse is motion-as-liveness, and it's optional

Only the `open` marker animates — a green pulse ring expanding outward (`.marker-pulse` +
`@keyframes pulse`, `:186`). Motion is reserved for the one state that means *right now*; nothing
else moves, so the eye is drawn only to currently-open spaces.

Two guardrails:
- It's a **user toggle** (`data-tweak="pulse"`, `:764`) — liveness is a preference, not forced.
- It's killed under `prefers-reduced-motion` (`.marker-pulse { animation: none }`, `:507`).

## Where the rules live in code

| Decision | Anchor |
|---|---|
| Palette tokens | `:root` `maps-of-making.html:23` |
| Marker fills (circle states) | `.map-marker.<kind> .marker-fill` `:174` |
| Decay glyphs / emoji-only set | `createMarkerSVG`, `MARKER_GLYPH`, `EMOJI_ONLY` — `web/app.js` (see [03](../../reference/freshness-axes.md)) |
| Legend swatches | `.pin-swatch.<kind>` `:146`; legend markup `:696` |
| Open pulse | `.marker-pulse` `:186`, toggle `:764`, reduced-motion `:507` |

## The basemap is altitude-aware

The map has no manual theme toggle. Zoom level *is* the theme. Two surfaces share one continuous
visual grammar, connected by a transition zone:

| Altitude | Zoom | Surface | Feeling |
|---|---|---|---|
| Continental / orbit | z1.5–6 | Dark (`#1a1a2e`) | overview effect — dark field, glowing dots |
| Transition | z6–9 | lerp dark → light | descending into the world |
| Street / find | z9+ | Light (`#e8e8e8`) | find a space near me |

All colour variables (`bg`, `water`, `road`, `bldg`, `label`) are MapLibre `interpolate` expressions
over this same z6→z9 range (`buildStyle`, `app.js:135`). One function, one transition, no branching.

### Layers reinforce the altitude reading

The layer stack is ordered so that **geography precedes human construction**:

1. `background` — solid field (dark at orbit, light at street)
2. `hillshade` — topographic texture from AWS Terrain DEM (terrarium encoding); shadow `#0d1020`,
   highlight `#2a2a4a`; exaggeration fades from `0.4` at z2 to `0.15` at z9 so mountain ranges
   read at orbit without competing with the light basemap at street scale
3. `landcover` / `water` / `waterway` — natural geography
4. `roads-*` — human grid; `roads-major` opacity is `0` at z6, `1` at z8 — invisible from orbit
5. `buildings` / `labels` — neighbourhood detail

**Rule:** at continental altitude the map shows geology and living lights, not roads and borders.
Roads fade in as you descend. This is a direct encoding of overview-effect north star §1 ("the
borders aren't there") and §4 ("restraint — dark field, slow glow"). See
`_bmad-output/planning-artifacts/overview-effect-north-stars.md`.

### Hillshade tuning notes

- Source: `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png` — free, no key,
  global coverage from z0
- Both shadow and highlight are navy variants of the background — the effect is a *darkening* of
  mountain flanks, not a grey overlay fighting the palette
- Illumination direction: 315° (NW), conventional cartographic convention
- To increase drama at orbit: raise `hillshade-exaggeration` at z2 (currently `0.4`); to suppress
  at street scale: lower the z9 stop (currently `0.15`)

---

These are *map-surface* rules. The space-profile card (Zone 3 trust receipt), the wizard, and
Bernard's voice carry their own design decisions — out of scope here, candidates for a later
companion doc.
