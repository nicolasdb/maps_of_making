# Supplier list schema — what a space publishes so MoM can ingest its suppliers

> **The horizontal/vertical split from [semantic-layer](semantic-layer.md), applied one level down.**
> A space's supplier list is *content* and stays with the space. The **categories** in it are
> *vocabulary* and live once, centrally, in `ontology/sup.ttl`. This doc is the contract between
> the two.
>
> Canonical namespace: `mom:` = `https://nicolasdb.github.io/mapsofmaking_ontology/ns#`.

## Why the vocabulary is not yours to mint

If OpenFab publishes `ofs:category-bois` and a Charleroi fablab publishes `ccl:categorie-bois`, a
machine sees two unrelated concepts. Nothing cross-references, and "wood suppliers near me" returns
only the list of whichever space you happened to ask. The shared category IRIs are not
housekeeping — **they are the feature.** Use `mom:supplier-*`; if the category you need is missing,
raise a gap (below) rather than minting a local one.

Language is the same story from the other side. Lists are curated in the space's own language —
OpenFab's is French — but a Dutch- or English-speaking maker has to find the same suppliers. The
shared concepts carry FR/EN/NL `skos:altLabel`s, so one query serves all three. That only works if
you point at the shared concept.

## Categories

Thirteen concepts in `mom:SupplierCategoryScheme`. `prefLabel` is the canonical untagged English
tag (mom.ttl's convention); the FR/EN/NL forms are language-tagged `altLabel`s.

| IRI | prefLabel | FR | NL |
|---|---|---|---|
| `mom:supplier-wood` | `wood` | bois | hout |
| `mom:supplier-specialty-wood` | `specialty-wood` | bois spéciaux | speciaal hout |
| `mom:supplier-plastic` | `plastic` | plastique | plastiek |
| `mom:supplier-metal` | `metal` | métal | metaal |
| `mom:supplier-cnc-bits` | `cnc-bits` | mèches CNC | CNC boren |
| `mom:supplier-fasteners` | `fasteners` | visserie | bevestigingsmateriaal |
| `mom:supplier-electronics` | `electronics` | électronique | elektronica |
| `mom:supplier-textile` | `textile` | textile | textiel |
| `mom:supplier-leather` | `leather` | cuir | leder |
| `mom:supplier-paper` | `paper` | papier | papier |
| `mom:supplier-services` | `services` | services | diensten |
| `mom:supplier-drinks` | `drinks` | boissons | dranken |
| `mom:supplier-maintenance-consumables` | `maintenance-consumables` | consommable d'entretien | onderhoudsverbruiksgoederen |

`specialty-wood` is `skos:broader mom:supplier-wood`, so a query that walks `skos:broader*` returns
specialty-wood suppliers under a plain "wood" question — and one that does not, does not. Both are
legitimate; know which you are asking.

## Per-supplier fields

**Required**

| Field | Predicate | Note |
|---|---|---|
| name | `schema:name` | |
| category | `mom:supplierCategory` | one of the IRIs above; repeatable |

**Optional — but a street address is the one that pays**

| Field | Predicate | Note |
|---|---|---|
| url | `schema:url` | http/https only; anything else is dropped with a warning |
| phone | `schema:telephone` | E.164 preferred |
| email | `schema:email` | |
| street | `schema:streetAddress` | street + number |
| postcode | `schema:postalCode` | |
| city | `schema:addressLocality` | commune |
| comment | `rdfs:comment` (language-tagged) | see below |

Coordinates are **derived, not published**: `scripts/geocode_suppliers.py` resolves the address and
records how precisely it managed to in `mom:geolocationFidelity` (`exact` / `approximate` / `city`),
with `mom:geolocationNote` carrying the plain-language caveat. A commune name alone collapses every
supplier in that commune onto one point, so "near me" cannot rank them. **A real street address is
the single most valuable field you can provide.**

## The commentary is the point

`rdfs:comment` carries the member commentary — "la découpe est gratuite mais ils ont un choix
limité", "des bons copains, une très bonne bière, recommandation ++". This is the part no directory,
scraper or search engine reproduces, and it is why these lists are worth ingesting at all.

It is therefore **never** curated. MoM's curation pass corrects verifiable facts (is it still
trading, what is the address now, is the URL alive) and does not touch judgement. Keep it in the
space's own language, tagged (`@fr`, `@nl`, `@en`).

## Provenance and staleness

Supplier lists grow by append over years and rot silently. These fields make that visible instead of
assumed:

