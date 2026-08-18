# Mother Sands — Concept Document

Mother Sands is MOM's **diagnostic canary**: a synthetic reference space we control to test our own data pipeline. It appears on the public map with an honest label identifying it as an instrument, not a real space.

## What this document covers (Story 3.3)

This document captures the **diagnostic instrument** concept. The storytelling layer — Mother Sands' persona (Bernard), lore (Maunsell sea fort concept), broadcast rig, and website — is Epic 8's responsibility.

## Diagnostic purpose

Mother Sands' SpaceAPI endpoint is programmable: the operator can inject controlled states across three independent signal axes to attribute faults to specific layers when the public map shows something incoherent.

| Axis | What it drives | Fault attribution |
|------|---------------|-------------------|
| **A** Reachability | HTTP behaviour (200/304/503/timeout/DNS fail) | Endpoint fault → MOM nudges coordinator |
| **B** Lifecycle freshness | Days since last meaningful content update | System fault → MOM's responsibility |
| **C** Open/Close boolean | `state.open` propagation | Presentational |

See `../how-to/diagnose-a-broken-map.md` for how to use the canary to diagnose pipeline faults.

## Named graph isolation

All canary data lives in `<urn:mak:canary>`. Production space data lives in `<urn:mak:space/*>`. The coherence report verifies isolation on every run.

## `public_ledger` named graph — name locked, schema deferred

A third Oxigraph named graph exists: `<urn:mak:public_ledger>`.

This graph is an **append-only, immutable event ledger** — the authoritative record of significant space lifecycle events (registration, retirement, revival). The name and the append-only principle are locked as of Story 3.3.

**Deferred to a dedicated future epic:**
- Event schema and triple vocabulary
- IPFS/IPLD pinning mechanics (content-addressed immutability)
- Minting authority (who can write events)
- Relocation UX (what happens when a space changes its SpaceAPI URL)

Do not implement the schema or IPFS pinning in this story. Only the name `<urn:mak:public_ledger>` and the append-only principle are locked here.

## Epic 8 scope (NOT this story)

- Bernard persona (they/them pronouns, voice, reference inspirations)
- Maunsell sea fort lore (never-built eighth fort, squatted-gap framing)
- Broadcast rig (changelog, feature comms)
- Mother Sands website
- Time-bubble demo for federated PoC
- "Liveliness sovereignty" opt-out UX (Epic 5)

## Truthfulness

Mother Sands' drawer on the public map carries a clear label:

> **Synthetic reference space** — Mother Sands is MOM's diagnostic canary — a reference space we control to test our own data pipeline.

This label appears regardless of the current scenario state.
