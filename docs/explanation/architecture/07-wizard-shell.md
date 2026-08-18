# Wizard shell — the other front door to INPUT

> **Where coordinators author a space from scratch.** [05 · View shell](05-view-shell.md) showed the
> map's `addurl` drawer feeding the pipeline's INPUT — that's the *paste-an-endpoint* fork. This doc
> covers the **author-from-scratch** fork: Bernard's Workshop wizard at `genjson.mapsofmaking.org`.
> It produces a SpaceAPI-v15 JSON file the coordinator self-hosts; that raw URL then re-enters through
> `addurl` → `/api/validate-url` → the pipeline. The wizard writes *nothing* server-side — its only
> output is a downloaded file. One file builds it all: `web/genjson/genjson.js` (no framework, no build
> step). All anchors are exact.
>
> This is the **code ground-truth** companion to the aspirational spec at
> `_bmad-output/planning-artifacts/ux-bernard-wizard-spec.md` and the locked interaction frame
> (Story 9.12). Where they disagree, the code wins and this doc says so.

## Where it sits in the trunk

```
   author fork (this doc)                        pipeline (01)
   ──────────────────────                        ─────────────
   wizard ── assemble v15 ── download .json
                                  │
                                  ▼  coordinator self-hosts (GitLab raw, etc.)
                            a public endpoint URL
                                  │
   map addurl drawer (05) ◀───────┘  paste → /api/validate-url ──▶ INPUT
```

The wizard never calls the pipeline. It hands the coordinator a file + (via the `#golive` tutorial)
the knowledge to host it. The hosted URL is what closes the loop, through the same front door the
paste-fork uses.

## One slot of attention: the beat machine

The wizard is **not a form** — it's a sequence of *beats* that reveal one at a time (the locked P2
frame). A beat is a CSS grid row animating `0fr→1fr`, `inert` until revealed so keyboard focus can't
land early (`.beat` `genjson.js:296`; `revealBeat` `genjson.js:1020`).

```
intro (recedes)
  └─▶ Tier 0 — floor          tier0-beat-name ──commit──▶ tier0-beat-location ──geocode──▶ tier0-beat-bedrock
        └─ Continue ─▶ Tier 1 — SpaceAPI core
              └─ fork ──┬─ "Go deeper →"  (Tier 2 teaser only — 9.6, not built)
                        └─ "Go live →"    #golive tutorial: 5 steps + close (9.8)
  ownership strip (always present once a name exists)
```

- **Commit-to-advance, never per-keystroke.** Reveals + field-advance fire on Tab / Enter / blur
  (name commit `genjson.js:1097`; address commit → geocode `genjson.js:1077`). Enter advances focus
  within a cluster; the last field commits in place.
- **Transient intro.** Bernard's opening line launches visible then recedes (`bernard-intro`,
  `genjson.js:736`) at t=4s on fresh entry, or snaps away instantly on resume.
- **One tier active at a time.** `tier-active` lifts the current frontier's border; settled tiers go
  muted, locked tiers are dashed tombstones (`.tier-locked` `genjson.js:287`). `Continue` settles
  Tier 0 and reveals Tier 1 (`genjson.js:1200`).

## Honest derivation — "automated, not automatic" (P3)

The location beat asks only **street + city**. Bernard *derives* lat/lon (+ postcode + country) via
`POST /api/geocode` (`geocode` `genjson.js:572`) — given a visible beat so the result reads as
*derived*, not magicked:

- The coords line runs an animated meter with a sustained UV "working" glow for ≥2.3 s
  (`startCoordsMeter` `genjson.js:1404`; `triggerGeocodeDebounce` waits the longer of fetch-vs-beat
  `genjson.js:1345`). UV = **Bernard's labor**, and it lives on the meter, never on the green result.
- On success: lat/lon fill, postcode/country narrate next to the pin (`· postcode · country`),
  bedrock beat reveals (`genjson.js:1367`).
- **Graceful fallback, loud not silent:** Nominatim unavailable or no-result → red coords line +
  manual lat/lon fields (`showManualCoords` `genjson.js:1445`); a result with no country → manual
  country field (`showManualCountry` `genjson.js:1458`). Continue stays reachable via manual entry.

## Field → v15 document (the INPUT mirror of [02](../../reference/field-traceability.md)/[06](06-space-card.md))

`assemblev15Doc` (`genjson.js:645`) builds the file in tier order so it mirrors the coordinator's
mental model (meta → Tier 0 → Tier 1 → mom: last):

