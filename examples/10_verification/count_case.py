"""Chapter 10: chapter 2's wrong count, with its evidence shown.

The agent must cite the log entry behind every audit it counts. Code checks
each citation against the log, and the count against the citations. It does
not know the right answer, so it can catch an invented entry and a count
that does not match, but not an entry the agent missed.
"""

import re

import earlier  # noqa: F401  (chapter 2's code on the import path)
from done import FINISH, Gate
from hard_experiment import LENGTHS
from haystack import COUNTED, build_haystack

from agentkit import Tool

QUESTION = "How many times did the security team audit something?"
SYSTEM = "You answer questions about Brindle's internal activity log."
GATED = SYSTEM + " " + FINISH


def numbered(document: str) -> dict[str, str]:
    """The log as entries with ids, one sentence each."""
    sentences = re.split(r"(?<=\.)\s+", document)
    return {f"E{i:05d}": s for i, s in enumerate(sentences, 1)}


def as_prompt(entries: dict[str, str]) -> str:
    body = "\n".join(f"{e} {s}" for e, s in entries.items())
    return f"<document>\n{body}\n</document>\n\n{QUESTION}"


def hard_log() -> dict[str, str]:
    return numbered(build_haystack(LENGTHS["128k"], 0.5, False))


# --8<-- [start:check]
def citations_hold(entries: dict[str, str], matches):
    """Each cited entry exists and says it; the count is the list."""
    def check(claim: dict) -> list[str]:
        cited = claim["entries"]
        problems = [f"{e} is not in the log." for e in cited
                    if e not in entries]
        problems += [f"{e} does not say that: {entries[e]}"
                     for e in cited
                     if e in entries and not matches(entries[e])]
        if len(set(cited)) != len(cited):
            problems.append("You cited the same entry twice.")
        if claim["count"] != len(set(cited)):
            problems.append(f"You counted {claim['count']} and cited "
                            f"{len(set(cited))} entries.")
        return problems
    return check
# --8<-- [end:check]


def is_audit(sentence: str) -> bool:
    return COUNTED in sentence


def count_gate(entries: dict[str, str]) -> tuple[Gate, Tool]:
    gate = Gate(citations_hold(entries, is_audit))
    tool = gate.tool(
        "Finish with your answer. count is the number. entries lists the "
        "id of every log entry you counted, each once.",
        {"count": {"type": "integer", "minimum": 0},
         "entries": {"type": "array", "items": {"type": "string"}}})
    return gate, tool
