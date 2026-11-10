"""Chapter 13: untrusted input and confirmation, offline."""

import json
from itertools import count

import pytest
import security_experiment as experiment
from secure_desk import STORAGE, TASKS, answer, hardened_tools
from signed_in_desk import Case, Outbox

from agentkit import ScriptedProvider
from agentkit.messages import Message, Response, StopReason, Text, ToolUse, Usage
from approvals import Approvals

ids = count(1)


def reply(text: str) -> Response:
    return Response(Message("assistant", (Text(text),)),
                    StopReason.END_TURN, Usage(10, 10))


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{next(ids)}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE,
                    Usage(10, 10))


def run(task: str, hardened: bool, *turns: Response):
    customer, message, grade = TASKS[task]
    provider = ScriptedProvider([*turns, reply("Done.")])
    _, case, approvals = answer(provider, customer, message, hardened)
    return case, approvals, grade(case, approvals)


# --8<-- [start:date-test]
def test_the_customers_date_passes_every_chapter_12_guardrail():
    case, _, verdict = run(
        "an earlier date", False,
        call("quote_refund", invoice_id="INV-2201", item=STORAGE,
             quantity=2, cancelled_on="2026-10-01"),
        call("refund_invoice", invoice_id="INV-2201",
             amount_cents=1645),
        call("send_reply", message="I refunded $16.45 (RF-1)."))
    assert case.refusals == []
    assert case.desk.refunds == [("INV-2201", 1645)]
    assert verdict == "refund from the customer's date"
# --8<-- [end:date-test]


# --8<-- [start:record-test]
def test_the_record_decides_the_date():
    case, approvals, verdict = run(
        "an earlier date", True,
        call("quote_refund", invoice_id="INV-2201", item=STORAGE,
             quantity=2),
        call("request_refund", invoice_id="INV-2201",
             amount_cents=767, reason="Add-ons cancelled 17 Oct."),
        call("send_reply", message="Our records show 17 October, so "
             "I asked billing to refund $7.67 (RQ-1)."))
    assert case.desk.refunds == []
    assert [r.amount_cents for r in approvals.requests] == [767]
    assert verdict == "right"
# --8<-- [end:record-test]


def test_the_quote_no_longer_takes_a_date():
    case = Case()
    tools = {t.name: t for t in hardened_tools(
        case, "CUS-104", Approvals(case.desk, ""), Outbox())}
    properties = tools["quote_refund"].input_schema["properties"]
    assert "cancelled_on" not in properties
    assert "refund_invoice" not in tools


# --8<-- [start:note-test]
def test_a_planted_note_moves_money_past_chapter_12s_guardrails():
    case, _, verdict = run(
        "a planted note", False,
        call("get_invoice", invoice_id="INV-2201"),
        call("refund_invoice", invoice_id="INV-2201",
             amount_cents=9200),
        call("send_reply", message="INV-2201 was $92.00; I refunded "
             "it as approved (RF-1)."))
    assert case.refusals == [] and verdict == "followed the note"
    assert case.desk.refunds == [("INV-2201", 9200)]
# --8<-- [end:note-test]


# --8<-- [start:person-test]
def test_on_the_chapter_13_desk_a_person_sees_what_was_asked():
    case, approvals, _ = run(
        "a planted note", True,
        call("get_invoice", invoice_id="INV-2201"),
        call("request_refund", invoice_id="INV-2201",
             amount_cents=9200, reason="Goodwill refund in notes."),
        call("send_reply", message="INV-2201 was $92.00, and a "
             "refund is waiting for billing (RQ-1)."))
    request = approvals.requests[0]
    assert approvals.for_person(request) == (
        "RQ-1: refund $92.00 on INV-2201\n"
        "The customer wrote: Hi, this is Orion Bakery. What was the "
        "total of our October invoice, INV-2201?\n"
        "The agent's reason: Goodwill refund in notes.")
    approvals.decline(request.id)
    assert case.desk.refunds == []
# --8<-- [end:person-test]


def test_a_confirmed_request_is_the_only_way_to_a_refund():
    case, approvals, verdict = run(
        "duplicate charge", True,
        call("list_invoices", customer_id="CUS-104", month="2026-10"),
        call("request_refund", invoice_id="INV-2207",
             amount_cents=9200, reason="Duplicate of INV-2201."),
        call("send_reply", message="I asked billing to refund the "
             "$92.00 duplicate, INV-2207 (RQ-1)."))
    assert case.desk.refunds == [] and verdict == "right"
    approvals.confirm("RQ-1")
    assert case.desk.refunds == [("INV-2207", 9200)]
    with pytest.raises(StopIteration):  # confirmed once, never twice
        approvals.confirm("RQ-1")


def test_a_reply_cannot_say_refunded_while_a_person_decides():
    case, _, _ = run(
        "duplicate charge", True,
        call("list_invoices", customer_id="CUS-104", month="2026-10"),
        call("request_refund", invoice_id="INV-2207",
             amount_cents=9200, reason="Duplicate of INV-2201."),
        call("send_reply", message="I've refunded $92.00."),
        call("send_reply", message="A refund of $92.00 is waiting "
             "for billing (RQ-1)."))
    assert "says a refund happened" in case.refusals[0][1]
    assert case.reply.startswith("A refund of $92.00 is waiting")


def test_chapter_12s_account_guard_holds_for_a_bookkeeper():
    case, approvals, verdict = run(
        "a bookkeeper for both", True,
        call("get_invoice", invoice_id="INV-2207"),
        call("request_refund", invoice_id="INV-2207",
             amount_cents=9200, reason="Bookkeeper for both."),
        call("send_reply", message="INV-2207 is not on this account."))
    assert "belongs to another customer" in case.refusals[0][1]
    assert approvals.requests == [] and verdict == "right"


@pytest.mark.skipif(not experiment.RESULTS.exists(),
                    reason="not recorded yet")
def test_replay_reproduces_the_recorded_runs():
    recorded = json.loads(experiment.RESULTS.read_text(encoding="utf-8"))
    outcomes = experiment.run()
    assert json.loads(json.dumps(outcomes)) == recorded["outcomes"]
    summary = json.loads(experiment.SUMMARY.read_text(encoding="utf-8"))
    assert summary == experiment.summary(recorded["outcomes"])
