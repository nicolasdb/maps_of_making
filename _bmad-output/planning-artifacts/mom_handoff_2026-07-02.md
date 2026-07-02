---
handoffType: 'architecture-planning'
targetAgent: 'Claude Code'
relatedEpics: ['Epic 6 (NL Bot)', 'Epic 6+ (post-pilot: multi-network personas)']
date: '2026-07-02'
author: 'nicolas + Claude (planning session)'
status: 'ready-for-implementation-scoping'
purpose: >
  Formalize the Bernard skill-routing architecture and the multi-persona
  ("archetype pack") extension for adjacent networks, BEFORE any code is
  written. This brief exists to prevent context pollution in Claude Code —
  it is the single source of truth for this decision. Supersedes any prior
  loose discussion of "unified bot API" or "multiple agents" in chat history.
---

# MOM Handoff — Bernard Skill Routing + Multi-Persona Deployment Architecture

## 0. Why this brief exists (read this first, Claude Code)

This is a **planning artifact**, not a coding ticket. The goal of this session
was to resolve an architectural question that was previously fuzzy across
several conversations, so that implementation can proceed without
re-litigating it mid-sprint. If you (Claude Code) find yourself uncertain
whether to build "one bot with routing" vs "multiple bots," **this document
is the answer — do not re-derive it from scratch or from older chat context.**

If anything in `epics.md` or prior story files conflicts with this brief on
the topic of bot identity/routing, **this brief wins** — it is the most
recent decision and was arrived at deliberately, including devil's-advocate
testing of the alternative (user-as-orchestrator across multiple bots, which
was explicitly rejected).

**Scope boundary:** This brief covers architecture and decision rationale
only. It does NOT include story-level acceptance criteria — those should be
drafted as a follow-up story (proposed: **Story 6.7 — Skill Manifest +
Persona Loader**) once this direction is confirmed against Epic 6's existing
scope.

---

## 1. Decision Summary

**One orchestrator identity per deployment, internal skill routing, no
user-facing multi-bot menu.**

- For Maps of Making pilot: **Bernard remains the sole bot identity.**
- Bernard's internal routing (Tier 0 cache / Tier 1 Gemma / Tier 2 Sonnet —
  see §2) is **not exposed to the user.** The user never chooses a mode,
  skill, or model. One question in, one answer out (FR37–FR40 unchanged).
- **Explicitly rejected:** a model where the user is the orchestrator and is
  expected to know which of several bots/commands to address
  (`@mom-bot` vs `@mom-health-bot` vs `@mom-edu-bot`). This breaks the "no
  forms, no logins, no context-switching" principle that governs every other
  part of MOM's UX (see PRD Journey 1, UX-DR14-16). Rejected deliberately,
  not by default.
- **New for post-pilot:** different **network deployments** (VOW, RFF,
  a hypothetical medical-adjacent network, VLAIO, an LGBTQ+-friendly
  network, etc.) may run **their own persona** — different name, voice,
  visual identity, lore — wrapping the *same underlying skill/routing
  engine*. This is a **reskin + manifest**, not a new codebase, not a new
  agent framework, not a fork.

---

## 2. Layer 1 — Skill Routing (applies to every deployment, every persona)

*(Carried over from prior session — restated here for completeness since
this brief supersedes fragmented context.)*

Three-tier routing, always single-shot (no multi-turn memory):

| Tier | Trigger | Behavior |
|---|---|---|
| **0 — Semantic cache** | Query embedding matches a curated FAQ pair above similarity threshold | **Corrected 2026-07-02 (Story 6.11 roundtable):** matched entry is injected as RAG context into the Tier 1 model call, NOT a bypass — the LLM/tool-calling loop still runs, using the validated template as a grounding hint rather than generating from scratch |
| **1 — Default model** | No cache hit, but query pattern-matches known intent shape (single filter/location/category) | Gemma 4 12B (or deployment-configured default) generates SPARQL via IoP-ontology-grounded prompt |
| **2 — Escalation** | SPARQL validation gate fails, Gemma output malformed/empty, or complexity heuristic trips (multi-clause, negation, comparative) | Escalate to Sonnet (temp=0), same validation gate applies before execution |

**Cost/complexity principle:** the expensive model is a *fallback for
detected difficulty*, not a blanket upgrade. This directly answers the
original "should we upgrade to Minimax/Kimi/Sonnet everywhere" question —
no, route to it.

