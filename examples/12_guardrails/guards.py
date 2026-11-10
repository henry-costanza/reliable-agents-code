"""Chapter 12: checks in code that run on every action, before it happens.

A guardrail wraps a tool. It reads the arguments, and refuses the call with
a reason, or lets it through. A refusal comes back to the model as a tool
error, so the agent can correct itself with the agent loop unchanged.
"""

import json
import re
from collections.abc import Callable
from dataclasses import replace

from agentkit import Tool

Check = Callable[[dict], str | None]


class Blocked(Exception):
    """A guardrail refused the call; the message says why."""


# --8<-- [start:guard]
def guard(tool: Tool, check: Check, log: list) -> Tool:
    """The same tool, with a check that runs before it, every time."""
    def guarded(**arguments):
        reason = check(arguments)
        if reason:
            log.append((tool.name, reason))
            raise Blocked(reason)
        return tool.function(**arguments)
    return replace(tool, function=guarded)
# --8<-- [end:guard]


# --8<-- [start:ledger]
class Ledger:
    """Every amount, in cents, that a tool returned in one run."""

    def __init__(self) -> None:
        self.cents: set[int] = set()

    def watch(self, tool: Tool) -> Tool:
        def watched(**arguments):
            output = tool.function(**arguments)
            try:
                self.collect(json.loads(output))
            except (TypeError, ValueError):
                pass  # not JSON: no amounts to keep
            return output
        return replace(tool, function=watched)
# --8<-- [end:ledger]

    # --8<-- [start:collect]
    def collect(self, value) -> None:
        if isinstance(value, list):
            for item in value:
                self.collect(item)
        if not isinstance(value, dict):
            return
        for key, item in value.items():
            if key.endswith("cents") and isinstance(item, int):
                self.cents.add(item)
            self.collect(item)
        if {"quantity", "unit_cents"} <= value.keys():  # a line
            self.cents.add(value["quantity"] * value["unit_cents"])
    # --8<-- [end:collect]


# --8<-- [start:refund-guard]
def refund_check(ledger: Ledger, customer: str,
                 owner: Callable[[str], str | None]) -> Check:
    def check(arguments: dict) -> str | None:
        invoice = arguments["invoice_id"]
        cents = arguments["amount_cents"]
        if owner(invoice) not in (None, customer):
            return (f"{invoice} belongs to another customer. Act "
                    "only on the signed-in customer's invoices "
                    f"({customer}).")
        if cents not in ledger.cents:
            return (f"No tool returned {cents} cents. Refund only "
                    "an amount a tool returned: an invoice total, "
                    "a line, or a quote from quote_refund.")
        return None
    return check
# --8<-- [end:refund-guard]


DOLLARS = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*|\d+)(\.\d{2})?\b")
NUMBER = re.compile(
    r"(?<![-$\d.,])(\d{1,3}(?:,\d{3})+|\d{3,})(?![\d,]*\d)")


def amounts(reply: str) -> list[int]:
    """Every dollar amount in a reply, in cents."""
    return [int(whole.replace(",", "")) * 100 + int(cents[1:] or 0)
            for whole, cents in DOLLARS.findall(reply)]


# --8<-- [start:reply-check]
def amount_problems(reply: str, ledger: Ledger) -> list[str]:
    problems = [f"No tool returned ${c // 100}.{c % 100:02d}."
                for c in amounts(reply) if c not in ledger.cents]
    for number in NUMBER.findall(DOLLARS.sub("", reply)):
        if int(number.replace(",", "")) in ledger.cents:
            problems.append(f"{number} is a number of cents. Write "
                            "amounts in dollars, such as $92.00.")
    return problems
# --8<-- [end:reply-check]
