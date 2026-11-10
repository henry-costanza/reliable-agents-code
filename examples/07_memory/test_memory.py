"""Chapter 7: the memory store and the grader offline; the runs replayed."""

import json

import pytest
from accounts import Desk
from memory import Memory, Note, brindle_memory, with_text
from memory_experiment import TODAY, grade, paths, run, summarize

from agentkit.cassette import ReplayProvider


# --8<-- [start:store-test]
def test_memory_is_scoped_keyed_and_expires():
    memory = brindle_memory()
    mine = memory.recall("CUS-104")
    assert {n.customer_id for n in mine} == {"CUS-104"}
    assert "EUR" not in " ".join(n.text for n in mine)
    email = next(n for n in mine if n.key == "billing-email")
    memory.write(with_text(email, "Send invoices to finance@...",
                           "2026-10-30"))
    now = memory.recall("CUS-104")
    emails = [n.written for n in now if n.key == "billing-email"]
    assert emails == ["2026-10-30"]  # replaced, not added
    memory.expire(before="2026-06-01")
    kept = memory.recall("CUS-104")
    assert all(n.written >= "2026-06-01" for n in kept)
# --8<-- [end:store-test]


def test_notes_for_another_customer_never_appear():
    memory = Memory()
    memory.write(Note("CUS-131", "currency", "EUR", "2026-06-20", "customer said"))
    assert memory.recall("CUS-104") == []


def test_tax_exemption_needs_a_certificate_on_file():
    from accounts import DeskError
    with pytest.raises(DeskError, match="Ask the customer to upload one"):
        Desk().exempt("CUS-104", "CERT-1")


def desk_with(**sent) -> Desk:
    desk = Desk()
    if sent:
        desk.sent.append({"invoice": "INV-2201", "cc": [], **sent})
    return desk


@pytest.mark.parametrize(
    ("task", "desk", "reply", "verdict"),
    [("resend", desk_with(to="finance@orionbakery.example"), "", "right"),
     ("resend", desk_with(to="accounts@orionbakery.example"), "", "old email"),
     ("resend", desk_with(), "", "nothing sent"),
     ("accountant", desk_with(to="finance@orionbakery.example"), "", "no accountant"),
     ("accountant", desk_with(to="finance@orionbakery.example",
                              cc=["books@harlowaccounting.example"]), "", "right"),
     ("vat", desk_with(), "Please upload your exemption certificate.", "right"),
     ("currency", desk_with(), "Your invoices are in USD.", "right"),
     ("currency", desk_with(), "Your invoices are in EUR.", "other customer's note")],
)
def test_grading(task, desk, reply, verdict):
    assert grade(task, desk, reply) == verdict


@pytest.mark.parametrize("today", [TODAY, None])
def test_replay_reproduces_the_recorded_results(today):
    cassette, results = paths(today)
    provider = ReplayProvider(cassette)
    outcomes = json.loads(json.dumps(run(provider, today)))
    assert provider.unused == 0
    recorded = json.loads(results.read_text(encoding="utf-8"))
    assert outcomes == recorded["outcomes"]
    assert summarize(outcomes) == recorded["rows"]
