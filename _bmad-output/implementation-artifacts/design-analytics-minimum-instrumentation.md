# Design — Minimum instrumentation (the analytics gap)

**Created:** 2026-08-15 · **Source:** roundtable (John, Winston, Mary, Sally) · **Status:** design agreed, **open decisions at the end — not yet a story**
**Trigger:** "By the way, analytics are totally missing from this project. We should plan something to at least be able to watch adoption progress." — and the follow-up: *"Can we implement Google Analytics or something? 7 days rotation is different logs and avoids bloating the VPS."*

---

## The first numbers this project has ever had

Read from the surviving 7 days of `maps-nginx` access logs (08–15 Aug 2026, 16,070 lines) before they rotated out:

| | |
|---|---|
| `GET /` map index loads | **338** — of which **56** are self-identified crawlers (Googlebot, GPTBot) |
| `POST /api/validate-url` | **2** |
| `POST /api/register-url` | **1** |

Referrers on those index loads:

| referrer | hits |
|---|---|
| `mapsofmaking.com` | 70 |
| `mapsofmaking.org` | 59 |
| `openfab.be` | 43 |
| `google.com` (organic) | 6 |
| `jasonpettiaux.com` | 2 |

So: **~280 non-bot loads → 2 endpoint-form reaches → 1 registration**, in a week. And that one registration is the OpenFab one that **showed the user a red `JSON.parse` failure while actually succeeding** (see `quick-dev-zoom-legibility-register-timeout.md`). The single most motivated human who touched the project all week was told it didn't work. Nobody knew for seven days.

`jasonpettiaux.com` is a third-party site hitting `GET /?preset=maps-of-making&bbox=...` — **the embed is live in production on a site Nicolas doesn't control.**

## Answer on Google Analytics: no. Unanimous, four different reasons.

**It measures the wrong layer.** Against the four decisions worth instrumenting, a browser tag scores two out of four — and gets the important one *wrong*. GA would have logged this week's registration as success or failure depending on which JS branch fired, i.e. it would have recorded the lie. Matrix bots have no browser; MCP calls from another machine have no browser. Those are structurally invisible to GA, not merely hard.

**The disk-bloat premise is inverted.** 16,070 access-log lines ≈ **3.5 MB/week**, ~180 MB/year — that's the thing you're already storing, and it's 95% noise (16,070 lines to describe 338 page loads and one registration). A five-field event log at this volume is **under 80 KB/week, ~4 MB/year**. You could keep ten years and not notice. Deleting your entire history to save 3.5 MB on a Hetzner box isn't a disk decision, it's an accident. And GA doesn't reduce disk at all — it offloads it to Google.

**It contradicts the product.** Zone 3 (raw source JSON on the card) is a claim about restraint aimed at trust evaluators. `gtag.js` in devtools retroactively downgrades every sovereignty sentence to marketing, and the nuance is invisible while the script tag isn't. The IoP Alliance gets asked by its own funders what tooling it endorses; "the mapping partner ships Google tracking" is a sentence someone would have to answer for.

**EU/Belgium, concretely.** GA is non-essential analytics → prior opt-in consent, refuse-as-easy-as-accept, APD/GBA enforcement. Several EU DPAs (Austria, France, Italy) ruled specific GA deployments unlawful over US transfers; the ground shifted with the EU–US Data Privacy Framework, but "currently arguable" is a bad foundation for a solo dev with no legal budget in a project whose brand *is* data governance.

**And the embed makes it other people's problem.** Every makerspace embedding MoM would become an unwitting joint controller, shipping their visitors to Google, uncovered by their own consent banner. **Whatever gets built, the embed must be measurement-free. Non-negotiable.** Sally's version: black screen, 3193 lights come up, Overview Effect — and a white cookie rectangle slides over it. You'd destroy the best moment the product has, for every visitor, forever.

Self-hosted containers: **emit nothing by default.** Phoning home is a trust liability in a sovereignty project. But don't over-apply that into blindness — instrumenting *your own hosted surface* is operating a service, not surveillance.

## Do this — in order

