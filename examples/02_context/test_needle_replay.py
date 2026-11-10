"""Chapter 2: the recorded measurement replays offline and matches its results.

The cassette holds the model's answers from one live run. Replaying it
rebuilds every document from its seed, checks each request against the
recorded fingerprint, and must reproduce the committed results file exactly,
so the numbers in the chapter and in its figure cannot drift from the run.
"""

import json
from dataclasses import asdict

from needle_experiment import CASSETTE, LENGTHS, POSITIONS, RESULTS, TRIALS, run, summarize

from agentkit.cassette import ReplayProvider


def test_grid_is_sixty_requests():
    assert len(LENGTHS) * 2 * len(POSITIONS) * TRIALS == 60


def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(CASSETTE)
    outcomes = run(provider)
    assert provider.unused == 0
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert [asdict(o) for o in outcomes] == recorded["outcomes"]
    assert summarize(outcomes) == recorded["rows"]
