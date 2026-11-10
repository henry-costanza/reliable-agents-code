"""Chapter 6: Brindle's help center, and the questions customers ask it.

Brindle is fictional, and so are these articles. One of them is out of
date on purpose: the 2024 refund policy, archived when the 2026 one
replaced it, but still in the help center's database, as old articles are.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    updated: str
    archived: bool
    body: str  # Markdown; each "## " heading starts a section


ARTICLES = (
    Article("HC-101", "Refunds and credits", "2026-09-15", False, """\
## Refund window
You can ask for a refund within 30 days of a charge. We refund the full
amount to the original payment method, and it reaches your account in 5
to 10 business days.

## Duplicate charges
If you were charged twice for the same billing period, we refund the
extra charge at any time. There is no time limit on duplicate charges.

## Annual plans
If you cancel an annual plan, we refund the months you have not used,
prorated to the day.

## Credit instead of a refund
You can take account credit instead of a refund. Credit is applied to
your next invoice and never expires.
"""),
    Article("HC-090", "Refund policy (2024)", "2024-03-02", True, """\
## Refunds
Refunds are available within 14 days of a charge. After 14 days, charges
are final. Annual plans are not refunded after the first 14 days, and
unused months are not prorated.

## Duplicate charges
Duplicate charges must be reported within 14 days to be refunded.
"""),
    Article("HC-110", "Team seats", "2026-06-01", False, """\
## Price
Each team seat costs $25 per month. Seats added in the middle of a month
are prorated on your next invoice.

## Removing seats
Removing a seat takes effect at the end of the billing period. The
person keeps access until then.
"""),
    Article("HC-111", "Extra storage", "2026-06-01", False, """\
## Price
Extra storage is sold in blocks of 50 GB. Each block costs $8.50 per
month, and you can add as many blocks as you need.

## When you run out
Uploads stop when you reach your storage limit. Nothing is deleted.
"""),
    Article("HC-120", "Exporting invoices to CSV", "2026-02-10", False, """\
## Export limits
One export holds up to 10,000 rows. Larger exports are split into
several files, delivered together in one ZIP archive.

## Columns
Every export has the invoice number, customer, date, line items, tax and
total. Amounts are in the account's currency.
"""),
    Article("HC-130", "Payment reminders", "2026-04-22", False, """\
## Schedule
Brindle emails a payment reminder 3, 7 and 14 days after an invoice's
due date. You can turn reminders off for each customer.

## Wording
You can edit the subject and text of each reminder. The invoice link is
always added at the end.
"""),
    Article("HC-140", "Webhooks", "2026-05-30", False, """\
## Events
Brindle sends a webhook when an invoice is created, paid, refunded or
voided.

## Retries
If your endpoint does not answer with a 2xx status, we retry the
delivery 5 times over 24 hours, waiting longer after each attempt.
"""),
    Article("HC-150", "Closing your account", "2026-08-19", False, """\
## Before you close
Export anything you want to keep. After the account is closed, you can
no longer sign in or download invoices.

## What we delete
We delete your customers, products and settings 90 days after you close
the account. Until then, support can reopen it for you.

## What we keep
We keep copies of the invoices you issued for 7 years, because tax law
in most countries requires it. They are not visible to anyone at
Brindle outside the finance team.
"""),
    Article("HC-160", "Two-factor authentication", "2026-07-07", False, """\
## Methods
Brindle supports authenticator apps and hardware security keys. Codes
by text message are not supported.

## Lost device
If you lose your device, sign in with one of the recovery codes you
saved when you turned on two-factor authentication.
"""),
    Article("HC-180", "Invoice numbers", "2026-01-12", False, """\
## Numbering
Invoice numbers are sequential for each account. A number is never
reused, even after its invoice is voided.

## Prefixes
You can set a prefix, such as INV-, in Settings. Changing the prefix
does not renumber invoices you already issued.
"""),
)

BY_ID = {article.id: article for article in ARTICLES}


@dataclass(frozen=True)
class Question:
    text: str
    source: str | None  # the article that answers it, or None
    fact: str | None    # a regular expression the right answer contains
    stale: str | None = None  # what the archived article would say


# --8<-- [start:questions]
QUESTIONS = (
    Question("How long do I have to ask for a refund?",
             "HC-101", r"\b30 days\b", stale=r"\b14 days\b"),
    Question("We were charged twice in May. Is it too late to get "
             "the extra charge back?",
             "HC-101", r"\b(any time|no time limit)\b",
             stale=r"\b14 days\b"),
    Question("I paid for a year and want to cancel after three "
             "months. Do I get anything back?",
             "HC-101", r"\bprorat|\bby the day\b",
             stale=r"\b14 days\b"),
    # Seven more with answers, then two the help center lacks.
# --8<-- [end:questions]
    Question("How much does one extra team seat cost?",
             "HC-110", r"\$25\b"),
    Question("What does extra storage cost?", "HC-111", r"\$8\.50\b"),
    Question("How many rows fit in one CSV export?",
             "HC-120", r"\b10,000\b"),
    Question("How often does Brindle retry a failed webhook?",
             "HC-140", r"\b5 times\b"),
    Question("If I close my account, how long do you keep my "
             "invoices?", "HC-150", r"\b7 years\b"),
    Question("Can I get two-factor codes by text message?",
             "HC-160", r"\bnot supported\b|\bno\b"),
    Question("Is an invoice number ever reused after I void the "
             "invoice?", "HC-180", r"\bnever\b|\bnot\b"),
    Question("Can I pay my Brindle bill in Bitcoin?", None, None),
    Question("What is Brindle's phone number for support?", None, None),
)
