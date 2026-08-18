#!/usr/bin/env python3
"""check_docs.py — staleness tripwire for the planning + architecture docs.

Greps LIVE docs for known-DEAD architecture tokens (facts superseded by Epic 3.5
and the canonical-namespace migration) and fails if one reappears in a context
that isn't an explicit negation / supersession / edit-history line.

This is a tripwire, not a linter. It does not prove the docs are correct — it
only catches *regressions* of facts we have already reconciled. When a new fact
is superseded, add its dead token to DEAD_TOKENS so the guard protects it too.

Scope
-----
  STRICT    architecture.md, prd.md, docs/explanation/architecture/*.md,
            docs/reference/{field-traceability,semantic-layer,freshness-axes}.md
            (must be fully clean)
  PREAMBLE  epics.md, only the reference sections ABOVE '## Epic 0'
            (Requirements Inventory + Architecture References + traceability +
            Epic List). Done-epic story bodies below are intentional history and
            are NOT scanned — see the correct-course decision 2026-06-05.
  SKIPPED   planning-artifacts/archive/**  (the historical record; stale on purpose)

Escape hatch
------------
  A line that legitimately mentions a dead token (e.g. a retained-for-rationale
  superseded ADR) can be allowed two ways:
    1. phrase it as a negation/supersession (see ALLOW), or
    2. append the sentinel  # stale-ok   (or <!-- stale-ok -->) to the line.

Exit code 0 = clean, 1 = stale token found, 2 = bad invocation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "_bmad-output" / "planning-artifacts"
# Former docs/architecture/*.md, now split by Diátaxis quadrant.
ARCH_EXPLANATION = ROOT / "docs" / "explanation" / "architecture"
ARCH_REFERENCE_NAMES = ["field-traceability.md", "semantic-layer.md", "freshness-axes.md"]

# dead token (regex) -> the live replacement, shown in the error so it teaches.
DEAD_TOKENS: dict[str, str] = {
    r"/data/snapshots": "raw payload lives in SQLite snapshot_store.db (not on disk)",
    r"<urn:mak:status>": "no materialized-status graph; buckets computed in the browser",
    r"\bmak:probeResult\b": "freshness = 3 tokens (observed_at / updatedAt / lastOpenChange)",
    r"\beffective_marker\b": "marker is computed in the browser from tokens + thresholds",
    r"tasks/heartbeat\.py": "ingestion entry point is infra/link_handler/pipeline.py",
    r"tasks/ingest\.py": "transform is scripts/spaceapi_extract/ (core, mom)",
    r"\bmetrics\.db\b": "operational data lives in data/tasks/snapshot_store.db",
    r"\bmak-scheduler\b": "no scheduler container; APScheduler runs inside link_handler",
    r"w3id\.org/maps-of-making": "canonical ns = nicolasdb.github.io/mapsofmaking_ontology",
    r"\bbuild_state_only_update\b": "deleted in Epic 3.5 (304 writes nothing to Oxigraph)",
    # NOTE: `mom:observedAt` is NOT listed — it is a LIVE predicate (SQLite token
    # name; written to Oxigraph only in the canary-skeleton path). The dead fact is
    # narrower ("write mom:observedAt to Oxigraph in the registered-space heartbeat
    # path") and is not safely greppable by token alone.
    r"every 6h": "heartbeat cadence is ~10 min",
    r"\b6h cycle\b": "heartbeat cadence is ~10 min",
    r"\b6h default\b": "heartbeat cadence is ~10 min",
}

# Lines allowed to mention a dead token: negations, history, supersession, sentinel.
ALLOW = re.compile(
    r"(editHistory|changes:\s|lastReconciled|"
    r"supersed|never built|ever built|never been|not used|no longer|there is no|is no |"
    r"\bno on-disk\b|deleted|absent|NOT written|do not reintroduce|reserved|"
    r"replaced by|removed|~~|stale-ok)",
    re.IGNORECASE,
)

# Scan only the pure reference sections of epics.md (Requirements Inventory +
# Architecture References + traceability). Stop at the Epic List, whose per-epic
# summaries legitimately describe done-epic mechanics.
PREAMBLE_STOP = re.compile(r"^##\s+Epic List\b")


def scan(path: Path, *, preamble_only: bool = False) -> list[tuple[int, str, str]]:
    """Return [(lineno, token, line)] for dead tokens on non-allowed lines."""
    hits: list[tuple[int, str, str]] = []
    compiled = {tok: re.compile(tok) for tok in DEAD_TOKENS}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if preamble_only and PREAMBLE_STOP.match(line):
            break
        if ALLOW.search(line):
            continue
        for tok, rx in compiled.items():
            if rx.search(line):
                hits.append((i, tok, line.strip()))
    return hits


def main() -> int:
    targets: list[tuple[Path, bool]] = [
        (PLAN / "architecture.md", False),
        (PLAN / "prd.md", False),
        (PLAN / "epics.md", True),  # preamble (reference sections) only
    ]
    targets += [(p, False) for p in sorted(ARCH_EXPLANATION.glob("*.md"))]
    targets += [(ROOT / "docs" / "reference" / name, False) for name in ARCH_REFERENCE_NAMES]

    total = 0
    for path, preamble in targets:
        if not path.exists():
            continue
        hits = scan(path, preamble_only=preamble)
        if hits:
            rel = path.relative_to(ROOT)
            scope = " (preamble)" if preamble else ""
            print(f"\n✗ {rel}{scope}")
            for lineno, tok, line in hits:
                fix = DEAD_TOKENS[tok]
                print(f"    L{lineno}: dead token /{tok}/ — {fix}")
                print(f"          {line[:100]}")
            total += len(hits)

    if total:
        print(
            f"\n{total} stale reference(s) found. Fix the line, phrase it as a "
            "negation, or append '# stale-ok' if the mention is deliberate.\n"
        )
        return 1
    print("✓ docs clean — no stale architecture references in live artifacts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
