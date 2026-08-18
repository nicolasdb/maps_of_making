# Seed import runbook — adding a new batch of spaces

> **Scope:** Path B seeding — spaces that don't yet publish a SpaceAPI endpoint.
> Each record lands as a grey/seeded pin. When a coordinator later claims it and
> registers a live endpoint URL, the heartbeat pipeline takes over in-place.
>
> Path A (live endpoint → heartbeat fetch → auto-seed) is documented in
> [operate-the-vps.md](operate-the-vps.md) under "register URL".

## The philosophy — curate, don't auto-parse

MoM does **not** try to parse every messy source format. Scraped lists are dirty
(duplicate entries, corrupt URLs, addresses crammed into one string, swapped lat/lon).
Rather than grow an import script that guesses at all of it, we **curate a clean CSV by
hand** and convert that to a bundle. This is deliberate:

- A batch import happens rarely — the one-time cleanup effort is cheap.
- **It is not our job to do a space's homework.** This is a demo whose whole point is to
  convince spaces to publish a clean SpaceAPI endpoint. A space seeing *"that's me on the
  map — but the data is wrong, how do I fix it?"* is the nudge working as designed.
- Missing data stays missing. A blank website or absent tags is honest signal, not a
  failure to paper over.

So the pipeline is: **messy source → CSV pivot → human cleanup → canonical bundle → seed.**

## The CSV pivot workflow

```
 any list  ──to-csv──▶  curation.csv  ──(edit in a spreadsheet)──▶  clean.csv
                                                                       │
                                                                  to-bundle
                                                                       ▼
 map ◀── make seed-bundle ◀── BE.bundle.json  (canonical mom:Space records)
```

### Step 1 — get a starting CSV

Already have a merged/scraped JSON (like `data/seed-lists/BE.spaces.json`)? Dump it to a
CSV to start from:

```bash
source venv/bin/activate
python scripts/seed_csv.py to-csv --bundle data/seed-lists/BE.spaces.json --out /tmp/be.csv
```

Starting from scratch instead? Copy the template:

```bash
cp data/seed-lists/template.csv /tmp/be.csv
```

### Step 2 — clean it in a spreadsheet

Open the CSV in LibreOffice / Excel / Google Sheets and fix the data by hand:

- **Deduplicate.** Merge tools emit the same space twice (e.g. `BUDA::lab` and
  `BUDA::lab Kortrijk`). Keep one.
- **Split the address.** `to-csv` dumps a free-form address string into the `street`
  column. Split it into `street` / `postcode` / `city` / `country` (ISO code: `BE`, `NL`).
  The `city` feeds the space's slug, so it matters for uniqueness.
- **Fix or blank bad URLs.** Corrupt URLs are already blanked during `to-csv`. Add the
  real website if you know it; otherwise leave it blank — the space still appears.
- **Drop junk rows.** Stub/placeholder names (`Unnamed`, `£dFix`) — delete them.
- **Check lat/lon.** Anything outside Europe gets flagged at convert time.

### CSV columns

| Column | Maps to | Notes |
|---|---|---|
| `name`* | `schema:name` | **required** |
| `lat`* | `schema:geo` latitude | **required**, decimal degrees |
| `lon`* | `schema:geo` longitude | **required**, decimal degrees |
| `street` | `schema:address` streetAddress | |
| `postcode` | `schema:address` postalCode | |
| `city` | `schema:address` addressLocality | feeds the slug |
| `country` | `schema:address` addressCountry | ISO 3166-1 alpha-2 (`BE`) |
| `url` | `schema:url` | http/https only; else dropped + warned |
| `profile_url` | `mom:profileUrl` | http/https only |
| `tags` | `schema:knowsAbout` | **semicolon-separated**: `3d-printing;laser-cutting` |
| `fidelity` | `mom:geolocationFidelity` | `exact` / `approximate` / `city-level` |
| `note` | `mom:geolocationNote` | free text |

Unknown columns are ignored. Header row required; column order is free.

### Step 3 — convert to a bundle

```bash
python scripts/seed_csv.py to-bundle --csv /tmp/be-clean.csv --out data/seed-lists/BE.bundle.json
```

It prints a summary (`written`, `no_name`, `no_geo`, `out_of_bbox`, `url_dropped`).
**Read it** — every dropped row is logged with a reason (no silent drops). The output is
a canonical `mom:Space` array, the same shape as `data/archive/moms_seed.json`.

### Step 4 — seed it

```bash
# Local first (verify on http://localhost:8080 before VPS). Needs the dev stack up.
make seed-bundle BUNDLE=data/seed-lists/BE.bundle.json NETWORK=be

# Then VPS (requires ssh to hetzner)
make vps-seed-bundle BUNDLE=data/seed-lists/BE.bundle.json NETWORK=be
```

`NETWORK` becomes `mom:memberOf <urn:mak:network/be>` and the map filter-chip label.
Use a short lowercase slug: `be`, `vow`, `rff`, `vulca`, …

`make seed-bundle` (local) runs `seed_bundle.py` via venv against the published
`localhost:7878`, then rematerializes the GeoJSON. `make vps-seed-bundle` does the same on
the VPS: scp → `docker cp` into `maps-link-handler` → run → `/api/rematerialize`.

`--force` (always passed by both targets) overwrites graphs **with the same source tag**.
It never overwrites self-registered spaces — a coordinator who has already claimed and
registered a live endpoint is safe from a re-import.

## After seeding — verify

```bash
# Count seeded spaces in Oxigraph
ssh hetzner 'docker exec maps-link-handler python3 -c "
import httpx
r = httpx.post(\"http://oxigraph:7878/query\",
    data=\"SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s a <https://nicolasdb.github.io/mapsofmaking_ontology/ns#Space> } }\",
    headers={\"Content-Type\":\"application/sparql-query\",\"Accept\":\"application/sparql-results+json\"})
print(r.json()[\"results\"][\"bindings\"])
"'
```

Then reload the map — grey pins should appear, and the new slug shows in the network
filter. (New spaces are invisible if a filter is already active — clear filters after a
fresh import. See the registration-filter-reset note.)

## The slug collision risk

The space URI is `urn:mak:space/<name-slug>-<city-slug>`. Two spaces with the same name
*and* city collide; the second is skipped with `SKIP (graph exists, different source)`.
This is why deduplicating and filling `city` during curation matters. Records with no
`city` get a name-only slug.

## `seed_bundle.py` also accepts JSON directly (no CSV)

If you already have clean records, you can skip the CSV and feed `seed_bundle.py` a JSON
array or a `{"spaces":[…]}` wrapper directly. Per-record keys are tolerant: name accepts
`schema:name` / `name` / `space`; coordinates accept `schema:geo` / `geo` / `location`
with `lat`/`lon` or `schema:latitude`/`schema:longitude`. But for anything scraped, the
CSV pivot is the supported path — it's where the cleanup belongs.
