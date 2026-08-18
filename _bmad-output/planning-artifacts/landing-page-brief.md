# Landing page — design handoff brief

*For Claude Design. Everything here is intent and constraint. Nothing here is a layout —
the layout is yours to find.*

---

## What this page is

The public one-pager for Maps of Making, replacing the GitHub README as the front door.

**Primary reader:** someone who runs a making space — often not technical — who has been
told to "get listed" and doesn't know what that means.

**The hook is a different feeling than the ask.** The reader arrives caring about the map
(they have been burned by a dead listing themselves) and leaves being asked to publish. The
"you" switches exactly once, at the third section, on purpose. That is not hedging between
two audiences — the operator *is* a finder, and their reason to publish is that they already
know the pain first-hand.

**One call to action:** publish your space — landing on the guided helper, never on the JSON
spec. A second CTA would make it zero CTAs.

**Success metric:** registered endpoints. Not traffic, not stars.

## The copy

**The content source is [`docs/what-is-maps-of-making.md`](../../docs/what-is-maps-of-making.md).**
Six sections, in order. Do not rewrite them here — if the copy needs to change, it changes
there and both the docs page and this page follow. One source, two renderings.

Divergence is allowed only at the **frame**:

| Belongs to the landing page only | Belongs to the docs page only |
|---|---|
| the CTA | the "what's real today, and what isn't" table |
| network / pilot credibility | the "where to go next" nav |

The six section bodies are shared and must not drift.

## Voice

Plain and warm. Short sentences. No winks, no jokes at the reader's expense, no cleverness
that needs a second read.

**Not Bernard.** The project has a bot persona with a very dry register — that voice earns
trust *in conversation*, once a relationship exists. A first-time visitor has no such
relationship and just reads it as cold.

**Every gap is phrased as an invitation, never as an apology or a silence.** "Needs a first
adopter" rather than "not supported yet." This is the page's most distinctive move — the
honesty is the recruitment.

## The hero: an honest map

The hero is the real map with real data. Not an illustration, not a mockup, not a stock
globe. A page about a map that opens with a drawing is a lie of a different kind, on a
project whose entire proposition is that its claims are checkable.

**Every dot, individually. Never aggregated counts, never clusters.** The count is not the
point; the field of points is the point. Being visible at that scale is how a small space
gets to exist at a large one.

Three reactions to design for, in order:

1. *"There are actually a lot of these."* → **I am not alone.**
2. *"Several are near me."* → **connecting is easy.**
3. *"And some are open right now."* → **alive, making things, today.**

**No country borders. No network colouring. No place labels.** These are the drawn lines the
project exists to dissolve — the reasoning is already written up in
[`overview-effect-north-stars.md`](overview-effect-north-stars.md), which is the design
compass for this hero and should be read before starting. Its arc — *recognition, then
belonging* — is reactions 1 and 2 as a designed movement rather than two separate moments.

### The motion

One animation for the whole page, not one per section.

The view **drifts**, on a slow inclined path that gradually passes over everywhere — a ground
track, not a pan to a chosen place. This matters for a reason beyond beauty: **it dissolves
the empty-region problem.** If a visitor's own area looks sparse, a travelling view means
that emptiness is never the verdict — the map is always on its way somewhere else.

The drift is **indifferent to the viewer**. The map is not centred on you; it carries on
without you. That is the belonging message expressed as motion instead of copy.

Constraints:

- **Deterministic geometry, no live data feed.** The path is computed, not fetched. An
  external call would add a failure mode and one more claim to keep true.
- **The inspiration is not named anywhere in the copy.** The geometry does the work. Readers
  who recognise where the orbit comes from were never the audience.
- **`prefers-reduced-motion` gets a composed static frame.** The map surface already honours
  reduced-motion; stay consistent.
- **Motion yields to reading.** It should settle or slow once the visitor scrolls, or it
  competes with the sections.
- **Weight budget: drifting points.** Not a rendered 3D earth. Heavy the moment it becomes one.

## The state vocabulary — please read before choosing colours

Pins carry a state, and the states come from **three independent questions**. Collapsing them
into one "health" scale would be wrong in a way that is expensive to undo later, because these
distinctions are ontological, not cosmetic.

| Question | States | Means |
|---|---|---|
| **Is the space alive right now?** | `open` · `shut` | the space's own claim about this moment |
| **Is the listing being looked after?** | `confirmed` · `aging` · `zombie` · `dead` | how long since the file's content changed |
| **Can we reach the file at all?** | `broken` | fetch failure — says nothing about the space |
| *(not yet fetched)* | `seeded` | we know it exists, nobody has claimed it |

The trap: **"open" and "well-maintained" are different axes.** A space can be shut for the
evening and perfectly maintained; a space can be open daily with a listing nobody has touched
in a year. If the palette implies one scale from healthy to dead, we will be correcting that
misreading for years.

## Things that would make this page fail

Drawn from a pre-mortem, in likelihood order:

1. **Promising less work than the next click requires.** The page says "one small file"; if
   the CTA lands on a JSON spec, the reader meets an account signup and a raw URL and leaves.
   Land on the helper.
2. **Ending on a network effect.** "Once enough spaces join…" reads as *not useful yet* and
   politely invites the reader to come back later. The final section must pay off for a
   reader who joins alone, today.
3. **A hero that disproves the copy.** See above — travelling view, and sparse-but-true is a
   stronger argument than dense-but-rotten ("verified this hour" beats "three thousand
   listings nobody checked").
4. **Stating behaviour we can't demonstrate.** Every behavioural claim must be verified
   against the running system before it ships. Note the architecture has **two planes** — the
   map data plane and the agent plane live in different repositories, so checking one proves
   nothing about the other. Both mistakes have already been made once each during this work.
5. **Talking down.** The copy was drafted at a deliberately young reading level as a
   comprehension test, then lifted. Don't lift it back down.

## Assets and facts

- Content source: `docs/what-is-maps-of-making.md`
- Design compass: `_bmad-output/planning-artifacts/overview-effect-north-stars.md`
- Existing palette work: `_bmad-output/planning-artifacts/design-tokens.md`
- Live data: `https://mapsofmaking.org/data/spaces.geojson`
- Pilot networks: RFF (Réseau des Fablabs Français), VOW (Verbund Offener Werkstätten)
- Licence: Apache 2.0 · code at github.com/nicolasdb/mapsofmaking
