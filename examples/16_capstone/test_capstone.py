"""Chapter 16: Brindle's desk 1.0 and its release gate, offline."""

import json

import release_experiment as experiment
from brindle_desk import current_help_center, desk
from release_gate import TASKS, gate, released
from retrieval import SECTION_INDEX
from traces import Trace

from agentkit import ScriptedProvider
from agentkit.messages import Message, Response, StopReason, Text, Usage


# --8<-- [start:search-test]
def test_the_search_missed_what_the_help_center_holds():
    query = "close account invoice retention"  # sent in chapter 15
    labels = [c.label for c in SECTION_INDEX.hits(query, 3)]
    assert not any("What we keep" in label for label in labels)
    assert "## What we keep" in current_help_center()
    assert "We keep copies of the invoices" in current_help_center()
# --8<-- [end:search-test]


def test_retired_articles_never_reach_the_model():
    assert "HC-090" not in current_help_center()
    assert "ARCHIVED" not in current_help_center()


def test_desk_1_has_no_search_and_cannot_refund():
    provider = ScriptedProvider([Response(
        Message("assistant", (Text("Done."),)), StopReason.END_TURN,
        Usage(10, 10))])
    outcome = desk(provider, "CUS-104", "Hello")
    request = provider.requests[0]
    names = {tool.name for tool in request.tools}
    assert "search_help_center" not in names
    assert "refund_invoice" not in names and "request_refund" in names
    assert "## What we keep" in request.system
    assert outcome.case.fallback  # no reply sent: a person takes over


def fake(task: str, right: bool, trial: int) -> dict:
    trace = Trace(f"Haiku 5.5 | desk 1.0 | {task} | {trial}", "fake",
                  "CUS-104", [{"input": 0, "cache_read": 1800,
                               "cache_write": 100, "output": 200}],
                  [], 0, False, 0.0006)
    return {"task": task, "trial": trial, "failures": {},
            "verdict": "right" if right else "wrong",
            "trace": trace.line()}


# --8<-- [start:gate-test]
def test_the_gate_blocks_only_what_chance_cannot_explain():
    def run(planted: int) -> list[dict]:  # right runs of the note
        return [fake(task, task != "a planted note" or n < planted, n)
                for task in TASKS for n in range(5)]
    blocked = gate("Haiku 5.5", run(planted=0))
    assert blocked["block"] == ["a planted note"]
    looked = gate("Haiku 5.5", run(planted=3))
    assert looked["block"] == []
    assert "a planted note" in looked["read"]
    assert "days and closing" in looked["better"]
# --8<-- [end:gate-test]


def test_the_released_scores_are_the_books():
    scores, traces = released("Haiku 5.5")
    assert scores["days and closing"] == (1, 5)
    assert scores["a planted note"] == (5, 5)
    assert len(scores) == 9 and len(traces) == 20 + 25


def test_replay_reproduces_the_recorded_release():
    recorded = json.loads(experiment.SUMMARY.read_text(encoding="utf-8"))
    assert experiment.summary(experiment.run()) == recorded
