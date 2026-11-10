"""Chapter 10: three kinds of "done", with and without evidence.

    uv run python examples/10_verification/verification_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs every case against the
live model (costs money) and rewrites the cassette and the results file. The
run stops if the whole recording passes MAX_TOTAL.
"""

import json
import sys
from pathlib import Path

import count_case
import fix_case
import refund_case
from count_case import count_gate, hard_log
from fix_case import PROJECT, Bench, fix_gate, fixed
from mini_repo import workspace_tools
from refund_case import LockedDesk, claims, desk_tools, refund_gate, ticket_tool

from agentkit import OPUS_5_5, Budget, Provider, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch10_verification.json"
RESULTS = BOOK / "fixtures" / "results" / "ch10_verification.json"
REFUND_TRIALS = 5
FIX_TRIALS = 4
COUNT_TRIALS = 3
MAX_TOTAL = 8.00
REFUND_ARMS = ("plain", "told", "gated", "gated, ticket tool")
FIX_ARMS = ("no tests", "tests", "gated")


def spent(result) -> dict:
    return {"ok": result.ok, "steps": result.steps,
            "tool_calls": list(result.tool_calls),
            "cost": round(OPUS_5_5.cost(result.usage), 4)}


def refund_run(provider: Provider, arm: str, trial: int) -> dict:
    desk = LockedDesk()
    tools, gate = desk_tools(desk), None
    system = {"plain": refund_case.SYSTEM,
              "told": refund_case.TOLD}.get(arm, refund_case.GATED)
    if arm.startswith("gated"):
        gate, finish = refund_gate(desk)
        tools.append(finish)
    if arm == "gated, ticket tool":
        tools.append(ticket_tool(desk))
    result = run_agent(provider, refund_case.TASK, system=system, tools=tools,
                       max_steps=15,
                       budget=Budget(max_cost=0.40, prices=OPUS_5_5))
    message = ((gate.accepted or {}).get("message", "") if gate
               else result.final_text.strip())
    backed = set(desk.receipts.values())
    return {"case": "refund", "arm": arm, "trial": trial, "message": message,
            "refunds": [list(r) for r in desk.refunds],
            "tickets": desk.tickets,
            "claims": sorted(claims(message)),
            "unbacked": sorted(claims(message) - backed),
            "refusals": gate.refusals if gate else [],
            "accepted": gate.accepted is not None if gate else None,
            **spent(result)}


def fix_run(provider: Provider, arm: str, trial: int) -> dict:
    files = dict(PROJECT)
    bench, gate = Bench(files), None
    tools = workspace_tools(files)
    system = fix_case.NO_TESTS
    if arm != "no tests":
        tools.append(bench.tool())
        system = fix_case.WITH_TESTS
    if arm == "gated":
        gate, finish = fix_gate(bench)
        tools.append(finish)
        system = fix_case.GATED
    result = run_agent(provider, fix_case.TASK, system=system, tools=tools,
                       max_steps=20,
                       budget=Budget(max_cost=0.60, prices=OPUS_5_5))
    reply = ((gate.accepted or {}).get("message", "") if gate
             else result.final_text.strip())
    return {"case": "fix", "arm": arm, "trial": trial, "reply": reply,
            "fixed": fixed(files), "proven": bench.proven(),
            "test_runs": len(bench.runs),
            "totals": files["invoices/totals.py"],
            "refusals": gate.refusals if gate else [],
            "accepted": gate.accepted is not None if gate else None,
            **spent(result)}


def count_run(provider: Provider, trial: int) -> dict:
    entries = hard_log()
    gate, finish = count_gate(entries)
    result = run_agent(provider, count_case.as_prompt(entries),
                       system=count_case.GATED, tools=[finish], max_steps=4,
                       budget=Budget(max_cost=3.00, prices=OPUS_5_5))
    truth = sum(count_case.is_audit(s) for s in entries.values())
    accepted = gate.accepted or {}
    return {"case": "count", "arm": "gated", "trial": trial, "truth": truth,
            "count": accepted.get("count"),
            "missed": truth - len(set(accepted.get("entries", []))),
            "refusals": gate.refusals, "accepted": gate.accepted is not None,
            **spent(result)}


def run(provider: Provider) -> list[dict]:
    plan = [(refund_run, (arm, t)) for arm in REFUND_ARMS
            for t in range(REFUND_TRIALS)]
    plan += [(fix_run, (arm, t)) for arm in FIX_ARMS
             for t in range(FIX_TRIALS)]
    plan += [(count_run, (t,)) for t in range(COUNT_TRIALS)]
    outcomes = []
    for function, arguments in plan:
        outcomes.append(function(provider, *arguments))
        total = sum(o["cost"] for o in outcomes)
        if total > MAX_TOTAL:
            raise RuntimeError(f"stopped at ${total:.2f}, over the cap")
    return outcomes


def summarize(outcomes: list[dict]) -> list[dict]:
    rows = []
    for case, arm in dict.fromkeys((o["case"], o["arm"]) for o in outcomes):
        runs = [o for o in outcomes if (o["case"], o["arm"]) == (case, arm)]
        row = {"case": case, "arm": arm, "runs": len(runs),
               "accepted": sum(bool(o["accepted"]) for o in runs),
               "refusals": sum(len(o["refusals"]) for o in runs),
               "cost": round(sum(o["cost"] for o in runs), 4)}
        if case == "refund":
            row["unbacked"] = sum(bool(o["unbacked"]) for o in runs)
            row["tickets"] = sum(bool(o["tickets"]) for o in runs)
        if case == "fix":
            row["fixed"] = sum(o["fixed"] for o in runs)
            row["proven"] = sum(o["proven"] for o in runs)
        if case == "count":
            row["right"] = sum(o["count"] == o["truth"] for o in runs)
            row["counts"] = [o["count"] for o in runs]
            row["truth"] = runs[0]["truth"]
        rows.append(row)
    return rows


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    rows = summarize(outcomes)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"recorded_with": provider.describe(),
                                   "rows": rows, "outcomes": outcomes},
                                  indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(row)
    print(f"total ${sum(o['cost'] for o in outcomes):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
