"""Chapter 9: ten agent failures, and a detector for each one a trace can show.

A detector reads one conversation and returns the evidence of a failure,
or None. Five of the ten failures cannot be seen in a trace: the reply
looks fine until you compare it with the system of record. Those entries
say which check found them instead.
"""

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from tracing import Conversation

from agentkit.messages import StopReason

Detector = Callable[[Conversation], str | None]
BIG_RESULT = 10_000  # estimated tokens in one tool result


# --8<-- [start:stopped]
def stopped_early(conversation: Conversation) -> str | None:
    """The last reply did not end the turn: cut off or mid-task."""
    reason = conversation.last.stop_reason
    if reason is StopReason.END_TURN:
        return None
    return f"last reply stopped with {reason.value}"
# --8<-- [end:stopped]


def huge_result(conversation: Conversation) -> str | None:
    """A tool result that fills a large part of the context."""
    sizes = [len(r.content) // 4 for r in conversation.tool_results()]
    if sizes and max(sizes) > BIG_RESULT:
        return f"a tool result of about {max(sizes):,} tokens"
    return None


def gave_up(conversation: Conversation) -> str | None:
    """The run ended on the reply that came right after a tool error."""
    before = conversation.calls[-1].request.messages[-1]
    errors = [b for b in before.content if getattr(b, "is_error", False)]
    if errors and conversation.last.stop_reason is StopReason.END_TURN:
        return f"ended after the error {errors[0].content[:60]!r}"
    return None


# --8<-- [start:claims]
CLAIM = re.compile(r"\bI(?:'ve| have)\s+(?:also\s+|now\s+)?"
                   r"(sent|emailed|refunded|flagged|raised|escalated"
                   r"|passed|forwarded)\b", re.I)
ACTION = {"sent": "send", "emailed": "send", "refunded": "refund"}


def unbacked_claim(conversation: Conversation) -> str | None:
    """A reply says 'I've done X', and no tool call did X."""
    done = conversation.succeeded()
    for reply in conversation.replies():
        for match in CLAIM.finditer(reply.replace("’", "'")):
            verb = match.group(1).lower()
            tool = ACTION.get(verb, "escalate")
            if not any(tool in name for name in done):
                return f"said {match.group(0)!r}; no {tool} tool ran"
    return None
# --8<-- [end:claims]


def repeated_call(conversation: Conversation) -> str | None:
    """The same tool with the same arguments, more than once."""
    seen = Counter(json.dumps([u.name, u.input], sort_keys=True)
                   for u in conversation.tool_uses())
    for key, times in seen.items():
        if times > 1:
            name, arguments = json.loads(key)
            return f"called {name}({arguments}) {times} times"
    return None


# --8<-- [start:failure]
@dataclass(frozen=True)
class Failure:
    id: str
    name: str
    chapter: int
    mast: str         # nearest MAST failure mode, if any
    detect: Detector | None  # None: the trace cannot show it
    check: str        # what does find it
# --8<-- [end:failure]


# --8<-- [start:in-trace]
IN_TRACE = (
    Failure("stopped", "Stopped before the work was done", 1,
            "Premature termination", stopped_early, "stop reason"),
    Failure("huge-result", "A tool result that floods the context",
            3, "", huge_result, "result size"),
    Failure("gave-up", "Gave up after a tool error", 5,
            "", gave_up, "error, then end of turn"),
    Failure("unbacked", "Claimed an action no tool performed", 5,
            "Reasoning-action mismatch", unbacked_claim,
            "claims against tool calls"),
    Failure("repeated", "Repeated the same tool call", 8,
            "Step repetition", repeated_call, "identical calls"),
)
# --8<-- [end:in-trace]

# --8<-- [start:needs-record]
NEEDS_RECORD = (
    Failure("miscount", "Wrong answer over a large input", 2,
            "", None, "the true count, from code"),
    Failure("rule-broken", "An instruction not followed", 4,
            "Disobey task specification", None, "a check per rule"),
    Failure("stale", "Answered from a retired source", 6,
            "", None, "the current policy"),
    Failure("leak", "Used another customer's data", 7,
            "", None, "the account's own records"),
    Failure("forgot", "Lost an instruction across turns", 8,
            "Loss of conversation history", None,
            "the desk's record"),
)
# --8<-- [end:needs-record]

CATALOG = IN_TRACE + NEEDS_RECORD


def scan(conversation: Conversation) -> dict[str, str]:
    """Every failure the trace shows in one conversation, with evidence."""
    found = {}
    for failure in CATALOG:
        if failure.detect and (evidence := failure.detect(conversation)):
            found[failure.id] = evidence
    return found
