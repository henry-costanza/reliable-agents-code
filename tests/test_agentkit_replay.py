"""Layer 3: real recorded model responses, replayed offline.

Replay is the default and needs no API key. To re-record (spends money, needs
ANTHROPIC_API_KEY in .env), on purpose and in a reviewed commit:

    AGENTKIT_MODE=record uv run pytest tests/test_agentkit_replay.py
"""

from pathlib import Path

import pytest

from agentkit import GoldenTask, Tool, contains, exact, finished, open_provider, run_agent, run_eval
from agentkit.cassette import ReplayProvider

CASSETTES = Path(__file__).resolve().parent.parent / "fixtures" / "cassettes"

INTEGER_PAIR = {
    "type": "object",
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "required": ["a", "b"],
    "additionalProperties": False,
}
ADD = Tool("add", "Return a + b.", INTEGER_PAIR, lambda a, b: a + b)
MULTIPLY = Tool("multiply", "Return a * b.", INTEGER_PAIR, lambda a, b: a * b)
CALCULATOR = (
    "You are a careful calculator. Use the provided tools for every arithmetic step. "
    "Never do arithmetic yourself."
)
ARITHMETIC = "Compute (17 + 25) * 3. Reply with just the number."


@pytest.fixture
def provider(request):
    provider = open_provider(CASSETTES / f"{request.param}.json")
    yield provider
    if isinstance(provider, ReplayProvider):
        assert provider.unused == 0, f"{provider.path.name}: recorded calls were not replayed"


@pytest.mark.parametrize("provider", ["agent_loop_arithmetic"], indirect=True)
def test_agent_uses_tools_to_reach_the_answer(provider):
    result = run_agent(provider, ARITHMETIC, system=CALCULATOR, tools=[ADD, MULTIPLY])
    assert result.ok, result.stop_reason
    assert "126" in result.final_text
    assert {"add", "multiply"} <= set(result.tool_calls)
    assert result.usage.input_tokens > 0 and result.usage.output_tokens > 0


TASKS = [
    GoldenTask("pong", "Reply with exactly the word PONG and nothing else.", finished(exact("PONG"))),
    GoldenTask("capital", "What is the capital of France? Answer in one word.", finished(contains("Paris"))),
    GoldenTask(
        "arithmetic", ARITHMETIC, finished(contains("126")), system=CALCULATOR, tools=(ADD, MULTIPLY)
    ),
]


@pytest.mark.parametrize("provider", ["eval_smoke"], indirect=True)
def test_smoke_eval_passes_its_threshold(provider):
    report = run_eval(provider, TASKS)
    assert report.pass_rate >= 2 / 3, report.failing