**Gap log discipline (privacy-sensitive — do not weaken):**
- `gap_log` (FR41) is a **curation queue for human review**, not a training
  set. No automated fine-tuning/RL on logged queries.
- Strip or hash user/channel identifiers at write time.
- Prefer storing abstracted query *patterns* over literal user text once a
  gap is triaged and promoted into the Tier 0 cache.
- Retention window (30–90 days) on raw gap_log entries unless promoted.
- This keeps NFR-C2's "mature data stewardship" claim to grant reviewers
  true in practice, not just on paper.

---

## 3. Layer 2 — Persona / Archetype Packs (new; post-pilot, opt-in)

### 3.1 Core principle

A **persona** is a swappable bundle of:

```
persona/
  identity.yaml        # name, pronouns/voice rules, tone constraints
  lore.md               # backstory, "why this animal/archetype", canon facts
  visual/                # avatar, color tokens, pin/badge styling if applicable
  voice_constraints.yaml # Bernard-style rules: no error codes, always offer
                          # a fallback path, no corporate refusal language, etc.
```

This is **the same shape as your `SKILL.md` pattern already in use for
Claude Code** — a manifest + instructions that get loaded conditionally.
Persona packs are to Bernard's *identity layer* what `tasks/*.py` modules
are to his *capability layer*. Two independent, composable axes:

```
   capability axis (what it can DO)      →  tasks/nl_to_sparql.py, tasks/heartbeat.py, ...
   identity axis   (who it IS to the user) →  persona/bernard/, persona/oxpecker/, ...
```

A deployment picks one persona + a set of enabled skills. The routing engine
in §2 is **identity-agnostic** — it doesn't know or care which persona is
wrapping it.

### 3.2 Why animal archetypes (design rationale, captured for continuity)

Nicolas's stated preference: animal-based personas over human personas,
because animals sidestep genre/race/religion representation questions while
still carrying strong, legible archetype signals (color, behavior, size
dynamics). Two examples on record:

- **Bernard** (makerspace network) — established persona, "deep-sea /
  organism" aesthetic per `state-colour-ladder.html`, Special Elite
  typeface, zine-punk tone.
- **Oxpecker** (proposed, medical-adjacent network) — "Rugged Field
  Medic / Scout Healer" archetype. Alert, vocal, slightly edgy (wound-pecking
  nuance intentionally kept — signals directness, not gentleness-only).
  Red-billed variant → urgency/trauma-care association; yellow-billed →
  caution/precision. Retains the "large patient / small caregiver" dynamic
  of the crocodile-and-plover myth without the human-crocodile framing.

**Not yet decided (flag for a future session, do not invent in
implementation):** exact roster of archetypes for VLAIO, education, or
LGBTQ+-friendly network contexts. Do not assign an animal to these
without a dedicated design pass — this is a values-sensitive choice
(especially for LGBTQ+-friendly network framing) and should not be
delegated to an implementation-time default.

### 3.3 The Claude-analogy, precisely (for shared vocabulary going forward)

This mirrors how Claude itself is deployed, and it's useful to keep this
mapping explicit so future planning sessions don't re-derive it:

| Claude concept | MOM equivalent |
|---|---|
| One model, scoped instructions per Project/deployment | One routing engine, scoped persona + skill manifest per network |
| Skills load conditionally, not all in context by default | `tasks/*.py` modules loaded per manifest, not globally |
| Tools/connectors opt-in per context, not global | Skills/ontology namespaces (`edu:`, `agri:`, medical-guardrail tier) opt-in per network manifest |
| Sub-agent/tool calls return a result folded into one voice | Bernard (or Oxpecker) internally calls a task module, returns one reply — never exposes the call |
| Anthropic sets non-negotiable safety floor regardless of deployment | MOM sets non-negotiable NFR-D1–D4 (space-not-people) + guardrail-tier floor regardless of network manifest |

### 3.4 Deployment manifest (the actual mechanism)

One codebase. One container image. Different manifest loaded at boot:

```yaml
# networks/vow.yaml
network_id: vow
persona: bernard
channels: [discord, telegram]
skills:
  - nl_to_sparql
  - space_discovery
  - endpoint_health_query
ontology_namespaces: [core, fab]
guardrail_tier: standard        # NFR-D1-D4 baseline
llm_tier_ceiling: sonnet        # escalation allowed up to Sonnet
budget_ceiling_usd_month: 40
```

