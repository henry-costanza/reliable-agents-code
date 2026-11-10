"""Chapter 8: the compactors and the subagent offline; the runs replayed."""

import json

import pytest
from compaction_experiment import CASSETTE, RESULTS, grade, named_who, run, summarize_runs
from florist_desk import ACTIVITY, Desk, tools
from session import KEEP, Session, drop_old_turns, handoff, log_reader, summarize

from agentkit import ScriptedProvider
from agentkit.cassette import ReplayProvider
from agentkit.messages import Message, Response, StopReason, Text, ToolUse, Usage


def reply(text: str, tokens: int = 100) -> Response:
    return Response(Message("assistant", (Text(text),)), StopReason.END_TURN,
                    Usage(input_tokens=tokens))


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{name}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE,
                    Usage(input_tokens=100))


def three_turns(compactor, *condensed: str) -> tuple[Session, ScriptedProvider]:
    """Turn 2 grows past the limit, so turn 3 starts with compaction."""
    responses = [reply("Noted: no emails until you say so."),
                 reply("Here is the log.", 9000),
                 *[reply(text) for text in condensed], reply("Done.")]
    provider = ScriptedProvider(responses)
    desk = Desk()
    desk.set_po("INV-3108", "PO-77214-W")
    session = Session(provider, "SYSTEM", tools(desk), handoff(desk)
                      if compactor == "handoff" else compactor, limit=5000)
    session.send("Don't email us any invoices until I say so.")
    session.send("Show me the log.")
    session.send("Thanks.")
    return session, provider


def test_drop_old_turns_forgets_the_instruction():
    session, provider = three_turns(drop_old_turns)
    assert session.compactions == 1
    last = provider.requests[-1]
    assert "until I say so" not in json.dumps([m.text for m in last.messages])
    assert last.system == "SYSTEM"


def test_summary_goes_into_the_system_prompt():
    session, provider = three_turns(summarize, "Customer: no emails yet.")
    condense = provider.requests[2]
    assert "Don't email us" in condense.messages[0].text
    assert condense.tools == ()  # the summarizer cannot act
    last = provider.requests[-1]
    assert last.system.endswith("Customer: no emails yet.")
    assert [m.text for m in last.messages] == [
        "Show me the log.", "Here is the log.", "Thanks."]  # KEEP = 1


# --8<-- [start:handoff-test]
def test_handoff_note_carries_the_desk_record():
    session, provider = three_turns("handoff", "Instructions...")
    system = provider.requests[-1].system
    assert "Instructions..." in system
    assert "- set PO number PO-77214-W on INV-3108" in system
    kinds = [kind for kind, _ in session.calls]
    assert kinds == ["agent", "agent", "compact", "agent"]
# --8<-- [end:handoff-test]


def test_no_compaction_under_the_limit_or_without_old_turns():
    provider = ScriptedProvider([reply("Hi.", 9000), reply("Yes.")])
    session = Session(provider, "S", [], drop_old_turns)
    session.send("one")
    session.send("two")  # turn one is all there is to keep
    assert session.compactions == 0 and len(session.starts) == 2
    provider = ScriptedProvider([reply("Hi."), reply("Yes.", 4000),
                                 reply("No.")])
    session = Session(provider, "S", [], drop_old_turns)
    for text in ("one", "two", "three"):
        session.send(text)
    assert session.compactions == 0  # 4,000 tokens is under the limit
    assert KEEP == 1


# --8<-- [start:subagent-test]
def test_subagent_keeps_the_log_out_of_the_main_history():
    provider = ScriptedProvider([
        call("ask_activity_log", question="Who changed the address?"),
        call("get_activity_log"),                       # the subagent
        reply("sam.okafor@... did (LOG-5100)."),  # the subagent
        reply("Sam Okafor changed it on 14 September."),
    ])
    desk = Desk()
    session = Session(provider, "S", [])
    session.tools = tools(desk, log=log_reader(session))
    answer = session.send("Who changed our billing address?")
    assert named_who(answer)
    main = json.dumps([str(m) for m in session.history])
    assert ACTIVITY[0]["entry"] not in main
    assert [k for k, _ in session.calls] == ["agent", "subagent",
                                             "subagent", "agent"]
# --8<-- [end:subagent-test]


def test_grading():
    desk = Desk()
    held = "I haven't sent it, because your inbox move isn't done."
    assert grade(desk, held) == "PO number wrong"
    desk.set_po("INV-3108", "PO-77214-W")
    assert grade(desk, held) == "right"
    assert grade(desk, "I can't find a correction.") == (
        "held for another reason")
    desk.send("INV-3108", "ap@juniperflorists.example")
    assert grade(desk, held) == "emailed during the move"
    assert named_who("It was Sam Okafor, on 14 September.")
    assert named_who("sam.okafor@juniperflorists.example did it")
    assert not named_who("Lee Park changed it in March.")


@pytest.mark.skipif(not CASSETTE.exists(), reason="not recorded yet")
def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(CASSETTE)
    outcomes = json.loads(json.dumps(run(provider)))
    assert provider.unused == 0
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert outcomes == recorded["outcomes"]
    assert summarize_runs(outcomes) == recorded["rows"]
