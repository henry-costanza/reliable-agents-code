"""Chapter 12: chapter 4's money rule, checked on every write.

Chapter 4 checked the project's rules after the run, and found the agent
had broken them because nobody told it. Here the same check runs inside the
loop: a write to the billing code that divides money is refused, with the
rule as the reason. The agent gets no instruction file at all.
"""

import ast

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from checks import _integer_money
from guards import guard
from instructions import system_prompt
from mini_repo import FILES, TASKS, workspace_tools

from agentkit import Budget, Provider, RunResult, run_agent

BILLING = "invoices/totals.py"


# --8<-- [start:money]
def money_check(arguments: dict) -> str | None:
    if arguments["path"] != BILLING:
        return None
    try:
        tree = ast.parse(arguments["content"])
    except SyntaxError as error:
        return f"{BILLING} does not parse: {error}."
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and not _integer_money(node)):
            return (f"{node.name} uses /, float() or a float. In "
                    "this project money is an integer number of "
                    "cents: use // and say in the docstring how it "
                    "rounds.")
    return None
# --8<-- [end:money]


def attempt(provider: Provider, task: str, budget: Budget | None = None
            ) -> tuple[RunResult, dict[str, str], list]:
    """Chapter 4's run with no instructions, and the rule as a check."""
    files, refusals = dict(FILES), []
    tools = [guard(t, money_check, refusals) if t.name == "write_file"
             else t for t in workspace_tools(files)]
    result = run_agent(provider, TASKS[task], system=system_prompt(None),
                       tools=tools, max_steps=15, budget=budget)
    return result, files, refusals
