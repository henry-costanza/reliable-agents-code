"""The loop and tools against scripted replies, including the ways a run goes wrong."""

import pytest

from agentkit.evals import GoldenTask, contains, exact, finished, run_eval
from agentkit.loop import run_agent
from agentkit.messages import Message, Opaque, Response, StopReason, Text, ToolResult, ToolUse, Usage
from agentkit.provider import ScriptedProvider
from agentkit.tools import Tool

ADD = Tool(
    "add",
    "Add two integers.",
    {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    },
    lambda a, b: a + b,
)
DIVIDE = Tool(
    "divide",
    "Divide a by b.",
    {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
    lambda a, b: a / b,
)
THINKING = Opaque("anthropic", {"type": "thinking", "thinking": "", "signature": "s"})


def reply(*blocks, stop=StopReason.END_TURN, usage=Usage(10, 2)):
    return Response(Message("assistant", blocks), stop, usage)


def asks(*calls):
    return reply(THINKING, *calls, stop=StopReason.TOOL_USE)


def test_tool_round_trip_appends_history_and_sums_usage():
    provider = ScriptedProvider([asks(ToolUse("t1", "add", {"a": 2, "b": 3})), reply(Text("5"))])
    result = run_agent(provider, "2+3?", tools=[ADD], system="sys")
    assert result.ok and result.final_text == "5" and result.steps == 2
    assert result.tool_calls == ("add",)
    assert result.usage == Usage(20, 4)
    second = provider.requests[1]
    assert second.system == "sys" and [t.name for t in second.tools] == ["add"]
    # history is append-only: the first reply goes back with its thinking block unchanged
    assert second.messages[1].content[0] is THINKING
    assert second.messages[2] == Message("user", (ToolResult("t1", "5"),))


def test_parallel_calls_come_back_in_one_message():
    provider = ScriptedProvider(
        [asks(ToolUse("t1", "add", {"a": 1, "b": 1}), ToolUse("t2", "add", {"a": 2, "b": 2})), reply(Text("ok"))]
    )
    run_agent(provider, "q", tools=[ADD])
    assert provider.requests[1].messages[-1].content == (ToolResult("t1", "2"), ToolResult("t2", "4"))


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (ToolUse("t1", "add", {"a": "two", "b": 3}), "invalid input: a: 'two' is not of type 'integer'"),
        (ToolUse("t1", "add", {"a": 1}), "invalid input: input: 'b' is a required property"),
        (ToolUse("t1", "divide", {"a": 1, "b": 0}), "ZeroDivisionError: division by zero"),
        (ToolUse("t1", "search", {}), "unknown tool 'search'"),
    ],
)
def test_tool_failures_go_back_to_the_model_as_errors(call, message):
    provider = ScriptedProvider([asks(call), reply(Text("sorry"))])
    result = run_agent(provider, "q", tools=[ADD, DIVIDE])
    assert result.ok
    assert provider.requests[1].messages[-1].content == (ToolResult("t1", message, is_error=True),)


@pytest.mark.parametrize(
    "stop", [StopReason.MAX_TOKENS, StopReason.REFUSAL, StopReason.CONTEXT_WINDOW_EXCEEDED]
)
def test_truncated_or_refused_runs_are_not_ok(stop):
    result = run_agent(ScriptedProvider([reply(Text("partial"), stop=stop)]), "q")
    assert result.stop_reason is stop and not result.ok and result.steps == 1


def test_runaway_loop_stops_at_the_step_limit():
    calls = [asks(ToolUse(f"t{i}", "add", {"a": i, "b": i})) for i in range(3)]
    result = run_agent(ScriptedProvider(calls), "q", tools=[ADD], max_steps=3)
    assert result.hit_step_limit and not result.ok and result.steps == 3


def test_pause_turn_resumes_with_the_same_history():
    provider = ScriptedProvider([reply(Text("working"), stop=StopReason.PAUSE_TURN), reply(Text("done"))])
    result = run_agent(provider, "q")
    assert result.ok and result.final_text == "done"
    assert provider.requests[1].messages[-1].text == "working"


def test_tool_use_stop_without_calls_ends_the_run():
    result = run_agent(ScriptedProvider([reply(Text("hm"), stop=StopReason.TOOL_USE)]), "q")
    assert result.stop_reason is StopReason.TOOL_USE and not result.ok


def test_bad_tool_definitions_are_refused():
    with pytest.raises(ValueError, match="tool name"):
        Tool("has space", "d", {"type": "object"}, print)
    with pytest.raises(Exception, match="is not valid"):
        Tool("t", "d", {"type": "nonsense"}, print)


def test_bad_limits_are_refused():
    with pytest.raises(ValueError):
        run_agent(ScriptedProvider([]), "q", max_steps=0)
    with pytest.raises(ValueError):
        run_eval(ScriptedProvider([]), [], trials=0)


def test_graders():
    result = run_agent(ScriptedProvider([reply(Text(" Paris "))]), "q")
    assert contains("paris")(result) and not contains("paris", case_sensitive=True)(result)
    assert exact("Paris")(result) and not exact("paris")(result)
    refused = run_agent(ScriptedProvider([reply(Text("Paris"), stop=StopReason.REFUSAL)]), "q")
    assert contains("Paris")(refused) and not finished(contains("Paris"))(refused)


def test_eval_reports_pass_rate_per_task():
    provider = ScriptedProvider([reply(Text("Paris")), reply(Text("Lyon")), reply(Text("PONG")), reply(Text("PONG"))])
    report = run_eval(
        provider,
        [GoldenTask("capital", "Capital of France?", contains("Paris")), GoldenTask("pong", "Say PONG", exact("PONG"))],
        trials=2,
    )
    assert [(s.name, s.passed, s.trials) for s in report.scores] == [("capital", 1, 2), ("pong", 2, 2)]
    assert report.pass_rate == 0.75
    assert report.failing == ("capital",)
