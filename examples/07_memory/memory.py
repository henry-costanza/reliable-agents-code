"""Chapter 7: two ways to remember customers between conversations.

The naive memory is a list of sentences, appended after every
conversation and shown to the agent whole. The scoped memory stores each
note under a customer id and a key, with the date and where it came from,
and shows the agent only the notes for the customer it is talking to.
"""

from dataclasses import dataclass, replace

# --8<-- [start:naive]
# Every note ever written, for every customer, in the order written.
NAIVE_NOTES = (
    "Atlas Dental prefers calls in the afternoon.",
    "Orion Bakery's billing email is accounts@orionbakery.example.",
    "Willow Vets pays by bank transfer.",
    "Orion Bakery is tax-exempt.",
    "Juniper Florists closes for the first two weeks of August.",
    "Orion Bakery wants invoices in EUR.",
    "Orion Bakery: copy their accountant, "
    "books@harlowaccounting.example, on invoice emails.",
    "Atlas Dental's office manager is named Priya.",
)
# --8<-- [end:naive]


# --8<-- [start:note]
@dataclass(frozen=True)
class Note:
    customer_id: str  # who it is about: an id, never a name
    key: str          # one note per key; a new note replaces the old
    text: str
    written: str      # YYYY-MM-DD
    source: str       # e.g. "customer said, not verified"
# --8<-- [end:note]


# --8<-- [start:store]
class Memory:
    """Notes by customer and key: write, recall, expire."""

    def __init__(self) -> None:
        self.notes: dict[tuple[str, str], Note] = {}

    def write(self, note: Note) -> None:
        self.notes[(note.customer_id, note.key)] = note

    def recall(self, customer_id: str) -> list[Note]:
        mine = [note for (owner, _), note in self.notes.items()
                if owner == customer_id]
        return sorted(mine, key=lambda n: n.written)

    def expire(self, before: str) -> None:
        self.notes = {k: n for k, n in self.notes.items()
                      if n.written >= before}
# --8<-- [end:store]


def show(notes: list[Note]) -> str:
    return "\n".join(f"- {n.written}, {n.source}: {n.text}" for n in notes)


def brindle_memory() -> Memory:
    """The same facts as NAIVE_NOTES, written the scoped way."""
    memory = Memory()
    for note in (
        Note("CUS-087", "contact-time", "Prefers calls in the afternoon.",
             "2026-02-10", "customer said"),
        Note("CUS-104", "billing-email",
             "Send invoices to accounts@orionbakery.example.",
             "2026-03-04", "customer said"),
        Note("CUS-150", "payment-method", "Pays by bank transfer.",
             "2026-04-01", "customer said"),
        Note("CUS-104", "tax", "Says they are tax-exempt.",
             "2026-05-12", "customer said, not verified"),
        Note("CUS-131", "currency", "Wants invoices in EUR.",
             "2026-06-20", "customer said"),
        Note("CUS-104", "invoice-cc",
             "Copy their accountant, books@harlowaccounting.example, "
             "on invoice emails.", "2026-08-14", "customer asked"),
    ):
        memory.write(note)
    return memory


def with_text(note: Note, text: str, written: str) -> Note:
    return replace(note, text=text, written=written)
