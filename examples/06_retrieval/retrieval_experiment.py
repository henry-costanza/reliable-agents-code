"""Chapter 6: twelve customer questions, three ways to give the agent the
help center.

    uv run python examples/06_retrieval/retrieval_experiment.py

Replays by default. With AGENTKIT_MODE=record it asks every question TRIALS
times per arm against the live model (costs money) and rewrites the
cassette and the results file. The cassette stores fingerprints; every
request is rebuilt exactly from code.
"""

import json
import re
import sys
from collections import Counter
from itertools import product
from pathlib import Path

from help_center import QUESTIONS, Question
from retrieval import (
    GOOD_SEARCH, NAIVE_INDEX, NAIVE_SEARCH, SECTION_INDEX, found,
    whole_help_center,
)

from agentkit import OPUS_5_5, Budget, Provider, RunResult, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch06_retrieval.json"
RESULTS = BOOK / "fixtures" / "results" / "ch06_retrieval.json"
TRIALS = 2
SAFETY = Budget(max_cost=0.20, prices=OPUS_5_5)

# --8<-- [start:system]
SYSTEM = (
    "You are Brindle's support agent. Answer the customer's "
    "question from Brindle's help center only, in at most three "
    "sentences. End with one line: 'Source: <article id>', or "
    "'Source: none' if the help center does not answer the question."
)
# --8<-- [end:system]

ARMS = ("naive search", "section search", "whole help center")


def ask(provider: Provider, arm: str, question: Question) -> RunResult:
    if arm == "whole help center":
        system = f"{SYSTEM}\n\nThe help center:\n\n{whole_help_center()}"
        return run_agent(provider, question.text, system=system,
                         max_steps=1, budget=SAFETY)
    tool = NAIVE_SEARCH if arm == "naive search" else GOOD_SEARCH
    return run_agent(provider, question.text, system=SYSTEM,
                     tools=[tool], max_steps=6, budget=SAFETY)


SOURCE = re.compile(r"Source:\s*\**\s*(HC-\d+|none)", re.IGNORECASE)


# --8<-- [start:grade]
def grade(question: Question, answer: str) -> str:
    """right, hedged, stale, wrong source, declined, wrong or
    made up."""
    cited = SOURCE.findall(answer)
    source = cited[-1].upper() if cited else None
    if question.source is None:
        return "right" if source == "NONE" else "made up"
    has = lambda pattern: bool(re.search(pattern, answer, re.I))  # noqa: E731
    stale = bool(question.stale) and has(question.stale)
    if has(question.fact):
        if stale:  # gives the old rule too: the customer must choose
            return "hedged"
        return "right" if source == question.source else "wrong source"
    if stale:
        return "stale"
    return "declined" if source == "NONE" else "wrong"
# --8<-- [end:grade]


def run(provider: Provider) -> list[dict]:
    outcomes = []
    for arm, (n, question), trial in product(ARMS, enumerate(QUESTIONS), range(TRIALS)):
        result = ask(provider, arm, question)
        answer = result.final_text.strip()
        outcomes.append({
            "arm": arm, "question": n, "trial": trial, "ok": result.ok,
            "verdict": grade(question, answer) if result.ok else "stopped",
            "answer": answer, "queries": [
                b.input["query"] for m in result.messages if m.role == "assistant"
                for b in m.tool_uses],
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost": round(OPUS_5_5.cost(result.usage), 4),
        })
    return outcomes


INDEXES = {"naive search": NAIVE_INDEX, "section search": SECTION_INDEX}


def recall(runs: list[dict], index, k: int) -> int:
    """Runs on answerable questions whose own queries found the answer."""
    return sum(found(index, QUESTIONS[o["question"]], o["queries"], k)
               for o in runs if QUESTIONS[o["question"]].source)


def summarize(outcomes: list[dict]) -> list[dict]:
    rows = []
    for arm in ARMS:
        runs = [o for o in outcomes if o["arm"] == arm]
        row = {
            "arm": arm, "runs": len(runs),
            "verdicts": dict(sorted(Counter(o["verdict"] for o in runs).items())),
            "input_tokens": sum(o["input_tokens"] for o in runs),
            "cost": round(sum(o["cost"] for o in runs), 4),
        }
        if arm in INDEXES:
            index = INDEXES[arm]
            row["answerable"] = sum(1 for o in runs if QUESTIONS[o["question"]].source)
            row["recall_at_3"] = recall(runs, index, 3)
            row["recall_at_5"] = recall(runs, index, 5)
            row["saw_archived"] = sum(
                any(c.article == "HC-090" for q in o["queries"] for c in index.hits(q, 3))
                for o in runs)
        rows.append(row)
    return rows


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    rows = summarize(outcomes)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"recorded_with": provider.describe(), "rows": rows,
                                   "outcomes": outcomes}, indent=2) + "\n", encoding="utf-8")
    for o in outcomes:
        if o["verdict"] != "right":
            print(f"{o['arm']:<18} q{o['question']:<2} {o['verdict']:<13} {o['answer'][:110]!r}")
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
