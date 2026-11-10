"""Chapter 10: the promise check, on recorded replies and offline."""

import pytest
from done import Refused
from promise_case import (
    promises,
    promises_by_arm,
    strict_gate,
    sweep_chapter_5,
)
from refund_case import LockedDesk


@pytest.mark.parametrize("message, offered", [
    ("Contact us and we'll refund the $92.00 right away.", True),
    ("If you close the dispute, we can refund the extra charge.", True),
    ("Once it is withdrawn, the $92.00 can be refunded.", True),
    ("It must be closed before we can issue the $92.00 refund.", True),
    ("We can't refund it right now.", False),
    ("We couldn't refund INV-2207 because a dispute is open.", False),
    ("No refund has been issued.", False),
])
def test_promises_in_a_message(message, offered):
    assert promises(message) is offered


# --8<-- [start:promise-test]
def test_a_refund_offered_for_later_is_refused():
    gate, _ = strict_gate(LockedDesk())
    with pytest.raises(Refused, match="offers a refund later"):
        gate.report_done(
            status="not_done", receipts=[],
            message="Close the dispute and we'll refund the $92.00.")
    gate.report_done(
        status="not_done", receipts=[],
        message="I could not refund this: a bank dispute is open.")
    assert gate.accepted is not None
# --8<-- [end:promise-test]


def test_the_receipt_check_catches_every_false_handoff_of_chapter_5():
    assert sweep_chapter_5() == {
        "runs": 5, "no_refund": 5, "would_refuse": 5}


def test_the_recorded_replies_offer_refunds_in_these_arms():
    assert promises_by_arm() == {
        "plain": 5, "told": 1, "gated": 5, "gated, ticket tool": 0}
