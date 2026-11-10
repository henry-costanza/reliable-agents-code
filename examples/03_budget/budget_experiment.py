"""Chapter 3: record or replay both agents and write their per-step costs.

    uv run python examples/03_budget/budget_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs each agent TRIALS times
against the live model (costs money) and rewrites the cassettes and results.
The whole-log agent's requests are stored as fingerprints; the logs are
rebuilt exactly by team_logs.py.
"""

import json
import sys
from pathlib import Path

from cost_report import attribute, table
from log_agent import ask, count_tool, read_log_tool
from team_logs import LOGS, truth

from agentkit import OPUS_5_5, Budget, Provider, open_provider

BOOK = Path(__file__).resolve().parents[2]
CASSETTES = BOOK / "fixtures" / "cassettes"
RESULTS = BOOK / "fixtures" / "results" / "ch03_budget.json"
TRIALS = 2
# A cap on what one recorded run may spend if the model keeps rereading
# logs. It is part of the experiment, so replay uses it too.
SAFETY = Budget(max_cost=2.00, prices=OPUS_5_5)

AGENTS = {
    "whole logs": (read_log_tool, CASSETTES / "ch03_whole_logs.json", "fingerprint"),
    "counts": (count_tool, CASSETTES / "ch03_counts.json", "full"),
}


def picked(answer: str) -> str | None:
    """The log an answer names first, ignoring any explanation after it."""
    found = [(answer.lower().find(log), log) for log in LOGS if log in answer.lower()]
    return min(found)[1] if found else None


def run(agent: str, provider: Provider) -> list[dict]:
    make_tool = AGENTS[agent][0]
    runs = []
    for _ in range(TRIALS):
        result = ask(provider, make_tool(), budget=SAFETY)
        steps = attribute(result)
        runs.append({
            "answer": result.final_text.strip(),
            "picked": picked(result.final_text),
            "right": picked(result.final_text) == truth(),
            "ok": result.ok,
            "hit_budget": result.hit_budget,
            "tool_calls": list(result.tool_calls),
            "steps": steps,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost": round(OPUS_5_5.cost(result.usage), 4),
        })
    return runs


def main() -> int:
    results = {"truth": truth(), "prices": "OPUS_5_5", "agents": {}}
    for agent, (_, cassette, store) in AGENTS.items():
        provider = open_provider(cassette, store=store)
        results["agents"][agent] = run(agent, provider)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for agent, runs in results["agents"].items():
        for i, r in enumerate(runs, 1):
            print(f"\n{agent}, run {i}: answer {r['answer']!r} (right: {r['right']}), "
                  f"tools {r['tool_calls']}")
            print(table(r["steps"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
