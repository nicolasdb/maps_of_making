# Maps of Making

> Maker spaces are invisible because maps go stale. We're fixing that.

---

## The Problem

Fifteen directories list makerspaces, fablabs, hackerspaces, and maker labs across Europe and globally.

And yet — when someone in a 200+ member network needs to know if the Venice fab lab is still open, they post in the group chat. Because they know maps are stale.

**Here's why:**
- Spaces register once to claim presence, then never update. The reward for signing up is being on the map. There's no incentive to maintain.
- So you update one directory, realize you need to update thirteen others, and… you stop.
- Meanwhile, every group chat keeps asking the same questions: *"Anyone know a space near Barcelona? Is this place still open? Who hosts residencies?"*

The real problem: you're pushing data to fifteen platforms. Nothing incentivizes keeping it fresh.

---

## The Flip

What if it worked backwards?

**You publish one file** — a small, structured file about your space (name, address, status, specialties) — at any public URL you control. Your website, GitHub, Nextcloud, a simple server. Anywhere.

We read *from you*. Continuously. When you update that file, the map updates everywhere instantly. No forms, no logins, no middleman.

```json
{
  "name": "FabLab of Ooo",
  "address": "12 Sugar Plum Street, Land of Ooo",
  "website": "https://fablab-of-ooo.example",
  "status": "open",
  "opening_hours": "Mon–Fri 14:00–20:00",
  "specialties": ["woodworking", "electronics", "candy engineering"],
  "networks": ["VULCA", "Adventure Makers Network"]
}
```

This is the logic behind [SpaceAPI](https://spaceapi.io/) — thousands of hackerspaces have used it for years. We're bringing that spirit to the broader maker ecosystem.

---

## What it unlocks — progressively

**Day 1:** From that file alone, the map answers real questions:
- *"Show me all open spaces within 100km of Bath"*
- *"Which spaces in Germany have woodworking?"*
- *"Who's part of the VOW network?"*

**Layer 2:** Once networks agree on shared vocabulary — that "woodworking" and "wood shop" are the same thing — we unlock cross-network queries. A simple ontology that lets your data talk to other people's data.

**Layer 3:** A bot in a Mattermost channel reads: *"Cherche espace ouvert à accueil en Allemagne"* — and instead of the group chat guessing, it queries all French and German networks' endpoints, finds matches, returns them as a map with train times. All from structured, live, open data.

---

## Built on open standards

- **[SpaceAPI](https://spaceapi.io/)** — proven endpoint pattern, already used by hackerspaces globally
- **[W3C Linked Data](https://www.w3.org/standards/semanticweb/data)** — structured data that means the same thing everywhere
- **[Solid](https://solidproject.org/)** — your data, your file, your URL
- **[SPARQL](https://www.w3.org/TR/sparql11-query/) & [Oxigraph](https://oxigraph.org/)** — federated queries across all space endpoints

This isn't proprietary. It's infrastructure you can understand, audit, and fork.

---

## Where we are now

**Pilot networks:** RFF (Réseau des Fablabs Français) and VOW (Verbund Offener Werkstätten) are the first to participate.

**Live stack:** The `lod-prototype` branch runs the full federation: Oxigraph ingesting endpoints, SPARQL queries over the aggregated data, an interactive map powered by fresh, decentralized data.

**Next:** Workshops with pilot networks to walk spaces through setup (no solo effort required). Then scaling to more regions.

---

## Documentation

| | | |
|---|---|---|
| 🧭 **Tutorial** | Learn by doing | [Publish your first space](docs/tutorial/01-publish-your-first-space.md) |
| 🛠️ **How-to guides** | Solve a specific task | [Register your space](docs/how-to/register-your-space.md) · [Import a batch of spaces](docs/how-to/import-a-space-batch.md) · [Set up Mother Sands](docs/how-to/set-up-mother-sands.md) · [Diagnose a broken map](docs/how-to/diagnose-a-broken-map.md) · [Operate the VPS](docs/how-to/operate-the-vps.md) |
| 📖 **Reference** | Look up the facts | [Field traceability](docs/reference/field-traceability.md) · [Semantic layer](docs/reference/semantic-layer.md) · [Freshness axes](docs/reference/freshness-axes.md) · [VPS topology](docs/reference/vps-topology.md) |
| 💡 **Explanation** | Understand the why | [Mother Sands concept](docs/explanation/mother-sands-concept.md) · [Field lifecycle](docs/explanation/field-lifecycle.md) · [OHM integration](docs/explanation/ohm-integration.md) · [Architecture](docs/explanation/architecture/01-walking-skeleton.md) |

## For space operators

Early pilot networks (RFF, VOW) are rolling out workshops now. If you're outside those
networks and want to join, [reach out](mailto:nicolas.de.barquin@gmail.com) — or jump
straight to the [tutorial](docs/tutorial/01-publish-your-first-space.md) or the
[how-to guide](docs/how-to/register-your-space.md).

The setup is simple:
1. Publish a structured file at a URL you control
2. Tell us the URL
3. Your space appears on the map — and stays fresh when you update the file

---

## For developers

- **`/web`** — React frontend, live map powered by SPARQL queries
- **`/infra`** — Docker Compose stack: Oxigraph, Nginx, the full federation layer
- **`/ontology`** — Shared vocabulary (RDF schema) that spaces and networks define together
- **`/harness`** — Integration test suite for the federation protocol

The architecture is designed for sovereignty: networks can run local Oxigraph replicas, communities own their vocabularies, spaces control their data.

---

## For researchers

Space history is preserved, not deleted. Time-based queries are part of the design — "Which spaces closed in 2024? What patterns exist?" Research on makerspace ecosystems doesn't require scraping; it comes from shared, structured data.

---

## License

**Apache 2.0** — enables community remixing, derivative funding, and institutional partnerships without gatekeeping.

All code and schemas are open source. We're building commons infrastructure, not extracting data.

---

## Citation

```
Maps of Making: Federated Makerspace Data Commons.
Built on SpaceAPI, W3C Linked Data, and open standards.
https://github.com/maps-of-making
Apache 2.0 License, 2025
```

---

<div align="center">

**One file per space. Fresh data everywhere. A map the ecosystem maintains because it owns it.**

[🚀 Blog post](https://nicolasdb.eu) • [🔧 Architecture](/ontology) • [💬 Contact](mailto:nicolas.de.barquin@gmail.com)

</div>