**1. Fix the log_format. Today. Ten minutes.**
`maps-nginx`'s `log_format main` records only `$remote_addr`, which is always the `nginx-gateway` container IP — **unique visitors currently resolve to exactly 1, and always will.** `X-Forwarded-For` is already set on every `proxy_pass` but never written. Add `$http_x_forwarded_for` to the format — or better, `set_real_ip_from` the gateway subnet + `real_ip_header X-Forwarded-For`, so `$remote_addr` becomes correct everywhere and error logs and any future rate limiting get honest too.

**2. Stop rotating to nothing.** Either extend retention to 90 days compressed (~20 KB/day gzipped = under 2 MB — the bloat concern doesn't survive contact with the real numbers), or add a logrotate `prerotate` hook that appends **one aggregate row per day** (date, loads, non-bot loads, validates, registrations, embed referrers by domain) to a CSV before the raw lines die. ~50 bytes/day = 18 KB/year. The pain today is that nothing before 08 Aug exists; that pain repeats every Monday until this is fixed.

**3. GoAccess as a one-shot Makefile target.** Runs against the log files, emits static HTML, exits. **Zero resident containers.** Gets you unique visitors, referrers, geography, bot separation, status codes.

**4. The event log.** Append-only **JSONL file** written from `link_handler` — `{ts, event, surface, space_slug, ...}`. Explicitly **not** Oxigraph: the `public_ledger` graph's contract is "never dropped, publicly readable," and behavioural telemetry does not belong in it; also SPARQL is a bad language for "count events per week grouped by type." Explicitly not SQLite as the first move either. A file append cannot lock, cannot corrupt a shared DB, cannot block a request — **the failure mode of analytics must never take down the map.** Promoting JSONL into the heartbeat SQLite later is a thirty-line migration if real joins ever become necessary.

`make metrics` prints weekly counts to the terminal. **Not a dashboard.** If it takes more than a day, it's the wrong thing.

**Explicitly rejected:** Plausible (= Plausible + ClickHouse + Postgres; ClickHouse alone wants ~1 GB RAM), Umami, Matomo. Not primarily RAM — every persistent container is a backup surface, a CVE feed, a migration that can fail during `make publish`, and a service to debug at 11pm. For a solo dev that's a subscription paid in attention forever. Also: all of them need a client-side beacon, which third-party cookie blocking and ITP eat by an *unknowable* fraction inside an embed. Server-side isn't the compromise here — for this architecture it's the more accurate instrument.

## Which events, and why each earns its place

Rule: **a metric must name a decision it can flip.** Every event below has a plausible outcome where you *stop doing something*. A metric that can only produce "number went up" is decoration.

**Outcome events (server-side, `link_handler`):**
- `tool_invoked{tool, surface, caller}` — settles *does travel_search survive the migration?* Log the tool name and whether it returned results, **never the query text**.
- `registration_started` / `registration_succeeded` / `registration_failed{reason}` — the conversion that matters most; the failure *reason* is the gold ("endpoint didn't validate" ×40 is a roadmap).
- `wizard_started` / `wizard_completed` — is the wizard a bridge or a dead end? That last hop is the whole thesis of Epic 9.
- `gap_logged` — **already built and currently write-only.** Surface it in the same report. It's the only artifact containing a human's actual words about what they wanted and couldn't get. If only one event survived, this is the one.

**Sally's additions — the ones that explain rather than count:**
- `drawer_opened` — **the missing denominator.** Every event above fires *after* the fork decision. `wizard_started / page_load` is meaningless because it mixes people who wanted to register with people who wanted to look at a map; `wizard_started / drawer_opened` is a real question.
- `drawer_dismissed_at_fork` — opened, chose nothing, closed. If that's the fat number, the fork copy is the bug and no amount of wizard polish helps.
- `path_chosen{wizard|endpoint}` — and specifically people who choose endpoint, bounce, then choose wizard. That's the **intentional jargon polarization working**, a principle-driven decision that has never once seen evidence.
- `wizard_abandoned{last_beat_id}` — **one** event with a payload, not a per-beat pageview. The locked `<section>-beat-<leaf>` taxonomy turns it into a sentence ("people leave at `location-beat-address`") instead of a drop-off chart.
- `beat_reentered{beat_id}` — going backwards means not trusting your answer. Honest derivation is a locked wizard principle; re-entry is the measurable signal that the derivation *wasn't legible*. No analytics vendor would ever suggest this event.
- `registration_result_shown{outcome}` — **catches the exact bug that just happened.** A server-side log alone would have recorded `registration_succeeded` and shown nothing wrong; the failure was the *client rendering a server-side success as red text*. Server-succeeded + client-shown-failure = a loud alarm, not a seven-day-later log archaeology session.

## What NOT to measure

Page views, bounce rate, time on site, map pans and zooms, anything needing a chart to understand.

**Do not log query text or user identifiers.** The project's PII position is that *coordinator endpoints are public data the coordinator owns* — that is a completely different claim from "we retain what individual humans typed at our bot." Log the shape of the question: intent class, tool called, result count. Never the string. If the raw string is needed for debugging, that's `log_gap`'s job and it's opt-in by nature.

**Do not pipe the heartbeat into the event log.** It fires every 10 minutes against 3193 endpoints and would drown seven interesting events in millions of boring ones. Heartbeat health is operational and belongs in Epic 4's admin panel; it is not adoption.

**Consider hashing IPs if they're stored at all** — a daily-rotating salted hash of IP+UA gives unique-ish counts, stores no address, and removes a GDPR conversation permanently. Three lines.

## Known seam

`maps-nginx` serves the map statically (`root /var/www/mapsofmaking`, `location /` → `try_files`); `link_handler` sits behind `/api/` and `/claim/` only. So **nginx owns traffic; the event log owns outcomes**, and the event log structurally cannot see an index load. Know where the seam is rather than discovering it when the two numbers disagree.

Also: embed mode is detected via `window.self !== window.top` on the **same URL** (`web/app.js:47`), not a separate `/embed` route. So embed measurement is `GROUP BY referer` on `GET /`, not on a route.

## The dissent worth keeping

**Sally:** don't treat 280→2 as a conversion rate. 278 of those people never arrived intending to register — they came to look, and looking is the product working. Instrument it as a funnel and you'll start optimizing the drawer to catch people who were never walking toward it, making the map louder and more CTA-shaped, trading the Overview Effect for a 4% click-through. *"You have one registration. One person, with a URL, who saw red text. Go find them and ask what the drawer felt like. One conversation will out-explain six months of a dashboard."*

**John:** at ~280 loads/week you can hold usage in your head. You don't have an instrumentation problem, you have a **distribution** problem — and instrumentation is the cheap comfortable thing to build instead of facing it. Build the log because it's three days that compound and stop the bleeding, but don't mistake it for progress on the thing that's actually broken. *"What would you have done differently this week with perfect analytics? If the answer is nothing, that tells us where the month should go."*

**Mary:** don't measure visitors — measure the **network**, and publish it. The heartbeat over 3193 endpoints plus the three-token freshness model is a live dataset nobody else has: how many spaces reachable, how many stale, how many went dark this quarter, which regions maintained. A public "state of the network" page is the number the IoP Alliance can cite, a funder reads, and a coordinator sees and thinks *I should be on that map, and green*. **Analytics measures whether people looked at you; network health measures whether the commons is alive — and only one of those is a reason for anyone to fund you.** It's also already being collected and thrown away.

**Sequencing:** analytics does **not** block the MCP work — but the MCP work should not ship unmeasured. MoM-MCP would be a *third* consumer path (map, bot, now external MCP clients), and per-tenant tokens there are the only way a self-hosted install becomes an observable event without anything phoning home. See `design-mom-mcp-tool-surface.md`.

---

## Open decisions — need Nicolas

1. **Funnel or trend?** Is the question "is the wizard leaking?" or "is anything growing at all?" Different instruments. Mary suspects funnel; Sally argues the funnel framing is itself the trap.
2. **Store IPs, hashed IPs, or neither?** Default recommendation: salted daily hash, or nothing.
3. **"Avoids bloating the VPS" — disk, or not wanting another service to babysit?** If it's the second, the seven events are *less* operational burden than GA, not more, and the answer changes.
4. **Does Mary's public network-health page get built instead of, or alongside, the event log?** She argues it's the fundable artifact and the event log is not.
5. **Would you actually kill `travel_search` in 90 days if the number stays at four?** If not, don't instrument it — the decision is already made.
