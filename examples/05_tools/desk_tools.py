"""Chapter 5: two sets of tools over the same support desk.

Both sets reach the same data and make the same refunds. They differ only
in what the model is told: names, descriptions, units and error messages.
"""

from desk import CUSTOMERS, INVOICES, Desk, DeskError, as_json

from agentkit import Tool


def schema(required: dict, optional: dict | None = None) -> dict:
    return {"type": "object",
            "properties": {**required, **(optional or {})},
            "required": list(required), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}


# --8<-- [start:poor]
def poor_tools(desk: Desk) -> list[Tool]:
    """Tools as many first versions are written."""
    def refund(id: str, amount: float) -> str:  # amount is in dollars
        try:
            return as_json(desk.refund(id, round(amount * 100)))
        except (DeskError, KeyError):
            raise DeskError("bad request") from None

    return [
        Tool("search", "Search.", schema({"query": TEXT}),
             lambda query: as_json(search(desk, query))),
        Tool("get", "Get a record by id.", schema({"id": TEXT}),
             lambda id: as_json(get(desk, id))),
        Tool("refund", "Refund an invoice.",
             schema({"id": TEXT, "amount": {"type": "number"}}),
             refund),
    ]
# --8<-- [end:poor]


def search(desk: Desk, query: str) -> list[dict]:
    """Customers whose name matches, and their invoices; totals in cents."""
    found = []
    for match in desk.customers(query):
        cid = match["customer_id"]
        found.append({"id": cid, "type": "customer", "name": match["name"]})
        found += [{"id": i, "type": "invoice", "customer": cid,
                   "date": date, "total": desk.invoice(i)["total_cents"]}
                  for i, (c, date, _) in INVOICES.items() if c == cid]
    return found


def get(desk: Desk, id: str) -> dict:
    if id in CUSTOMERS:
        return {"id": id, "name": CUSTOMERS[id]}
    try:
        invoice = desk.invoice(id)
    except DeskError:
        raise DeskError("bad request") from None
    return {"id": id, "customer": invoice["customer_id"],
            "date": invoice["date"],
            "lines": [{"item": l["item"], "qty": l["quantity"],
                       "price": l["unit_cents"]} for l in invoice["lines"]],
            "total": invoice["total_cents"]}


# --8<-- [start:good-find]
FIND_CUSTOMERS = (
    "Find customers by name. Matching ignores case and accepts part "
    "of a name, so 'orion' returns every customer whose name "
    "contains it. Returns a JSON list of {customer_id, name}. "
    "Several customers can have similar names: compare the full name "
    "with the one the customer gave before you act on an account."
)
LIST_INVOICES = (
    "List one customer's invoices for one month. month is YYYY-MM, "
    "such as 2026-10. Returns a JSON list of invoices, each with its "
    "lines, total_cents and refunded_cents. All amounts are integer "
    "numbers of cents: 9200 means $92.00."
)
# --8<-- [end:good-find]

GET_INVOICE = (
    "Return one invoice by its id, such as INV-2201: customer, date, "
    "lines, total_cents and refunded_cents. All amounts are integer "
    "numbers of cents."
)

# --8<-- [start:good-refund]
REFUND_INVOICE = (
    "Refund all or part of one invoice. amount_cents is an integer "
    "number of cents, so 9200 refunds $92.00; it cannot be more than "
    "the invoice's total_cents minus its refunded_cents. A refund "
    "cannot be undone: check that the invoice belongs to the "
    "customer who asked, and refund each charge once."
)
# --8<-- [end:good-refund]


# --8<-- [start:good]
def good_tools(desk: Desk) -> list[Tool]:
    """The same desk, described for a reader with only this text."""
    month = {"type": "string", "pattern": r"^\d{4}-\d{2}$"}
    cents = {"type": "integer", "minimum": 1}
    return [
        Tool("find_customers", FIND_CUSTOMERS, schema({"name": TEXT}),
             lambda name: as_json(desk.customers(name))),
        Tool("list_invoices", LIST_INVOICES,
             schema({"customer_id": TEXT, "month": month}),
             lambda customer_id, month: as_json(
                 desk.invoices(customer_id, month))),
        Tool("get_invoice", GET_INVOICE, schema({"invoice_id": TEXT}),
             lambda invoice_id: as_json(desk.invoice(invoice_id))),
        Tool("refund_invoice", REFUND_INVOICE,
             schema({"invoice_id": TEXT, "amount_cents": cents}),
             lambda invoice_id, amount_cents: as_json(
                 desk.refund(invoice_id, amount_cents))),
    ]
# --8<-- [end:good]
