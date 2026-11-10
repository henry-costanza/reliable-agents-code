"""Chapter 11: one golden set, four versions of Brindle's agent.

    uv run python examples/11_evaluation/eval_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs against the live models
(costs money), cheapest first, and stops past MAX_TOTAL.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from desk_tools import good_tools
from golden import TASKS, trimmed_tools

from agentkit import OPUS_5_5, Prices, Provider, open_provider
from agentkit.anthropic_provider import AnthropicProvider

BOOK = Path(__file__).resolve().parents[2]
RESULTS = BOOK / "fixtures" / "results" / "ch11_evaluation.json"
SUMMARY = BOOK / "fixtures" / "results" / "ch11_summary.json"
TRIALS = 5
MAX_TOTAL = 9.00
SONNET_5_5 = Prices(input=2.0, output=10.0)
HAIKU_5_5 = Prices(input=0.10, output=0.50)  # prompts up to 100,000 tokens


@dataclass(frozen=True)
class Agent:
    name: str
    model: str
    prices: Prices
    desk_tools: object = good_tools
    desk_only: bool = False


# Cheapest first, so an overrun stops before the expensive model.
AGENTS = (
    Agent("Haiku 5.5", "claude-haiku-5-5", HAIKU_5_5),
    Agent("Sonnet 5.5", "claude-sonnet-5-5", SONNET_5_5),
    Agent("Opus, trimmed tools", "claude-opus-5-5", OPUS_5_5,
          trimmed_tools, desk_only=True),
    Agent("Opus 5.5", "claude-opus-5-5", OPUS_5_5),
)


def cassette(agent: Agent) -> Path:
    slug = agent.name.lower().replace(",", "").replace(" ", "-")
    return BOOK / "fixtures" / "cassettes" / f"ch11_{slug}.json"


def provider_for(agent: Agent) -> Provider:
    def live() -> Provider:
        from dotenv import load_dotenv
        load_dotenv()  # the API key, as agentkit's own default does
        return AnthropicProvider(model=agent.model)
    return open_provider(cassette(agent), store="fingerprint", live=live)


def trial(provider: Provider, agent: Agent, task, number: int) -> dict:
    attempt = task.run(provider, agent.desk_tools)
    result = attempt.result
    return {"agent": agent.name, "task": task.name,
            "incident": task.incident, "trial": number,
            "verdict": attempt.verdict,
            "reply": result.final_text.strip(),
            "tool_calls": list(result.tool_calls), "steps": result.steps,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost": round(agent.prices.cost(result.usage), 5)}


def run(providers=provider_for) -> list[dict]:
    outcomes, total = [], 0.0
    for agent in AGENTS:
        provider = providers(agent)
        tasks = [t for t in TASKS if t.uses_desk or not agent.desk_only]
        for task in tasks:
            for number in range(TRIALS):
                outcomes.append(trial(provider, agent, task, number))
                total += outcomes[-1]["cost"]
                if total > MAX_TOTAL:
                    raise RuntimeError(f"stopped at ${total:.2f}")
    return outcomes


def scores(outcomes: list[dict], agent: str) -> dict[str, tuple[int, int]]:
    """Task name to (passed, trials) for one agent."""
    found: dict[str, tuple[int, int]] = {}
    for o in outcomes:
        if o["agent"] == agent:
            passed, trials = found.get(o["task"], (0, 0))
            found[o["task"]] = (passed + (o["verdict"] == "right"),
                                trials + 1)
    return found


def spent(outcomes: list[dict], agent: str) -> str:
    return f"${sum(o['cost'] for o in outcomes if o['agent'] == agent):.2f}"


def summary(outcomes: list[dict]) -> dict:
    """One row per task, one column per version, for the figure."""
    rows = [{"task": t.name, "incident": t.incident,
             "scores": {a.name: list(scores(outcomes, a.name)[t.name])
                        for a in AGENTS
                        if t.name in scores(outcomes, a.name)}}
            for t in TASKS]
    costs = {a.name: spent(outcomes, a.name) for a in AGENTS}
    return {"agents": [a.name for a in AGENTS], "rows": rows,
            "costs": costs}


def main() -> int:
    outcomes = run()
    rows = {a.name: scores(outcomes, a.name) for a in AGENTS}
    RESULTS.write_text(json.dumps({"rows": rows, "outcomes": outcomes},
                                  indent=2) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary(outcomes), indent=2) + "\n",
                       encoding="utf-8")
    for name, row in rows.items():
        cost = sum(o["cost"] for o in outcomes if o["agent"] == name)
        print(name, f"${cost:.2f}", row)
    print(f"total ${sum(o['cost'] for o in outcomes):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
