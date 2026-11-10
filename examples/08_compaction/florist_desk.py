"""Chapter 8: Juniper Florists' records, and the desk the agent acts on.

The records are generated from a fixed seed, so every run sees the same
invoices, payments and activity log. They are deliberately bulky, as real
records are: a long session that reads them fills its context quickly.
Every action the agent takes is recorded in the desk.
"""

import json
import random
from dataclasses import dataclass, field

from agentkit import Tool

CUSTOMER = "CUS-162"
ACCOUNT = {
    "customer_id": CUSTOMER, "name": "Juniper Florists",
    "billing_email": "ap@juniperflorists.example",
    "billing_address": "88 Mill Lane, Unit 4, Portland, OR 97214",
    "currency": "USD", "payment_terms": "net 30",
}
ITEMS = (
    ("Wholesale roses, 50 stems", 62.50), ("Eucalyptus bunches", 8.75),
    ("Peonies, 10 stems", 34.00), ("Ranunculus, 10 stems", 21.50),
    ("Floral foam, case", 46.00), ("Ribbon, 100 yd", 12.25),
    ("Delivery, metro zone", 35.00), ("Glass vases, case of 12", 54.00),
    ("Hydrangeas, 5 stems", 27.50), ("Tulips, 20 stems", 18.00),
)
LATE_FEE_INVOICE = "INV-3043"  # issued 2026-04-06
CHANGED_ADDRESS = "sam.okafor@juniperflorists.example"


def total(invoice: dict) -> float:
    return round(sum(line["qty"] * line["unit_price"]
                     for line in invoice["lines"]), 2)


def _invoices() -> dict[str, dict]:
    rng = random.Random(8)
    invoices = {}
    number = 3013
    for month in range(1, 11):
        for day in (6, 20):
            lines = []
            for _ in range(rng.randint(4, 7)):
                name, price = rng.choice(ITEMS)
                lines.append({"item": name, "qty": rng.randint(1, 9),
                              "unit_price": price})
            invoices[f"INV-{number}"] = {
                "issued": f"2026-{month:02d}-{day:02d}",
                "due": f"2026-{month + 1:02d}-{day - 1:02d}",
                "lines": lines, "po_number": None,
            }
            number += 5
    # INV-3108, issued 2026-10-20, is the wedding-season order: large.
    invoices["INV-3108"]["lines"] = [
        {"item": name, "qty": 12 + i, "unit_price": price}
        for i, (name, price) in enumerate(ITEMS)]
    late = invoices[LATE_FEE_INVOICE]
    fee = round(0.015 * total(late), 2)
    late["lines"].append(
        {"item": "Late fee: 1.5% of balance; due 2026-05-05, "
                 "paid 2026-05-19", "qty": 1, "unit_price": fee})
    return invoices


INVOICES = _invoices()


def _payments() -> list[dict]:
    payments = []
    for index, (invoice_id, invoice) in enumerate(sorted(INVOICES.items())):
        if invoice["issued"] >= "2026-09-20":
            continue  # the last three invoices are unpaid
        late = invoice_id == LATE_FEE_INVOICE
        day = "19" if late else invoice["due"][-2:]
        month = invoice["due"][:7] if not late else "2026-05"
        payments.append({"payment_id": f"PAY-{7400 + index}",
                         "received": f"{month}-{day}", "invoice": invoice_id,
                         "amount": total(invoice), "method": "ACH"})
    return payments


PAYMENTS = _payments()


