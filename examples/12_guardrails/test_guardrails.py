"""Chapter 12: guardrails that refuse, offline."""

import json

import guardrail_experiment as experiment
import pytest
import reply_sweep
from desk import Desk
from desk_tools import good_tools
from guards import Ledger, amount_problems, amounts
from money_guard import money_check
from refund_case import LockedDesk
from signed_in_desk import TASKS, answer, quote

from agentkit import ScriptedProvider
from agentkit.messages import Message, Response, StopReason, Text, ToolUse, Usage

STORAGE = "Extra storage, 50 GB"


def reply(text: str) -> Response:
    return Response(Message("assistant", (Text(text),)),
                    StopReason.END_TURN, Usage(10, 10))


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{name}_{len(str(arguments))}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE,
                    Usage(10, 10))


def test_the_quote_follows_the_policy():
    found = quote(LockedDesk(()), "INV-2201", STORAGE, 2, "2026-10-17")
    assert (found["days_left"], found["days_in_month"]) == (14, 31)
    assert found["amount_cents"] == 1700 * 14 // 31 == 767


def test_the_ledger_keeps_every_amount_a_tool_returned():
    ledger = Ledger()
    tools = {t.name: ledger.watch(t) for t in good_tools(Desk())}
    tools["get_invoice"].function(invoice_id="INV-2201")
    assert {9200, 7500, 2500, 1700, 850, 0} <= ledger.cents
    assert 8350 not in ledger.cents


def test_amounts_reads_dollars_in_every_form():
    assert amounts("$92, $92.00 and $1,234.50") == [9200, 9200, 123450]


# --8<-- [start:refund-test]
def test_a_refund_no_tool_quoted_is_refused_and_corrected():
    customer, message, grade = TASKS["unused days"]
    provider = ScriptedProvider([
        call("refund_invoice", invoice_id="INV-2201",
             amount_cents=768),
        call("quote_refund", invoice_id="INV-2201", item=STORAGE,
             quantity=2, cancelled_on="2026-10-17"),
        call("refund_invoice", invoice_id="INV-2201",
             amount_cents=767),
        call("send_reply", message="I refunded $7.67 (RF-1)."),
        reply("Done.")])
    _, case = answer(provider, customer, message, guarded=True)
    assert case.refusals[0] == ("refund_invoice",
        "No tool returned 768 cents. Refund only an amount a tool "
        "returned: an invoice total, a line, or a quote from "
        "quote_refund.")
    assert case.desk.refunds == [("INV-2201", 767)]
    assert grade(case) == "right"
# --8<-- [end:refund-test]


def test_the_same_refund_goes_through_with_the_rule_only_in_the_prompt():
    customer, message, grade = TASKS["unused days"]
    provider = ScriptedProvider([
        call("refund_invoice", invoice_id="INV-2201", amount_cents=768),
        call("send_reply", message="I refunded $7.68 (RF-1)."),
        reply("Done.")])
    _, case = answer(provider, customer, message, guarded=False)
    assert case.desk.refunds == [("INV-2201", 768)]
    assert grade(case) == "wrong refund"


def test_another_customers_invoice_is_refused_whatever_was_looked_up():
    customer, message, grade = TASKS["another customer's invoice"]
    provider = ScriptedProvider([
        call("get_invoice", invoice_id="INV-2207"),
        call("refund_invoice", invoice_id="INV-2207", amount_cents=9200),
        call("send_reply", message="INV-2207 is not on your account."),
        reply("Done.")])
    _, case = answer(provider, customer, message, guarded=True)
    assert "belongs to another customer" in case.refusals[0][1]
    assert grade(case) == "right"


# --8<-- [start:reply-test]
@pytest.mark.parametrize("message, problem", [
    ("Your invoice now comes to $83.50.", "No tool returned $83.50."),
    ("We refunded 9,200 (RF-1).", "9,200 is a number of cents."),
    ("I've refunded the extra charge.", "says a refund happened"),
])
def test_the_reply_check_refuses_and_says_why(message, problem):
    customer, task, _ = TASKS["duplicate charge"]
    good = "I refunded $92.00 on INV-2207 (RF-1)."
    provider = ScriptedProvider([
        call("get_invoice", invoice_id="INV-2207"),
        call("send_reply", message=message),
        call("refund_invoice", invoice_id="INV-2207",
             amount_cents=9200),
        call("send_reply", message=good), reply("Done.")])
    _, case = answer(provider, customer, task, guarded=True)
    assert problem in case.refusals[0][1]
    assert case.reply == good
# --8<-- [end:reply-test]


def test_with_no_accepted_reply_a_person_takes_over():
    customer, message, _ = TASKS["duplicate charge"]
    provider = ScriptedProvider([reply("You were refunded $92.")])
    _, case = answer(provider, customer, message, guarded=True)
    assert case.fallback and "(ticket TCK-1)" in case.reply
    assert case.desk.tickets == [f"{customer}: {message}"]


# --8<-- [start:money-test]
def test_the_money_rule_refuses_division_on_every_write():
    average = ("def average_line_price(invoice):\n"
               "    cents = [l.unit_price_cents\n"
               "             for l in invoice.lines]\n"
               "    return sum(cents) {} len(cents)\n")
    totals = {"path": "invoices/totals.py"}
    readme = {"path": "README.md", "content": "a / b"}
    assert "uses /" in money_check(
        {**totals, "content": average.format("/")})
    assert money_check(
        {**totals, "content": average.format("//")}) is None
    assert money_check(readme) is None
# --8<-- [end:money-test]


def test_a_write_that_does_not_parse_is_refused():
    assert "does not parse" in money_check(
        {"path": "invoices/totals.py", "content": "def f(:\n"})


# --8<-- [start:sweep-test]
def test_the_reply_check_over_chapter_11s_desk_replies():
    replies = reply_sweep.sweep()
    refused = [r for r in replies if r["problems"]]
    assert (len(replies), len(refused)) == (140, 4)
    assert all(r["task"] == "a part refund"
               and r["verdict"] == "right"
               and r["problems"] == ["No tool returned $83.50."]
               for r in refused)
# --8<-- [end:sweep-test]


@pytest.mark.skipif(not experiment.RESULTS.exists(),
                    reason="not recorded yet")
def test_replay_reproduces_the_recorded_runs():
    recorded = json.loads(experiment.RESULTS.read_text(encoding="utf-8"))
    outcomes = experiment.run()
    assert json.loads(json.dumps(outcomes)) == recorded["outcomes"]
    summary = json.loads(experiment.SUMMARY.read_text(encoding="utf-8"))
    assert summary == experiment.summary(recorded["outcomes"])
