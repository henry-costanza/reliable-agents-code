"""Chapter 9: the tracer, the detectors and the checked note, offline."""

import json

import notes_experiment as notes
import pytest
from book_runs import replay_book
from catalog import CATALOG, scan
from catalog_sweep import RESULTS, sweep, table
from checked_notes import NOTE_IDS, Truncated, finished
from session import Session
from tracing import Tracer, conversations

from agentkit import ScriptedProvider, run_agent
from agentkit.cassette import ReplayProvider
from agentkit.messages import (Message, Request, Response, StopReason, Text,
                               ToolUse, Usage)


def reply(text: str, stop: StopReason = StopReason.END_TURN) -> Response:
    return Response(Message("assistant", (Text(text),)), stop, Usage(10, 10))


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{name}_{len(arguments)}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE)


def traced(responses, tools=(), task="Help me.") -> list:
    tracer = Tracer(ScriptedProvider(responses))
    run_agent(tracer, task, tools=list(tools))
    return conversations(tracer.calls)


def test_one_agent_run_is_one_conversation():
    tracer = Tracer(ScriptedProvider([call("look"), reply("Done."),
                                      reply("A summary.")]))
    run_agent(tracer, "Help me.", tools=[])
    tracer.complete(Request((Message.user("Summarize this."),), "S"))
    found = conversations(tracer.calls)
    assert [len(c.calls) for c in found] == [2, 1]


# --8<-- [start:detector-tests]
def test_detectors_read_the_trace():
    cut = traced([reply("| INV-3013 | $5", StopReason.MAX_TOKENS)])
    assert scan(cut[0]) == {
        "stopped": "last reply stopped with max_tokens"}
    claim = traced([reply("I've flagged this for our billing team.")])
    assert "unbacked" in scan(claim[0])
    honest = traced([reply("I haven't sent anything yet.")])
    assert scan(honest[0]) == {}
# --8<-- [end:detector-tests]


def test_repeated_calls_and_errors():
    from agentkit import Tool
    refuse = Tool("refund", "Refund.", {"type": "object"},
                  lambda **_: (_ for _ in ()).throw(ValueError("bad request")))
    found = traced([call("refund", id="INV-2207"), call("refund", id="INV-2207"),
                    reply("It failed.")], tools=[refuse])
    assert set(scan(found[0])) == {"gave-up", "repeated"}


def test_every_failure_has_a_check_and_five_need_the_record():
    assert len(CATALOG) == 10 and len({f.id for f in CATALOG}) == 10
    assert all(f.check for f in CATALOG)
    assert sum(f.detect is None for f in CATALOG) == 5


# --8<-- [start:finished-test]
def test_a_cut_off_note_is_retried_then_refused():
    provider = ScriptedProvider([
        reply("Customer instructions ...", StopReason.MAX_TOKENS),
        reply("Customer instructions ... (complete)")])
    session = Session(provider, "S", [])
    note = Message.user("Write the note.")
    request = Request((note,), max_tokens=2000)
    text = finished(session, request, "compact")
    assert text.endswith("(complete)")
    sizes = [r.max_tokens for r in provider.requests]
    assert sizes == [2000, 4000]
    cut = reply("Customer ...", StopReason.MAX_TOKENS)
    session = Session(ScriptedProvider([cut, cut]), "S", [])
    with pytest.raises(Truncated):
        finished(session, request, "compact")
# --8<-- [end:finished-test]


def test_the_note_asks_for_ids_not_tables():
    assert "Do not copy tables" in NOTE_IDS
    assert NOTE_IDS.endswith("Reply with the note only.")


# --8<-- [start:sweep-test]
def test_the_sweep_finds_the_cut_off_notes_of_chapter_8():
    recordings = replay_book()
    findings = sweep(recordings)
    cut = [f for f in findings if f["chapter"] == 8]
    assert len(cut) == 14
    assert {f["failure"] for f in cut} == {"stopped"}
    assert {f["evidence"] for f in cut} == {
        "last reply stopped with max_tokens"}
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert findings == recorded["findings"]
    assert table(recordings, findings) == recorded["rows"]
# --8<-- [end:sweep-test]


@pytest.mark.skipif(not notes.CASSETTE.exists(), reason="not recorded yet")
def test_replay_reproduces_the_checked_notes_runs():
    provider = ReplayProvider(notes.CASSETTE)
    outcomes = json.loads(json.dumps(notes.run(provider)))
    assert provider.unused == 0
    recorded = json.loads(notes.RESULTS.read_text(encoding="utf-8"))
    assert outcomes == recorded["outcomes"]
    assert notes.summarize_runs(outcomes) == recorded["rows"]
