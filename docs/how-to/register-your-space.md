# Host Your Space JSON

Quick guide for coordinators who want to register their makerspace on
[mapsofmaking.org](https://mapsofmaking.org/). You publish a small JSON file
describing your space; Maps of Making fetches it once at registration and
re-polls it every 10 minutes to keep your card fresh.

## What you need

- A **public URL** that returns valid JSON over HTTPS.
- A few fields about your space (name + coordinates are the only must-haves).

That's it. No account, no API key, no server-side software. The map ingests
your file and lets visitors find you.

## What goes in the JSON

The format is [SpaceAPI v15](https://spaceapi.io/) — the same format ~250
hackerspaces already use. If you already publish one, you're done; submit
the URL and skip the rest of this page.

Minimal example:

```json
{
  "api_compatibility": ["15"],
  "space": "Example Space",
  "url": "https://example.org",
  "location": {
    "lat": 50.8503,
    "lon": 4.3517,
    "address": "Rue de l'Exemple 12, 1000 Brussels, Belgium",
    "country_code": "BE"
  },
  "state": { "open": null },
  "contact": { "email": "contact@example.org" }
}
```

Add what you have, leave the rest out. Every additional field unlocks more
of the space card:

| Field | Effect |
|---|---|
| `space` + `location.lat`/`lon` | A pin on the map |
| `url`, `opening_hours`, `description` | Full detail card |
| `logo`, `contact`, `api_compatibility: ["15"]`, `state` | Passes the SpaceAPI validator → interop with mapall.space, etc. |
| `knowsAbout: ["3d-printing", "electronics", …]` | Filter chips for specialties |
| `memberOf: ["vow", "spaceapi"]` | Network filter chips. Declare every federation you belong to |

For richer field coverage and tier details, see `web/test-fixtures/SKILL.md`
or the [SpaceAPI v15 spec](https://spaceapi.io/pages/docs.html).

## Where to host the file

You need a stable HTTPS URL. Cheapest options first:

### 1. GitHub Pages (recommended — durable, free, version-controlled)

1. Create a public repo (or use an existing one).
2. Add a file like `spaceapi.json` at the repo root.
3. Settings → Pages → Source: `main` branch, `/ (root)`. Save.
4. Wait ~1 minute. Your URL is `https://<your-user>.github.io/<repo>/spaceapi.json`.

### 2. GitLab Pages

Same idea. Add a `.gitlab-ci.yml` with the `pages` job from
[GitLab's static-site template](https://docs.gitlab.com/ee/user/project/pages/),
or use the simpler "Pages from public folder" pattern.

### 3. Your own website

If your space already has a website, put the file at any path on it —
e.g. `https://yourspace.org/spaceapi.json`. Make sure your web server sends
`Content-Type: application/json` (most do automatically for `.json` files).

### 4. GitHub Gist (quickest, less durable)

1. Create a public Gist at [gist.github.com](https://gist.github.com/).
2. Name the file `spaceapi.json` and paste the content.
3. Click the **Raw** button — that URL (`https://gist.githubusercontent.com/…/raw/…`) is what you submit.

Gist URLs include a hash and change if you re-create the gist; prefer one
of the first three options for anything you intend to maintain long-term.

## Submit your URL

Once your JSON is live at a public URL:

1. Go to [mapsofmaking.org](https://mapsofmaking.org/).
2. Open the **"Add your space"** drawer (top-left).
3. Paste the URL. Maps of Making fetches it, validates, and adds your pin.

If your space was already on the map as a **grey/seeded pin** (we bulk-loaded
it from a partner network like VOW), submitting your URL **upgrades it in
place** — same pin, now live, with your data as the source of truth.

## Validate before you submit

```bash
# SpaceAPI official validator
# (paste your URL at https://validator.spaceapi.io)

# Or the mom-side validator (what registration uses):
curl -X POST https://mapsofmaking.org/api/validate-url \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://your-public-url/spaceapi.json"}'
```

Both should return a success / `200 OK`. If something's off, the response
explains which field is missing.

## Common pitfalls

- **`Response is not valid JSON`** — usually unquoted keys (JSON5/HJSON) or a
  UTF-8 BOM. Save as plain UTF-8, quote every key.
- **`Name not found`** — add `"space": "Your Space Name"` at the top level.
- **`Coordinates not found`** — `location.lat` and `location.lon` must be
  **numbers**, not strings.
- **Logo doesn't show** — the URL must be reachable over HTTPS; mixed-content
  HTTP gets blocked by browsers.

## Updating later

Just edit your JSON. The next heartbeat tick (within 10 minutes) picks up
the change automatically — no re-registration needed. If you ever change
the URL itself, contact us and we'll re-point.

## Questions, edge cases

Open an issue at [github.com/nicolasdb/mapsofmaking](https://github.com/nicolasdb/mapsofmaking)
or reach out directly. The plan is to add a Discord/Telegram bot that walks
new coordinators through this flow conversationally — until then, this page
is the canonical reference.
