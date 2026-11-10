"""Chapter 5: the desk, both tool sets and the grader, offline."""

import pytest
from desk import DUPLICATE_CENTS, Desk, grade, total_cents
from desk_tools import good_tools, poor_tools

from agentkit import ToolUse


def run(tools, name, **arguments):
    tool = {t.name: t for t in tools}[name]
    return tool.run(ToolUse("t1", name, arguments))


def test_orion_bakery_was_charged_twice_in_october():
    october = Desk().invoices("CUS-104", "2026-10")
    assert [i["invoice_id"] for i in october] == ["INV-2201", "INV-2207"]
    assert total_cents("INV-2201") == total_cents("INV-2207") == DUPLICATE_CENTS


def test_a_similar_name_matches_two_customers():
    assert [c["name"] for c in Desk().customers("orion")] == ["Orion Bakery", "Orion Bakeries"]


@pytest.mark.parametrize(
    ("refunds", "verdict"),
    [([], "no refund"),
     ([("INV-2207", 9200)], "right"),
     ([("INV-2201", 9200)], "right"),
     ([("INV-2212", 5000)], "wrong customer"),
     ([("INV-2201", 9200), ("INV-2207", 9200)], "refunded twice"),
     ([("INV-2150", 9200)], "wrong invoice"),
     ([("INV-2207", 92)], "wrong amount")],
)
def test_grading(refunds, verdict):
    assert grade(refunds) == verdict


# --8<-- [start:error-test]
def test_good_errors_say_what_to_do_poor_ones_do_not():
    good = run(good_tools(Desk()), "refund_invoice",
               invoice_id="INV-2207", amount_cents=920_000)
    assert good.is_error
    assert "9200 cents left to refund" in good.content
    poor = run(poor_tools(Desk()), "refund",
               id="INV-2207", amount=9200)
    assert poor.is_error
    assert poor.content == "DeskError: bad request"
# --8<-- [end:error-test]


def test_poor_refund_takes_dollars_and_good_refund_takes_cents():
    poor_desk, good_desk = Desk(), Desk()
    run(poor_tools(poor_desk), "refund", id="INV-2207", amount=92)
    run(good_tools(good_desk), "refund_invoice", invoice_id="INV-2207", amount_cents=9200)
    assert poor_desk.refunds == good_desk.refunds == [("INV-2207", 9200)]


def test_a_charge_cannot_be_refunded_twice():
    desk = Desk()
    tools = good_tools(desk)
    run(tools, "refund_invoice", invoice_id="INV-2207", amount_cents=9200)
    again = run(tools, "refund_invoice", invoice_id="INV-2207", amount_cents=9200)
    assert again.is_error and "0 cents left" in again.content
    assert desk.refunds == [("INV-2207", 9200)]


def test_schemas_reject_a_bad_month_before_the_desk_sees_it():
    result = run(good_tools(Desk()), "list_invoices", customer_id="CUS-104", month="October")
    assert result.is_error and result.content.startswith("invalid input: month")
