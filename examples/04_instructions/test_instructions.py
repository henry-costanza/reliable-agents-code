"""Chapter 4: the project, its tools and the rule checks offline; the recorded
runs replayed."""

import json

import pytest
from checks import check
from instructions import BASE, SPECIFIC, VAGUE, system_prompt
from instructions_experiment import CASSETTE, RESULTS, TRIALS, run, summarize
from mini_repo import FILES, TASKS, workspace_tools

from agentkit import ToolUse
from agentkit.cassette import ReplayProvider

GOOD = {
    **FILES,
    "invoices/totals.py": FILES["invoices/totals.py"] + (
        "\n\ndef total_due(invoice):\n"
        "    return subtotal_cents(invoice) - invoice.paid_cents\n"),
    "tests/unit/test_totals.py": "def test_total_due_after_payment():\n    pass\n",
    "CHANGELOG.md": FILES["CHANGELOG.md"].replace(
        "## Unreleased\n", "## Unreleased\n\n- total_due: amount still to pay.\n"),
}


def test_untouched_project_follows_no_rule():
    assert check(dict(FILES), "total_due") == dict.fromkeys(
        ["function added", "integer money", "test in place", "changelog entry"], False)


def test_a_complete_change_follows_every_rule():
    assert all(check(GOOD, "total_due").values())


@pytest.mark.parametrize(
    ("change", "broken"),
    [
        ({"invoices/totals.py": GOOD["invoices/totals.py"].replace(
            "- invoice.paid_cents", "- invoice.paid_cents / 1")}, "integer money"),
        ({"invoices/totals.py": GOOD["invoices/totals.py"].replace(
            "    return subtotal_cents(invoice) - invoice.paid_cents",
            "    return float(subtotal_cents(invoice) - invoice.paid_cents)")},
         "integer money"),
        ({"tests/unit/test_totals.py": "", "tests/test_totals.py":
          GOOD["tests/unit/test_totals.py"]}, "test in place"),
        ({"CHANGELOG.md": GOOD["CHANGELOG.md"].replace(
            "- total_due:", "- Added total_due")}, "changelog entry"),
        ({"CHANGELOG.md": FILES["CHANGELOG.md"] + "\n- total_due: late entry.\n"},
         "changelog entry"),
    ],
)
def test_each_rule_catches_its_mistake(change, broken):
    result = check({**GOOD, **change}, "total_due")
    assert result[broken] is False
    assert all(v for k, v in result.items() if k != broken)


def test_tools_read_and_write_the_in_memory_project():
    files = dict(FILES)
    tools = {t.name: t for t in workspace_tools(files)}
    listing = tools["list_files"].run(ToolUse("1", "list_files", {}))
    assert "invoices/totals.py" in listing.content
    tools["write_file"].run(ToolUse("2", "write_file", {"path": "x.py", "content": "a"}))
    assert files["x.py"] == "a" and "x.py" not in FILES
    missing = tools["read_file"].run(ToolUse("3", "read_file", {"path": "nope.py"}))
    assert missing.is_error


def test_system_prompt_appends_the_instructions():
    assert system_prompt(None) == BASE
    assert system_prompt(SPECIFIC).endswith(SPECIFIC)
    assert "rounds down" in SPECIFIC and "rounds down" not in VAGUE


def test_grid_is_eighteen_runs():
    assert len(TASKS) * 3 * TRIALS == 18


def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(CASSETTE)
    outcomes = run(provider)
    assert provider.unused == 0
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert outcomes == recorded["outcomes"]
    assert summarize(outcomes) == recorded["rows"]
