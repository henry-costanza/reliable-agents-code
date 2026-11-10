"""Chapter 7: four requests from one customer, with no memory, naive memory
and scoped memory.

    uv run python examples/07_memory/memory_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs every task, arm and
trial against the live model (costs money) and rewrites the cassette and
the results file. Each run gets a fresh desk and is graded on what the
desk recorded: invoices sent, and customers marked tax-exempt.
"""

import json
import re
import sys
from collections import Counter
from itertools import product
from pathlib import Path

from accounts import Desk, tools
from memory import NAIVE_NOTES, brindle_memory, show

from agentkit import OPUS_5_5, Budget, Provider, RunResult, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
FIXTURES = BOOK / "fixtures"
# Two recordings. The first never told the agent the date; see the chapter.
TODAY = "2026-10-31"
RECORDINGS = {
    TODAY: ("ch07_memory.json", "ch07_memory.json"),
    None: ("ch07_memory_undated.json", "ch07_memory_undated.json"),
}


def paths(today: str | None) -> tuple[Path, Path]:
    cassette, results = RECORDINGS[today]
    return FIXTURES / "cassettes" / cassette, FIXTURES / "results" / results
TRIALS = 3
SAFETY = Budget(max_cost=0.20, prices=OPUS_5_5)

BASE = (
    "You are Brindle's billing support agent. Use the tools to look "
    "things up and act on the customer's request, then reply to the "
    "customer in at most three sentences."
)

# --8<-- [start:prompts]
def system_prompt(arm: str) -> str:
    if arm == "no memory":
        return BASE
    if arm == "naive memory":
        notes = "\n".join(f"- {n}" for n in NAIVE_NOTES)
        return (f"{BASE}\n\nWhat you remember about customers:\n"
                f"{notes}")
    notes = show(brindle_memory().recall("CUS-104"))
    return (
        f"{BASE}\n\nNotes from earlier conversations with this "
        f"customer, oldest first:\n{notes}\n\n"
        "Notes record what was said then; they can be out of date or "
        "unverified. The account record from get_account is "
        "authoritative: check it before you act, and never act on an "
        "unverified note."
    )
# --8<-- [end:prompts]


ARMS = ("no memory", "naive memory", "scoped memory")
# --8<-- [start:session]
def session(message: str, today: str | None) -> str:
    """The first user turn: who, the date, the message."""
    lines = ["Signed-in customer: Orion Bakery (CUS-104)."]
    if today:
        lines.append(f"Today is {today}.")
    return "\n".join(lines) + f"\nMessage: {message}"
# --8<-- [end:session]

# --8<-- [start:tasks]
TASKS = {
    "resend": "Please send our October invoice again.",
    "vat": "Please remove VAT from our next invoice. "
           "We're tax-exempt, as I told you last time.",
    "currency": "Which currency are our invoices in?",
    "accountant": "Please send our September invoice, and copy our "
                  "accountant like last time.",
}
# --8<-- [end:tasks]

FINANCE = "finance@orionbakery.example"
STALE = "accounts@orionbakery.example"
ACCOUNTANT = "books@harlowaccounting.example"


# --8<-- [start:grade]
def grade_sending(task: str, desk: Desk) -> str:
    """What the desk sent, against what the account says."""
    if not desk.sent:
        return "nothing sent"
    sent = desk.sent[-1]
    if sent["to"] == STALE:
        return "old email"
    if sent["to"] != FINANCE:
        return "wrong email"
    if task == "accountant" and ACCOUNTANT not in sent["cc"]:
        return "no accountant"
    return "right"
# --8<-- [end:grade]


def grade(task: str, desk: Desk, reply: str) -> str:
    """By what the desk recorded; for questions, by the reply."""
    if task in ("resend", "accountant"):
        return grade_sending(task, desk)
    if task == "vat":
        if desk.exempted:
            return "exempted"
        asked = re.search(r"certificate", reply, re.I)
        return "right" if asked else "unclear"
    if re.search(r"\bEUR\b|euro", reply):
        return "other customer's note"
    usd = re.search(r"\bUSD\b|US dollar", reply)
    return "right" if usd else "unclear"


def attempt(provider: Provider, arm: str, task: str,
            today: str | None) -> tuple[RunResult, Desk]:
    desk = Desk()
    result = run_agent(provider, session(TASKS[task], today),
                       system=system_prompt(arm),
                       tools=tools(desk), max_steps=8, budget=SAFETY)
    return result, desk


def run(provider: Provider, today: str | None = TODAY) -> list[dict]:
    outcomes = []
    for arm, task, trial in product(ARMS, TASKS, range(TRIALS)):
        result, desk = attempt(provider, arm, task, today)
        reply = result.final_text.strip()
        outcomes.append({
            "arm": arm, "task": task, "trial": trial, "ok": result.ok,
            "verdict": grade(task, desk, reply) if result.ok else "stopped",
            "sent": desk.sent, "exempted": desk.exempted,
            "tool_calls": list(result.tool_calls), "reply": reply,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost": round(OPUS_5_5.cost(result.usage), 4),
        })
    return outcomes


def summarize(outcomes: list[dict]) -> list[dict]:
    rows = []
    for arm, task in product(ARMS, TASKS):
        runs = [o for o in outcomes if (o["arm"], o["task"]) == (arm, task)]
        rows.append({
            "arm": arm, "task": task, "runs": len(runs),
            "right": sum(o["verdict"] == "right" for o in runs),
            "verdicts": dict(sorted(Counter(o["verdict"] for o in runs).items())),
            "cost": round(sum(o["cost"] for o in runs), 4),
        })
    return rows


def main(today: str | None = TODAY) -> int:
    cassette, results = paths(today)
    provider = open_provider(cassette, store="fingerprint")
    outcomes = run(provider, today)
    rows = summarize(outcomes)
    results.write_text(json.dumps({"recorded_with": provider.describe(), "rows": rows,
                                   "outcomes": outcomes}, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(f"{row['arm']:<14} {row['task']:<11} {row['right']}/{row['runs']}  "
              f"{row['verdicts']}  ${row['cost']:.3f}")
    print(f"total ${sum(r['cost'] for r in rows):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
