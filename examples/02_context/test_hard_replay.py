"""Chapter 2: the harder tasks replay offline and match their results file."""

import json
from dataclasses import asdict

from hard_experiment import (
    CASSETTE,
    COUNT_LENGTHS,
    PARAPHRASE_LENGTHS,
    PARAPHRASE_POSITIONS,
    RESULTS,
    TRIALS,
    run,
    summarize,
)

from agentkit.cassette import ReplayProvider


def test_grid_is_twenty_seven_requests():
    assert (len(PARAPHRASE_LENGTHS) * len(PARAPHRASE_POSITIONS) + len(COUNT_LENGTHS)) * TRIALS == 27


def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(CASSETTE)
    outcomes = run(provider)
    assert provider.unused == 0
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert [asdict(o) for o in outcomes] == recorded["outcomes"]
    assert summarize(outcomes) == recorded["rows"]
