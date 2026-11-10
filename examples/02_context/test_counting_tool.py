"""Chapter 2's fix: the agent counts with a tool and gets the exact answer."""

import json

from counting_tool import CASSETTE, RESULTS, TRIALS, ask_with_tool, counting_tool, run
from haystack import build_haystack, count_truth, grade_count
from needle_experiment import LENGTHS

from agentkit import ToolUse
from agentkit.cassette import ReplayProvider

DOCUMENT = build_haystack(LENGTHS["128k"], 0.5, False)


def test_tool_counts_exactly_and_ignores_case():
    tool = counting_tool("The security team audited. the SECURITY team audited.")
    result = tool.run(ToolUse("t1", "count_matches", {"phrase": "security team audited"}))
    assert result.content == "2" and not result.is_error


def test_tool_refuses_a_phrase_too_short_to_mean_anything():
    result = counting_tool(DOCUMENT).run(ToolUse("t1", "count_matches", {"phrase": "a"}))
    assert result.is_error


# --8<-- [start:test]
def test_agent_with_a_tool_counts_the_long_document_right():
    provider = ReplayProvider(CASSETTE)
    truth = count_truth(DOCUMENT)  # 59
    for _ in range(TRIALS):
        result = ask_with_tool(provider, DOCUMENT)
        assert result.ok and "count_matches" in result.tool_calls
        assert grade_count(result.final_text, truth) == "right"
        assert result.usage.input_tokens < 10_000  # not 166,000
    assert provider.unused == 0
# --8<-- [end:test]


def test_results_file_matches_the_replay():
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    replayed = run(ReplayProvider(CASSETTE))
    assert {k: recorded[k] for k in replayed} == replayed