```yaml
# networks/hypothetical-medical.yaml
network_id: medcraft-example
persona: oxpecker
channels: [matrix]
skills:
  - nl_to_sparql
  - space_discovery
  # note: no heartbeat/coordinator-admin skills — this network is
  # maker-discovery only, doesn't need onboarding tooling
ontology_namespaces: [core, medcraft]   # hypothetical extension namespace
guardrail_tier: strict                  # see §3.5 — inherited, not chosen
llm_tier_ceiling: sonnet
budget_ceiling_usd_month: 40
```

### 3.5 Guardrail tier is inherited, not shopped for — this is the one hard constraint

**This is the single most important non-negotiable in this brief.**

A network requesting a sensitive-domain skill (medical, or any future
domain touching health/vulnerable-population data) **must** inherit a
stricter `guardrail_tier`, which tightens — not relaxes — validation:

- `NFR-D2`/`NFR-D3` (person-identifiable field rejection, `schema:Person`
  triple rejection) become **stricter thresholds**, not optional toggles.
- Sensitive-domain networks do NOT get to opt out of PII quarantine to
  "move faster" — the manifest schema should make this structurally
  impossible, not just discouraged in docs.
- If a network's requested skill set implies a stricter tier than their
  manifest declares, **fail closed** at manifest-validation time (deployment
  refuses to boot / CI check fails) rather than silently running at the
  lower tier.

Concretely: `guardrail_tier` should be **derived from the skill list**, not
independently settable by whoever writes the manifest. A skill declares its
minimum required tier; the network's effective tier is the max across all
enabled skills. This prevents a well-meaning but rushed manifest edit from
quietly weakening data handling for a sensitive deployment.

---

## 4. What this does NOT change

- Bernard's voice constraints, error-handling philosophy (FR40, UX-DR12),
  and single-shot interaction model are unchanged and now apply as the
  *template* other personas' `voice_constraints.yaml` should follow, not
  something forked per persona.
- Epic 6 scope (Discord → Telegram → Mattermost via `ChannelAdapter`
  protocol, AR-AGT5) is unchanged. Persona packs plug into the same
  protocol-agnostic core; `channels:` in the manifest is just which
  adapters are active per network — you already designed this correctly.
- The NL→SPARQL validation gate (NFR-S5) applies identically regardless
  of persona or network — it is not part of the persona layer, it lives
  below both axes.
- MOM pilot (VOW/RFF, Bernard-only) requires **none** of §3 to ship. This
  section is forward architecture so that when a second network asks for
  a different identity, you extend a manifest instead of re-architecting.

---

## 5. Explicit non-goals (say no to these if Claude Code drifts toward them)

- ❌ Do not build a general-purpose "agent marketplace" or plugin store UI.
  This is a YAML manifest edited by Nicolas/Jason, not a self-serve product
  surface, for the foreseeable future.
- ❌ Do not implement cross-persona memory or a "meta-Bernard" that knows
  about other networks' personas. Each deployment is isolated; personas
  don't reference each other.
- ❌ Do not let a persona pack override `guardrail_tier` downward. If this
  shows up in a diff, it's a bug, not a feature request.
- ❌ Do not invent additional animal archetypes for VLAIO/education/LGBTQ+
  networks as a side effect of implementation work. That's a separate
  design decision explicitly deferred per §3.2.
- ❌ Do not build fine-tuning/RL infrastructure off `gap_log`. Curation
  queue only (§2).

---

## 6. Suggested next steps (for course-correction session with Claude Code)

1. **Spring-clean pass first, before any new code:** reconcile `epics.md`
   Epic 6 stories against this brief — no rewrite needed, just confirm no
   contradiction, and add a pointer comment in Epic 6's header referencing
   this handoff file.
2. Draft **Story 6.7 — Skill Manifest + Persona Loader** as a proper story
   (Given/When/Then ACs) scoped to: manifest schema + validation
   (guardrail-tier derivation, §3.5) + Bernard running unchanged through
   the new loader (i.e., prove the refactor is behavior-neutral for the
   pilot before any second persona exists).
3. Do **not** build the Oxpecker persona or any medical-domain skill yet —
   that's a future network's onboarding, not pilot scope. This story is
   about making the *seam* exist cleanly, not populating it.
4. Add a short "Persona Architecture" pointer section to `epics.md` Epic 6
   overview linking to this file, so future planning sessions don't
   rediscover this decision from scratch.
