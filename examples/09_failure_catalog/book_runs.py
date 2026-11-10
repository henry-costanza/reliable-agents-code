"""Chapter 9: replay every recorded experiment in chapters 1 to 8, traced.

Each chapter's own code runs unchanged, against its own cassette, with a
`Tracer` in place of the provider. Nothing calls a live model. Each
replay also reports the failures that chapter's grader found by checking
the system of record, under the catalog's ids, so they can be counted
next to what the trace shows.
"""

import importlib
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import chapters  # noqa: F401  (chapters 1 to 8 on the import path)
from tracing import Call, Tracer

from agentkit.cassette import ReplayProvider

CASSETTES = Path(__file__).resolve().parents[2] / "fixtures" / "cassettes"


@dataclass
class Recording:
    chapter: int
    name: str
    calls: list[Call]
    graded: Counter  # catalog id -> runs the chapter's grader failed


def chapter(folder: str, module: str) -> ModuleType:
    """Import one module from another chapter's example folder."""
    assert any(p.endswith(folder) for p in sys.path), folder
    return importlib.import_module(module)


def replay(number: int, name: str, cassette: str,
           run: Callable, grade: Callable = lambda _: Counter()) -> Recording:
    provider = ReplayProvider(CASSETTES / cassette)
    tracer = Tracer(provider)
    outcome = run(tracer)
    assert provider.unused == 0 or number == 1, f"{cassette} not fully replayed"
    return Recording(number, name, tracer.calls, grade(outcome))


def failed(outcomes, failure: str, wrong: Callable) -> Counter:
    return Counter({failure: sum(1 for o in outcomes if wrong(o))})


def chapter_1() -> list[Recording]:
    invoices = chapter("01_agent_loop", "invoices")
    naive = chapter("01_agent_loop", "naive_agent")
    agentkit = importlib.import_module("agentkit")
    tools = [invoices.GET_INVOICE, invoices.INVOICE_TOTAL]
    task, system = invoices.TASK, invoices.SYSTEM
    return [
        replay(1, "one round trip", "ch01_agent_loop.json",
               lambda p: naive.one_round_trip(p, task, system=system, tools=tools)),
        replay(1, "agent loop", "ch01_agent_loop.json",
               lambda p: agentkit.run_agent(p, task, system=system, tools=tools)),
    ]


def chapter_2() -> list[Recording]:
    needle = chapter("02_context", "needle_experiment")
    hard = chapter("02_context", "hard_experiment")
    tool = chapter("02_context", "counting_tool")
    return [
        replay(2, "find one fact", "ch02_needle.json", needle.run),
        replay(2, "count and paraphrase", "ch02_hard.json", hard.run,
               lambda out: failed(out, "miscount", lambda o: o.verdict == "wrong")),
        replay(2, "count with a tool", "ch02_tool.json", tool.run),
    ]


def chapter_3() -> list[Recording]:
    budget = chapter("03_budget", "budget_experiment")
    return [
        replay(3, "whole logs", "ch03_whole_logs.json",
               lambda p: budget.run("whole logs", p),
               lambda out: failed(out, "miscount", lambda r: not r["right"])),
        replay(3, "counts", "ch03_counts.json", lambda p: budget.run("counts", p)),
    ]


def chapter_4() -> list[Recording]:
    experiment = chapter("04_instructions", "instructions_experiment")
    return [replay(4, "instruction variants", "ch04_instructions.json",
                   experiment.run,
                   lambda out: failed(out, "rule-broken", lambda o: not o["all"]))]


def chapter_5() -> list[Recording]:
    experiment = chapter("05_tools", "tools_experiment")
    return [replay(5, "poor and good tools", "ch05_tools.json", experiment.run,
                   lambda out: failed(out, "gave-up",
                                      lambda o: o["verdict"] == "no refund"))]


def chapter_6() -> list[Recording]:
    experiment = chapter("06_retrieval", "retrieval_experiment")
    return [replay(6, "three retrieval arms", "ch06_retrieval.json", experiment.run,
                   lambda out: failed(out, "stale",
                                      lambda o: o["verdict"] in ("hedged", "stale")))]


def chapter_7() -> list[Recording]:
    experiment = chapter("07_memory", "memory_experiment")
    leaked = "other customer's note"
    return [replay(7, "three memory arms", "ch07_memory.json", experiment.run,
                   lambda out: failed(out, "leak", lambda o: o["verdict"] == leaked))]


def chapter_8() -> list[Recording]:
    experiment = chapter("08_compaction", "compaction_experiment")
    lost = ("emailed during the move", "held for another reason")
    return [replay(8, "five compaction arms", "ch08_compaction.json", experiment.run,
                   lambda out: failed(out, "forgot", lambda o: o["verdict"] in lost))]


CHAPTERS = (chapter_1, chapter_2, chapter_3, chapter_4,
            chapter_5, chapter_6, chapter_7, chapter_8)


def replay_book() -> list[Recording]:
    return [recording for each in CHAPTERS for recording in each()]