| Field | Predicate | Note |
|---|---|---|
| status | `mom:operationalState` | `active` / `closed` / `unknown` — the same vocabulary spaces use |
| death reason | `mom:deathReason` | when closed |
| verified at | `mom:confirmedAt` | when a curator last checked |
| verified source | `mom:verifiedSource` | **where** they checked; absent = unverified |
| list source | `mom:supplierListSource` | upstream URL of the list this entry came from |
| recommended by | `mom:recommendedBy` | the space vouching for the entry |

`mom:recommendedBy` reads *"this space recommends this supplier"*, not "this supplier serves this
space". The supplier makes no commitment by appearing; the space does. A supplier recommended by
several spaces carries several of these — which is the cross-referencing signal the whole shared
vocabulary exists to produce.

`mom:supplierListSource` is per-entry rather than per-graph deliberately, so entries from a curated
repo list stay distinguishable from entries captured any other way after they land in the same graph.

## Querying

The graph is `<urn:mak:suppliers/<space>>`; the vocabulary is `<urn:mak:ontology/sup>`.

**One question, three languages.** Match the language-tagged `altLabel` and the supplier set is
identical whichever language the asker used:

```sparql
PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX schema: <https://schema.org/>
SELECT ?name WHERE {
  GRAPH <urn:mak:ontology/sup> {
    ?c skos:altLabel ?l .
    FILTER(LANG(?l) = 'fr' && LCASE(STR(?l)) = 'bois')   # or 'en'/'wood', 'nl'/'hout'
    ?n skos:broader* ?c .                                 # include sub-categories
  }
  GRAPH <urn:mak:suppliers/openfab> {
    ?s mom:supplierCategory ?n ; schema:name ?name .
  }
}
```

Dropping `skos:broader*` narrows the answer to the exact concept — "wood" then excludes
specialty-wood. Both readings are valid; pick deliberately.

**Nearby — mind the missing SQRT.** Oxigraph has no `SQRT` function (nor a geospatial
extension), so rank and filter on **squared** distance. Squaring is monotonic, so the ordering is
identical; only the radius must be squared (5 km → `< 25`):

```sparql
  GRAPH <urn:mak:suppliers/openfab> {
    ?s schema:latitude ?lat ; schema:longitude ?lon ; mom:geolocationFidelity ?fid .
  }
  BIND(111.32 * (?lat - 50.8466) AS ?dy)    # degrees → km, latitude
  BIND(70.6 * (?lon - 4.3528) AS ?dx)       # degrees → km, longitude at ~51°N
  BIND((?dy * ?dy) + (?dx * ?dx) AS ?sq)
  FILTER(?sq < 25)                          # within 5 km
} ORDER BY ?sq
```

Two syntax traps worth naming, because both fail with the same unhelpful
`expected ENCODE_FOR_URI`:

- **Spaces around `-` are mandatory.** `?lon-4.3528` tokenizes as `?lon` followed by the signed
  literal `-4.3528`, which is two terms and a parse error. Write `?lon - 4.3528`.
- The equirectangular approximation above is fine at city scale. It is not a geodesic; do not reuse
  it for country-wide distances.

Always select `mom:geolocationFidelity` alongside the distance. A `city` result is a commune
centroid, so its rank is not meaningful against an `exact` one — a UI that hides that is
misrepresenting the data.

## A missing category

Do not mint a local concept. Raise a `mom:OntologyGap` (`ontology/mom.ttl`) with the query and the
context; promotion from local need to shared commons is Epic 10's curation pipeline. A gap logged is
a category that eventually serves every space; a local IRI is a category that serves none.

## Ingestion today, and where this is going

Today MoM vendors the list: `data/supplier-lists/<space>.ttl`, generated from a reviewed CSV by
`scripts/parse_suppliers.py`, loaded by `scripts/load_ontology.sh` into
`<urn:mak:suppliers/<space>>`. The markdown never becomes triples without a human reading the CSV in
between — supplier lists are too messy for one-shot parsing, the same reason `seed_csv.py` exists for
spaces.

**Serialization note.** The file is plain Turtle with **no `GRAPH` block**; the named graph comes
from the load URL (`PUT /store?graph=…`), exactly as `mom.ttl` does. This is not stylistic:
Oxigraph rejects TriG on `?graph=` with `400 Named graphs are not allowed`, and `POST /store` with
TriG merges rather than replaces — meaning a supplier deleted upstream would survive every future
reload. Turtle + graph-at-load-time is the only combination that is both valid and idempotent.

Next, the list moves upstream: it lives in the space's own repo and MoM fetches it — the same
coordinator-endpoint pattern spaces already use for their own data.

Eventually a supplier may want to publish its own endpoint. **This schema is deliberately already
that schema.** The space hosts on the supplier's behalf meanwhile, so the migration asks the supplier
for nothing they would not have had to provide anyway — which is the only version of that
conversation worth having.
