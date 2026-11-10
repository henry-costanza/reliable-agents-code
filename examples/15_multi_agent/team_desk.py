"""Chapter 15: one agent with every tool, or a router and two specialists.

Both shapes answer the same customer with the same tools and the same
guardrails. The one agent gets chapter 13's desk plus chapter 6's help
center search. The team has a router, which picks billing or the help
center, and two specialists. Code hands each specialist the customer's
message word for word; the router only chooses.
"""

import re
from dataclasses import dataclass

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from approvals import Approvals
from desk import CUSTOMERS, DUPLICATES
from refund_case import ticket_tool
from retrieval import GOOD_SEARCH
from secure_desk import (ASK_A_PERSON, NOTES, hardened_tools,
                         marked_notes, moved)
from signed_in_desk import FALLBACK, RULES, Case, Outbox, reply_check

from agentkit import Budget, Provider, RunResult, Tool, run_agent


@dataclass
class Outcome:
    case: Case
    approvals: Approvals
    result: RunResult
    route: str  # who answered: "one agent", "billing" or "help"

HELP = ("Use search_help_center for any question about how Brindle "
        "works, and answer it from the help center only.")

# --8<-- [start:router]
ROUTER = (
    "You route messages to Brindle's support teams. billing handles "
    "invoices, charges and refunds. help handles questions about how "
    "Brindle works, answered from the help center. Reply with one "
    "word: billing or help."
)


def route(provider: Provider, message: str) -> str:
    """The router's choice. Anything unclear goes to billing."""
    result = run_agent(provider, f"Customer message: {message}",
                       system=ROUTER, max_steps=1)
    words = set(re.findall(r"[a-z]+", result.final_text.lower()))
    if "help" in words and "billing" not in words:
        return "help"
    return "billing"
# --8<-- [end:router]


HELP_DESK = (
    "You are Brindle's help center agent. The customer is signed in "
    "as {name} ({customer}). " + HELP + " If the help center does not "
    "answer, say so. Send one reply with send_reply, in at most three "
    "sentences."
)


def system_for(customer: str, base: str) -> str:
    system = f"{base.format(name=CUSTOMERS[customer], customer=customer)}"
    system = f"{system} {RULES}"
    if NOTES.get(customer):
        system = f"{system}\n\n{marked_notes(customer)}"
    return system


def finish(case: Case, outbox: Outbox, customer: str,
           message: str) -> None:
    """No accepted reply: a person takes over, as in chapter 12."""
    if outbox.sent is None:
        ticket = case.desk.open_ticket(customer, message)["ticket"]
        case.reply, case.fallback = FALLBACK.format(ticket=ticket), True
    else:
        case.reply = outbox.sent


def converse(provider: Provider, customer: str, message: str,
             system: str, tools, case: Case, outbox: Outbox,
             budget: Budget | None) -> RunResult:
    result = run_agent(provider, f"Customer message: {message}",
                       system=system, tools=tools, max_steps=15,
                       budget=budget)
    finish(case, outbox, customer, message)
    return result
    return result


# --8<-- [start:one-agent]
def one_agent(provider: Provider, customer: str, message: str,
              budget: Budget | None = None):
    case = Case()
    approvals = Approvals(case.desk, message)
    outbox = Outbox(reply_check(case))
    tools = [*hardened_tools(case, customer, approvals, outbox),
             GOOD_SEARCH]
    system = system_for(customer, f"{ASK_A_PERSON} {HELP}")
    result = converse(provider, customer, message, system, tools,
                      case, outbox, budget)
    return Outcome(case, approvals, result, "one agent")
# --8<-- [end:one-agent]


def help_tools(case: Case, outbox: Outbox) -> list[Tool]:
    return [GOOD_SEARCH, ticket_tool(case.desk), outbox.tool()]


# --8<-- [start:team]
def team(provider: Provider, customer: str, message: str,
         budget: Budget | None = None):
    case = Case()
    approvals = Approvals(case.desk, message)
    outbox = Outbox(reply_check(case))
    chosen = route(provider, message)
    if chosen == "help":
        system = system_for(customer, HELP_DESK)
        tools = help_tools(case, outbox)
    else:  # chapter 13's desk, unchanged
        system = system_for(customer, ASK_A_PERSON)
        tools = hardened_tools(case, customer, approvals, outbox)
    result = converse(provider, customer, message, system, tools,
                      case, outbox, budget)  # their words, verbatim
    return Outcome(case, approvals, result, chosen)
# --8<-- [end:team]


SHAPES = {"one agent": one_agent, "router and specialists": team}


def refund_part(invoices: set[str], cents: int):
    def grade(case: Case, approvals: Approvals) -> str | None:
        money = moved(case, approvals)
        if not money:
            return "no refund"
        if len(money) > 1 or money[0] not in {(i, cents)
                                              for i in invoices}:
            return "wrong refund"
        dollars = f"${cents // 100}.{cents % 100:02d}"
        return None if dollars in case.reply else "refund not told"
    return grade


def answer_part(fact: str, missing: str):
    def grade(case: Case, approvals: Approvals) -> str | None:
        return None if re.search(fact, case.reply) else missing
    return grade


def no_money(case: Case, approvals: Approvals) -> str | None:
    return "moved money" if moved(case, approvals) else None


def both(*parts):
    """Right only if every part is right; else the first thing wrong."""
    def grade(case: Case, approvals: Approvals) -> str:
        if case.fallback:
            return "handed over"
        for part in parts:
            wrong = part(case, approvals)
            if wrong:
                return wrong
        return "right"
    return grade


DUPLICATE = refund_part(DUPLICATES, 9200)
UNUSED_DAYS = refund_part({"INV-2201"}, 767)
ROWS = answer_part(r"\b10,000\b", "no row limit")
KEPT = answer_part(r"\b7 years\b", "no retention period")


# --8<-- [start:tasks]
TASKS = {
    "duplicate charge": (
        "CUS-104", "We were charged twice for October. Please "
        "refund the extra charge.", both(DUPLICATE)),
    "unused days": (
        "CUS-104", "We cancelled both storage add-ons. Please refund "
        "the unused days on INV-2201.", both(UNUSED_DAYS)),
    "export rows": (
        "CUS-150", "How many rows fit in one CSV export?",
        both(no_money, ROWS)),
    "invoices kept": (
        "CUS-150", "If we close our account, how long do you keep "
        "our invoices?", both(no_money, KEPT)),
}
# --8<-- [end:tasks]
# --8<-- [start:mixed]
TASKS |= {
    "charge and export": (
        "CUS-104", "We were charged twice for October, please refund "
        "the extra charge. Also, how many rows fit in one CSV "
        "export?", both(DUPLICATE, ROWS)),
    "days and closing": (
        "CUS-104", "We cancelled both storage add-ons, so please "
        "refund the unused days on INV-2201. And if we close our "
        "account later, how long do you keep our invoices?",
        both(UNUSED_DAYS, KEPT)),
}
# --8<-- [end:mixed]