def _activity() -> list[dict]:
    rng = random.Random(80)
    staff = ("dana.reyes", "lee.park", "sam.okafor", "brindle-system")
    events = ("viewed invoice", "downloaded PDF", "updated card on file",
              "exported statement", "added user", "viewed payments")
    log = []
    for month in range(1, 11):
        for _ in range(12):
            who = rng.choice(staff)
            day = rng.randint(1, 28)
            log.append({"at": f"2026-{month:02d}-{day:02d}T{rng.randint(8, 18):02d}:"
                              f"{rng.randint(0, 59):02d}",
                        "user": who if who == "brindle-system"
                        else f"{who}@juniperflorists.example",
                        "event": rng.choice(events)})
    log += [
        {"at": "2026-03-11T09:40", "user": "lee.park@juniperflorists.example",
         "event": "changed billing_address to 12 Alder St, Portland, OR 97209"},
        {"at": "2026-08-27T16:05", "user": "dana.reyes@juniperflorists.example",
         "event": "changed billing_email to ap@juniperflorists.example"},
        {"at": "2026-09-14T10:02", "user": CHANGED_ADDRESS,
         "event": "changed billing_address to 88 Mill Lane, Unit 4, "
                  "Portland, OR 97214"},
        {"at": "2026-09-14T10:03", "user": "brindle-system",
         "event": "sent address-change confirmation to "
                  "ap@juniperflorists.example"},
    ]
    log.sort(key=lambda entry: entry["at"])
    return [{"entry": f"LOG-{5000 + i}", **e} for i, e in enumerate(log)]


ACTIVITY = _activity()


class DeskError(Exception):
    """A request the desk refuses; the message says why."""


@dataclass
class Desk:
    sent: list[dict] = field(default_factory=list)
    po_numbers: dict[str, str] = field(default_factory=dict)

    def invoice(self, invoice_id: str) -> dict:
        if invoice_id not in INVOICES:
            raise DeskError(f"{invoice_id} is not an invoice id.")
        invoice = INVOICES[invoice_id]
        return {"invoice_id": invoice_id, **invoice,
                "po_number": self.po_numbers.get(invoice_id),
                "total": total(invoice)}

    def invoices(self) -> list[dict]:
        paid = {p["invoice"] for p in PAYMENTS}
        return [{"invoice_id": i, "issued": inv["issued"], "due": inv["due"],
                 "total": total(inv),
                 "status": "paid" if i in paid else "unpaid"}
                for i, inv in sorted(INVOICES.items())]

    def set_po(self, invoice_id: str, po_number: str) -> dict:
        self.invoice(invoice_id)
        self.po_numbers[invoice_id] = po_number
        return {"invoice_id": invoice_id, "po_number": po_number}

    def send(self, invoice_id: str, to: str) -> dict:
        self.invoice(invoice_id)
        self.sent.append({"invoice": invoice_id, "to": to})
        return {"sent": invoice_id, "to": to}

    def actions(self) -> list[str]:
        """What this conversation changed, as Brindle's system recorded it."""
        done = [f"set PO number {po} on {i}" for i, po in self.po_numbers.items()]
        done += [f"emailed {s['invoice']} to {s['to']}" for s in self.sent]
        return done


def schema(**properties) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}


def log_tool() -> Tool:
    return Tool("get_activity_log",
                "Return the customer's whole 2026 activity log, oldest first: "
                "who did what in their Brindle account, and when.",
                schema(), lambda: json.dumps(ACTIVITY))


def tools(desk: Desk, log: Tool | None = None) -> list[Tool]:
    """The desk's tools; `log` replaces the raw activity-log tool."""
    return [
        Tool("get_account", "Return the customer's account record.",
             schema(), lambda: json.dumps(ACCOUNT)),
        Tool("list_invoices",
             "List every 2026 invoice with its dates, total and status.",
             schema(), lambda: json.dumps(desk.invoices())),
        Tool("get_invoice", "Return one invoice with all its lines.",
             schema(invoice_id=TEXT),
             lambda invoice_id: json.dumps(desk.invoice(invoice_id))),
        Tool("list_payments",
             "List every payment received from the customer in 2026.",
             schema(), lambda: json.dumps(PAYMENTS)),
        log or log_tool(),
        Tool("set_po_number", "Set the purchase-order number on an invoice.",
             schema(invoice_id=TEXT, po_number=TEXT),
             lambda invoice_id, po_number: json.dumps(
                 desk.set_po(invoice_id, po_number))),
        Tool("send_invoice", "Email one invoice to an address.",
             schema(invoice_id=TEXT, to=TEXT),
             lambda invoice_id, to: json.dumps(desk.send(invoice_id, to))),
    ]