| v15 key | From draft field | Tier | Note |
|---|---|---|---|
| `api_compatibility: ["15"]` | — | meta | always |
| `space` | `space` | 0 | |
| `location.address` | `address`+`city`+`postcode`+`country_code` joined | 0 | single string per v15 |
| `location.country_code` | `country_code` | 0 | derived or manual |
| `location.lat` / `.lon` | `lat` / `lon` | 0 | derived or manual |
| `logo` | `normalizeUrl(logo)` | 1 | scheme prepended |
| `url` | `normalizeUrl(url)` | 1 | scheme prepended |
| `description` | `description` | 1 | |
| `contact.email` | `contact_email` | 1 | |
| `contact.matrix` | `normalizeMatrix(matrix)` | 1 | `#` room sigil prepended |
| `state.open` | — (literal `null`) | 1 | "opted out" → pipeline resolves `confirmed` (`pipeline.py`) |
| `mom:memberOf` | — (literal `null`) | 2 | **stub** — Tier 2 (9.6) not built |

Empty fields are omitted, not emitted blank. `exportJSON` (`genjson.js:688`) validates required keys
against the bundled v15 schema (`loadSchema` `genjson.js:585`) and **warns without blocking** — gaps
are surfaced in the strip, the download still happens (coordinator agency over their own data).

## The ownership strip (P1) — the single export affordance

A static footer that appears the moment a name exists (`updateStrip` `genjson.js:1471`):

- **Live filename** `<space>-<city>-<date>.json` (`draftFilename` `genjson.js:615`) — the coordinator
  watches their file take shape.
- **One-threshold progress bar** — fills toward *bedrock* (name + location resolved), turns green at
  the threshold; never a percentage, never red (`genjson.js:1482`). It's a horizon, not a quota.
- **Always-on export button** — the *only* export affordance; no per-tier download buttons.

## Design rules the wizard enforces

These are the locked frame (Story 9.12) as they actually appear in code — see
[[project_wizard_interaction_frame]]:

- **Beats, not boxes.** Every step is a `.beat`; adding Tier 2/3 means more beats, never stacked
  panels. Mirrors the map shell's single-slot discipline ([05](05-view-shell.md)).
- **Bernard's voice is typeset, not quoted.** Special Elite + amber + leading em-dash, no quote-bar
  (`.bernard-voice` `genjson.js:98`). System/affordance copy is flat mono, no em-dash.
- **Semantic colour (Bernard's hermit-crab spectrum, bible §1):** amber = voice/CTA, blue =
  links/navigation/focus, green = valid, **red = errors only**, UV = Bernard's labor (has a duration;
  never on a green result). All on a liminal-dusk base, not pitch black (`:root` `genjson.js:47`).
  This palette is **surface-scoped** — the opposite world to the map's light riso ([04](04-design-rules.md));
  do not merge (see [[project_per_surface_palette_strategy]]).
- **Acknowledgment, not congratulations (P4).** Per-beat lines acknowledge and move on
  (`beat_name_ack`, `bedrock_confirm`) — never praise.
- **Copy is SSOT.** Every string is a key in `bernard_copy.yaml` → built to gitignored
  `bernard_copy.json`, loaded via a null-safe proxy that yields `''` on fetch failure
  (`emptyProxy` `genjson.js:16`) — no hardcoded fallback mirror (see
  [[feedback_no_triple_source_of_truth]]). Guarded by `test_bernard_voice_completeness.py`.

## Honest-inventory triage (2026-06-04)

Scanned `genjson.js` the same way as [05](05-view-shell.md)/[06](06-space-card.md):

- 🔴 **`resumeHint` (`genjson.js:716`) is dead** — assigned, zero reads. Its comment describes a
  `?resume=1`-with-no-draft path the code never branches on; the fresh-entry default (`hasDraft`
  false) already satisfies that AC. **Cut candidate** (+ trim the misleading comment).
- 🔴 **`tutorial_teaser` (was `bernard_copy.yaml`) cut** — Story 9.8 wired the real `#golive`
  tutorial, deprecating the "walkthrough is on the way" teaser. It had been kept "for the test
  guard," but `test_keys_referenced_in_js` is **warn-only** (asserts nothing) — retention guarded
  nothing. Removed from YAML, regenerated `bernard_copy.json` (`make bernard-copy`), trimmed the
  stale JS comment; all 3 copy-completeness tests pass.
- 🟡 **Tier 2 / Tier 3 not built.** "Go deeper →" shows only a teaser note (`fork_stub.tier2_teaser`
  `genjson.js:1216`); `mom:memberOf` exports as a `null` stub. Tier 2 = Story 9.6, Tier 3 = 9.10 —
  their UX is meant to *emerge* from the locked frame, not be pre-designed (see [[project_wizard_ux_vision]]).
- ⬜ **Timezone derivation deferred** to its own story (needs `timezonefinder`); not in code.
- No open wires — every `getElementById` resolves to a built node. `node --check` clean.

---

This extends the schematic set past the map: [01](01-walking-skeleton.md) pipeline ·
[02](../../reference/field-traceability.md) net-list · [03](../../reference/freshness-axes.md) marker mechanics ·
[04](04-design-rules.md) map visual grammar · [05](05-view-shell.md) drawer shell ·
[06](06-space-card.md) card field-surface · **07 wizard shell** (this doc). The pipeline's INPUT now
has both its doors documented: paste-an-endpoint ([05](05-view-shell.md)) and author-from-scratch (here).
