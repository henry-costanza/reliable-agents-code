"""Chapter 10: a promise about the future, which no receipt can back.

The live runs made no false claim about the past. They did offer a refund
later, once the bank dispute closed. No tool and no policy says that.
"""

import json
import re
from pathlib import Path

from refund_case import LockedDesk, claims, receipts_hold, refund_gate

BOOK = Path(__file__).resolve().parents[2]
RESULTS = BOOK / "fixtures" / "results"


# --8<-- [start:offer]
OFFER = re.compile(
    r"\b(?:we(?:'ll| will| can(?!'t))|can be)\b"
    r"(?:[^.]|\.\d){0,40}\brefund", re.I)


def promises(message: str) -> bool:
    """Does the message offer a refund later?"""
    return bool(OFFER.search(message))
# --8<-- [end:offer]


# --8<-- [start:no-promises]
def no_promises(desk: LockedDesk):
    receipts = receipts_hold(desk)

    def check(claim: dict) -> list[str]:
        problems = receipts(claim)
        if promises(claim["message"]):
            problems.append(
                "Your message offers a refund later. No tool and "
                "no policy promises one. Say what is blocked, and "
                "stop there.")
        return problems
    return check
# --8<-- [end:no-promises]


def strict_gate(desk: LockedDesk) -> tuple:
    return refund_gate(desk, no_promises(desk))


def recorded(name: str) -> list[dict]:
    path = RESULTS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))["outcomes"]


# --8<-- [start:sweep]
def sweep_chapter_5() -> dict:
    """The new check on the replies chapter 5 recorded, for $0."""
    poor = [o for o in recorded("ch05_tools") if o["tools"] == "poor"]
    refused = [o for o in poor if "ticket" in claims(o["reply"])]
    return {"runs": len(poor),
            "no_refund": sum(not o["refunds"] for o in poor),
            "would_refuse": len(refused)}
# --8<-- [end:sweep]


def promises_by_arm() -> dict[str, int]:
    """How many recorded replies in each refund arm offer a refund later."""
    arms: dict[str, int] = {}
    for run in recorded("ch10_verification"):
        if run["case"] == "refund":
            arms[run["arm"]] = (arms.get(run["arm"], 0)
                                + promises(run["message"]))
    return arms
