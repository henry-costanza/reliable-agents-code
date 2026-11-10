"""Brindle's billing tools and the question chapter 1 gives the agent.

Brindle is a fictional invoicing startup. Its support agent runs through
the whole book; here it answers one question about one invoice.
"""

import json
from decimal import Decimal

from agentkit import Tool

INVOICES = {
    "INV-1042": [
        {"item": "Team seat", "quantity": 3, "unit_cents": 2500},
        {"item": "Extra storage, 50 GB", "quantity": 2, "unit_cents": 850},
        {"item": "Onboarding call", "quantity": 1, "unit_cents": 4900},
    ],
}


# --8<-- [start:functions]
def get_invoice(invoice_id: str) -> str:
    return json.dumps(INVOICES[invoice_id])


def invoice_total(lines: list[dict]) -> str:
    cents = sum(x["quantity"] * x["unit_cents"] for x in lines)
    return f"${Decimal(cents) / 100:.2f}"
# --8<-- [end:functions]


LINE = {
    "type": "object",
    "properties": {
        "item": {"type": "string"},
        "quantity": {"type": "integer", "minimum": 1},
        "unit_cents": {"type": "integer", "minimum": 0},
    },
    "required": ["item", "quantity", "unit_cents"],
}

# --8<-- [start:tools]
GET_INVOICE = Tool(
    "get_invoice",
    "Return the line items of one invoice, by its id.",
    {
        "type": "object",
        "properties": {"invoice_id": {"type": "string"}},
        "required": ["invoice_id"],
    },
    get_invoice,
)
INVOICE_TOTAL = Tool(
    "invoice_total",
    "Return the total of a list of line items, in dollars.",
    {
        "type": "object",
        "properties": {"lines": {"type": "array", "items": LINE}},
        "required": ["lines"],
    },
    invoice_total,
)
# --8<-- [end:tools]

# --8<-- [start:task]
SYSTEM = (
    "You are Brindle's billing support agent. Look up invoices with "
    "get_invoice. Compute every amount with invoice_total; never do "
    "arithmetic yourself."
)
TASK = (
    "What is the total of invoice INV-1042? "
    "Reply with just the amount."
)
# --8<-- [end:task]
