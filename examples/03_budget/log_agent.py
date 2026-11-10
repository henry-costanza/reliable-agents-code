"""Chapter 3: an agent that reads whole logs, and one that asks for counts."""

from team_logs import LOGS, QUESTION, SYSTEM, build_log

from agentkit import Budget, Provider, RunResult, Tool, run_agent

LOG_NAME = {"type": "string", "enum": list(LOGS)}


# --8<-- [start:read-log]
def read_log_tool() -> Tool:
    """Returns a whole log: about 38,000 tokens a call."""
    return Tool(
        "read_log",
        "Return the full text of one team log.",
        {"type": "object", "properties": {"name": LOG_NAME},
         "required": ["name"], "additionalProperties": False},
        lambda name: build_log(name),
    )
# --8<-- [end:read-log]


# --8<-- [start:count]
def count_tool() -> Tool:
    """Returns one number: a few tokens a call."""
    phrase = {"type": "string", "minLength": 3}
    return Tool(
        "count_in_log",
        "Count how many times a phrase occurs in one team log. "
        "Matching ignores case.",
        {"type": "object",
         "properties": {"name": LOG_NAME, "phrase": phrase},
         "required": ["name", "phrase"],
         "additionalProperties": False},
        lambda name, phrase: count_in(build_log(name), phrase),
    )


def count_in(text: str, phrase: str) -> int:
    return text.lower().count(phrase.lower())
# --8<-- [end:count]


def ask(provider: Provider, tool: Tool, budget: Budget | None = None) -> RunResult:
    return run_agent(provider, QUESTION, system=SYSTEM, tools=[tool], budget=budget)
