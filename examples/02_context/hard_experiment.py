"""Chapter 2: the harder tasks, where the research found degradation.

    uv run python examples/02_context/hard_experiment.py

Two variants, recorded once (27 requests; costs money with
AGENTKIT_MODE=record) and replayed offline afterwards:

  - paraphrase: the needle question reworded so it shares one word with
    the fact, with distractors present;
  - count: how many times one team did one thing, which needs the whole
    document rather than one sentence.
"""

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

from haystack import COUNT_QUESTION, PARAPHRASE, build_haystack, count_truth, grade, grade_count
from needle_experiment import LENGTHS, SYSTEM

from agentkit import Provider, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch02_hard.json"
RESULTS = BOOK / "fixtures" / "results" / "ch02_hard.json"

PARAPHRASE_LENGTHS = ("32k", "128k")
PARAPHRASE_POSITIONS = (0.0, 0.5, 1.0)
COUNT_LENGTHS = ("4k", "32k", "128k")
TRIALS = 3


@dataclass(frozen=True)
class Outcome:
    task: str
    length: str
    position: float
    trial: int
    answer: str
    truth: str
    verdict: str
    input_tokens: int
    output_tokens: int


def ask(provider: Provider, document: str, question: str):
    prompt = f"<document>\n{document}\n</document>\n\n{question}"
    return run_agent(provider, prompt, system=SYSTEM, max_steps=1)


def run(provider: Provider) -> list[Outcome]:
    outcomes = []
    for length, position, trial in product(PARAPHRASE_LENGTHS, PARAPHRASE_POSITIONS, range(TRIALS)):
        result = ask(provider, build_haystack(LENGTHS[length], position, True), PARAPHRASE)
        answer = result.final_text.strip()
        verdict = grade(answer) if result.ok else f"stopped: {result.stop_reason.value}"
        outcomes.append(Outcome("paraphrase", length, position, trial, answer, "7341", verdict,
                                result.usage.input_tokens, result.usage.output_tokens))
    for length, trial in product(COUNT_LENGTHS, range(TRIALS)):
        document = build_haystack(LENGTHS[length], 0.5, False)
        truth = count_truth(document)
        result = ask(provider, document, COUNT_QUESTION)
        answer = result.final_text.strip()
        verdict = grade_count(answer, truth) if result.ok else f"stopped: {result.stop_reason.value}"
        outcomes.append(Outcome("count", length, 0.5, trial, answer, str(truth), verdict,
                                result.usage.input_tokens, result.usage.output_tokens))
    return outcomes


def summarize(outcomes: list[Outcome]) -> list[dict]:
    """One row per task, length and position: verdicts and answers given."""
    rows = []
    keys = sorted({(o.task, o.length, o.position) for o in outcomes},
                  key=lambda k: (k[0], list(LENGTHS).index(k[1]), k[2]))
    for task, length, position in keys:
        group = [o for o in outcomes if (o.task, o.length, o.position) == (task, length, position)]
        counts = Counter(o.verdict for o in group)
        rows.append({
            "task": task, "length": length, "position": position,
            "trials": len(group), "right": counts["right"],
            "verdicts": dict(sorted(counts.items())),
            "truth": group[0].truth, "answers": [o.answer for o in group],
            "input_tokens": max(o.input_tokens for o in group),
        })
    return rows


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    rows = summarize(outcomes)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps({"recorded_with": provider.describe(), "rows": rows,
                    "outcomes": [asdict(o) for o in outcomes]}, indent=2) + "\n",
        encoding="utf-8",
    )
    for row in rows:
        print(f"{row['task']:<10} {row['length']:>5} at {row['position']:.1f}: "
              f"{row['right']}/{row['trials']} right  truth {row['truth']}  "
              f"answers {row['answers']}  ({row['input_tokens']:,} input tokens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
