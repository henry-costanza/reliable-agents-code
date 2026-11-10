"""Chapter 14: traces, cost by kind, caching and alerts, offline."""

import json
from itertools import count

import cache_experiment as experiment
from dashboard import alerts, day
from secure_desk import answer
from traces import CachingProvider, Trace, record, tokens_by_kind
from tracing import Tracer

from agentkit import ScriptedProvider
from agentkit.messages import (Message, Request, Response, StopReason,
                               Text, ToolUse, Usage)

ids = count(1)


def reply(text: str) -> Response:
    return Response(Message("assistant", (Text(text),)),
                    StopReason.END_TURN, Usage(100, 10), "fake")


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{next(ids)}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE,
                    Usage(100, 10), "fake")


def traced(*turns: Response) -> Trace:
    tracer = Tracer(ScriptedProvider([*turns, reply("Done.")]))
    message = "We were charged twice for October."
    result, case, approvals = answer(tracer, "CUS-104", message, True)
    return record("test", "CUS-104", tracer.calls, result,
                  len(approvals.requests), case.fallback,
                  experiment.HAIKU_5_5)


def conversation(*calls: tuple[int, int, int]) -> Trace:
    """A trace from (input, cache read, cache write) per model call."""
    return Trace("test", "fake", "CUS-104",
                 [{"input": i, "cache_read": r, "cache_write": w,
                   "output": 10} for i, r, w in calls], [], 0, False, 0.0)


# --8<-- [start:trace-test]
def test_a_trace_says_how_each_tool_call_ended():
    trace = traced(
        call("get_invoice", invoice_id="INV-9999"),
        call("send_reply", message="I refunded $92.00."),
        call("request_refund", invoice_id="INV-2201",
             amount_cents=9200, reason="Charged twice."),
        call("send_reply", message="I asked billing to refund "
             "$92.00 (RQ-1)."))
    assert [(t["name"], t["outcome"]) for t in trace.tools] == [
        ("get_invoice", "error"), ("send_reply", "refused"),
        ("request_refund", "refused"), ("send_reply", "refused")]
    assert len(trace.calls) == 5 and trace.handed_over
# --8<-- [end:trace-test]


# --8<-- [start:kinds-test]
def test_most_of_each_prompt_was_sent_before():
    plain = tokens_by_kind(conversation(
        (1800, 0, 0), (2000, 0, 0), (2300, 0, 0)))
    assert plain["carried"] == 1800 + 2000
    assert plain["new"] == 1800 + 200 + 300
    cached = tokens_by_kind(conversation(
        (0, 1700, 100), (200, 1800, 0), (300, 2000, 0)))
    assert cached["carried"] == 0
    assert cached["cache read"] == 1700 + 1800 + 2000
# --8<-- [end:kinds-test]


# --8<-- [start:caching-test]
def test_caching_marks_the_shared_start():
    provider = CachingProvider("claude-haiku-5-5", client=object())
    request = Request((Message("user", (Text("Hello"),)),),
                      system="You are Brindle's desk.")
    params = provider.request_params(request)
    mark = {"type": "ephemeral"}
    assert params["system"] == [{"type": "text",
                                 "text": "You are Brindle's desk.",
                                 "cache_control": mark}]
    assert params["cache_control"] == mark
# --8<-- [end:caching-test]


def numbers(conversations: int, refused: int, p95: float = 0.05) -> dict:
    return {"conversations": conversations, "refused": refused,
            "handed over": 0, "p95 cost": p95}


# --8<-- [start:alert-test]
def test_an_alert_needs_more_than_chance():
    assert alerts(numbers(20, 0), numbers(20, 2)) == []
    assert alerts(numbers(20, 0), numbers(20, 4)) == []
    assert alerts(numbers(40, 0), numbers(40, 6)) == [
        "refused: 6 of 40, was 0 of 40"]
    assert alerts(numbers(40, 0, 0.05), numbers(40, 0, 0.08)) == [
        "p95 cost per conversation $0.0800, was $0.0500"]
# --8<-- [end:alert-test]


# --8<-- [start:incident-test]
def test_chapter_13_paid_again_for_what_it_had_sent():
    found = experiment.run(arms=experiment.ARMS[:2])
    today = day([f["trace"] for f in found])
    assert today["conversations"] == 80
    assert today["read from cache"] == 0
    assert today["carried at full price"] > 0.68
# --8<-- [end:incident-test]


def test_replay_reproduces_the_cached_runs():
    recorded = json.loads(experiment.SUMMARY.read_text(encoding="utf-8"))
    assert experiment.summary(experiment.run()) == recorded
