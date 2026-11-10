"""Chapter 7: Brindle's account records, and the desk the agent acts on.

The account record is the system of record: what Brindle's billing system
knows for certain. Every action the agent takes is recorded in the desk,
so a run is graded on what was sent or changed, not on what it said.
"""

import json
from dataclasses import dataclass, field

from agentkit import Tool

ACCOUNTS = {
    "CUS-104": {"name": "Orion Bakery", "billing_email": "finance@orionbakery.example",
                "currency": "USD", "tax_exempt": False},
    "CUS-131": {"name": "Orion Bakeries", "billing_email": "billing@orionbakeries.example",
                "currency": "EUR", "tax_exempt": False},
}
INVOICES = {
    "INV-2150": ("CUS-104", "2026-09"),
    "INV-2201": ("CUS-104", "2026-10"),
    "INV-2204": ("CUS-131", "2026-10"),
}
CERTIFICATES: dict[str, str] = {}  # tax-exemption certificates on file


class DeskError(Exception):
    """A request the desk refuses; the message says why."""


@dataclass
class Desk:
    sent: list[dict] = field(default_factory=list)
    exempted: list[str] = field(default_factory=list)

    def account(self, customer_id: str) -> dict:
        if customer_id not in ACCOUNTS:
            raise DeskError(f"{customer_id} is not a customer id.")
        return {"customer_id": customer_id, **ACCOUNTS[customer_id]}

    def invoices(self, customer_id: str, month: str) -> list[str]:
        return [i for i, (c, m) in INVOICES.items()
                if c == customer_id and m == month]

    def send(self, invoice_id: str, to: str, cc: list[str]) -> dict:
        if invoice_id not in INVOICES:
            raise DeskError(f"{invoice_id} is not an invoice id.")
        self.sent.append({"invoice": invoice_id, "to": to, "cc": sorted(cc)})
        return {"sent": invoice_id, "to": to, "cc": sorted(cc)}

    def exempt(self, customer_id: str, certificate_id: str) -> dict:
        if CERTIFICATES.get(certificate_id) != customer_id:
            raise DeskError(
                f"No tax-exemption certificate {certificate_id} is on file "
                f"for {customer_id}. Ask the customer to upload one in "
                "Settings > Tax; it is checked before VAT is removed."
            )
        self.exempted.append(customer_id)
        return {"tax_exempt": customer_id}


def tools(desk: Desk) -> list[Tool]:
    text = {"type": "string", "minLength": 1}
    emails = {"type": "array", "items": text}

    def schema(required: dict, optional: dict | None = None) -> dict:
        return {"type": "object", "properties": {**required, **(optional or {})},
                "required": list(required), "additionalProperties": False}

    return [
        Tool("get_account",
             "Return a customer's account record: name, billing_email, "
             "currency and tax_exempt. This is Brindle's system of record.",
             schema({"customer_id": text}),
             lambda customer_id: json.dumps(desk.account(customer_id))),
        Tool("list_invoices",
             "List a customer's invoice ids for one month, given as YYYY-MM.",
             schema({"customer_id": text, "month": text}),
             lambda customer_id, month: json.dumps(desk.invoices(customer_id, month))),
        Tool("send_invoice",
             "Email one invoice to an address, with optional cc addresses.",
             schema({"invoice_id": text, "to": text}, {"cc": emails}),
             lambda invoice_id, to, cc=(): json.dumps(desk.send(invoice_id, to, list(cc)))),
        Tool("set_tax_exempt",
             "Mark a customer as tax-exempt, which removes VAT from future "
             "invoices. Needs the id of a certificate on file.",
             schema({"customer_id": text, "certificate_id": text}),
             lambda customer_id, certificate_id: json.dumps(
                 desk.exempt(customer_id, certificate_id))),
    ]
