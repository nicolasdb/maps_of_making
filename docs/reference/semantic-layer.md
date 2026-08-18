# Semantic layer — the triplestore, the ontologies, the crosswalk

> **The upstream hop [02](field-traceability.md) assumes.** The net-list traces a SpaceAPI field
> into *storage* — but "storage" is an Oxigraph triplestore with a deliberate named-graph layout, a
> set of `.ttl` vocabularies, and a `crosswalk.csv` that licenses the mapping. This doc documents that
> layer: **what RDF the pipeline writes, where, against which vocabulary, and which of it is live vs.
> staged for later.** All anchors are exact.
>
> Canonical namespace authority (the one all queries use): `https://nicolasdb.github.io/mapsofmaking_ontology/`.
> `mom:` = `…/ns#`, `core:` = `…/ns/core#`, `iop:` = `…/iop#`. `mom.ttl` is authoritative — **not**
> `mapsofmaking.eu` (see [[reference_ontology_repo]]).

## Why this layer exists — the enhancer

MoM is **way more than a map**. A pin isn't just a dot on a tile — it's a space with meaning: things
you can search, compare, and connect to other spaces. This layer is what makes that possible — it
**enhances flat JSON into a searchable semantic layer** laid over the map, turning isolated points into
a queryable fabric. (*How* it does that is the rest of this doc; this section is the *why*.)

The meaning is organised in **the same layers the wizard authors** ([07](../explanation/architecture/07-wizard-shell.md)) — the
tiers are the shared spine between authoring and storage:

| Tier | Layer | Axis | What it buys | Namespace |
|---|---|---|---|---|
| **0** | bedrock | — | the minimum to *exist* on the map: name + location | `schema:` |
| **1** | core | **horizontal** | interop / compliance with the SpaceAPI app ecosystem | `schema:` (+ `core:`) |
| **2** | mom | **horizontal** | shared MoM meaning *beyond* SpaceAPI: `mom:memberOf`, SDGs, … | `mom:` |
| **3** | ext_* | **vertical** | community silo meaning — the "private joke" relevant to one group | `fab:` / `omt:` / `edu:` |

The load-bearing distinction is **horizontal vs. vertical**:

- **Horizontal / transversal** layers (core, mom) are *common sense* — every community shares them, so
  they're the basis of federation and cross-space queries.
- **Vertical** layers (ext_*) are *silo meaning* — a fab lab's `fab:equipment`, a clinic's
  `omt:treatmentFocus`. Specific, not universally shared.

