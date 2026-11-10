"""The agent loop: ask the model, run the tools it asks for, repeat.

The history only ever grows. Each reply is appended as received, and all tool
results for one reply go back in a single user message. The loop stops on any
stop reason other than `tool_use` and `pause_turn`, or when `max_steps` runs
out, and `RunResult` says which, so callers can tell a finished task from a
truncated, refused or runaway one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from agentkit.budget import Budget
from agentkit.messages import Message, Request, StopReason, ToolResult, Usage
from agentkit.provider import Provider
from agentkit.tools import Tool

__all__ = ["RunResult", "run_agent"]


@dataclass(frozen=True)
class RunResult:
    messages: tuple[Message, ...]
    stop_reason: StopReason
    steps: int
    usage: Usage
    hit_step_limit: bool = False
    step_usage: tuple[Usage, ...] = ()
    """Usage of each model call in order; they add up to `usage`."""
    hit_budget: bool = False

    @property
    def ok(self) -> bool:
        """The model ended its turn on its own, within its limits."""
        return (
            self.stop_reason is StopReason.END_TURN
            and not self.hit_step_limit
            and not self.hit_budget
        )

    @property
    def final_text(self) -> str:
        for message in reversed(self.messages):
            if message.role == "assistant":
                return message.text
        return ""

    @property
    def tool_calls(self) -> tuple[str, ...]:
        """Names of the tools called, in order."""
        return tuple(
            use.name for m in self.messages if m.role == "assistant" for use in m.tool_uses
        )


def run_agent(
    provider: Provider,
    prompt: str,
    *,
    system: str = "",
    tools: Iterable[Tool] = (),
    max_steps: int = 10,
    max_tokens: int = 16000,
    budget: Budget | None = None,
) -> RunResult:
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")
    by_name = {tool.name: tool for tool in tools}
    specs = tuple(tool.spec for tool in by_name.values())
    messages = [Message.user(prompt)]
    meter = _Meter(budget)
    stop_reason = StopReason.END_TURN

    # --8<-- [start:loop]
    for step in range(1, max_steps + 1):
        request = Request(tuple(messages), system, specs, max_tokens)
        response = provider.complete(request)
        meter.add(response.usage)
        stop_reason = response.stop_reason
        messages.append(response.message)
        calls = response.message.tool_uses

        if meter.over_budget:
            return meter.result(messages, stop_reason, step, budget=True)
        if stop_reason is StopReason.PAUSE_TURN:
            continue  # resending the history resumes a paused turn
        if stop_reason is StopReason.TOOL_USE and calls:
            messages.append(_run_tools(calls, by_name))
            continue
        return meter.result(messages, stop_reason, step)

    return meter.result(messages, stop_reason, max_steps, limit=True)
    # --8<-- [end:loop]


class _Meter:
    """Adds up usage per step and checks it against the budget."""

    def __init__(self, budget: Budget | None) -> None:
        self.budget = budget
        self.total = Usage()
        self.steps: list[Usage] = []

    def add(self, usage: Usage) -> None:
        self.total += usage
        self.steps.append(usage)

    @property
    def over_budget(self) -> bool:
        return self.budget is not None and self.budget.exceeded(self.total) is not None

    def result(self, messages, stop_reason, steps, *, limit=False, budget=False) -> RunResult:
        return RunResult(
            tuple(messages), stop_reason, steps, self.total,
            hit_step_limit=limit, step_usage=tuple(self.steps), hit_budget=budget,
        )


# --8<-- [start:run-tools]
def _run_tools(calls, by_name: dict[str, Tool]) -> Message:
    """Run every call in one reply; answer them all in one message."""
    results = []
    for call in calls:
        tool = by_name.get(call.name)
        if tool is None:
            error = f"unknown tool {call.name!r}"
            result = ToolResult(call.id, error, is_error=True)
        else:
            result = tool.run(call)
        results.append(result)
    return Message("user", tuple(results))
# --8<-- [end:run-tools]
