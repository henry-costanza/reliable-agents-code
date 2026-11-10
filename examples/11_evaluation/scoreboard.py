"""Chapter 11: Brindle's first scoreboard, on runs it already recorded.

`run_eval` hands a grader the agent's reply and nothing else. A grader that
reads only the reply passes a refund that never happened. Replayed from
chapter 5's cassette, so this costs nothing.
"""

import json
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from desk import Desk, grade
from desk_tools import good_tools, poor_tools
from tools_experiment import CASSETTE, RESULTS, SYSTEM, TASK

from agentkit import GoldenTask, contains, finished, run_eval
from agentkit.cassette import ReplayProvider

BOOK = Path(__file__).resolve().parents[2]


def recorded(name: str) -> list[dict]:
    path = BOOK / "fixtures" / "results" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))["outcomes"]


# --8<-- [start:first]
def says_refund(result) -> bool:
    return (contains("INV-2207")(result)
            and contains("refund")(result))


def golden(name: str, tools) -> GoldenTask:
    return GoldenTask(name, TASK, finished(says_refund), SYSTEM,
                      tuple(tools(Desk())))


def first_scoreboard() -> dict[str, int]:
    """The refund task, graded on the reply, as run_eval allows."""
    replay = ReplayProvider(CASSETTE)
    poor = run_eval(replay, [golden("poor", poor_tools)], trials=5,
                    max_steps=15)
    good = [run_eval(replay, [golden("good", good_tools)],
                     max_steps=15)
            for _ in range(5)]  # a fresh desk each time
    return {"poor tools": poor.scores[0].passed,
            "good tools": sum(r.scores[0].passed for r in good)}
# --8<-- [end:first]


def shared_desk_replay() -> None:
    """What run_eval does with one desk over five trials."""
    replay = ReplayProvider(CASSETTE)
    run_eval(replay, [golden("poor", poor_tools)], trials=5, max_steps=15)
    run_eval(replay, [golden("good", good_tools)], trials=5, max_steps=15)


def desk_scores() -> dict[str, int]:
    """The same ten runs, graded on what the desk recorded."""
    runs = json.loads(RESULTS.read_text(encoding="utf-8"))["outcomes"]
    scores = {"poor tools": 0, "good tools": 0}
    for run in runs:
        refunds = [tuple(r) for r in run["refunds"]]
        scores[f"{run['tools']} tools"] += grade(refunds) == "right"
    return scores


# --8<-- [start:weak]
def first_help_center_grader(question, answer: str) -> bool:
    """Chapter 6's first grader: the fact, and the right citation."""
    import re

    from retrieval_experiment import SOURCE
    cited = SOURCE.findall(answer)
    source = cited[-1].upper() if cited else None
    if question.source is None:
        return source == "NONE"
    return (bool(re.search(question.fact, answer, re.I))
            and source == question.source)
# --8<-- [end:weak]


def regrade_help_center() -> dict[str, dict[str, int]]:
    """Chapter 6's recorded answers under its first and last graders."""
    from help_center import QUESTIONS
    scores: dict[str, dict[str, int]] = {}
    for run in recorded("ch06_retrieval"):
        arm = scores.setdefault(run["arm"], {"first": 0, "last": 0})
        question = QUESTIONS[run["question"]]
        arm["first"] += first_help_center_grader(question, run["answer"])
        arm["last"] += run["verdict"] == "right"
    return scores
