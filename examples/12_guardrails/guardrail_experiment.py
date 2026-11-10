"""Chapter 12: the same rules in the prompt only, or also in code.

    uv run python examples/12_guardrails/guardrail_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs against the live models
(costs money), cheapest first, and stops past MAX_TOTAL.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from checks import check
from guards import amount_problems
from money_guard import attempt as write_with_guard
from signed_in_desk import TASKS, answer

from agentkit import OPUS_5_5, Budget, Prices, Provider, open_provider
from agentkit.anthropic_provider import AnthropicProvider

BOOK = Path(__file__).resolve().parents[2]
CASSETTES = BOOK / "fixtures" / "cassettes"
RESULTS = BOOK / "fixtures" / "results" / "ch12_guardrails.json"
SUMMARY = BOOK / "fixtures" / "results" / "ch12_summary.json"
TRIALS = 5
CODING_TRIALS = 3
MAX_TOTAL = 5.00
HAIKU_5_5 = Prices(input=0.10, output=0.50)  # prompts up to 100,000 tokens
ARMS = {"rules in the prompt": False, "rules and guardrails": True}


@dataclass(frozen=True)
class Model:
    name: str
    model: str
    prices: Prices


MODELS = (Model("Haiku 5.5", "claude-haiku-5-5", HAIKU_5_5),
          Model("Opus 5.5", "claude-opus-5-5", OPUS_5_5))


def provider_for(model: str, slug: str) -> Provider:
    def live() -> Provider:
        from dotenv import load_dotenv
        load_dotenv()  # the API key, as agentkit's own default does
        return AnthropicProvider(model=model)
    return open_provider(CASSETTES / f"ch12_{slug}.json",
                         store="fingerprint", live=live)


def desk_trial(provider, model: Model, arm: str, task: str,
               number: int) -> dict:
    customer, message, grade = TASKS[task]
    budget = Budget(max_cost=0.30, prices=model.prices)
    result, case = answer(provider, customer, message, ARMS[arm], budget)
    return {"model": model.name, "arm": arm, "task": task,
            "trial": number, "verdict": grade(case),
            "reply": case.reply, "fallback": case.fallback,
            "unbacked": amount_problems(case.reply, case.ledger),
            "refunds": case.desk.refunds,
            "refusals": [list(r) for r in case.refusals],
            "tool_calls": list(result.tool_calls), "steps": result.steps,
            "cost": round(model.prices.cost(result.usage), 5)}


def coding_trial(provider, number: int) -> dict:
    budget = Budget(max_cost=0.50, prices=OPUS_5_5)
    task = "average_line_price"
    result, files, refusals = write_with_guard(provider, task, budget)
    return {"model": "Opus 5.5", "arm": "money rule on every write",
            "task": task, "trial": number, "rules": check(files, task),
            "function": files["invoices/totals.py"],
            "refusals": [list(r) for r in refusals],
            "steps": result.steps,
            "cost": round(OPUS_5_5.cost(result.usage), 5)}


def run(providers=provider_for) -> list[dict]:
    outcomes, total = [], 0.0
    for model in MODELS:  # cheapest first
        provider = providers(model.model,
                             f"desk_{model.name.lower().replace(' ', '-')}")
        for arm in ARMS:
            for task in TASKS:
                for number in range(TRIALS):
                    outcomes.append(desk_trial(provider, model, arm,
                                               task, number))
                    total += outcomes[-1]["cost"]
                    if total > MAX_TOTAL:
                        raise RuntimeError(f"stopped at ${total:.2f}")
    provider = providers("claude-opus-5-5", "money_rule")
    for number in range(CODING_TRIALS):
        outcomes.append(coding_trial(provider, number))
        total += outcomes[-1]["cost"]
        if total > MAX_TOTAL:
            raise RuntimeError(f"stopped at ${total:.2f}")
    return outcomes


def summary(outcomes: list[dict]) -> dict:
    """Per model, arm and task: right runs, unbacked replies, refusals."""
    rows: dict[str, dict] = {}
    for o in outcomes:
        if "verdict" not in o:
            continue
        key = f"{o['model']} | {o['arm']} | {o['task']}"
        row = rows.setdefault(key, {"right": 0, "runs": 0, "unbacked": 0,
                                    "refused": 0, "fallback": 0})
        row["runs"] += 1
        row["right"] += o["verdict"] == "right"
        row["unbacked"] += bool(o["unbacked"])
        row["refused"] += bool(o["refusals"])
        row["fallback"] += o["fallback"]
    coding = [o for o in outcomes if "rules" in o]
    costs: dict[str, float] = {}
    for o in outcomes:
        costs[o["model"]] = costs.get(o["model"], 0) + o["cost"]
    costs = {model: round(cost, 4) for model, cost in costs.items()}
    return {"desk": rows,
            "coding": {"runs": len(coding),
                       "integer money": sum(o["rules"]["integer money"]
                                            for o in coding),
                       "refused": sum(bool(o["refusals"]) for o in coding)},
            "costs": costs}


def main() -> int:
    outcomes = run()
    RESULTS.write_text(json.dumps({"outcomes": outcomes}, indent=2) + "\n",
                       encoding="utf-8")
    result = summary(outcomes)
    SUMMARY.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for key, row in result["desk"].items():
        print(key, row)
    print("coding", result["coding"])
    print("costs", result["costs"], f"total ${sum(o['cost'] for o in outcomes):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
