"""Chapter 4: each task with no, vague and specific instructions.

    uv run python examples/04_instructions/instructions_experiment.py

Replays by default. With AGENTKIT_MODE=record it runs every task, variant and
trial against the live model (costs money) and rewrites the cassette and the
results file. The cassette stores fingerprints: the project files and tool
results are rebuilt exactly from code.
"""

import json
import sys
from itertools import product
from pathlib import Path

from checks import RULES, check
from instructions import VARIANTS, system_prompt
from mini_repo import FILES, TASKS, workspace_tools

from agentkit import OPUS_5_5, Budget, Provider, RunResult, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch04_instructions.json"
RESULTS = BOOK / "fixtures" / "results" / "ch04_instructions.json"
TRIALS = 3
# A cap per run in case an agent loops; part of the experiment, so replay
# applies it too.
SAFETY = Budget(max_cost=0.50, prices=OPUS_5_5)


# --8<-- [start:ask]
def attempt(
    provider: Provider, task: str, agents_md: str | None
) -> tuple[RunResult, dict[str, str]]:
    """Run the agent on a fresh copy of the project; return the files."""
    files = dict(FILES)
    result = run_agent(
        provider, TASKS[task], system=system_prompt(agents_md),
        tools=workspace_tools(files), max_steps=15, budget=SAFETY,
    )
    return result, files
# --8<-- [end:ask]


def run(provider: Provider) -> list[dict]:
    outcomes = []
    for task, variant, trial in product(TASKS, VARIANTS, range(TRIALS)):
        result, files = attempt(provider, task, VARIANTS[variant])
        passed = check(files, task)
        outcomes.append({
            "task": task, "variant": variant, "trial": trial,
            "ok": result.ok, "steps": result.steps,
            "rules": passed, "all": all(passed.values()),
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost": round(OPUS_5_5.cost(result.usage), 4),
        })
    return outcomes


def summarize(outcomes: list[dict]) -> list[dict]:
    """Per variant: how many runs followed each rule, and all of them."""
    rows = []
    for variant in VARIANTS:
        runs = [o for o in outcomes if o["variant"] == variant]
        row = {"variant": variant, "runs": len(runs),
               "all": sum(o["all"] for o in runs),
               "cost": round(sum(o["cost"] for o in runs), 4)}
        row.update({rule: sum(o["rules"][rule] for o in runs) for rule in RULES})
        rows.append(row)
    return rows


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    rows = summarize(outcomes)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"rows": rows, "outcomes": outcomes}, indent=2) + "\n",
                       encoding="utf-8")
    for row in rows:
        rules = "  ".join(f"{rule}: {row[rule]}/{row['runs']}" for rule in RULES)
        print(f"{row['variant']:<9} all rules: {row['all']}/{row['runs']}  {rules}  "
              f"(${row['cost']:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
