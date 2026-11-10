"""Chapter 15: six requests, answered by one agent and by a team.

    uv run python examples/15_multi_agent/team_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs against the live models
with prompt caching (costs money), cheapest first, and stops past MAX_TOTAL.
"""

import json
import sys
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from cache_experiment import PRICES
from dashboard import day
from security_experiment import MODELS
from team_desk import SHAPES, TASKS
from traces import CachingProvider, Trace, model_call, tool_calls
from tracing import Tracer

from agentkit import Budget, Provider, Usage, open_provider

BOOK = Path(__file__).resolve().parents[2]
CASSETTES = BOOK / "fixtures" / "cassettes"
RESULTS = BOOK / "fixtures" / "results" / "ch15_team.json"
SUMMARY = BOOK / "fixtures" / "results" / "ch15_summary.json"
TRIALS = 5
MAX_TOTAL = 3.00


def provider_for(model) -> Provider:
    def live() -> Provider:
        from dotenv import load_dotenv
        load_dotenv()  # the API key, as agentkit's own default does
        return CachingProvider(model=model.model)
    return open_provider(CASSETTES / f"ch15_{model.slug}.json",
                         store="fingerprint", live=live)


def trial(tracer: Tracer, model, shape: str, task: str,
          number: int) -> dict:
    customer, message, grade = TASKS[task]
    prices = PRICES[model.name]
    start = len(tracer.calls)
    outcome = SHAPES[shape](tracer, customer, message,
                            Budget(max_cost=0.30, prices=prices))
    calls = tracer.calls[start:]
    usage = sum((c.response.usage for c in calls), Usage())
    trace = Trace(f"{model.name} | {shape} | {task} | {number}",
                  model.model, customer, [model_call(c) for c in calls],
                  tool_calls(outcome.result),
                  len(outcome.approvals.requests),
                  outcome.case.fallback, round(prices.cost(usage), 6))
    return {"model": model.name, "shape": shape, "task": task,
            "trial": number, "route": outcome.route,
            "verdict": grade(outcome.case, outcome.approvals),
            "reply": outcome.case.reply,
            "moved": [list(m) for m in
                      outcome.case.desk.refunds
                      + [(r.invoice_id, r.amount_cents)
                         for r in outcome.approvals.requests]],
            "refusals": [list(r) for r in outcome.case.refusals],
            "trace": trace.line()}


def run(providers=provider_for) -> list[dict]:
    outcomes, spent = [], 0.0
    for model in MODELS:  # cheapest first
        tracer = Tracer(providers(model))
        for shape in SHAPES:
            for task in TASKS:
                for number in range(TRIALS):
                    outcomes.append(trial(tracer, model, shape, task,
                                          number))
                    spent += json.loads(outcomes[-1]["trace"])["cost"]
                    if spent > MAX_TOTAL:
                        raise RuntimeError(f"stopped at ${spent:.2f}")
    return outcomes


def summary(outcomes: list[dict]) -> dict:
    rows: dict[str, dict] = {}
    for o in outcomes:
        key = f"{o['model']} | {o['shape']} | {o['task']}"
        row = rows.setdefault(key, {"right": 0, "runs": 0, "routes": {},
                                    "wrong": {}})
        row["runs"] += 1
        row["right"] += o["verdict"] == "right"
        row["routes"][o["route"]] = row["routes"].get(o["route"], 0) + 1
        if o["verdict"] != "right":
            row["wrong"][o["verdict"]] = row["wrong"].get(o["verdict"],
                                                          0) + 1
    shapes = {}
    for model in MODELS:
        for shape in SHAPES:
            chosen = [o for o in outcomes if o["model"] == model.name
                      and o["shape"] == shape]
            traces = [Trace(**json.loads(o["trace"])) for o in chosen]
            numbers = day(traces)
            shapes[f"{model.name} | {shape}"] = {
                "right": sum(o["verdict"] == "right" for o in chosen),
                "runs": len(chosen), "cost": numbers["cost"],
                "median cost": numbers["median cost"],
                "model calls": sum(len(t.calls) for t in traces)}
    return {"rows": rows, "shapes": shapes}


def main() -> int:
    outcomes = run()
    RESULTS.write_text(json.dumps({"outcomes": outcomes}, indent=2) + "\n",
                       encoding="utf-8")
    result = summary(outcomes)
    SUMMARY.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for key, row in result["rows"].items():
        print(key, row)
    for key, row in result["shapes"].items():
        print(key, row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
