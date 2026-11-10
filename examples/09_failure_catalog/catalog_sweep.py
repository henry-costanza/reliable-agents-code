"""Chapter 9: run the failure catalog over every recording in the book.

    uv run python examples/09_failure_catalog/catalog_sweep.py

Offline and free: it replays chapters 1 to 8 from their cassettes, groups
each trace into conversations, runs every detector on every conversation,
and counts what each chapter's grader found next to it. It writes the
results file the chapter's table is drawn from.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from book_runs import Recording, replay_book
from catalog import CATALOG, scan
from tracing import conversations

RESULTS = Path(__file__).resolve().parents[2] / "fixtures" / "results" / "ch09_catalog.json"


# --8<-- [start:sweep]
def sweep(recordings: list[Recording]) -> list[dict]:
    """One finding per failure the trace shows, everywhere."""
    findings = []
    for recording in recordings:
        talks = conversations(recording.calls)
        for n, conversation in enumerate(talks):
            for failure, evidence in scan(conversation).items():
                findings.append({
                    "chapter": recording.chapter,
                    "recording": recording.name,
                    "conversation": n, "failure": failure,
                    "system": conversation.system[:60],
                    "evidence": evidence})
    return findings
# --8<-- [end:sweep]


def table(recordings: list[Recording], findings: list[dict]) -> list[dict]:
    """Per failure: what the trace showed, and what the graders found."""
    rows = []
    for failure in CATALOG:
        mine = [f for f in findings if f["failure"] == failure.id]
        rows.append({
            "id": failure.id, "name": failure.name, "chapter": failure.chapter,
            "mast": failure.mast, "check": failure.check,
            "in_trace": failure.detect is not None,
            "trace_found": len(mine),
            "trace_chapters": sorted({f["chapter"] for f in mine}),
            "graded": sum(r.graded[failure.id] for r in recordings),
        })
    return rows


def main() -> int:
    recordings = replay_book()
    findings = sweep(recordings)
    rows = table(recordings, findings)
    totals = {
        "recordings": len(recordings),
        "calls": sum(len(r.calls) for r in recordings),
        "conversations": sum(len(conversations(r.calls)) for r in recordings),
    }
    RESULTS.write_text(json.dumps({"totals": totals, "rows": rows,
                                   "findings": findings}, indent=2) + "\n",
                       encoding="utf-8")
    print(totals)
    for row in rows:
        print(f"{row['id']:<12} trace {row['trace_found']:>3} {row['trace_chapters']}"
              f"  graded {row['graded']:>2}")
    for kind, n in Counter((f["chapter"], f["failure"]) for f in findings).items():
        print(kind, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
