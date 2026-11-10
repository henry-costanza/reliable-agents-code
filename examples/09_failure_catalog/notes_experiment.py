"""Chapter 9: chapter 8's conversation again, with checked handoff notes.

    uv run python examples/09_failure_catalog/notes_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs the two arms that
used handoff notes in chapter 8, TRIALS times each, against the live model
(costs money), and rewrites the cassette and the results file. Each run
is graded as in chapter 8, and every condensing call is checked for a
cut-off reply.
"""

import json
import sys
from collections import Counter
from itertools import product
from pathlib import Path

from checked_notes import Truncated, checked_handoff
from compaction_experiment import SYSTEM, TURNS, cost, costs, grade, named_who
from florist_desk import Desk, tools
from session import Session, log_reader
from tracing import Tracer

from agentkit import Provider, open_provider
from agentkit.messages import StopReason

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch09_notes.json"
RESULTS = BOOK / "fixtures" / "results" / "ch09_notes.json"
TRIALS = 3
MAX_COST = 0.60  # per conversation, as in chapter 8
ARMS = ("handoff note", "note and subagent")
CONDENSER = "You condense support conversations"


def converse(provider: Provider, arm: str) -> tuple[Session, Desk, list[str], str]:
    desk = Desk()
    session = Session(provider, SYSTEM, tools(desk), checked_handoff(desk))
    if arm == "note and subagent":
        session.tools = tools(desk, log=log_reader(session))
    replies, error = [], ""
    for text in TURNS:
        if cost(session.calls) > MAX_COST:
            break
        try:
            replies.append(session.send(text).strip())
        except Truncated as cut:
            error = str(cut)
            break
    return session, desk, replies, error


def run(provider: Provider) -> list[dict]:
    outcomes = []
    for arm, trial in product(ARMS, range(TRIALS)):
        tracer = Tracer(provider)
        session, desk, replies, error = converse(tracer, arm)
        finished = len(replies) == len(TURNS)
        notes = [c.response for c in tracer.calls
                 if c.request.system.startswith(CONDENSER)]
        outcomes.append({
            "arm": arm, "trial": trial,
            "verdict": grade(desk, replies[-1]) if finished else "stopped",
            "error": error,
            "named_who": finished and named_who(replies[4]),
            "compactions": session.compactions,
            "note_calls": len(notes),
            "cut_off": sum(r.stop_reason is StopReason.MAX_TOKENS for r in notes),
            "note_tokens": [r.usage.output_tokens for r in notes],
            "notes": session.notes, "replies": replies,
            "calls": Counter(kind for kind, _ in session.calls),
            "cost": cost(session.calls), "cost_by_kind": costs(session.calls),
        })
    return outcomes


def summarize_runs(outcomes: list[dict]) -> list[dict]:
    rows = []
    for arm in ARMS:
        runs = [o for o in outcomes if o["arm"] == arm]
        tokens = [t for o in runs for t in o["note_tokens"]]
        rows.append({
            "arm": arm, "runs": len(runs),
            "right": sum(o["verdict"] == "right" for o in runs),
            "verdicts": dict(sorted(Counter(o["verdict"] for o in runs).items())),
            "named_who": sum(o["named_who"] for o in runs),
            "compactions": sum(o["compactions"] for o in runs),
            "note_calls": sum(o["note_calls"] for o in runs),
            "cut_off": sum(o["cut_off"] for o in runs),
            "longest_note": max(tokens, default=0),
            "cost": round(sum(o["cost"] for o in runs), 4),
        })
    return rows


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    rows = summarize_runs(outcomes)
    RESULTS.write_text(json.dumps({"recorded_with": provider.describe(), "rows": rows,
                                   "outcomes": outcomes}, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(row)
    print(f"total ${sum(r['cost'] for r in rows):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
