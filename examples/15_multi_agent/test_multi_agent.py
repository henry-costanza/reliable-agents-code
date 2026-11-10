"""Chapter 15: one agent and a team, each with its own tests, offline."""

import json
from itertools import count

import pytest
import team_experiment as experiment
from team_desk import TASKS, help_tools, one_agent, route, team
from tracing import Tracer

from agentkit import ScriptedProvider
from agentkit.messages import (Message, Response, StopReason, Text,
                               ToolUse, Usage)
from signed_in_desk import Case, Outbox

ids = count(1)


def reply(text: str) -> Response:
    return Response(Message("assistant", (Text(text),)),
                    StopReason.END_TURN, Usage(10, 10))


def call(name: str, **arguments) -> Response:
    use = ToolUse(f"tu_{next(ids)}", name, arguments)
    return Response(Message("assistant", (use,)), StopReason.TOOL_USE,
                    Usage(10, 10))


# --8<-- [start:route-test]
@pytest.mark.parametrize("said, chosen", [
    ("help", "help"), ("Billing.", "billing"),
    ("help, then billing", "billing"), ("Not sure.", "billing")])
def test_the_router_only_chooses_and_doubt_goes_to_billing(said,
                                                           chosen):
    assert route(ScriptedProvider([reply(said)]), "Hi") == chosen
# --8<-- [end:route-test]


# --8<-- [start:handoff-test]
def test_the_specialist_reads_the_customers_own_words():
    customer, message, _ = TASKS["charge and export"]
    tracer = Tracer(ScriptedProvider([
        reply("help"),
        call("send_reply", message="One export holds 10,000 rows."),
        reply("Done.")]))
    outcome = team(tracer, customer, message)
    handed = tracer.calls[1].request.messages[0].text
    assert handed == f"Customer message: {message}"
    assert outcome.route == "help"
# --8<-- [end:handoff-test]


def test_the_help_specialist_cannot_move_money():
    case = Case()
    names = {t.name for t in help_tools(case, Outbox())}
    assert names == {"search_help_center", "open_ticket", "send_reply"}


def run_one(task: str, *turns: Response):
    customer, message, grade = TASKS[task]
    outcome = one_agent(ScriptedProvider([*turns, reply("Done.")]),
                        customer, message)
    return grade(outcome.case, outcome.approvals)


# --8<-- [start:mixed-test]
def test_a_mixed_request_needs_both_halves():
    lookup = call("get_invoice", invoice_id="INV-2207")
    ask = call("request_refund", invoice_id="INV-2207",
               amount_cents=9200, reason="Charged twice.")
    half = run_one("charge and export", lookup, ask, call(
        "send_reply", message="I asked billing to refund $92.00."))
    whole = run_one("charge and export", lookup, ask, call(
        "send_reply", message="I asked billing to refund $92.00. "
        "One export holds 10,000 rows."))
    assert (half, whole) == ("no row limit", "right")
# --8<-- [end:mixed-test]


def test_replay_reproduces_the_recorded_runs():
    recorded = json.loads(experiment.SUMMARY.read_text(encoding="utf-8"))
    assert experiment.summary(experiment.run()) == recorded
