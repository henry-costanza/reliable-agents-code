"""Chapter 10: replay the follow-up, and pin what it found."""

import json

import followup_experiment as experiment
import summary
from promise_case import promises

from agentkit.cassette import ReplayProvider


def recorded() -> list[dict]:
    text = experiment.RESULTS.read_text(encoding="utf-8")
    return json.loads(text)["outcomes"]


def test_replay_reproduces_the_followup():
    provider = ReplayProvider(experiment.CASSETTE)
    outcomes = json.loads(json.dumps(experiment.run(provider)))
    assert provider.unused == 0
    assert outcomes == recorded()


# --8<-- [start:corrected-test]
def test_refused_agents_corrected_their_reply_on_the_first_retry():
    runs = [o for o in recorded() if o["case"] == "promise"]
    refused = [o for o in runs if o["refusals"]]
    assert len(runs) == 5 and len(refused) == 4
    for run in refused:
        first, last = run["drafts"][0], run["drafts"][-1]
        assert promises(first) and not promises(last)
        assert len(run["drafts"]) == 2 and run["accepted"]
# --8<-- [end:corrected-test]


def test_one_offer_got_past_the_pattern():
    runs = [o for o in recorded() if o["case"] == "promise"]
    passed = [o for o in runs if not o["refusals"]]
    assert len(passed) == 1
    assert "refunded by us if you close it" in passed[0]["message"]
    assert not promises(passed[0]["message"])


def test_the_figure_reads_the_recordings():
    text = summary.TARGET.read_text(encoding="utf-8")
    assert json.loads(text)["rows"] == summary.build()


def test_the_numbered_log_without_citations():
    runs = [o for o in recorded() if o["case"] == "numbered count"]
    assert [o["answer"] for o in runs] == ["58", "59", "59"]
    assert {o["truth"] for o in runs} == {59}
