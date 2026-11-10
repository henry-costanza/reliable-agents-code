"""Chapter 3: logs, tools and cost attribution offline; the recorded runs replayed."""

import json

import pytest
from budget_experiment import AGENTS, RESULTS, picked, run
from cost_report import attribute
from log_agent import ask, count_tool, read_log_tool
from team_logs import LOGS, build_log, mentions, truth

from agentkit import OPUS_5_5, Budget, RunResult, StopReason, ToolUse, Usage
from agentkit.cassette import ReplayProvider


def test_logs_are_deterministic_and_long():
    assert build_log("billing") == build_log("billing")
    assert all(128_000 <= len(build_log(t)) <= 128_200 for t in LOGS)


def test_sales_mentions_atlas_dental_most():
    assert {t: mentions(t) for t in LOGS} == {"billing": 291, "support": 285, "sales": 312}
    assert truth() == "sales"


def test_read_log_returns_the_whole_log_and_count_returns_a_number():
    whole = read_log_tool().run(ToolUse("t1", "read_log", {"name": "support"}))
    assert whole.content == build_log("support")
    count = count_tool().run(ToolUse("t2", "count_in_log", {"name": "support", "phrase": "atlas dental"}))
    assert count.content == "285"


def test_unknown_log_is_refused():
    result = read_log_tool().run(ToolUse("t1", "read_log", {"name": "payroll"}))
    assert result.is_error and "is not one of" in result.content


# --8<-- [start:attribute-test]
def test_attribution_splits_carried_from_added_tokens():
    usage = (Usage(1_000, 100), Usage(40_000, 200), Usage(41_000, 50))
    result = RunResult((), StopReason.END_TURN, 3, sum(usage, Usage()),
                       step_usage=usage)
    rows = attribute(result)
    assert [(r["carried"], r["added"]) for r in rows] == [
        (0, 1_000), (1_100, 38_900), (40_200, 800)]
    assert rows[1]["cost"] == pytest.approx(0.164)  # $4/M in, $20/M out
# --8<-- [end:attribute-test]


@pytest.mark.parametrize("agent", list(AGENTS))
def test_replay_reproduces_the_recorded_results(agent):
    provider = ReplayProvider(AGENTS[agent][1])
    replayed = run(agent, provider)
    assert provider.unused == 0
    assert replayed == json.loads(RESULTS.read_text(encoding="utf-8"))["agents"][agent]


# --8<-- [start:budget-test]
def test_a_budget_flags_the_whole_log_agent_but_cannot_undo_it():
    provider = ReplayProvider(AGENTS["whole logs"][1])
    budget = Budget(max_cost=0.25, prices=OPUS_5_5)
    result = ask(provider, read_log_tool(), budget=budget)
    assert result.hit_budget and not result.ok
    assert budget.exceeded(result.usage)  # says why, in words
    # One step read all three logs: the money went before any check.
    assert OPUS_5_5.cost(result.step_usage[-1]) > budget.max_cost
# --8<-- [end:budget-test]


# --8<-- [start:fix-test]
def test_the_count_agent_fits_a_budget_ten_times_smaller():
    provider = ReplayProvider(AGENTS["counts"][1])
    budget = Budget(max_cost=0.025, prices=OPUS_5_5)
    result = ask(provider, count_tool(), budget=budget)
    assert result.ok and picked(result.final_text) == truth()
# --8<-- [end:fix-test]


@pytest.mark.parametrize(
    ("answer", "log"),
    [("billing", "billing"), ("**billing**\n\nI estimated...", "billing"),
     ("Sales, not billing", "sales"), ("I cannot tell.", None)],
)
def test_picked_reads_the_first_log_named(answer, log):
    assert picked(answer) == log
