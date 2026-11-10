"""Chapter 16: Brindle's support desk 1.0, assembled from every chapter.

One agent (chapter 15) with chapter 13's hardened desk: facts from the
record, notes marked as what a customer said, refunds only on a person's
confirmation. Chapter 12's guardrails check every refund request and every
reply. The help center goes into the prompt whole, current articles only,
as chapter 6 measured; chapter 14's caching makes that cheap.
"""

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from approvals import Approvals
from help_center import ARTICLES
from secure_desk import ASK_A_PERSON, hardened_tools
from signed_in_desk import Case, Outbox, reply_check
from team_desk import Outcome, converse, system_for

from agentkit import Budget, Provider

VERSION = "1.0"


# --8<-- [start:help-center]
def current_help_center() -> str:
    """Every current article, whole. Retired ones stay out."""
    return "\n\n".join(
        f"# [{a.id}] {a.title} (updated {a.updated})\n"
        f"{a.body.strip()}"
        for a in ARTICLES if not a.archived)


FROM_THE_HELP_CENTER = (
    "Answer questions about how Brindle works from the help center "
    "below, and only from it. If it does not answer, say so.")
# --8<-- [end:help-center]


# --8<-- [start:desk]
def desk(provider: Provider, customer: str, message: str,
         budget: Budget | None = None) -> Outcome:
    case = Case()
    approvals = Approvals(case.desk, message)
    outbox = Outbox(reply_check(case))
    tools = hardened_tools(case, customer, approvals, outbox)
    system = system_for(customer, f"{ASK_A_PERSON} "
                                  f"{FROM_THE_HELP_CENTER}")
    system += f"\n\nBrindle's help center:\n\n{current_help_center()}"
    result = converse(provider, customer, message, system, tools,
                      case, outbox, budget)
    return Outcome(case, approvals, result, f"desk {VERSION}")
# --8<-- [end:desk]
