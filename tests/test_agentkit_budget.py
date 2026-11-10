"""Budgets stop a run after the step that crosses them; usage is kept per step."""

import pytest

from agentkit import OPUS_5_5, Budget, Prices, run_agent
from agentkit.messages import Message, Response, StopReason, Text, ToolUse, Usage
from agentkit.provider import ScriptedProvider
from agentkit.tools import Tool

ECHO = Tool("echo", "Echo.", {"type": "object"}, lambda: "ok")


def asks(n: int, input_tokens: int) -> Response:
    call = ToolUse(f"t{n}", "echo", {})
    return Response(Message("assistant", (call,)), StopReason.TOOL_USE, Usage(input_tokens, 10))


def done(input_tokens: int) -> Response:
    return Response(Message("assistant", (Text("done"),)), StopReason.END_TURN, Usage(input_tokens, 5))


GROWING = [asks(1, 1_000), asks(2, 30_000), asks(3, 60_000), done(90_000)]


def test_usage_is_kept_per_step_and_adds_up():
    result = run_agent(ScriptedProvider(GROWING), "q", tools=[ECHO])
    assert [u.input_tokens for u in result.step_usage] == [1_000, 30_000, 60_000, 90_000]
    assert result.usage == Usage(181_000, 35)
    assert result.ok and not result.hit_budget


def test_token_budget_stops_after_the_step_that_crosses_it():
    model = ScriptedProvider(GROWING)
    result = run_agent(model, "q", tools=[ECHO], budget=Budget(max_input_tokens=50_000))
    assert result.hit_budget and not result.ok
    assert result.steps == 3 and len(model.requests) == 3  # 1k + 30k + 60k > 50k
    assert result.usage.input_tokens == 91_000
    assert result.stop_reason is StopReason.TOOL_USE  # stopped before running more tools


def test_cost_budget_uses_prices():
    model = ScriptedProvider(GROWING)
    result = run_agent(model, "q", tools=[ECHO], budget=Budget(max_cost=0.20, prices=OPUS_5_5))
    # $4 per million: 31k tokens is $0.124, 91k tokens is $0.364.
    assert result.hit_budget and result.steps == 3


def test_a_run_inside_its_budget_is_untouched():
    result = run_agent(ScriptedProvider(GROWING), "q", tools=[ECHO], budget=Budget(max_input_tokens=1_000_000))
    assert result.ok and result.steps == 4


def test_budget_explains_itself():
    assert Budget(max_input_tokens=50_000).exceeded(Usage(91_000, 0)) == "91,000 input tokens; the budget is 50,000"
    assert Budget(max_cost=0.2, prices=OPUS_5_5).exceeded(Usage(91_000, 0)) == "$0.36 spent; the budget is $0.20"
    assert Budget(max_input_tokens=50_000).exceeded(Usage(10_000, 0)) is None


def test_cache_tokens_count_against_a_token_budget():
    assert Budget(max_input_tokens=50_000).exceeded(Usage(1_000, 0, 60_000, 0)) is not None


def test_prices_turn_usage_into_dollars():
    assert OPUS_5_5.cost(Usage(1_000_000, 0)) == pytest.approx(4.0)
    assert OPUS_5_5.cost(Usage(0, 1_000_000)) == pytest.approx(20.0)
    assert OPUS_5_5.cost(Usage(0, 0, 1_000_000, 0)) == pytest.approx(0.20)
    assert OPUS_5_5.cost(Usage(0, 0, 0, 1_000_000)) == pytest.approx(5.0)
    assert Prices(input=1.0, output=2.0).cost(Usage(0, 0, 1_000_000, 1_000_000)) == pytest.approx(2.0)


def test_a_cost_budget_without_prices_is_refused():
    with pytest.raises(ValueError, match="needs prices"):
        Budget(max_cost=1.0)
