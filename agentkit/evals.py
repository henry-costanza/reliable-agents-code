"""Golden tasks and graders.

A golden task is a prompt plus a grader that decides whether a run passed.
Live output varies, so an eval reports a pass rate over several trials, not a
single yes or no. Against a cassette the rate is fixed, which makes it a
regression test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from agentkit.loop import RunResult, run_agent
from agentkit.provider import Provider
from agentkit.tools import Tool

__all__ = ["Grader", "contains", "exact", "finished", "GoldenTask", "TaskScore", "EvalReport", "run_eval"]

Grader = Callable[[RunResult], bool]


def contains(expected: str, *, case_sensitive: bool = False) -> Grader:
    """Pass when the final text contains `expected`."""

    def grade(result: RunResult) -> bool:
        text = result.final_text
        if case_sensitive:
            return expected in text
        return expected.lower() in text.lower()

    return grade


def exact(expected: str) -> Grader:
    """Pass when the final text, stripped, equals `expected`."""
    return lambda result: result.final_text.strip() == expected


def finished(grader: Grader) -> Grader:
    """Pass only when the run ended on its own and `grader` passes."""
    return lambda result: result.ok and grader(result)


@dataclass(frozen=True)
class GoldenTask:
    name: str
    prompt: str
    grader: Grader
    system: str = ""
    tools: tuple[Tool, ...] = ()


@dataclass(frozen=True)
class TaskScore:
    name: str
    passed: int
    trials: int

    @property
    def rate(self) -> float:
        return self.passed / self.trials


@dataclass(frozen=True)
class EvalReport:
    scores: tuple[TaskScore, ...]

    @property
    def pass_rate(self) -> float:
        trials = sum(s.trials for s in self.scores)
        return sum(s.passed for s in self.scores) / trials if trials else 0.0

    @property
    def failing(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.scores if s.passed < s.trials)


def run_eval(
    provider: Provider, tasks: Iterable[GoldenTask], *, trials: int = 1, max_steps: int = 10
) -> EvalReport:
    if trials < 1:
        raise ValueError("trials must be at least 1")
    scores = []
    for task in tasks:
        passed = 0
        for _ in range(trials):
            result = run_agent(
                provider, task.prompt, system=task.system, tools=task.tools, max_steps=max_steps
            )
            passed += bool(task.grader(result))
        scores.append(TaskScore(task.name, passed, trials))
    return EvalReport(tuple(scores))
