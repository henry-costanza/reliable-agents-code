"""Chapter 8: one seven-turn conversation, five ways to keep it in budget.

    uv run python examples/08_compaction/compaction_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs every arm and trial
against the live model (costs money) and rewrites the cassette and the
results file. Each run gets a fresh desk and is graded on what the desk
recorded and on two of the agent's replies.
"""

import json
import re
import sys
from collections import Counter
from itertools import product
from pathlib import Path

from florist_desk import CHANGED_ADDRESS, Desk, tools
from session import Session, drop_old_turns, handoff, log_reader, summarize

from agentkit import OPUS_5_5, Provider, open_provider
from agentkit.messages import Usage

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch08_compaction.json"
RESULTS = BOOK / "fixtures" / "results" / "ch08_compaction.json"
TRIALS = 3
MAX_COST = 0.60  # per conversation; a run that passes it is stopped

SYSTEM = (
    "You are Brindle's billing support agent. The signed-in customer is "
    "Juniper Florists (CUS-162), and today is 2026-11-01. Use the tools "
    "to look things up and act on the customer's requests, then reply "
    "in at most three sentences."
)

# --8<-- [start:turns]
TURNS = (
    "Hi, Dana here. Before anything else: we're moving our finance "
    "inbox this week, so please don't email us any invoices until I "
    "tell you the move is done. Which of our invoices are unpaid?",
    "What's on INV-3108? It looks higher than usual.",
    "Which payments have you received from us since June?",
    "Please put our PO number, PO-77214-W, on INV-3108.",
    "Who changed our billing address in September?",
    "Why was there a late fee on INV-3043?",
    "Thanks. Please get the corrected INV-3108 over to us.",
)
# --8<-- [end:turns]

ARMS = ("full history", "drop old turns", "summary", "handoff note",
        "note and subagent")


def build(provider: Provider, arm: str, desk: Desk) -> Session:
    session = Session(provider, SYSTEM, tools(desk))
    if arm == "drop old turns":
        session.compactor = drop_old_turns
    elif arm == "summary":
        session.compactor = summarize
    elif arm in ("handoff note", "note and subagent"):
        session.compactor = handoff(desk)
    if arm == "note and subagent":
        session.tools = tools(desk, log=log_reader(session))
    return session


def cites_move(reply: str) -> bool:
    """Did the last reply give the inbox move as the reason?"""
    return bool(re.search(r"\bmov(e|ing)\b", reply, re.I))


# --8<-- [start:grade]
def grade(desk: Desk, last_reply: str) -> str:
    """The desk's record first; then why the agent held the email."""
    if desk.sent:
        return "emailed during the move"
    if desk.po_numbers != {"INV-3108": "PO-77214-W"}:
        return "PO number wrong"
    if not cites_move(last_reply):
        return "held for another reason"
    return "right"
# --8<-- [end:grade]


def named_who(reply: str) -> bool:
    """Did the answer to turn 5 name the person the log records?"""
    first, last = CHANGED_ADDRESS.split("@")[0].split(".")
    return bool(re.search(rf"{first}[ .]?{last}", reply, re.I))


def cost(calls: list[tuple[str, Usage]]) -> float:
    return round(sum(OPUS_5_5.cost(u) for _, u in calls), 4)


def costs(calls: list[tuple[str, Usage]]) -> dict[str, float]:
    kinds = sorted({kind for kind, _ in calls})
    return {k: cost([c for c in calls if c[0] == k]) for k in kinds}


def converse(provider: Provider, arm: str) -> tuple[Session, Desk, list[str]]:
    desk = Desk()
    session = build(provider, arm, desk)
    replies = []
    for text in TURNS:
        if cost(session.calls) > MAX_COST:
            break
        replies.append(session.send(text).strip())
    return session, desk, replies


def run(provider: Provider) -> list[dict]:
    outcomes = []
    for arm, trial in product(ARMS, range(TRIALS)):
        session, desk, replies = converse(provider, arm)
        finished = len(replies) == len(TURNS)
        agent = [u.input_tokens for kind, u in session.calls if kind == "agent"]
        outcomes.append({
            "arm": arm, "trial": trial,
            "verdict": grade(desk, replies[-1]) if finished else "stopped",
            "named_who": finished and named_who(replies[4]),
            "cites_move": finished and cites_move(replies[-1]),
            "sent": desk.sent, "po_numbers": desk.po_numbers,
            "compactions": session.compactions, "notes": session.notes,
            "replies": replies, "agent_context": agent,
            "calls": Counter(kind for kind, _ in session.calls),
            "input_tokens": sum(u.input_tokens for _, u in session.calls),
            "output_tokens": sum(u.output_tokens for _, u in session.calls),
            "cost": cost(session.calls), "cost_by_kind": costs(session.calls),
        })
    return outcomes


def summarize_runs(outcomes: list[dict]) -> list[dict]:
    rows = []
    for arm in ARMS:
        runs = [o for o in outcomes if o["arm"] == arm]
        rows.append({
            "arm": arm, "runs": len(runs),
            "right": sum(o["verdict"] == "right" for o in runs),
            "verdicts": dict(sorted(Counter(o["verdict"] for o in runs).items())),
            "named_who": sum(o["named_who"] for o in runs),
            "cites_move": sum(o["cites_move"] for o in runs),
            "compactions": sum(o["compactions"] for o in runs),
            "peak_context": max(max(o["agent_context"]) for o in runs),
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
        print(f"{row['arm']:<18} {row['right']}/{row['runs']}  {row['verdicts']}  "
              f"who {row['named_who']}/{row['runs']}  "
              f"move {row['cites_move']}/{row['runs']}  peak {row['peak_context']:,}  "
              f"${row['cost']:.3f}")
    print(f"total ${sum(r['cost'] for r in rows):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
