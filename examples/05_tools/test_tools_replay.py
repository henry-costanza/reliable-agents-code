"""Chapter 5: the recorded runs replay offline, locally and over MCP."""

import json

from mcp_desk import connect, serve
from tools_experiment import CASSETTE, RESULTS, run, summarize

from agentkit.cassette import ReplayProvider


def recorded() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(CASSETTE)
    outcomes = json.loads(json.dumps(run(provider)))
    assert provider.unused == 0
    assert outcomes == recorded()["outcomes"]
    assert summarize(outcomes) == recorded()["rows"]


# --8<-- [start:replay-mcp]
def over_mcp(tools):
    return connect(serve("brindle-desk", tools))


def test_the_same_recording_replays_over_mcp():
    provider = ReplayProvider(CASSETTE)
    outcomes = json.loads(json.dumps(run(provider, connect=over_mcp)))
    assert provider.unused == 0
    assert outcomes == recorded()["outcomes"]
# --8<-- [end:replay-mcp]
