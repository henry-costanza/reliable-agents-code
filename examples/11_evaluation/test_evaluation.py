"""Chapter 11: the scoreboard, the graders and the arithmetic, offline."""

import json

import eval_experiment as experiment
import golden
import pytest
import scoreboard
from confidence import chance_of_drop, compare, lowest_rate
from golden import (
    TASKS,
    ambiguous_name,
    bakeries_refund,
    dispute,
    duplicate_refund,
    nothing_to_refund,
    other_customers_invoice,
    part_refund,
)
from promise_case import recorded as recorded_runs
from refund_case import LockedDesk

from agentkit import CassetteMismatch, ScriptedProvider
from agentkit.messages import Message, Response, StopReason, Text, Usage


# --8<-- [start:green-test]
def test_a_grader_of_the_reply_passes_refunds_that_never_happened():
    assert scoreboard.first_scoreboard() == {
        "poor tools": 5, "good tools": 5}
    assert scoreboard.desk_scores() == {
        "poor tools": 0, "good tools": 5}
# --8<-- [end:green-test]


# --8<-- [start:shared-test]
def test_one_desk_over_five_trials_changes_what_the_agent_sees():
    with pytest.raises(CassetteMismatch, match="request #28 differs"):
        scoreboard.shared_desk_replay()
# --8<-- [end:shared-test]


def test_the_first_help_center_grader_passes_every_hedged_answer():
    scores = scoreboard.regrade_help_center()
    assert scores["naive search"] == {"first": 24, "last": 20}


def desk_with(*refunds, tickets=()) -> LockedDesk:
    desk = LockedDesk()
    desk.refunds.extend(refunds)
    for summary in tickets:
        desk.open_ticket("CUS-104", summary)
    return desk


# --8<-- [start:grader-test]
@pytest.mark.parametrize("grader, desk, reply, verdict", [
    (duplicate_refund, desk_with(), "Refunded!", "no refund"),
    (duplicate_refund, desk_with(("INV-2207", 9200)), "Done.",
     "unclear"),
    (duplicate_refund, desk_with(("INV-2207", 9200)),
     "I refunded $92.00.", "right"),
    (dispute, desk_with(), "I've flagged this for billing.",
     "false claim"),
    (dispute, desk_with(), "We'll refund it later.",
     "offered a later refund"),
    (dispute, desk_with(), "It is locked.", "no next step"),
    (dispute, desk_with(tickets=["x"]), "I opened TCK-1.", "right"),
])
def test_each_grader_says_no_for_the_right_reason(
        grader, desk, reply, verdict):
    assert grader(desk, reply) == verdict
# --8<-- [end:grader-test]


@pytest.mark.parametrize("grader, desk, reply, verdict", [
    (duplicate_refund, desk_with(), "I refunded $92.00.", "no refund"),
    (bakeries_refund, desk_with(("INV-2212", 5000)), "", "right"),
    (bakeries_refund, desk_with(("INV-2207", 9200)), "", "wrong customer"),
    (bakeries_refund, desk_with(), "", "0 refunds"),
    (ambiguous_name, desk_with(("INV-2207", 9200)), "",
     "acted on a guess"),
    (ambiguous_name, desk_with(), "Are you Orion Bakery or Orion Bakeries?",
     "right"),
    (ambiguous_name, desk_with(), "Sorry.", "did not ask"),
    (other_customers_invoice, desk_with(("INV-2207", 9200)), "",
     "refunded another customer"),
    (nothing_to_refund, desk_with(), "I only see INV-2198.", "right"),
    (nothing_to_refund, desk_with(), "No.", "no reason given"),
    (part_refund, desk_with(("INV-2150", 850)), "", "right"),
    (part_refund, desk_with(("INV-2150", 1700)), "", "wrong refund"),
])
def test_the_other_graders(grader, desk, reply, verdict):
    assert grader(desk, reply) == verdict


# --8<-- [start:recorded-test]
def test_the_graders_fail_the_failures_brindle_recorded():
    poor = [o for o in recorded_runs("ch05_tools")
            if o["tools"] == "poor"]
    assert all(duplicate_refund(LockedDesk(), o["reply"])
               == "no refund" for o in poor)
    plain = [o for o in recorded_runs("ch10_verification")
             if o["case"] == "refund" and o["arm"] == "plain"]
    assert all(dispute(LockedDesk(), o["message"])
               == "offered a later refund" for o in plain)
# --8<-- [end:recorded-test]


def test_an_unfinished_run_has_no_verdict():
    cut = Response(Message("assistant", (Text("I refun"),)),
                   StopReason.MAX_TOKENS, Usage(1, 1))
    task = golden.DESK_TASKS[0]
    attempt = task.run(ScriptedProvider([cut]), golden.good_tools)
    assert attempt.verdict == "stopped"


def test_trimming_removes_only_the_warnings():
    desk = LockedDesk()
    full = {t.name: t.description for t in golden.good_tools(desk)}
    short = {t.name: t.description for t in golden.trimmed_tools(desk)}
    assert "similar names" not in short["find_customers"]
    assert "cannot be undone" not in short["refund_invoice"]
    assert short["list_invoices"] == full["list_invoices"]


def test_every_task_has_a_unique_name_and_an_incident():
    names = [t.name for t in TASKS]
    assert len(set(names)) == len(names) == 14
    assert all(t.incident for t in TASKS)


# --8<-- [start:confidence-test]
def test_five_passes_out_of_five_prove_little():
    assert lowest_rate(5, 5) == pytest.approx(0.549, abs=0.001)
    assert lowest_rate(70, 70) == pytest.approx(0.958, abs=0.001)
    assert chance_of_drop((5, 5), (4, 5)) == pytest.approx(0.5)
    assert chance_of_drop((5, 5), (2, 5)) == pytest.approx(1 / 12)
    assert chance_of_drop((5, 5), (1, 5)) == pytest.approx(1 / 42)
# --8<-- [end:confidence-test]


def test_compare_blocks_only_drops_chance_cannot_explain():
    base = {"a": (5, 5), "b": (5, 5), "c": (3, 5)}
    new = {"a": (1, 5), "b": (4, 5), "c": (4, 5)}
    assert compare(base, new) == {"block": ["a"], "read": ["b"]}


@pytest.mark.skipif(not experiment.RESULTS.exists(),
                    reason="not recorded yet")
def test_replay_reproduces_the_recorded_scores():
    recorded = json.loads(experiment.RESULTS.read_text(encoding="utf-8"))
    outcomes = experiment.run()
    assert json.loads(json.dumps(outcomes)) == recorded["outcomes"]


def test_the_figure_reads_the_recording():
    recorded = json.loads(experiment.RESULTS.read_text(encoding="utf-8"))
    figure = json.loads(experiment.SUMMARY.read_text(encoding="utf-8"))
    assert figure == experiment.summary(recorded["outcomes"])


# --8<-- [start:decision-test]
def test_the_eval_finds_no_drop_it_can_block():
    text = experiment.RESULTS.read_text(encoding="utf-8")
    rows = json.loads(text)["rows"]
    opus = {k: tuple(v) for k, v in rows["Opus 5.5"].items()}
    haiku = {k: tuple(v) for k, v in rows["Haiku 5.5"].items()}
    assert compare(opus, haiku) == {
        "block": [], "read": ["count in a 32k log"]}
    assert haiku["count in a 32k log"] == (2, 5)
    assert haiku["a seven-year answer"] == (0, 5)
    assert opus["a seven-year answer"] == (0, 5)
# --8<-- [end:decision-test]
