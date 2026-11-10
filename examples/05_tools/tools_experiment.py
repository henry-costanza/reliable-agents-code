"""Chapter 5: the same refund request, with poor tools and with good ones.

    uv run python examples/05_tools/tools_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs each tool set TRIALS
times against the live model (costs money) and rewrites the cassette and
the results file. Each run gets a fresh desk, and is graded on the refunds
the desk recorded.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from desk import Desk, grade
from desk_tools import good_tools, poor_tools

from agentkit import (
    OPUS_5_5, Budget, Provider, RunResult, Tool, open_provider, run_agent,
)

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch05_tools.json"
RESULTS = BOOK / "fixtures" / "results" / "ch05_tools.json"
TRIALS = 5
TOOL_SETS = {"poor": poor_tools, "good": good_tools}
# A cap per run in case an agent loops; part of the experiment, so replay
# applies it too.
SAFETY = Budget(max_cost=0.30, prices=OPUS_5_5)

# --8<-- [start:task]
SYSTEM = (
    "You are Brindle's billing support agent. Use the tools to look "
    "up customers and invoices and to issue refunds. Act on the "
    "customer's request, then reply to the customer in two sentences."
)
TASK = (
    "Customer message: Hi, this is Orion Bakery. We were charged "
    "twice for October. Please refund the extra charge."
)
# --8<-- [end:task]


def attempt(provider: Provider, tools: list[Tool]) -> RunResult:
    return run_agent(provider, TASK, system=SYSTEM, tools=tools,
                     max_steps=15, budget=SAFETY)


def errors(result: RunResult) -> int:
    """Tool results the model saw as errors."""
    return sum(block.is_error for m in result.messages if m.role == "user"
               for block in m.content if hasattr(block, "is_error"))


def record(tool_set: str, trial: int, result: RunResult, desk: Desk) -> dict:
    return {
        "tools": tool_set, "trial": trial, "ok": result.ok,
        "verdict": grade(desk.refunds),
        "refunds": [list(refund) for refund in desk.refunds],
        "tool_calls": list(result.tool_calls), "errors": errors(result),
        "steps": result.steps, "reply": result.final_text.strip(),
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cost": round(OPUS_5_5.cost(result.usage), 4),
    }


def run(provider: Provider, connect=None) -> list[dict]:
    """Every tool set, TRIALS times. `connect`, if given, turns local
    tools into the tools the agent uses (chapter 5 passes MCP)."""
    outcomes = []
    for tool_set, make in TOOL_SETS.items():
        for trial in range(TRIALS):
            desk = Desk()
            tools = make(desk)
            if connect is None:
                result = attempt(provider, tools)
            else:
                with connect(tools) as remote_tools:
                    result = attempt(provider, remote_tools)
            outcomes.append(record(tool_set, trial, result, desk))
    return outcomes


def summarize(outcomes: list[dict]) -> list[dict]:
    rows = []
    for tool_set in TOOL_SETS:
        runs = [o for o in outcomes if o["tools"] == tool_set]
        rows.append({
            "tools": tool_set, "runs": len(runs),
            "verdicts": dict(sorted(Counter(o["verdict"] for o in runs).items())),
            "tool_calls": sum(len(o["tool_calls"]) for o in runs),
            "errors": sum(o["errors"] for o in runs),
            "steps": sum(o["steps"] for o in runs),
            "cost": round(sum(o["cost"] for o in runs), 4),
        })
    return rows


def main() -> int:
    provider = open_provider(CASSETTE)
    outcomes = run(provider)
    rows = summarize(outcomes)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"recorded_with": provider.describe(), "rows": rows,
                                   "outcomes": outcomes}, indent=2) + "\n", encoding="utf-8")
    for o in outcomes:
        print(f"{o['tools']:<5} {o['trial']}  {o['verdict']:<15} refunds {o['refunds']}  "
              f"{len(o['tool_calls'])} calls, {o['errors']} errors, ${o['cost']:.3f}")
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
