"""Chapter 1: an early stop, the loop that fixes it, and a runaway model.

The first two tests replay a real recorded run (claude-opus-5-5, 31 Oct 2026).
The runaway test uses a scripted model, because a real one rarely misbehaves
on cue.
"""

from pathlib import Path

from invoices import GET_INVOICE, INVOICE_TOTAL, SYSTEM, TASK
from naive_agent import one_round_trip

from agentkit import (
    Message,
    Response,
    ScriptedProvider,
    StopReason,
    ToolUse,
    open_provider,
    run_agent,
)
from agentkit.cassette import ReplayProvider

TOOLS = [GET_INVOICE, INVOICE_TOTAL]
CASSETTE = Path(__file__).resolve().parents[2] / "fixtures" / "cassettes" / "ch01_agent_loop.json"


# --8<-- [start:early-stop]
def test_one_round_trip_returns_nothing():
    provider = ReplayProvider(CASSETTE)
    answer = one_round_trip(
        provider, TASK, system=SYSTEM, tools=TOOLS
    )
    assert answer == ""  # the model was still working
    assert provider.unused == 1  # one recorded reply never read
# --8<-- [end:early-stop]


# --8<-- [start:loop-test]
def test_the_loop_reaches_the_answer():
    provider = open_provider(CASSETTE)
    result = run_agent(provider, TASK, system=SYSTEM, tools=TOOLS)
    assert result.ok
    assert result.final_text == "$141.00"
    assert result.tool_calls == ("get_invoice", "invoice_total")
    assert result.steps == 3
# --8<-- [end:loop-test]


# --8<-- [start:runaway]
def asks_for_a_total(n: int) -> Response:
    call = ToolUse(f"call_{n}", "invoice_total", {"lines": []})
    reply = Message("assistant", (call,))
    return Response(reply, StopReason.TOOL_USE)


def test_a_runaway_model_stops_at_the_step_limit():
    model = ScriptedProvider(map(asks_for_a_total, range(100)))
    result = run_agent(model, TASK, tools=TOOLS, max_steps=5)
    assert result.hit_step_limit and not result.ok
    assert len(model.requests) == 5
# --8<-- [end:runaway]
