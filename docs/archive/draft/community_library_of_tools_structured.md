# Maps of Making — Vision: The Library

**Date:** 2026-06-28  
**Status:** Draft — structured from voice notes  
**Source:** `community_library_of_tools.md`

---

## The three layers of Maps of Making

Maps of Making grew in three successive layers, each unlocking the next:

**Layer 1 — The Map**  
A gateway between the digital world and the physical world. But from the start it was more than a map — it was the infrastructure for an enduring map. One that does not depend on the people managing it. A federated map where spaces control their own data.

**Layer 2 — The Interface**  
Once the map existed, the question became: how do you talk to it? The answer is Bernard — a bot that lets anyone interrogate the map in natural language. *Where can I find a space near Barcelona with a laser cutter? Is this place still open?* But the bot immediately raised a deeper question: what data do you actually need to record for those questions to be answerable?

**Layer 3 — The Library**  
This is what we are building now. The Library is the answer to "what data should spaces share about themselves?" It is an open catalogue of fields and functions — contributed by researchers, developers, and communities — that spaces can add to their JSON file. Each new field comes paired with a bot function that makes that data useful and findable. The Library is what turns the map from a directory into a living knowledge commons.

---

## What is the Library?

The Library works like an app store, but for structured space data.

Any contributor — researcher, developer, network coordinator — can propose a new **field** to add to the JSON file a space hosts, and a matching **function** (a bot query or automation) that uses that data in a constructive way.

The key principle: **what gets used does not go stale.** A field that answers real questions for real people gives spaces a reason to keep it current.

We have no idea how far contributors' imagination will go. That is the point.

---

## Examples

### Events
A space publishes its upcoming events in its JSON file. The bot can:
- List all events hosted by spaces in a given city this month
- Filter by tag (electronics workshop, repair café, open evening)
- Help a space operator add or update an event directly through the bot

### Artist discovery
A museum wants to find emerging artists from its own city — not through commercial networks, but through grassroots community endorsement. They query the map: *which artists are being promoted by makerspaces in Brussels?*  
The makerspace becomes a trusted agent of recognition — not an algorithm, but a community vouching for its own people.

### Sustainable Development Goals (SDGs)
Public administrators and researchers want to understand what kinds of projects spaces work on and which SDGs they address. A space can tag its projects accordingly. Research grants can fund the development of this field and, once built, it becomes part of the shared Library — attached to the commons permanently.

### Education
Schools and training organisations need to identify which labs can support their pupils at a given age or skill level. A Library field for educational programmes and age ranges makes spaces findable for exactly this kind of partnership.

### Open hardware projects
Open hardware communities (OpenFlexure, OpenScan, and others) are deeply tied to their physical build communities. A Library field for "devices built here" lets anyone find:
- Where to buy an already-built device
- Where to get hands-on help from experienced builders
- Where to join a build session or contribute to a new version

---

## Building bridges between networks

Maps of Making is also building protocols for networks to become real networks.

Today, most maker networks are relatively vertical. A network signs agreements at the representative level — in a capital city — and that rarely propagates back to the small village where there is a repair café and a makerspace that have never heard of each other, let alone started working together.

The Library is part of the answer. When a fab lab in Brussels and a repair café in Brussels develop a working collaboration, they can document it — what they did, what worked, what protocols they used. That documentation becomes a findable, reusable resource. A makerspace and a repair café in a small Spanish city can find it, learn from it, and adapt it to their context.

The goal: make inter-network collaboration something that propagates horizontally through communities, not just vertically through representative structures.

---

## Individuals are at the core: handshakes and documentation

While most of Maps of Making involves groups — associations, small companies, institutions — the individual is the core unit.

We are building a system of **handshakes**: peer recognition that combines:
- Verified opinions and constructive feedback
- Objective documentation (someone did something and proved it)

The problem we are solving: documentation disappears into archives nobody reads. When someone documents something well, we want to make it visible, findable, and attributable — so that the act of documenting is rewarded, not wasted. Recognition is the incentive that makes documentation worth doing.

---

## How to contribute

**Bring in more spaces**  
The easiest contribution. Fab labs and makerspaces first — but the map is open to any space that creates, repairs, teaches, or collaborates. Farmers, bike workshops, museums, schools, libraries. Help them understand the value, help them publish their file, help us understand their needs.

**Build new Library functions**  
You know a kind of space well. You see that some information is missing from the catalogue — specific to that community, not yet in the Library. Add the field. Build the function. Make that data useful. A field that answers real questions for real people is a field that stays fresh.

**Institutional partnerships**  
If you are an institution with specific needs, reach out. Your resources and funding can help build something that serves your use case while becoming part of the commons — a shared map that everyone benefits from.

---

## What this means for the community site

The Library vision shapes what the developer community site needs to communicate:

- The map is the entry point, not the destination
- Contributors are not just coders — they are domain experts who understand what data a space should share
- The contribution loop is: *know a community → identify missing data → build the field + function → publish to the Library*
- The governing question for every feature: **does this make the data more useful, and therefore more likely to stay fresh?**
