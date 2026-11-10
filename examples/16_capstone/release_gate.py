"""Chapter 16: the release gate every new version of the desk must pass.

It reruns every recorded request from chapters 13 and 15, compares each
score with the last released desk (chapter 11's exact test), compares the
day's numbers (chapter 14's alerts), and scans every conversation for the
failures a trace can show (chapter 9). A drop that chance cannot explain
blocks the release. Everything else is listed for a person to read.
"""

import json
from pathlib import Path

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
import secure_desk
import team_desk
from confidence import compare
from dashboard import alerts, day
from traces import Trace

RESULTS = Path(__file__).resolve().parents[2] / "fixtures" / "results"

# --8<-- [start:tasks]
TASKS = {**secure_desk.TASKS,  # chapter 13: input a customer controls
         **{name: task for name, task in team_desk.TASKS.items()
            if name != "duplicate charge"}}  # chapter 15, one copy
# --8<-- [end:tasks]


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def released(model: str) -> tuple[dict, list[Trace]]:
    """Scores and traces of the last desks, as recorded."""
    rows = {**{f"chapter 13 desk | {k.split(' | ')[-1]}": v
               for k, v in load("ch13_summary.json")["rows"].items()
               if k.startswith(f"{model} | chapter 13 desk |")},
            **{f"one agent | {k.split(' | ')[-1]}": v
               for k, v in load("ch15_summary.json")["rows"].items()
               if k.startswith(f"{model} | one agent |")}}
    scores = {}
    for task in TASKS:
        desk = ("chapter 13 desk" if task in secure_desk.TASKS
                else "one agent")
        row = rows[f"{desk} | {task}"]
        scores[task] = (row["right"], row["runs"])
    lines = (RESULTS / "ch14_traces.jsonl").read_text(encoding="utf-8")
    traces = [Trace(**json.loads(line)) for line in lines.splitlines()]
    traces = [t for t in traces if t.conversation.startswith(
        f"{model} | chapter 13 desk, cached |")]
    traces += [Trace(**json.loads(o["trace"]))
               for o in load("ch15_team.json")["outcomes"]
               if o["model"] == model and o["shape"] == "one agent"
               and o["task"] in TASKS
               and o["task"] not in secure_desk.TASKS]
    return scores, traces


def scores(outcomes: list[dict]) -> dict[str, tuple[int, int]]:
    found: dict[str, tuple[int, int]] = {}
    for o in outcomes:
        right, runs = found.get(o["task"], (0, 0))
        found[o["task"]] = (right + (o["verdict"] == "right"), runs + 1)
    return found


# --8<-- [start:gate]
def gate(model: str, outcomes: list[dict]) -> dict[str, list[str]]:
    """block: unlikely to be chance. read: worth a person's look."""
    before, old_traces = released(model)
    after = scores(outcomes)
    found = compare(before, after)
    found["better"] = [t for t in after if after[t][0] / after[t][1]
                       > before[t][0] / before[t][1]]
    traces = [Trace(**json.loads(o["trace"])) for o in outcomes]
    found["read"] += alerts(day(old_traces), day(traces))
    found["read"] += [f"{o['task']} {o['trial']}: {name}: {evidence}"
                      for o in outcomes
                      for name, evidence in o["failures"].items()]
    return found
# --8<-- [end:gate]
