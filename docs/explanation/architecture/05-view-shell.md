# View shell — the drawers

> **The UI layer that wraps the map.** The pipeline ([01](01-walking-skeleton.md)) ends at two
> outputs: `spaces.geojson` (the map source) and the raw-receipt API (`/api/space/{id}/raw`). This
> doc covers what sits *on top* of those — the five drawers and how they connect back to the trunk.
> They are **features, not pipeline stages**: a presentation layer over in-memory `state`, not part
> of the data flow. All anchors are in `web/app.js` + `web/maps-of-making.html`.

## One slot, five panels

Every drawer is governed by a **single-slot state machine** (`setDrawer`, `app.js:1540`):

```
state.openDrawer ∈ { find · preset · addurl · detail · bot · null }
```

`find` is a unified panel that consolidates what were once separate `filters`, `search`, and `tweaks`
drawers — search, status/network chip filters, and render prefs all live in one place now.

**Mutually exclusive by construction.** `setDrawer(name)` closes whatever was open before opening
the next (`app.js:1544`); only one panel is ever visible. There is no z-order stack to manage — the
slot *is* the stack, depth 1.

Wiring is uniform across all five:

```
#btn-<name>  ──click──▶  toggleDrawer(name)  ──▶  setDrawer / closeDrawer
                                                    │
                          ┌─────────────────────────┼──────────────────────────┐
                          ▼                          ▼                          ▼
                  node.classList            node.aria-hidden            syncTopbar()
                  .add/remove('open')        true / false              (aria-pressed mirror)
                  (CSS transform slide-in)
```

- The `.open` class drives a CSS `transform` slide-in per edge — `.drawer.left/right/bottom`
  (`maps-of-making.html:104–110`); `addurl` docks from the top, `bot` from bottom-right.
- `syncTopbar` (`app.js:1580`) keeps every `#btn-*`'s `aria-pressed` in sync and hides the bot FAB
  while the bot drawer is open.
- **Keyboard:** `Esc` closes the open drawer; `Escape` also opens `find` when no drawer is active
  (`app.js:1691–1695`).

`detail` and `addurl` **share the right edge** — opening one force-closes the other (called out at
`app.js:1542`). That's the only slot collision, and the state machine handles it for free.

## The five drawers and their trunk ties

Only **three** drawers touch the pipeline. The other two are self-contained view utilities.

| Drawer | Edge | Trunk tie | Anchor |
|---|---|---|---|
| **detail** | right | **reads OUTPUT** — renders the space profile + Zone 3 raw receipt | opened by marker click → `selectSpace` → `setDrawer('detail')` `app.js:619,621` |
| **find** | left | **filters OUTPUT** — search + status/network chips + render prefs; narrows the rendered `spaces.geojson` features | `filteredSpaces()` `app.js:665` |
| **addurl** | right | **feeds INPUT** — `/api/validate-url` + register (wizard CTA / paste-endpoint fork) | `_wireAddUrlHandlers()` `app.js:1362` |
| preset | bottom | — local | embed/iframe builder; re-renders on map `moveend` `app.js:1745` |
| bot | bottom-right | — local | Bernard preview |

### The three touchpoints in detail

- **detail ← OUTPUT.** A pin click calls `selectSpace(id)` (`app.js:619`): sets `selectedId`,
  highlights, `renderDetail()`, then opens the drawer *unless* addurl is up (don't hijack a
  registration in progress). The card is where the Zone 3 raw-receipt guarantee from
  [01](01-walking-skeleton.md) surfaces to the reader.
- **find → OUTPUT.** `filteredSpaces()` (`app.js:665`) is the single predicate; the status facet
  calls **`computeMarker(s)`** — *the same marker computation documented in
  [03](../../reference/freshness-axes.md)*. So a status chip and a map pin can never disagree: one source, two
  readers. Filter changes re-run `refreshSpacesLayer()` + `updateCounts()`.
- **addurl → INPUT.** The only drawer that writes back into the pipeline — it's the front door for
  the two onboarding paths (the wizard CTA and the paste-your-endpoint fork).

## Mental model

```
   pipeline (01)                    view shell (this doc)
   ─────────────                    ─────────────────────
   INPUT  ◀───────────────────────  addurl   (feed)
   PROCESS
   OUTPUT ── spaces.geojson ──────▶  find     (filter) ─▶ map markers
          └─ /api/.../raw  ───────▶  detail   (read)
                                     preset · bot  (local only)
```

The pipeline doesn't know the drawers exist; the drawers read its two outputs and feed its one
input, and otherwise manage their own `state`.

## Design rules carried here

- **Single-slot, mutually exclusive.** Adding a sixth drawer means adding one enum value + one
  `#btn-`; the machine enforces exclusivity. Don't introduce a second concurrent slot without a
  reason — the depth-1 invariant is what keeps focus and `Esc` unambiguous.
- **Filter status ≡ marker kind.** Any new status facet must route through `computeMarker` / the
  axes in [03](../../reference/freshness-axes.md) — never a parallel re-derivation.
- **Palettes are surface-scoped.** The map's `:root` is not shared with `admin`/`genjson`/
  `mothersands` (each owns its own; see [04](04-design-rules.md)). Don't merge them into one file
  without renaming tokens — collisions would silently repaint. (Extraction to a shared `tokens.css`
  is an Epic-4 task, when admin reuses the map palette.)
