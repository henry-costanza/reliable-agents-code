"""Chapter 2: ask for the needle across lengths, positions and distractors.

    uv run python examples/02_context/needle_experiment.py

Replays the recorded run by default. With AGENTKIT_MODE=record it calls the
live model (60 requests; costs money) and rewrites the cassette and the
results file. The cassette stores request fingerprints, not the documents:
build_haystack rebuilds them exactly.
"""

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

from haystack import QUESTION, build_haystack, grade

from agentkit import Provider, RunResult, open_provider, run_agent

BOOK = Path(__file__).resolve().parents[2]
CASSETTE = BOOK / "fixtures" / "cassettes" / "ch02_needle.json"
RESULTS = BOOK / "fixtures" / "results" / "ch02_needle.json"

# --8<-- [start:grid]
# Document sizes in characters; the token counts are measured.
LENGTHS = {"4k": 16_000, "32k": 128_000, "128k": 512_000}
POSITIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
TRIALS = 2
SYSTEM = "Answer from the document only."
# --8<-- [end:grid]


# --8<-- [start:ask]
def ask(
    provider: Provider,
    length: str,
    position: float,
    distractors: bool,
) -> RunResult:
    document = build_haystack(LENGTHS[length], position, distractors)
    prompt = f"<document>\n{document}\n</document>\n\n{QUESTION}"
    return run_agent(provider, prompt, system=SYSTEM, max_steps=1)
# --8<-- [end:ask]


@dataclass(frozen=True)
class Outcome:
    length: str
    position: float
    distractors: bool
    trial: int
    answer: str
    verdict: str
    input_tokens: int
    output_tokens: int


def run(provider: Provider) -> list[Outcome]:
    outcomes = []
    grid = product(LENGTHS, (False, True), POSITIONS, range(TRIALS))
    for length, distractors, position, trial in grid:
        result = ask(provider, length, position, distractors)
        answer = result.final_text.strip()
        verdict = grade(answer) if result.ok else f"stopped: {result.stop_reason.value}"
        outcomes.append(
            Outcome(length, position, distractors, trial, answer, verdict,
                    result.usage.input_tokens, result.usage.output_tokens)
        )
    return outcomes


def summarize(outcomes: list[Outcome]) -> list[dict]:
    """One row per length, distractor setting and position: verdict counts."""
    rows = []
    for length, distractors, position in product(LENGTHS, (False, True), POSITIONS):
        group = [o for o in outcomes
                 if (o.length, o.distractors, o.position) == (length, distractors, position)]
        counts = Counter(o.verdict for o in group)
        rows.append({
            "length": length, "distractors": distractors, "position": position,
            "trials": len(group), "right": counts["right"],
            "verdicts": dict(sorted(counts.items())),
            "input_tokens": max(o.input_tokens for o in group),
        })
    return rows


def main() -> int:
    provider = open_provider(CASSETTE, store="fingerprint")
    outcomes = run(provider)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps({"recorded_with": provider.describe(),
                    "rows": summarize(outcomes),
                    "outcomes": [asdict(o) for o in outcomes]}, indent=2) + "\n",
        encoding="utf-8",
    )
    for row in summarize(outcomes):
        noise = "distractors" if row["distractors"] else "plain"
        print(f"{row['length']:>5} {noise:<11} at {row['position']:.2f}: "
              f"{row['right']}/{row['trials']} right  {row['verdicts']}  "
              f"({row['input_tokens']:,} input tokens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
