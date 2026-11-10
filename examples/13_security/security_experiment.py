"""Chapter 13: four requests a customer controls, on two versions of the desk.

    uv run python examples/13_security/security_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs against the live models
(costs money), cheapest first, and stops past MAX_TOTAL.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from secure_desk import TASKS, answer, moved

from agentkit import OPUS_5_5, Budget, Prices, Provider, open_provider
from agentkit.anthropic_provider import AnthropicProvider

BOOK = Path(__file__).resolve().parents[2]
CASSETTES = BOOK / "fixtures" / "cassettes"
RESULTS = BOOK / "fixtures" / "results" / "ch13_security.json"
SUMMARY = BOOK / "fixtures" / "results" / "ch13_summary.json"
TRIALS = 5
MAX_TOTAL = 5.00
HAIKU_5_5 = Prices(input=0.10, output=0.50)  # prompts up to 100,000 tokens
DESKS = {"chapter 12 desk": False, "chapter 13 desk": True}


@dataclass(frozen=True)
class Model:
    name: str
    model: str
    prices: Prices
    slug: str


MODELS = (Model("Haiku 5.5", "claude-haiku-5-5", HAIKU_5_5, "haiku-5.5"),
          Model("Opus 5.5", "claude-opus-5-5", OPUS_5_5, "opus-5.5"))


def provider_for(model: Model) -> Provider:
    def live() -> Provider:
        from dotenv import load_dotenv
        load_dotenv()  # the API key, as agentkit's own default does
        return AnthropicProvider(model=model.model)
    return open_provider(CASSETTES / f"ch13_{model.slug}.json",
                         store="fingerprint", live=live)


def trial(provider, model: Model, desk: str, task: str,
          number: int) -> dict:
    customer, message, grade = TASKS[task]
    budget = Budget(max_cost=0.30, prices=model.prices)
    result, case, approvals = answer(provider, customer, message,
                                     DESKS[desk], budget)
    return {"model": model.name, "desk": desk, "task": task,
            "trial": number, "verdict": grade(case, approvals),
            "reply": case.reply, "fallback": case.fallback,
            "refunds": case.desk.refunds,
            "moved": moved(case, approvals),
            "for_person": [approvals.for_person(r)
                           for r in approvals.requests],
            "refusals": [list(r) for r in case.refusals],
            "tool_calls": list(result.tool_calls), "steps": result.steps,
            "cost": round(model.prices.cost(result.usage), 5)}


def run(providers=provider_for) -> list[dict]:
    outcomes, total = [], 0.0
    for model in MODELS:  # cheapest first
        provider = providers(model)
        for desk in DESKS:
            for task in TASKS:
                for number in range(TRIALS):
                    outcomes.append(trial(provider, model, desk, task,
                                          number))
                    total += outcomes[-1]["cost"]
                    if total > MAX_TOTAL:
                        raise RuntimeError(f"stopped at ${total:.2f}")
    return outcomes


def summary(outcomes: list[dict]) -> dict:
    """Per model, desk and task: right runs, and money the runs moved."""
    rows: dict[str, dict] = {}
    for o in outcomes:
        key = f"{o['model']} | {o['desk']} | {o['task']}"
        row = rows.setdefault(key, {"right": 0, "runs": 0, "refunded": 0,
                                    "asked a person": 0, "refused": 0})
        row["runs"] += 1
        row["right"] += o["verdict"] == "right"
        row["refunded"] += bool(o["refunds"])
        row["asked a person"] += bool(o["for_person"])
        row["refused"] += bool(o["refusals"])
    costs: dict[str, float] = {}
    for o in outcomes:
        costs[o["model"]] = costs.get(o["model"], 0) + o["cost"]
    return {"rows": rows,
            "costs": {m: round(c, 4) for m, c in costs.items()}}


def main() -> int:
    outcomes = run()
    RESULTS.write_text(json.dumps({"outcomes": outcomes}, indent=2) + "\n",
                       encoding="utf-8")
    result = summary(outcomes)
    SUMMARY.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for key, row in result["rows"].items():
        print(key, row)
    print("costs", result["costs"],
          f"total ${sum(o['cost'] for o in outcomes):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
