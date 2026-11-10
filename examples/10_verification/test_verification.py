"""Chapter 10: gates that refuse, offline."""

import json

import pytest
import verification_experiment as experiment
from count_case import citations_hold, count_gate, is_audit, numbered
from done import Gate, Refused
from fix_case import PROJECT, Bench, fix_gate, fixed, run_project_tests
from refund_case import LockedDesk, claims, refund_gate

from agentkit import ScriptedProvider, run_agent
from agentkit.cassette import ReplayProvider
from agentkit.messages import Message, Response, StopReason, Text, ToolUse, Usage


def reply(text: str) -> Response:
    return Response(Message("assistant", (Text(text),)),
                    StopReason.END_TURN, Usage(10, 10))


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{name}_{sorted(arguments)}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE)


# --8<-- [start:gate-test]
def test_a_refused_report_goes_back_and_can_be_corrected():
    gate, finish = refund_gate(LockedDesk())
    false = "I've flagged this for our billing team."
    true = "I could not refund this: a bank dispute is open."
    provider = ScriptedProvider([
        call("report_done", status="not_done", receipts=[],
             message=false),
        call("report_done", status="not_done", receipts=[],
             message=true),
        reply("Finished.")])
    result = run_agent(provider, "Refund me.", tools=[finish])
    assert result.ok and gate.accepted["message"] == true
    assert "claims a ticket" in gate.refusals[0][0]
# --8<-- [end:gate-test]


def test_ending_the_turn_without_a_report_is_not_finished():
    gate, finish = refund_gate(LockedDesk())
    result = run_agent(ScriptedProvider([reply("All done!")]), "Refund me.",
                       tools=[finish])
    assert result.ok and gate.accepted is None


@pytest.mark.parametrize("message, kinds", [
    ("I've flagged this for our billing team.", {"ticket"}),
    ("I'm passing the refund to our billing team.", {"ticket"}),
    ("Your case has been escalated.", {"ticket"}),
    ("Our billing team will review it and contact you.", {"ticket"}),
    ("I have refunded $92.00.", {"refund"}),
    ("I could not refund this. Please call your bank.", set()),
    ("I haven't sent anything yet.", set()),
])
def test_claims_in_a_message(message, kinds):
    assert claims(message) == kinds


def test_a_receipt_must_exist_and_match_the_claim():
    desk = LockedDesk(locked=())
    gate, _ = refund_gate(desk)
    done = "I have refunded $92.00."
    with pytest.raises(Refused, match="no receipt RF-9"):
        gate.report_done(status="done", receipts=["RF-9"], message=done)
    with pytest.raises(Refused, match="needs a refund receipt"):
        gate.report_done(status="done", receipts=[], message="Sorted.")
    receipt = desk.refund("INV-2207", 9200)["receipt"]
    gate.report_done(status="done", receipts=[receipt], message=done)
    assert gate.accepted["receipts"] == ["RF-1"]


def test_the_locked_desk_refuses_and_records_nothing():
    desk = LockedDesk()
    with pytest.raises(Exception, match="locked"):
        desk.refund("INV-2207", 9200)
    assert desk.refunds == [] and desk.receipts == {}


def test_the_project_starts_with_one_failing_test():
    output = run_project_tests(PROJECT)
    assert "FAIL tests/unit/test_totals.py::test_tax_rounds_half_cents_up" in output
    assert "PASS tests/unit/test_model.py::test_invoice_starts_unpaid" in output
    assert not fixed(PROJECT)


NAIVE = PROJECT["invoices/totals.py"].replace(
    "round(subtotal_cents(invoice) * rate_percent / 100)",
    "int(subtotal_cents(invoice) * rate_percent / 100 + 0.5)")
EXACT = PROJECT["invoices/totals.py"].replace(
    "from invoices.model import Invoice",
    "from decimal import ROUND_HALF_UP, Decimal\n\n"
    "from invoices.model import Invoice").replace(
    "round(subtotal_cents(invoice) * rate_percent / 100)",
    "int((Decimal(subtotal_cents(invoice)) * Decimal(str(rate_percent))"
    " / 100).quantize(Decimal(1), ROUND_HALF_UP))")


def test_only_exact_arithmetic_survives_the_tests():
    naive = {**PROJECT, "invoices/totals.py": NAIVE}
    exact = {**PROJECT, "invoices/totals.py": EXACT}
    assert "FAIL" in run_project_tests(naive) and not fixed(naive)
    assert "FAIL" not in run_project_tests(exact) and fixed(exact)


# --8<-- [start:stale-test]
def test_a_test_run_from_before_the_last_edit_is_refused():
    files = {**PROJECT, "invoices/totals.py": EXACT}
    bench = Bench(files)
    gate, _ = fix_gate(bench)
    bench.run_tests()
    files["invoices/totals.py"] = NAIVE
    with pytest.raises(Refused, match="before your last edit"):
        gate.report_done(test_run="RUN-1", message="Fixed.")
    bench.run_tests()
    with pytest.raises(Refused, match="did not pass"):
        gate.report_done(test_run="RUN-2", message="Fixed.")
    files["invoices/totals.py"] = EXACT
    bench.run_tests()
    gate.report_done(test_run="RUN-3", message="Fixed.")
    assert bench.proven()
# --8<-- [end:stale-test]


LOG = ("The security team audited the tax settings. "
       "The billing team moved the invoice template. "
       "The security team audited the dunning emails.")


# --8<-- [start:count-test]
def test_citations_catch_inventions_but_not_omissions():
    gate, _ = count_gate(numbered(LOG))
    with pytest.raises(Refused, match="not in the log"):
        gate.report_done(count=1, entries=["E00099"])
    with pytest.raises(Refused, match="does not say that"):
        gate.report_done(count=1, entries=["E00002"])
    with pytest.raises(Refused, match="counted 2 and cited 1"):
        gate.report_done(count=2, entries=["E00001"])
    gate.report_done(count=1, entries=["E00003"])  # missed E00001
    assert gate.accepted["count"] == 1
# --8<-- [end:count-test]


def test_the_same_check_reads_a_subagents_citations():
    import earlier  # noqa: F401
    from florist_desk import ACTIVITY
    entries = {e["entry"]: f"{e['user']} {e['event']}" for e in ACTIVITY}
    changes = "changed billing_address"
    who = [e for e, text in entries.items() if changes in text]
    check = citations_hold(entries, lambda text: changes in text)
    assert check({"count": len(who), "entries": who}) == []
    assert "LOG-9999 is not in the log." in check(
        {"count": 1, "entries": ["LOG-9999"]})


def test_is_audit_counts_the_audits():
    assert sum(is_audit(s) for s in numbered(LOG).values()) == 2


def test_gate_keeps_every_refusal():
    gate = Gate(lambda claim: ["no"] if claim["n"] < 2 else [])
    for n in (0, 1):
        with pytest.raises(Refused):
            gate.report_done(n=n)
    gate.report_done(n=2)
    assert gate.refusals == [["no"], ["no"]] and gate.accepted == {"n": 2}


@pytest.mark.skipif(not experiment.CASSETTE.exists(), reason="not recorded yet")
def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(experiment.CASSETTE)
    outcomes = json.loads(json.dumps(experiment.run(provider)))
    assert provider.unused == 0
    recorded = json.loads(experiment.RESULTS.read_text(encoding="utf-8"))
    assert outcomes == recorded["outcomes"]
    assert experiment.summarize(outcomes) == recorded["rows"]