The bridge between them is the **wormhole**: a vertical field aliases to a horizontal concept via
`skos:closeMatch` (every community's skill field → `schema:knowsAbout`), so silos stay interoperable
without coordination ([[project_schema_bundle_model]]). The `crosswalk.csv` is where those bridges are
declared and the no-redefinition rule is enforced (a vertical layer may *alias* a horizontal field,
never *redefine* it).

> **How is the vocabulary used today?** The `.ttl` files declare the vocabulary; the extractor *chooses*
> which predicates to emit at ingest time (that's where the tier model is fully real). The SKOS bridges
> are **not executed by the internal pipeline** — `knowsAbout` activity strings are stored raw. They
> *are* executed at query time by external SPARQL clients: OHM joins across the vocabulary graph to
> resolve raw tags to Wikidata QIDs. See [§How the TTL is actually used](#how-the-ttl-is-actually-used)
> and `../explanation/ohm-integration.md`.

## The triplestore is named graphs, not one bag of triples

Oxigraph (`ghcr.io/oxigraph/oxigraph`, internal `:7878`) holds every fact in a **named graph**, and the
graph URI is load-bearing — it's how the pipeline keeps the canonical copy, the append-only ledger, and
the diagnostic canary from colliding.

| Graph | Holds | Lifecycle | Status |
|---|---|---|---|
| `urn:mak:space/<id>` | the per-space canonical semantic copy (one graph per space) | overwritten on content change only | 🟢 live |
| `urn:mak:public_ledger` | append-only provenance ledger | **never DROP** (append-only) | 🟢 live |
| `urn:mak:canary/mother-sands` (+ `urn:mak:canary`) | the diagnostic canary's triples | reset via `canary_ops` | 🟢 live |
| `urn:mak:network/<slug>` | network/community membership | rewritten on seed | 🟢 live |
| `urn:mak:ontology/mom` · `urn:mak:ontology/iop` | the loaded vocabularies | replaced by `load_ontology.sh` | 🟢 **live via OHM** (see below) |
| `urn:mak:crosswalk/mom-to-okw` | MoM↔OKW concept alignments (`skos:closeMatch`/`skos:relatedMatch`) | replaced by `load_ontology.sh` | 🟢 **live via OHM** (see below) |

The three-graph backbone (`space` / `canary` / `public_ledger`) is its own design decision — see
[[project_three_graph_model]]. The append-only ledger is the on-graph half of the Zone 3 trust
guarantee ([06](../explanation/architecture/06-space-card.md)).

## What the pipeline actually writes — and what it does NOT read

This is the load-bearing honest-inventory fact:

- **The extractor writes `schema:` and `mom:` triples** into `urn:mak:space/<id>`. The mapping lives in
  code: `scripts/spaceapi_extract/{core,mom}.py` (called by `pipeline.py`). There is
  no runtime config that drives it — the predicates are hardcoded. (`spaceapi_extract/` lives under
  `scripts/` and is staged into the link-handler container at build time.)
- **The heartbeat/materialize path does not query `urn:mak:ontology/*` or `urn:mak:crosswalk/*`.**
  Those graphs are consumed by *external SPARQL clients*, not the internal pipeline. The public SPARQL
  endpoint at `/sparql/query` is what makes them live.

The vocabulary and the internal runtime are still only *informally* coupled (via `crosswalk.csv`). The
vocabulary graphs are now load-bearing for *external* consumers — specifically OHM. See below and
`../explanation/ohm-integration.md`.

## How the TTL is actually used

The internal pipeline does not query the vocabulary graphs. External SPARQL clients do.

- **No reasoning.** Oxigraph runs plain `serve` and is a SPARQL 1.1 store with no OWL/RDFS reasoner.
  Loading `rdfs:domain`/`owl:Class` declarations infers nothing.
- **The wormhole is executed at query time, not ingest time.** `schema:knowsAbout` activities are stored
  as **raw string literals** (`spaceapi_extract/core.py:66`, `sparql.py:90`). The
  `skos:prefLabel|skos:altLabel` chain in `urn:mak:ontology/mom` resolves those strings to concept IRIs
  *when a SPARQL client issues a cross-graph query*. OHM does this live, issuing queries like:

  ```sparql
  SELECT ?name ?lat ?lon WHERE {
    GRAPH ?g { ?space schema:knowsAbout ?tag }
    GRAPH <urn:mak:ontology/mom> {
      ?concept skos:prefLabel|skos:altLabel ?tag ;
               owl:sameAs <https://www.wikidata.org/entity/Q3062349> .
    }
  }
  ```

  The vocabulary graph is the lookup table; the space graphs are the data; the query engine joins them.
  This pattern is live and tested — see `tests/test_ohm_mom_integration.py` T3/T4/T5.

- **`urn:mak:crosswalk/mom-to-okw`** bridges MoM activity concepts to OKW manufacturing process concepts
  via `skos:closeMatch`. Also queryable via SPARQL; currently read by OHM and the test suite.

**Where the enhancement really happens:** in the extractor's *choice of typed predicate* — flat
`{"space": "...", "state": {"open": true}}` becomes `schema:name`, `mom:openNow`, etc. The `.ttl` only
*declares* those terms; the crosswalk *documents+lints* the choice; the store holds the result.

The **Epic 6 NL→SPARQL bot** still needs the vocabulary as grounding context — that use case remains
forward-staged. The SHACL-style validation and Linked Data publishing use cases also remain aspirational.

## `crosswalk.csv` — a reviewable spec, not a lookup table

`ontology/crosswalk.csv` records, per concept: the predicate the code **actually emits**, the SpaceAPI
v15 field it derives from, any community-namespace alias (`fab:`/`omt:`/`edu:`), and the `mapping_type`
that licenses it. Read it with `ontology/crosswalk.md`.

Crucial: **it is read only by `scripts/validate_crosswalk.py`** — never at runtime. It is the
*documented, lintable form* of the mapping `spaceapi_extract` performs implicitly. Its job is review +
the **no-redefinition rule**: no extension namespace may redefine a `core:`/`mom:` field, only alias it
via `skos:exactMatch`/`skos:closeMatch` (the validator enforces this).

The hub of the model is the `activities` row: `schema:knowsAbout` is the **shared concept pivot** (the
"wormhole hub") every community's skill field aliases to — so a cross-community query works with zero
coordination ([[project_schema_bundle_model]]).

Recorded incoherences (documented, not silently fixed): `address` emits `mom:address` as a plain string
(handoff/ADR-015 wanted `schema:PostalAddress`); `contact` serializes to a non-standard `schema:contactJson`.
The crosswalk documents what the code does and flags the gap — the [[feedback_data_integrity_no_silent_drops]]
stance applied to the ontology.

## The `.ttl` files — and which are wired

| File | Defines | Loaded by `load_ontology.sh`? | Status |
|---|---|---|---|
| `ontology/mom.ttl` | `mom:` application vocab (34 SKOS concepts with Wikidata `owl:sameAs` links, `mom:Space`/`mom:Coordinator` classes, datatype properties) | ✅ → `urn:mak:ontology/mom` | 🟢 live — queried by OHM + test suite |
| `ontology/iop/iop.ttl` | `iop:` Internet-of-Places stub | ✅ → `urn:mak:ontology/iop` | 🟡 stub (Epic 6 expansion) |
| `ontology/crosswalks/mom-to-okw.ttl` | MoM↔OKW concept alignments (8 `skos:closeMatch`, 3 `skos:relatedMatch`, gap register) | ✅ → `urn:mak:crosswalk/mom-to-okw` | 🟢 live — queried by OHM + test suite |
| `ontology/core.ttl` | `core:` Layer-2 base vocabulary (the schema-architecture handoff's idealized shared layer) | ❌ **not loaded** | 🔴 disconnected — see below |

### The `core:` disconnect (honest finding)
`core.ttl` defines a `core:` base namespace, but: (1) `load_ontology.sh` never loads it; (2) the live
extractor emits `schema:`/`mom:` predicates, **never `core:`**; (3) even `crosswalk.csv`'s `core_field`
column holds `schema:`/`mom:` IRIs, not `core:` ones (the `core:` term survives only in prose notes).
It's aspirational scaffold from `mom-schema-architecture-handoff.md` that the implementation routed
around. Not wrong to keep — but it is *not* the live base layer it reads as. Reconciling (or retiring
it) is a deliberate future decision, not something to assume.

## Loading — `load_ontology.sh` (now wired)

`scripts/load_ontology.sh [OXIGRAPH_URL]` PUTs `mom.ttl` + `iop.ttl` into their named graphs
(idempotent — PUT replaces the graph). It auto-detects distrobox and falls back to `distrobox-host-exec`
against the `maps-oxigraph` container IP (see [[infra_local_dev]]). Verified by
`scripts/test_load_ontology.py` (two `ASK` queries: `mom:Space a owl:Class`; an `iop` `owl:Ontology`).

**Previously a manual run — now folded into the Makefile** so a fresh stack always has the vocabulary:

```
make devdeploy      # rebuild → load-ontology → heartbeat  (local; reset inherits it)
make load-ontology  # standalone, against localhost:7878
make vps-load-ontology   # parity twin on the VPS host
```

This closes the wiring gap the inventory flagged. The load remains idempotent and safe to re-run.

## Honest-inventory triage

### 2026-06-04

- 🟢 **`crosswalk.csv`** — live *as a spec/lint target* (read by `validate_crosswalk.py`), not at runtime.
- 🟢 **`load_ontology.sh`** — loader; **was ⚠️ manual, now wired** into `devdeploy` + `make load-ontology`
  + `vps-load-ontology`.
- ✅ **`urn:mak:mock/rff-health`** — **CUT (2026-06-04)**: removed the mock UNION branch, `rff_mockup.json` seed, `vps-seed-bundle` example.
- ✅ **`ontology/context/space.jsonld`** — **CUT (2026-06-04)**: JSON-LD `@context`, referenced by no code. Removed.
- ⬜ **`crosswalk.md` staleness** — prose still cites deleted `transformer.py`. Trim later.

### 2026-06-29 (OHM integration)

- 🟢 **`mom.ttl`** — **upgraded from dormant to live**. Added 34 SKOS concepts (previously ~15), 29 with
  Wikidata `owl:sameAs` links. The activity vocabulary is now queried by OHM via direct SPARQL using the
  `skos:prefLabel|skos:altLabel` bridge. See `../explanation/ohm-integration.md`.
- 🟢 **`ontology/crosswalks/mom-to-okw.ttl`** — **new file, live**. The planned-but-missing OKW crosswalk
  is now built and loaded into `<urn:mak:crosswalk/mom-to-okw>`. Queryable via SPARQL, tested by
  `tests/test_ohm_mom_integration.py`.
- 🟢 **the SKOS wormhole is now executed** — at query time (not ingest time). `knowsAbout` strings are
  still stored raw by the pipeline; the vocabulary graph resolves them on the SPARQL join. No pipeline
  changes were required.
- 🔴 **`core.ttl`** — still disconnected aspirational scaffold. Decide reconcile-vs-retire.

---

This adds the upstream hop to the trail: [01](../explanation/architecture/01-walking-skeleton.md) pipeline ·
[02](field-traceability.md) net-list · **08 semantic layer** (the store + vocabulary 02 writes into) ·
[03](freshness-axes.md) marker mechanics · [04](../explanation/architecture/04-design-rules.md) map grammar ·
[05](../explanation/architecture/05-view-shell.md) drawers · [06](../explanation/architecture/06-space-card.md) card · [07](../explanation/architecture/07-wizard-shell.md) wizard. A field's
life now traces from *SpaceAPI input → extractor → `urn:mak:space/<id>` RDF → materialize → map/card.*
