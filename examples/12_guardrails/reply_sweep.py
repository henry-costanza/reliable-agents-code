"""Chapter 12: the reply check, run over chapter 11's recorded desk replies.

Before Brindle turned the check on, it replayed the 140 desk runs of its
evaluation and asked which replies the check would have refused. The
replay costs nothing, and the tools run again, so the ledger sees exactly
what each recorded run saw.
"""

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
import eval_experiment as evaluation
from golden import DESK_TASKS
from guards import Ledger, amount_problems

from agentkit.cassette import ReplayProvider


# --8<-- [start:sweep]
def sweep() -> list[dict]:
    """Every recorded desk reply, with what the reply check says."""
    found = []
    for agent in evaluation.AGENTS:
        provider = ReplayProvider(evaluation.cassette(agent))
        for task in DESK_TASKS:
            for number in range(evaluation.TRIALS):
                ledger = Ledger()

                def watched(desk, tools=agent.desk_tools,
                            ledger=ledger):
                    return [ledger.watch(t) for t in tools(desk)]
                attempt = task.run(provider, watched)
                reply = attempt.result.final_text.strip()
                found.append({
                    "agent": agent.name, "task": task.name,
                    "verdict": attempt.verdict, "reply": reply,
                    "problems": amount_problems(reply, ledger)})
    return found
# --8<-- [end:sweep]
