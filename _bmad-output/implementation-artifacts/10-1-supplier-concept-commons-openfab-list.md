# Story 10.1: Supplier Concept Commons + First OpenFab List

Status: done

## Story

As a maker looking for materials (and as the MoM operator opening the map beyond makerspaces),
I want a shared supplier vocabulary in `mom:` plus OpenFab's curated Brussels supplier list ingested as geolocated, trilingual RDF,
so that "wood suppliers within 5 km" answers in FR, EN or NL — and so the next space's list cross-references OpenFab's instead of forming its own island.

## Context

OpenFab maintains ~55 Brussels suppliers in `openfab-lab/rtfm` (`faq/fournisseurs.md`) — free-form
French markdown grown by successive `append` over years, last meaningfully updated ~2 years ago.
Its irreplaceable value is the informal member commentary ("Des bons copains, une très bonne bière,
recommandation ++"), not the addresses.

An agent already converted it on the VPS (`hetzner:/home/nicolas/hermes-deploy/shared/openfab-suppliers/`):
trilingual SKOS categories, `schema:LocalBusiness` data, a reusable Python parser. The sorting work is
good and it solves the multilingual concern. Four defects block reuse as-is — see AC 1.

This story opens Epic 10. Suppliers are the first *real* case of the epic's "concept commons" and
"emergent community ontologies" vision: shared vocabulary at the centre, per-place content at the edge.

## Acceptance Criteria

1. **The four defects in the VPS artifact are fixed, not inherited.**
   1. **Serialization.** The VPS `.ttl` files contain `GRAPH <…> { … }` (`openfab-suppliers-complete.ttl:217`).
      Turtle has no such keyword — it is TriG. Output is `.trig`, served with `Content-Type: application/trig`.
   2. **Ingestion path.** The VPS README's `POST https://mapsofmaking.org/sparql/update` cannot work:
      nginx returns 403 (`infra/nginx/conf.d/app.conf:50-59`) and `/update` expects SPARQL UPDATE, not Turtle.
      Loading goes through `scripts/load_ontology.sh`'s existing internal `PUT /store?graph=…` path instead.
      **No new write surface is opened; the 403 stays.**
   3. **Source of truth.** Vocabulary, parser, curated CSV and generated TriG live in this repo, not in a
      VPS scratch directory. A store wipe loses nothing.
   4. **Namespace.** `ofs: <https://openfab.be/ns/suppliers#>` puts the *vocabulary* (Bois/Wood/Hout) in
      OpenFab's namespace. Categories belong to no one. All vocabulary terms move to `mom:`; only the
      55 businesses and their comments remain OpenFab's.
2. **Shared vocabulary — `ontology/sup.ttl`,** in the canonical MoM namespace
   (`https://nicolasdb.github.io/mapsofmaking_ontology/ns#`), loaded into `<urn:mak:ontology/sup>`:
   1. `mom:Supplier`, `rdfs:subClassOf schema:LocalBusiness` (keeps the schema.org interop the VPS agent
      correctly chose).
   2. `mom:SupplierCategoryScheme` (`skos:ConceptScheme`) + 13 `skos:Concept`: wood, plastic, metal,
      cnc-bits, fasteners, electronics, textile, leather, paper, services, drinks,
      maintenance-consumables, specialty-wood (`skos:broader mom:supplier-wood`).
   3. **English IRIs, trilingual labels** — `skos:prefLabel @en` + `skos:altLabel @fr/@nl`, matching
      `mom.ttl`'s existing English-IRI convention (`mom:ThreeDPrinting`). All three languages from the
      VPS work are preserved, none dropped.
   4. Predicates: `mom:supplierCategory`, `mom:recommendedBy` (Supplier → Space), `mom:supplierListSource`.
   5. `mom:geolocationFidelity` / `mom:geolocationNote` are **reused, not redefined** — their
      `rdfs:domain` widens from `mom:Space` to `owl:unionOf (mom:Space mom:Supplier)`.
3. **Parser — `scripts/parse_suppliers.py`,** two subcommands on the `seed_csv.py` model:
   `to-csv` (markdown → raw CSV) and `to-ttl` (curated + geocoded CSV → Turtle — renamed from
   the originally planned `to-trig`; see Completion Notes' TriG→Turtle correction, same reason).
   Markdown never becomes triples directly; it always passes through the reviewed CSV.
   Graph is `<urn:mak:suppliers/openfab>`, subjects `urn:mak:supplier/<slug>`, aligning with the
   store's existing `urn:mak:` convention.
   **No silent drops:** named WARNING counters for entries missing URL, address, or category.
   The VPS README's own 55-vs-~60 and 12-vs-13 discrepancies are resolved and reported, not carried over.
4. **Curation pass — `data/supplier-lists/openfab.curation.csv`.** WebSearch subagents, ~10 suppliers per
   batch, verify: still trading, canonical URL, street + postcode + city, normalized phone/email.
   1. **Member commentary is never touched.** Curation covers verifiable facts only, never member judgement.
   2. **Every verified fact carries `verified_source_url`.** No source → field left empty,
      `confidence: unverified`. An agent fills gaps by inventing when the tool finds nothing; the source
      column is what prevents it.
   3. **Nothing is deleted.** A closed or unfindable business is marked, not removed.
      `status` reuses MoM's existing liveness vocabulary (`mom:operationalState`, `mom:deathReason`,
      `mom:confirmedAt`) rather than inventing a parallel one — a dead supplier is the same problem as a
      dead makerspace.
   4. **Human checkpoint:** the CSV is committed and reviewed by Nicolas before geocoding. The batch report
      states how many URLs changed, how many are unreachable, how many stay `unverified`.
      If the first batch returns poor quality, stop and re-plan rather than curating 55 entries badly.
5. **Geocoding — `scripts/geocode_suppliers.py`,** over the curated CSV (not the raw markdown).
   Nominatim, identifying User-Agent, 1 req/s. Cache committed to
   `data/supplier-lists/geocode-cache.json`; the API is called only for cache misses, so regeneration is
   reproducible and does not hammer a free service.
   Fidelity cascade recorded in `mom:geolocationFidelity`: full street → `exact`; partial/postcode →
   `approximate`; commune centroid fallback → `city`; plain-language `mom:geolocationNote` for anything
   not `exact`. Coordinates validated against a Belgium bbox (precedent: ~5% invalid coordinates in the
   SpaceAPI directory, caught at seed time not render time).
6. **Loading — `scripts/load_ontology.sh` extended:** `PUT ontology/sup.ttl` → `<urn:mak:ontology/sup>`
   (`text/turtle`) and `PUT data/supplier-lists/openfab.trig` (`application/trig`).
   `PUT` replaces the graph, so reloading is idempotent. `vps-` parity twin works (`Makefile:243-250`).
7. **Published schema — `docs/reference/supplier-list-schema.md`** (Diátaxis *reference*): the 13 category
   IRIs, required vs optional per-supplier fields, how to propose a missing category via the existing
   `mom:OntologyGap` path, and an explicit note that this same schema is what a supplier would self-host
   the day they want their own endpoint — the space hosts on their behalf meanwhile, so migration asks
   the supplier for nothing new.
8. **Live done gate (DoD — live queries against Oxigraph, not pytest):**
   1. Counts match the parser's report; the 55/~60 discrepancy is explained.
   2. **Trilingual:** the same question via `"Bois"@fr`, `"Wood"@en`, `"Hout"@nl` returns the *same*
      supplier set. This is the test that validates the original concern.
   3. **Proximity — the point of the story:** wood suppliers within 5 km of a Brussels point, ordered by
      distance, return *distinct* ranks. All-equal distances mean the `city` fallback flattened everything
      onto centroids and geocoding failed.
   4. Fidelity distribution is plausible; no supplier has coordinates without `mom:geolocationFidelity`.
   5. Reloading twice does not change counts.
   6. No regression: `mom.ttl` / `iop.ttl` / OKW crosswalk still load; existing space queries unchanged.
9. **Ontology repo sync.** `sup.ttl` is pushed to `github.com/nicolasdb/mapsofmaking_ontology`
   (GitHub Pages), otherwise `mom:supplier-*` IRIs do not resolve. `ontology/` here is a working copy
   synced by hand — this is a real step, not a silent omission.

## Tasks / Subtasks

### Review Findings

- [x] [Review][Patch] AC 4.4 checkpoint framing was stale — CSV was reviewed out-of-band before geocoding/deploy; sprint-status "HALTED at AC 4.4" wording corrected to reflect the checkpoint was passed.
- [x] [Review][Patch] Parser subcommand renamed `to-trig` → `to-ttl` in AC 3/Task 7 to match shipped code, with a note on why (Oxigraph rejects TriG on PUT ?graph=).
- [ ] [Review][Patch] New Makefile targets suppliers-csv/suppliers-geocode/suppliers-ttl missing from .PHONY [Makefile:107-131]
- [ ] [Review][Patch] geocode_suppliers.py caches failed lookups permanently with no expiry/retry [scripts/geocode_suppliers.py:2911-2913]
- [ ] [Review][Patch] to_ttl emits mom:supplier-{cat} and mom:operatedBy without validating category/slug exist [scripts/parse_suppliers.py:3517,3566]
- [ ] [Review][Patch] split_address() misparses house/box number preceding postcode as the postcode [scripts/parse_suppliers.py:3261]
- [ ] [Review][Patch] category_for_header() bidirectional substring match can cross-map unrelated headers [scripts/parse_suppliers.py:3210-3217]
- [ ] [Review][Patch] make suppliers-csv overwrites curated CSV with no confirmation guard [Makefile:111-117]

- [ ] Task 1: Open Epic 10 (AC: —)
  - [ ] `sprint-status.yaml`: `epic-10: backlog` → `in-progress`, add this story
  - [ ] `epics.md`: dated note explaining why the supplier demo pulled Epic 10 onto the critical path
        (do not silently rewrite the original "post-demo" framing)
  - [ ] Backlog the identified follow-ups with `→ Story` tags at write time: Bernard Matrix
        recommendation capture, self-hosted supplier endpoint, MCP write path for Manny
- [ ] Task 2: Vendor the source (AC: 1.3)
  - [ ] Copy `fournisseurs.md` → `data/supplier-lists/openfab.source.md`
  - [ ] Port `parse_fournisseurs.py` from the VPS as the base for `scripts/parse_suppliers.py`
- [ ] Task 3: Shared vocabulary (AC: 2, 9)
  - [ ] Write `ontology/sup.ttl`, re-prefixing `ofs:` → `mom:`, all three languages preserved
  - [ ] Widen `geolocationFidelity` / `geolocationNote` domains in `ontology/mom.ttl`
  - [ ] Decide and document `mom:recommendedBy` direction in its `rdfs:comment`
  - [ ] Push to the ontology repo
- [ ] Task 4: Parser to-csv (AC: 3)
  - [ ] `to-csv` subcommand + WARNING counters; resolve the 55/~60 and 12/13 discrepancies
- [ ] Task 5: Curation (AC: 4)
  - [ ] Batch 1 (~10 suppliers) via WebSearch subagents; assess quality before continuing
  - [ ] Remaining batches; commit `openfab.curation.csv`
  - [ ] **HALT for Nicolas's review** — batch report with changed/unreachable/unverified counts
- [ ] Task 6: Geocoding (AC: 5)
  - [ ] `scripts/geocode_suppliers.py` + committed cache; fidelity cascade; Belgium bbox validation
- [ ] Task 7: Emit + load (AC: 3, 6)
  - [ ] `to-ttl` subcommand → `data/supplier-lists/openfab.ttl`
  - [ ] Extend `scripts/load_ontology.sh`; verify the `vps-` twin
- [ ] Task 8: Schema doc (AC: 7)
  - [ ] `docs/reference/supplier-list-schema.md`
- [ ] Task 9: Live done gate (AC: 8)
  - [ ] Run all six checks locally, then on the VPS; capture queries + results in Completion Notes

## Dev Notes

- **Write path, explicitly:** `scripts/load_ontology.sh` reaches Oxigraph internally (container IP /
  `distrobox-host-exec`), so the nginx 403 on `/sparql/update` is never in the path. This story opens
  **no** new write surface. Bernardo stays read-only by design; Manny's write path is a separate
  deliverable (`design-mom-mcp-tool-surface.md` + Story 13.4-write).
- **Why per-entry provenance matters now:** two future paths will write suppliers — Bernard capturing
  recommendations in Matrix rooms, and Manny administering via MCP. Both need chat-captured entries to be
  distinguishable from repo-curated ones. `mom:supplierListSource` + `verified_source_url` +
  `confidence` give them somewhere to land without a later migration.
- **Out of scope:** MCP write path; Bernard recommendation capture; upstream PR to `openfab-lab/rtfm`
  (planned once the schema stabilizes, at which point MoM switches to fetching their URL — the
  coordinator-endpoint pattern); emitting the `core:relationships` wormhole (ADR-016, documented but
  emitted nowhere).

## Completion Notes

**Status: awaiting operator review of `data/supplier-lists/openfab.curation.csv` (AC 4.4 checkpoint).**
Everything else is built and live-verified. Six operator decisions are listed at the end.

### Two design corrections made during implementation

1. **TriG → plain Turtle.** The story (AC 1.1) called for TriG. Verified against Oxigraph 0.5.7
   rather than assumed, and TriG is the *worse* of the two valid fixes:
   - `PUT /store?graph=… ` + TriG → `400 Named graphs are not allowed`
   - `POST /store` + TriG → `204`, but **merges**: a supplier deleted upstream would survive
     every future reload
   - `PUT /store?graph=…` + Turtle → replaces that one graph ← idempotent, and what mom.ttl
     already does
   The VPS artifact's defect was real; the fix is to name the graph at the load URL, not to
   re-serialize. AC 1.1's intent (the file must actually load, and reloading must be idempotent)
   is met; its stated mechanism was wrong.
2. **`mom:suppliesTo` → `mom:recommendedBy`.** The flagged ambiguity resolved in favour of "this
   space recommends this supplier". The supplier makes no commitment by appearing; the space does.
   This is also the sense a Matrix-captured recommendation will need.

### Also found
- **Oxigraph has no `SQRT`.** Distance queries must rank and filter on *squared* distance
  (monotonic, so identical ordering; the radius squares). Documented with the two syntax traps
  that both surface as `expected ENCODE_FOR_URI` — notably that `?lon-4.3528` tokenizes as two
  terms and needs spaces around the minus.
- **`country` column added** (not in the story's field list). The geocoder originally hardcoded
  `country_codes="be"`, so Roarockit's real French warehouse address could never resolve — a
  silent drop of exactly the kind AC 3 forbids. Country is now per-row (45 BE, 5 FR, 3 DE, 2 IT),
  the bbox guard widened from Belgium to the Europe box `seed_csv.py` already uses, and
  `schema:addressCountry` is emitted.
- **The repo venv was dead** (`venv/bin/python3.13 → /usr/bin/python3.13`, absent since the host
  moved to 3.14; packages stranded in `venv/lib/python3.13`). This broke every make target
  importing a third-party module, not just this story's. Rebuilt from `scripts/requirements.txt`
  with the operator's approval.

### Discrepancies resolved (AC 3)
- **55 suppliers.** The VPS README said "55" in one file and "~60" in another; 55 is correct.
- **13 categories in the vocabulary, 12 populated.** `maintenance-consumables` has no members:
  that section of the source documents VMC and laser filter part numbers, not businesses. The
  concept is kept — the category is real, that source section just is not a supplier list.
- `Bois spéciaux` is an H3 under `Bois`. The parser now treats an H3 as a sub-category only when
  it maps to a known concept, so `### autre?` and equipment-model headings do not clobber the
  parent category.

### Curation (AC 4) — 55/55, six WebSearch subagent batches
- **51 active, 1 closed, 3 unknown.** Closed: **En Stoemelings**, bankrupt end 2024; the brand
  continues under a successor entity (Pintjes) which is explicitly *not* substituted for it.
  Unknown: `amd-metal` (site is now a domain-for-sale parking page; only undated aggregator
  listings remain), `3dinthebox` (site password-locked, "temporarily closed" for illness/staffing),
  `urbia` (registry juridical-incident flag and negative equity vs. still-listed opening hours —
  genuinely ambiguous, a phone call settles it).
- **9 URLs dead or changed** — including `its-tools.eu` (refuses connections outright),
  `exobois.be` (NXDOMAIN), `steenhoudt.com` (301 → Cras Woodshops, acquisition),
  `fr.vink.be` (invalid TLS cert). Three had their URL blanked rather than left pointing at a
  domain broker.
- **~30 street addresses added or corrected**, including one the source had plain wrong
  (`atelier-cnc` is Rue des **Ateliers**, not "rue des artisans") and two businesses that moved
  (`deker-sprl` out of Bever-Biévène; `engels-proservices` out of Brussels entirely).
- **16 suppliers deliberately carry no address** — mail-order-only or foreign (Mouser, RS, Farnell,
  Exp-Tech, Watterott, Weerg, …). Empty is the correct answer, not a gap: they must never surface
  in a proximity query.
- **Personal data excluded**: a named private individual's home address and mobile (the Club Mate
  pickup arrangement) and two named staff members' personal work emails (Beer Project) were not
  carried over; generic business channels used instead.
- **Commentary integrity verified**: re-extracting from `openfab.source.md` and diffing the comment
  column against the curated CSV shows **0 of 55 altered**. 31 suppliers carry member commentary.

### Live verification (AC 8) — against Oxigraph 0.5.7, not pytest
| Check | Result |
|---|---|
| Supplier count | 55, matches the parser |
| Trilingual `bois`/`wood`/`hout` | **15 / 15 / 15** — identical sets |
| Proximity, wood within 5 km of Grand-Place | 7 suppliers, **distinct ranks** 2.6–4.9 km |
| Fidelity distribution | 38 `exact`, 1 `approximate`, **0 `city` fallbacks** |
| Coordinates without fidelity | 0 |
| Reload twice, then three times | 942 triples, unchanged |
| Regression | mom 484 / iop 33 / crosswalk 24 triples, all still load |
| Reproducibility | offline regeneration byte-identical; cached geocode is a no-op |

The zero `city` fallbacks matter: no supplier is being drawn on a commune centroid pretending to
be a shopfront. That outcome is a direct result of curating addresses before geocoding.

### Open — operator decisions before this ships
1. **Deduplication.** Three slugs point at two physical Watteau sites: `nordic` = Watteau's Laeken
   branch, `exobois` = Watteau's Sint-Pieters-Leeuw yard. Nothing was deleted; merging is a data
   decision.
2. **Multi-site suppliers.** One address per supplier loses real, geocodable locations: Watteau has
   6 branches, Schleiper 3, Carlier/Biemar/Lochten/Fabory 2 each. Either a supplier gets multiple
   locations in the schema, or those branches stay invisible to a proximity query.
3. **Geographic scope.** `laege` is now Belignum in Mouscron, ~90 km away; `gesibois`, `aludan`,
   `dejond`, `fablab-factory` are Belgian but well outside Brussels. They are correctly excluded by
   a radius filter, but should they be in a Brussels space's list at all?
4. **Names that no longer match reality.** `steenhoudt` trades as Cras Woodshop Evere;
   `rs-components` is now just "RS"; `finnvis` is a typo for FixNvis/VisserieFixations. The `name`
   field was **not** changed — that is an operator call.
5. **Three `unknown` statuses** need a phone call each (see above).
6. **`ontology/sup.ttl` must be pushed** to `github.com/nicolasdb/mapsofmaking_ontology` (AC 9), or
   the `mom:supplier-*` IRIs will not resolve.

### Deployed to production 2026-08-25 — and it surfaced two pre-existing deploy bugs

`ontology/sup.ttl` was pushed to the ontology repo by the operator (AC 9), then
`make sync-app` + `make vps-load-suppliers`. **The first attempt reported five green
checkmarks and loaded nothing.** Two independent defects, neither introduced by this story:

1. **`vps-load-ontology` was targeting the wrong triplestore.** Two Oxigraph containers run on
   the VPS: `maps-oxigraph` (MoM, `expose` only since Story 13.2 closed its published port) and
   `oxigraph` from the unrelated `pocpod0` project, which publishes `0.0.0.0:7878`. Host
   `localhost:7878` therefore answers 200 while being someone else's store. Prod's
   `urn:mak:ontology/mom` had been frozen at **210 triples** — it is 484 now, so this had been
   broken since 13.2. Fixed: the Makefile resolves `maps-oxigraph`'s container IP and **aborts**
   if it comes back empty rather than falling back to localhost.
2. **`load_ontology.sh` could not fail.** Bare `curl` exits 0 on HTTP 4xx/5xx, so
   `if curl …; then echo ✅` printed success on every failed load — this is what hid defect 1.
   All five calls now use `curl -fsS`; the fix proved itself immediately by turning the next
   bad run red.

A third, smaller one: `RSYNC_EXCLUDE` drops `data/`, so `openfab.ttl` would never have reached
the VPS. Added `vps-load-suppliers`, which scps the Turtle first — the same thing `vps-seed` and
`vps-seed-bundle` already do for their inputs. Also excluded `graphify-out/` from the deploy
(operator's call): a local analysis cache with no role in production.

**Live in production, verified through the PUBLIC endpoint** (`https://mapsofmaking.org/sparql/query`),
not through the loader's own output:

| Check | Result |
|---|---|
| `urn:mak:ontology/sup` / `urn:mak:suppliers/openfab` | 189 / 942 triples |
| Suppliers | 55 |
| Trilingual `bois`/`wood`/`hout` | 15 / 15 / 15 |
| Wood within 5 km of Grand-Place | 7, ordered by distance |
| Spaces still answering | 3193 |
| `mapsofmaking.org` | HTTP 200 |
| `POST /sparql/update` | **HTTP 403** — no new write surface, as designed |

### Operator decisions 1 & 2 applied 2026-08-25 (dedup + multi-site)

Both resolved with the same mechanism, since they were the same underlying question
(one physical site = one geolocatable record, however many share an owner):

- Added `mom:operatedBy` (`ontology/sup.ttl`) — links a supplier to another `mom:Supplier`
  that is the same current legal operator. Branches are **never merged or deleted**; each
  keeps its own address and its own member commentary, which is exactly what a proximity
  query and the source's per-branch recommendations both need.
- **9 branch records now carry `mom:operatedBy`**: `nordic`/`exobois` → `watteau` (decision 1,
  the original dedup candidates); and 7 new rows split out from single-address parents
  (decision 2) — `carlier-bois-suarlee`, `biemar-bois-malmedy`, `fabory-sint-pieters-leeuw`,
  `schleiper-becreative`, `schleiper-factory`, `beer-project-dansaert`, `lochten-schaerbeek`.
  Addresses came from the original curation research (already sourced, nothing re-guessed);
  each branch row carries its parent's `verified_source_url` and `confidence`.
- Supplier count: 55 → **62**. Redeployed, verified through the public endpoint: 62 suppliers,
  9 `operatedBy` links, all geocoded (no new `city`-fallbacks introduced).

**Cleanup left for the operator:** five `urn:mak:*` graphs this bug wrote into pocpod0's store
(942 + 484 + 189 + 33 + 24 triples among its 5308 graphs). Harmless but foreign. Not removed
here because that store belongs to another project.

### Not done, deliberately (out of scope, per the story)
MCP write path; Bernard Matrix recommendation capture; upstream PR to `openfab-lab/rtfm`;
`core:relationships` wormhole emission. Nothing is committed — the working tree is the
deliverable pending the operator's CSV review.
