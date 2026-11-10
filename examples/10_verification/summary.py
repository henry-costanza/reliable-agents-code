"""Chapter 10: one table from every recording, for the figure.

    uv run python examples/10_verification/summary.py
"""

import json

from promise_case import RESULTS, promises, recorded

from agentkit import OPUS_5_5
from agentkit.messages import Usage

TARGET = RESULTS / "ch10_summary.json"


def price(run: dict) -> float:
    """Chapter 2's recording kept tokens, not dollars."""
    if "cost" in run:
        return run["cost"]
    return OPUS_5_5.cost(Usage(run["input_tokens"], run["output_tokens"]))


def row(case: str, arm: str, runs: list[dict], result: str) -> dict:
    gated = any(o.get("accepted") is not None for o in runs)
    refused = sum(bool(o.get("refusals")) for o in runs)
    return {"case": case, "arm": arm, "runs": len(runs),
            "refused": refused if gated else "--",
            "result": result,
            "cost": f"${sum(price(o) for o in runs):.2f}"}


def offers(runs: list[dict]) -> str:
    offered = sum(promises(o["message"]) for o in runs)
    return f"{offered} offered a later refund"


def build() -> list[dict]:
    first = recorded("ch10_verification")
    later = recorded("ch10_followup")

    def arm(case: str, name: str) -> list[dict]:
        return [o for o in first if (o["case"], o["arm"]) == (case, name)]

    def fixes(name: str) -> str:
        runs = arm("fix", name)
        return (f"{sum(o['fixed'] for o in runs)} fixed, "
                f"{sum(o['proven'] for o in runs)} proven")

    strict = [o for o in later if o["case"] == "promise"]
    missed = sum(not o["refusals"] for o in strict)
    ticket = arm("refund", "gated, ticket tool")
    plain_count = [o for o in recorded("ch02_hard")
                   if o["task"] == "count" and o["length"] == "128k"]
    numbered = [o for o in later if o["case"] == "numbered count"]
    gated_count = arm("count", "gated")
    return [
        row("Refund", "plain", arm("refund", "plain"),
            offers(arm("refund", "plain"))),
        row("Refund", "told", arm("refund", "told"),
            offers(arm("refund", "told"))),
        row("Refund", "receipt check", arm("refund", "gated"),
            offers(arm("refund", "gated"))),
        row("Refund", "promise check", strict,
            f"{missed} offered a later refund"),
        row("Refund", "receipt check, ticket tool", ticket,
            f"{offers(ticket)}; {sum(bool(o['tickets']) for o in ticket)} "
            "tickets"),
        row("Bug fix", "no test tool", arm("fix", "no tests"),
            fixes("no tests")),
        row("Bug fix", "test tool", arm("fix", "tests"), fixes("tests")),
        row("Bug fix", "test run check", arm("fix", "gated"), fixes("gated")),
        row("Count", "chapter 2: number only", plain_count,
            ", ".join(o["answer"] for o in plain_count)),
        row("Count", "entry ids, number only", numbered,
            ", ".join(o["answer"] for o in numbered)),
        row("Count", "entry ids, citation check", gated_count,
            ", ".join(str(o["count"]) for o in gated_count)),
    ]


def main() -> None:
    rows = build()
    TARGET.write_text(json.dumps({"rows": rows}, indent=2) + "\n",
                      encoding="utf-8")
    for line in rows:
        print(line)


if __name__ == "__main__":
    main()
