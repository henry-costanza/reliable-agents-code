"""Chapter 14: numbers for one day of traces, and alerts between two days.

Cost alerts compare a high percentile, because a handful of expensive
conversations is what a change usually adds. Rate alerts use chapter 11's
exact test, so two refusals in twenty conversations do not wake anyone.
"""

import math

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from confidence import chance_of_drop
from traces import Trace, tokens_by_kind


def percentile(values: list[float], share: float) -> float:
    """Nearest rank: the smallest value at or above `share` of them."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


# --8<-- [start:day]
def day(traces: list[Trace]) -> dict:
    costs = [t.cost for t in traces]
    kinds = [tokens_by_kind(t) for t in traces]
    prompts = sum(k["new"] + k["carried"] + k["cache read"]
                  + k["cache write"] for k in kinds)
    return {
        "conversations": len(traces),
        "cost": round(sum(costs), 4),
        "median cost": percentile(costs, 0.5),
        "p95 cost": percentile(costs, 0.95),
        "carried at full price": sum(k["carried"]
                                     for k in kinds) / prompts,
        "read from cache": sum(k["cache read"]
                               for k in kinds) / prompts,
        "refused": sum(any(c["outcome"] == "refused" for c in t.tools)
                       for t in traces),
        "handed over": sum(t.handed_over for t in traces),
        "requests for a person": sum(t.requests for t in traces),
    }
# --8<-- [end:day]


# --8<-- [start:alerts]
COST_RISE = 1.5  # Brindle's choice: half again is worth a look
EVENTS = ("refused", "handed over")


def alerts(before: dict, today: dict) -> list[str]:
    found = []
    now, was = today["p95 cost"], before["p95 cost"]
    if now > COST_RISE * was:
        found.append(f"p95 cost per conversation ${now:.4f}"
                     f", was ${was:.4f}")
    for event in EVENTS:
        n, m = before["conversations"], today["conversations"]
        base, new = (n - before[event], n), (m - today[event], m)
        if chance_of_drop(base, new) < 0.05:
            found.append(f"{event}: {today[event]} of {m}, "
                         f"was {before[event]} of {n}")
    return found
# --8<-- [end:alerts]
