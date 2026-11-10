"""Chapter 5: Brindle's support desk, with the customer data behind it.

The desk keeps every amount in integer cents and records the refunds it
makes, so a run can be graded on what the agent did, not on what it said.
Each run gets a fresh Desk.
"""

import json
from dataclasses import dataclass, field

CUSTOMERS = {
    "CUS-087": "Atlas Dental",
    "CUS-104": "Orion Bakery",
    "CUS-131": "Orion Bakeries",
    "CUS-150": "Willow Vets",
}

SEATS = ("Team seat", 3, 2500)
STORAGE = ("Extra storage, 50 GB", 2, 850)
ONE_SEAT = ("Team seat", 2, 2500)

INVOICES = {
    "INV-2150": ("CUS-104", "2026-09-01", (SEATS, STORAGE)),
    "INV-2198": ("CUS-087", "2026-10-01", (SEATS,)),
    "INV-2201": ("CUS-104", "2026-10-01", (SEATS, STORAGE)),
    "INV-2204": ("CUS-131", "2026-10-01", (ONE_SEAT,)),
    "INV-2207": ("CUS-104", "2026-10-01", (SEATS, STORAGE)),
    "INV-2212": ("CUS-131", "2026-10-01", (ONE_SEAT,)),
    "INV-2215": ("CUS-150", "2026-10-02", (ONE_SEAT, STORAGE)),
}
# Orion Bakery was charged twice in October: INV-2201 and INV-2207.
DUPLICATES = {"INV-2201", "INV-2207"}
DUPLICATE_CENTS = 9200


class DeskError(Exception):
    """A request the desk refuses; the message says why."""


def total_cents(invoice_id: str) -> int:
    return sum(q * cents for _, q, cents in INVOICES[invoice_id][2])


@dataclass
class Desk:
    refunds: list[tuple[str, int]] = field(default_factory=list)

    def customers(self, name: str) -> list[dict]:
        name = name.lower()
        return [{"customer_id": cid, "name": n}
                for cid, n in CUSTOMERS.items() if name in n.lower()]

    def invoices(self, customer_id: str, month: str) -> list[dict]:
        if customer_id not in CUSTOMERS:
            raise DeskError(
                f"{customer_id} is not a customer id. Customer ids look "
                "like CUS-104; find_customers returns them."
            )
        return [self.invoice(i) for i, (c, date, _) in INVOICES.items()
                if c == customer_id and date.startswith(month)]

    def invoice(self, invoice_id: str) -> dict:
        if invoice_id not in INVOICES:
            raise DeskError(
                f"{invoice_id} is not an invoice id. Invoice ids look like "
                "INV-2201; list_invoices returns a customer's invoices."
            )
        customer, date, lines = INVOICES[invoice_id]
        return {
            "invoice_id": invoice_id, "customer_id": customer,
            "customer": CUSTOMERS[customer], "date": date,
            "lines": [{"item": i, "quantity": q, "unit_cents": c}
                      for i, q, c in lines],
            "total_cents": total_cents(invoice_id),
            "refunded_cents": self.refunded(invoice_id),
        }

    def refunded(self, invoice_id: str) -> int:
        return sum(c for i, c in self.refunds if i == invoice_id)

    def refund(self, invoice_id: str, cents: int) -> dict:
        left = self.invoice(invoice_id)["total_cents"] - self.refunded(invoice_id)
        if cents <= 0:
            raise DeskError(f"amount must be positive, not {cents} cents.")
        if cents > left:
            raise DeskError(
                f"{cents} cents is more than the {left} cents left to "
                f"refund on {invoice_id}."
            )
        self.refunds.append((invoice_id, cents))
        return {"refunded": invoice_id, "amount_cents": cents}


# --8<-- [start:grade]
def grade(refunds: list[tuple[str, int]]) -> str:
    """What the run did to the customer's account."""
    if not refunds:
        return "no refund"
    if any(INVOICES[i][0] != "CUS-104" for i, _ in refunds):
        return "wrong customer"
    if len(refunds) > 1:
        return "refunded twice"
    invoice, cents = refunds[0]
    if invoice not in DUPLICATES:
        return "wrong invoice"
    return "right" if cents == DUPLICATE_CENTS else "wrong amount"
# --8<-- [end:grade]


def as_json(value) -> str:
    return json.dumps(value)
