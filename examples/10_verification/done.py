"""Chapter 10: "done" as a tool that can refuse.

The agent finishes by calling `report_done` with its evidence. Code checks
the evidence against records the agent cannot write. A refusal comes back
as a tool error, so the agent can try again with the agent loop unchanged.
A run that ends its turn without an accepted report has not finished.
"""

from collections.abc import Callable

from agentkit import Tool

Check = Callable[[dict], list[str]]

FINISH = ("Finish by calling report_done with your evidence. "
          "Nothing counts as finished until it is accepted.")


class Refused(Exception):
    """The evidence did not hold."""


# --8<-- [start:gate]
class Gate:
    """The only way to finish: a check that can say no."""

    def __init__(self, check: Check) -> None:
        self.check = check
        self.accepted: dict | None = None
        self.refusals: list[list[str]] = []

    def report_done(self, **claim) -> str:
        problems = self.check(claim)
        if problems:
            self.refusals.append(problems)
            raise Refused(" ".join(problems))
        self.accepted = claim
        return "Accepted. End your turn now."
# --8<-- [end:gate]

    def tool(self, description: str, properties: dict) -> Tool:
        schema = {"type": "object", "properties": properties,
                  "required": list(properties),
                  "additionalProperties": False}
        return Tool("report_done", description, schema, self.report_done)
