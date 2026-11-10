"""Chapter 16: run Brindle's desk 1.0 through the release gate.

    uv run python examples/16_capstone/release_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs against the live models
with prompt caching (costs money), cheapest first, and stops past MAX_TOTAL.
"""

import json
import sys
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from brindle_desk import desk
from cache_experiment import PRICES
from catalog import scan
from release_gate import TASKS, gate, released
from security_experiment import MODELS
from traces import CachingProvider, Trace, model_call, tool_calls
from tracing import Tracer, conversations

from agentkit import Budget, Provider, Usage, open_provider

BOOK = Path(__file__).resolve().parents[2]
CASSETTES = BOOK / "fixtures" / "cassettes"
RESULTS = BOOK / "fixtures" / "results" / "ch16_release.json"
SUMMARY = BOOK / "fixtures" / "results" / "ch16_summary.json"
TRIALS = 5
MAX_TOTAL = 3.00


def provider_for(model) -> Provider:
    def live() -> Provider:
        from dotenv import load_dotenv
        load_dotenv()  # the API key, as agentkit's own default does
        return CachingProvider(model=model.model)
    return open_provider(CASSETTES / f"ch16_{model.slug}.json",
                         store="fingerprint", live=live)


def trial(tracer: Tracer, model, task: str, number: int) -> dict:
    customer, message, grade = TASKS[task]
    prices = PRICES[model.name]
    start = len(tracer.calls)
    outcome = desk(tracer, customer, message,
                   Budget(max_cost=0.30, prices=prices))
    calls = tracer.calls[start:]
    usage = sum((c.response.usage for c in calls), Usage())
    trace = Trace(f"{model.name} | desk 1.0 | {task} | {number}",
                  model.model, customer, [model_call(c) for c in calls],
                  tool_calls(outcome.result),
                  len(outcome.approvals.requests),
                  outcome.case.fallback, round(prices.cost(usage), 6))
    failures = {}
    for conversation in conversations(calls):
        failures |= scan(conversation)
    return {"model": model.name, "task": task, "trial": number,
            "verdict": grade(outcome.case, outcome.approvals),
            "reply": outcome.case.reply, "failures": failures,
            "refusals": [list(r) for r in outcome.case.refusals],
            "trace": trace.line()}


def run(providers=provider_for) -> list[dict]:
    outcomes, spent = [], 0.0
    for model in MODELS:  # cheapest first
        tracer = Tracer(providers(model))
        for task in TASKS:
            for number in range(TRIALS):
                outcomes.append(trial(tracer, model, task, number))
                spent += json.loads(outcomes[-1]["trace"])["cost"]
                if spent > MAX_TOTAL:
                    raise RuntimeError(f"stopped at ${spent:.2f}")
    return outcomes


def summary(outcomes: list[dict]) -> dict:
    rows: dict[str, dict] = {}
    for o in outcomes:
        row = rows.setdefault(f"{o['model']} | {o['task']}",
                              {"right": 0, "runs": 0, "wrong": {}})
        row["runs"] += 1
        row["right"] += o["verdict"] == "right"
        if o["verdict"] != "right":
            row["wrong"][o["verdict"]] = row["wrong"].get(o["verdict"],
                                                          0) + 1
    gates, costs, before = {}, {}, {}
    for model in MODELS:
        chosen = [o for o in outcomes if o["model"] == model.name]
        gates[model.name] = gate(model.name, chosen)
        costs[model.name] = round(sum(json.loads(o["trace"])["cost"]
                                      for o in chosen), 4)
        scores, _ = released(model.name)
        before[model.name] = {t: list(s) for t, s in scores.items()}
    return {"rows": rows, "gates": gates, "costs": costs,
            "released": before}


def main() -> int:
    outcomes = run()
    RESULTS.write_text(json.dumps({"outcomes": outcomes}, indent=2) + "\n",
                       encoding="utf-8")
    result = summary(outcomes)
    SUMMARY.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for key, row in result["rows"].items():
        print(key, row)
    print(json.dumps(result["gates"], indent=1), result["costs"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
