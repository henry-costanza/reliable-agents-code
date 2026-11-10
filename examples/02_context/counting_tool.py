"""Chapter 2's fix: keep the document out of the context, count with a tool.

    uv run python examples/02_context/counting_tool.py

The agent never sees the 150,000-token document. It gets a tool that counts
exact matches, so the count comes from code, not from reading. Replays by
default; AGENTKIT_MODE=record makes a few short live calls.
"""

import json
import sys
from pathlib import Path

from haystack import COUNT_QUESTION, build_haystack, count_truth, grade_count
from needle_experiment import LENGTHS

from agentkit import Provider, RunResult, Tool, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch02_tool.json"
RESULTS = BOOK / "fixtures" / "results" / "ch02_tool.json"
TRIALS = 3


# --8<-- [start:tool]
def counting_tool(document: str) -> Tool:
    """Count a phrase in a document the model never reads."""
    text = {"type": "string", "minLength": 3}
    return Tool(
        "count_matches",
        "Count how many times a phrase occurs in the document. "
        "Matching ignores case.",
        {
            "type": "object",
            "properties": {"phrase": text},
            "required": ["phrase"],
            "additionalProperties": False,
        },
        lambda phrase: document.lower().count(phrase.lower()),
    )
# --8<-- [end:tool]


# --8<-- [start:ask]
SYSTEM = (
    "You answer questions about Brindle's internal activity log, "
    "which is too large to show you. Use the tools to examine it."
)


def ask_with_tool(provider: Provider, document: str) -> RunResult:
    tool = counting_tool(document)
    return run_agent(
        provider, COUNT_QUESTION, system=SYSTEM, tools=[tool]
    )
# --8<-- [end:ask]


def run(provider: Provider) -> dict:
    """Ask TRIALS times; return what the results file records."""
    document = build_haystack(LENGTHS["128k"], 0.5, False)
    truth = count_truth(document)
    trials = []
    for _ in range(TRIALS):
        result = ask_with_tool(provider, document)
        answer = result.final_text.strip()
        trials.append({
            "answer": answer, "verdict": grade_count(answer, truth),
            "tool_calls": len(result.tool_calls), "steps": result.steps,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
        })
    right = sum(t["verdict"] == "right" for t in trials)
    return {"task": "count with a tool", "length": "128k", "truth": str(truth),
            "trials": len(trials), "right": right, "runs": trials}


def main() -> int:
    provider = open_provider(CASSETTE)
    results = run(provider)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps({"recorded_with": provider.describe(), **results},
                                  indent=2) + "\n", encoding="utf-8")
    for t in results["runs"]:
        print(f"{t['answer']!r} -> {t['verdict']} (truth {results['truth']}); "
              f"{t['tool_calls']} tool calls; {t['input_tokens']:,} input tokens "
              f"over {t['steps']} steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
