"""Chapter 10: two questions the first recording left open.

    uv run python examples/10_verification/followup_experiment.py

Does an agent correct its reply when the gate refuses it? Was the right count
due to the entry ids or to having to cite them? Replays by default; with
AGENTKIT_MODE=record it costs money and stops past MAX_TOTAL.
"""

import json
import sys
from pathlib import Path

import refund_case
from count_case import hard_log, is_audit
from haystack import COUNT_QUESTION, grade_count
from needle_experiment import SYSTEM as CHAPTER_2_SYSTEM
from promise_case import promises, strict_gate
from refund_case import LockedDesk, claims, desk_tools

from agentkit import OPUS_5_5, Budget, Provider, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch10_followup.json"
RESULTS = BOOK / "fixtures" / "results" / "ch10_followup.json"
PROMISE_TRIALS = 5
COUNT_TRIALS = 3
MAX_TOTAL = 3.50


def spent(result) -> dict:
    return {"ok": result.ok, "steps": result.steps,
            "tool_calls": list(result.tool_calls),
            "cost": round(OPUS_5_5.cost(result.usage), 4)}


def promise_run(provider: Provider, trial: int) -> dict:
    desk = LockedDesk()
    gate, finish = strict_gate(desk)
    drafts: list[str] = []
    check = gate.check

    def keeping_drafts(claim: dict) -> list[str]:
        drafts.append(claim["message"])
        return check(claim)
    gate.check = keeping_drafts
    result = run_agent(provider, refund_case.TASK, system=refund_case.GATED,
                       tools=[*desk_tools(desk), finish], max_steps=15,
                       budget=Budget(max_cost=0.40, prices=OPUS_5_5))
    message = (gate.accepted or {}).get("message", "")
    return {"case": "promise", "trial": trial, "drafts": drafts,
            "message": message, "offers": promises(message),
            "claims": sorted(claims(message)), "refunds": len(desk.refunds),
            "refusals": gate.refusals, "accepted": gate.accepted is not None,
            **spent(result)}


def numbered_prompt(entries: dict[str, str]) -> str:
    """Chapter 2's prompt, with only the entry ids added."""
    body = "\n".join(f"{e} {s}" for e, s in entries.items())
    return f"<document>\n{body}\n</document>\n\n{COUNT_QUESTION}"


def count_run(provider: Provider, trial: int) -> dict:
    entries = hard_log()
    truth = sum(is_audit(s) for s in entries.values())
    result = run_agent(provider, numbered_prompt(entries),
                       system=CHAPTER_2_SYSTEM, max_steps=1,
                       budget=Budget(max_cost=1.50, prices=OPUS_5_5))
    answer = result.final_text.strip()
    return {"case": "numbered count", "trial": trial, "answer": answer,
            "truth": truth, "verdict": grade_count(answer, truth),
            **spent(result)}


def run(provider: Provider) -> list[dict]:
    plan = [(promise_run, t) for t in range(PROMISE_TRIALS)]
    plan += [(count_run, t) for t in range(COUNT_TRIALS)]
    outcomes = []
    for function, trial in plan:
        outcomes.append(function(provider, trial))
        total = sum(o["cost"] for o in outcomes)
        if total > MAX_TOTAL:
            raise RuntimeError(f"stopped at ${total:.2f}, over the cap")
    return outcomes


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"recorded_with": provider.describe(),
                                   "outcomes": outcomes}, indent=2) + "\n",
                       encoding="utf-8")
    for outcome in outcomes:
        print(outcome)
    print(f"total ${sum(o['cost'] for o in outcomes):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
