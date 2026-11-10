"""Chapter 14: trace chapter 13's runs, then run the hardened desk cached.

    uv run python examples/14_observability/cache_experiment.py

Chapter 13's cassettes are always replayed. The cached runs replay by
default; with AGENTKIT_MODE=record they run against the live models (costs
money), cheapest first, and stop past MAX_TOTAL.
"""

import json
import sys
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
import security_experiment as chapter_13
from dashboard import alerts, day
from secure_desk import TASKS, answer
from traces import CachingProvider, Trace, dollars_by_kind, record
from tracing import Tracer

from agentkit import OPUS_5_5, Budget, Prices, Provider, open_provider

BOOK = Path(__file__).resolve().parents[2]
CASSETTES = BOOK / "fixtures" / "cassettes"
TRACES = BOOK / "fixtures" / "results" / "ch14_traces.jsonl"
SUMMARY = BOOK / "fixtures" / "results" / "ch14_summary.json"
TRIALS = chapter_13.TRIALS
MAX_TOTAL = 2.00
# Haiku 5.5 for prompts up to 100,000 tokens, with its cache prices
HAIKU_5_5 = Prices(input=0.10, output=0.50, cache_read=0.01,
                   cache_write=0.125)
PRICES = {"Haiku 5.5": HAIKU_5_5, "Opus 5.5": OPUS_5_5}
ARMS = ("chapter 12 desk", "chapter 13 desk", "chapter 13 desk, cached")


def cached_provider(model) -> Provider:
    def live() -> Provider:
        from dotenv import load_dotenv
        load_dotenv()  # the API key, as agentkit's own default does
        return CachingProvider(model=model.model)
    return open_provider(CASSETTES / f"ch14_cached_{model.slug}.json",
                         store="fingerprint", live=live)


def recorded_provider(model) -> Provider:
    """Chapter 13's recording, replayed whatever the mode."""
    return open_provider(CASSETTES / f"ch13_{model.slug}.json",
                         mode="replay")


def conversation(tracer: Tracer, model, arm: str, task: str,
                 number: int) -> tuple[Trace, str]:
    customer, message, grade = TASKS[task]
    prices = PRICES[model.name]
    start = len(tracer.calls)
    result, case, approvals = answer(
        tracer, customer, message, arm != "chapter 12 desk",
        Budget(max_cost=0.30, prices=prices))
    name = f"{model.name} | {arm} | {task} | {number}"
    trace = record(name, customer, tracer.calls[start:], result,
                   len(approvals.requests), case.fallback, prices)
    return trace, grade(case, approvals)


def run(arms=ARMS, cached=cached_provider) -> list[dict]:
    """Every conversation, in the order the cassettes were recorded."""
    found, spent = [], 0.0
    for model in chapter_13.MODELS:  # cheapest first
        recorded = Tracer(recorded_provider(model))  # both desks, in order
        for arm in arms:
            if arm == ARMS[2]:
                tracer = Tracer(cached(model))
            else:
                tracer = recorded
            for task in TASKS:
                for number in range(TRIALS):
                    trace, verdict = conversation(tracer, model, arm,
                                                  task, number)
                    found.append({"model": model.name, "arm": arm,
                                  "task": task, "verdict": verdict,
                                  "trace": trace})
                    if arm == ARMS[2]:
                        spent += trace.cost
                    if spent > MAX_TOTAL:
                        raise RuntimeError(f"stopped at ${spent:.2f}")
    return found


def group(found: list[dict], **match) -> list[dict]:
    return [f for f in found
            if all(f[key] == value for key, value in match.items())]


def summary(found: list[dict]) -> dict:
    arms = [arm for arm in ARMS if group(found, arm=arm)]
    rows = {}
    for model in chapter_13.MODELS:
        for arm in arms:
            chosen = group(found, model=model.name, arm=arm)
            traces = [f["trace"] for f in chosen]
            kinds: dict[str, float] = {}
            for trace in traces:
                for kind, cost in dollars_by_kind(
                        trace, PRICES[model.name]).items():
                    kinds[kind] = kinds.get(kind, 0) + cost
            rows[f"{model.name} | {arm}"] = {
                **day(traces),
                "right": sum(f["verdict"] == "right" for f in chosen),
                "dollars by kind": {k: round(v, 4)
                                    for k, v in kinds.items()}}
    raised = {}
    for before, after in zip(arms, arms[1:]):
        for model in [*chapter_13.MODELS, None]:
            pick = {"model": model.name} if model else {}
            name = model.name if model else "both models"
            first = day([f["trace"] for f in group(found, arm=before,
                                                   **pick)])
            second = day([f["trace"] for f in group(found, arm=after,
                                                    **pick)])
            raised[f"{name} | {before} -> {after}"] = alerts(first, second)
    return {"rows": rows, "alerts": raised}


def main() -> int:
    found = run()
    TRACES.write_text("".join(f["trace"].line() + "\n" for f in found),
                      encoding="utf-8")
    result = summary(found)
    SUMMARY.write_text(json.dumps(result, indent=2) + "\n",
                       encoding="utf-8")
    for key, row in result["rows"].items():
        print(key, row)
    for key, found_alerts in result["alerts"].items():
        print(key, found_alerts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
