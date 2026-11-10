"""Chapter 13: a refund waits for a person's confirmation.

The agent can only ask. A person on the billing team reads the request,
with the customer's own words next to the agent's reason, and confirms or
declines it. Only a confirmation reaches the desk.
"""

from dataclasses import dataclass

from refund_case import LockedDesk


@dataclass
class Request:
    id: str
    invoice_id: str
    amount_cents: int
    reason: str
    customer_said: str
    status: str = "waiting"


# --8<-- [start:approvals]
class Approvals:
    """Refund requests, and the only code that makes one a refund."""

    def __init__(self, desk: LockedDesk, customer_said: str) -> None:
        self.desk = desk
        self.customer_said = customer_said  # verbatim, by code
        self.requests: list[Request] = []

    def request(self, invoice_id: str, amount_cents: int,
                reason: str) -> dict:
        self.desk.invoice(invoice_id)  # an unknown invoice fails here
        receipt = self.desk.receipt("RQ", "refund request")
        self.requests.append(Request(
            receipt, invoice_id, amount_cents, reason,
            self.customer_said))
        return {"request": receipt, "status": "waiting for a person"}
# --8<-- [end:approvals]

    # --8<-- [start:person]
    def for_person(self, request: Request) -> str:
        """What the person reads before saying yes or no."""
        cents = request.amount_cents
        dollars = f"${cents // 100}.{cents % 100:02d}"
        return (f"{request.id}: refund {dollars}"
                f" on {request.invoice_id}\n"
                f"The customer wrote: {request.customer_said}\n"
                f"The agent's reason: {request.reason}")

    def confirm(self, request_id: str) -> dict:
        request = self.find(request_id)
        request.status = "confirmed"
        return self.desk.refund(request.invoice_id,
                                request.amount_cents)

    def decline(self, request_id: str) -> None:
        self.find(request_id).status = "declined"
    # --8<-- [end:person]

    def find(self, request_id: str) -> Request:
        return next(r for r in self.requests
                    if r.id == request_id and r.status == "waiting")
