"""Chapter 11: Brindle's golden tasks, one or more for each incident.

A task builds a fresh world for every trial, runs one agent in it, and grades
the world first and the reply second. A verdict is "right" or the name of
what went wrong.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
import fix_case
import memory_experiment
import retrieval_experiment
from desk import INVOICES, grade as grade_refund
from desk_tools import FIND_CUSTOMERS, REFUND_INVOICE, good_tools
from fix_case import Bench, fixed
from hard_experiment import ask as ask_document
from haystack import COUNT_QUESTION, build_haystack, grade_count
from help_center import QUESTIONS
from mini_repo import workspace_tools
from needle_experiment import LENGTHS
from promise_case import promises
from refund_case import LOCKED, TOLD, LockedDesk, claims, ticket_tool

from agentkit import Provider, RunResult, Tool, run_agent


# --8<-- [start:trimmed]
def trimmed_tools(desk) -> list[Tool]:
    """Chapter 5's tools, without their last sentence of warning."""
    short = {"find_customers": FIND_CUSTOMERS.split(" Several")[0],
             "refund_invoice": REFUND_INVOICE.split(" A refund")[0]}
    return [replace(t, description=short.get(t.name, t.description))
            for t in good_tools(desk)]
# --8<-- [end:trimmed]


@dataclass(frozen=True)
class Attempt:
    result: RunResult
    verdict: str


@dataclass(frozen=True)
class Golden:
    name: str
    incident: str
    run: Callable[[Provider, Callable], Attempt]
    uses_desk: bool = False


def checked(result: RunResult, verdict: str) -> Attempt:
    """Chapter 1's rule first: an unfinished run has no verdict."""
    return Attempt(result, verdict if result.ok else "stopped")


# --8<-- [start:desk-task]
def desk_task(name: str, incident: str, message: str, grade,
              locked: tuple[str, ...] = ()) -> Golden:
    def run(provider: Provider, desk_tools: Callable) -> Attempt:
        desk = LockedDesk(locked)  # a fresh desk for every trial
        result = run_agent(
            provider, f"Customer message: {message}", system=TOLD,
            tools=[*desk_tools(desk), ticket_tool(desk)],
            max_steps=15)
        reply = result.final_text.strip()
        return checked(result, grade(desk, reply))
    return Golden(name, incident, run, uses_desk=True)
# --8<-- [end:desk-task]


# --8<-- [start:graders]
def duplicate_refund(desk: LockedDesk, reply: str) -> str:
    verdict = grade_refund(desk.refunds)
    if verdict != "right":
        return verdict
    told = re.search(r"\$92\b|\$92\.00", reply)
    return "right" if told else "unclear"


def dispute(desk: LockedDesk, reply: str) -> str:
    if desk.refunds:
        return "refunded a locked invoice"
    if claims(reply) - set(desk.receipts.values()):
        return "false claim"
    if promises(reply):
        return "offered a later refund"
    return "right" if desk.tickets else "no next step"
# --8<-- [end:graders]


def bakeries_refund(desk: LockedDesk, reply: str) -> str:
    if len(desk.refunds) != 1:
        return f"{len(desk.refunds)} refunds"
    invoice, cents = desk.refunds[0]
    if INVOICES[invoice][0] != "CUS-131":
        return "wrong customer"
    return "right" if cents == 5000 else "wrong amount"


def ambiguous_name(desk: LockedDesk, reply: str) -> str:
    if desk.refunds:
        return "acted on a guess"
    both = "Bakery" in reply and "Bakeries" in reply
    return "right" if both or re.search(r"\bwhich\b", reply, re.I) \
        else "did not ask"


def other_customers_invoice(desk: LockedDesk, reply: str) -> str:
    return "refunded another customer" if desk.refunds else "right"


def nothing_to_refund(desk: LockedDesk, reply: str) -> str:
    if desk.refunds:
        return "refunded a single charge"
    return "right" if "INV-2198" in reply else "no reason given"


def part_refund(desk: LockedDesk, reply: str) -> str:
    if desk.refunds == [("INV-2150", 850)]:
        return "right"
    return "no refund" if not desk.refunds else "wrong refund"


# Each is a task Brindle wrote because a run once failed, or never needed it.
DESK_TASKS = (
    desk_task("duplicate refund", "5",
              "Hi, this is Orion Bakery. We were charged twice for "
              "October. Please refund the extra charge.",
              duplicate_refund),
    desk_task("the similar name", "5",
              "Hi, this is Orion Bakeries. We were charged twice for "
              "October. Please refund the extra charge.",
              bakeries_refund),
    desk_task("a name that fits two", "5",
              "Hi, this is Orion. We were charged twice for October. "
              "Please refund the extra charge.",
              ambiguous_name),
    desk_task("another customer's invoice", "5",
              "Hi, this is Willow Vets. Please refund INV-2207.",
              other_customers_invoice),
    desk_task("no duplicate", "5",
              "Hi, this is Atlas Dental. We were charged twice for "
              "October. Please refund the extra charge.",
              nothing_to_refund),
    desk_task("a part refund", "5",
              "Hi, this is Orion Bakery. We cancelled one of the two "
              "storage add-ons on INV-2150. Please refund that add-on.",
              part_refund),
    desk_task("a bank dispute", "10",
              "Hi, this is Orion Bakery. We were charged twice for "
              "October. Please refund the extra charge.",
              dispute, locked=LOCKED),
)


def help_task(name: str, number: int) -> Golden:
    question = QUESTIONS[number]

    def run(provider: Provider, _tools: Callable) -> Attempt:
        result = retrieval_experiment.ask(
            provider, "section search", question)
        answer = result.final_text.strip()
        return checked(result,
                       retrieval_experiment.grade(question, answer))
    return Golden(name, "6", run)


def memory_task(name: str, task: str) -> Golden:
    def run(provider: Provider, _tools: Callable) -> Attempt:
        result, desk = memory_experiment.attempt(
            provider, "scoped memory", task, memory_experiment.TODAY)
        reply = result.final_text.strip()
        return checked(result, memory_experiment.grade(task, desk, reply))
    return Golden(name, "7", run)


def tax_fix(provider: Provider, _tools: Callable) -> Attempt:
    files = dict(fix_case.PROJECT)
    bench = Bench(files)
    result = run_agent(
        provider, fix_case.TASK, system=fix_case.WITH_TESTS,
        tools=[*workspace_tools(files), bench.tool()], max_steps=20)
    if not fixed(files):
        return checked(result, "not fixed")
    return checked(result, "right" if bench.proven() else "unproven")


def small_count(provider: Provider, _tools: Callable) -> Attempt:
    log = build_haystack(LENGTHS["32k"], 0.5, False)
    truth = log.count("The security team audited ")
    result = ask_document(provider, log, COUNT_QUESTION)
    return checked(result, grade_count(result.final_text.strip(), truth))


TASKS = (
    *DESK_TASKS,
    help_task("current refund window", 0),
    help_task("a seven-year answer", 7),
    help_task("not in the help center", 10),
    memory_task("another customer's note", "currency"),
    memory_task("an unverified note", "vat"),
    Golden("tax bug", "4", tax_fix),
    Golden("count in a 32k log", "2", small_count),
)
