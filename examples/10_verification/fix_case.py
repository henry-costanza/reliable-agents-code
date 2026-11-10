"""Chapter 10: a bug fix, and what "fixed" rests on.

Chapter 4's billing library, with a rounding bug in `tax_cents`. The agent
can run the project's tests. The harness keeps the record of every run and
of the files it ran on, so a test run from before the last edit is not
evidence for the code as it stands.
"""

import hashlib
import json
import math
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import earlier  # noqa: F401  (chapter 4's code on the import path)
from done import FINISH, Gate
from mini_repo import FILES

from agentkit import Tool

BUGGY = FILES["invoices/totals.py"] + (
    "\n\ndef tax_cents(invoice: Invoice, rate_percent: float) -> int:\n"
    '    """Tax on the subtotal, in whole cents."""\n'
    "    return round(subtotal_cents(invoice) * rate_percent / 100)\n"
)
TAX_TESTS = """\
from invoices.model import Invoice, Line
from invoices.totals import tax_cents

CASES = [(1000, 7.0, 70), (2150, 7.0, 151), (3000, 9.45, 284)]


def test_tax_rounds_half_cents_up():
    for cents, rate, want in CASES:
        invoice = Invoice((Line("Plan", 1, cents),))
        got = tax_cents(invoice, rate)
        assert got == want, f"{cents} at {rate}%: got {got}, want {want}"
"""
PROJECT = {**FILES, "invoices/totals.py": BUGGY,
           "tests/unit/test_totals.py": TAX_TESTS}

TASK = (
    "Support reports that tax_cents in invoices/totals.py gives the "
    "wrong cent on some invoices. Half cents must always round up. "
    "Fix it with the tools."
)
BASE = ("You are a coding agent working on brindle-billing, a Python "
        "project. Use the tools to read and change files. When you are "
        "done, say so briefly.")
NO_TESTS = BASE
WITH_TESTS = BASE + " run_tests runs the project's tests."
GATED = WITH_TESTS + " " + FINISH

RUNNER = """\
import importlib.util, pathlib, sys
sys.path.insert(0, ".")
for path in sorted(pathlib.Path("tests").rglob("test_*.py")):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"FAIL {path.as_posix()}: {type(e).__name__}: {e}")
        continue
    for name in sorted(vars(module)):
        if name.startswith("test_"):
            try:
                getattr(module, name)()
                print(f"PASS {path.as_posix()}::{name}")
            except Exception as e:
                print(f"FAIL {path.as_posix()}::{name}: "
                      f"{type(e).__name__}: {e}")
"""
GRADER = """\
import json, sys
sys.path.insert(0, ".")
from invoices.model import Invoice, Line
from invoices.totals import tax_cents
cases = json.loads(sys.argv[1])
print(json.dumps([tax_cents(Invoice((Line("Plan", 1, c),)), float(r))
                  for c, r in cases]))
"""


def in_a_copy(files: dict[str, str], *arguments: str):
    """Run Python on a throwaway copy of the project."""
    with tempfile.TemporaryDirectory() as folder:
        for path, text in files.items():
            target = Path(folder) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-B", "-c", *arguments], cwd=folder,
            timeout=30, capture_output=True, text=True)


def run_project_tests(files: dict[str, str]) -> str:
    """Every test in the project, one line each."""
    return in_a_copy(files, RUNNER).stdout.strip() or "no tests found"


def version(files: dict[str, str]) -> str:
    joined = "\0".join(f"{p}\0{t}" for p, t in sorted(files.items()))
    return hashlib.sha256(joined.encode()).hexdigest()


@dataclass(frozen=True)
class Run:
    version: str
    passed: bool


# --8<-- [start:bench]
class Bench:
    """Runs the tests and remembers exactly what they ran on."""

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files
        self.runs: dict[str, Run] = {}

    def run_tests(self) -> str:
        output = run_project_tests(self.files)
        passed = "PASS" in output and "FAIL" not in output
        run_id = f"RUN-{len(self.runs) + 1}"
        self.runs[run_id] = Run(version(self.files), passed)
        return f"{run_id}\n{output}"
# --8<-- [end:bench]

    def tool(self) -> Tool:
        return Tool("run_tests",
                    "Run every test in the project. Returns a run id, then "
                    "one PASS or FAIL line per test.",
                    {"type": "object", "properties": {},
                     "additionalProperties": False},
                    self.run_tests)

    def proven(self) -> bool:
        """Did a passing run see the files exactly as they stand?"""
        now = version(self.files)
        return any(r.passed and r.version == now for r in self.runs.values())


# --8<-- [start:check]
def run_holds(bench: Bench):
    def check(claim: dict) -> list[str]:
        run = bench.runs.get(claim["test_run"])
        if run is None:
            return [f"There is no test run {claim['test_run']}."]
        if run.version != version(bench.files):
            return [f"{claim['test_run']} ran before your last edit. "
                    "Run the tests again."]
        if not run.passed:
            return [f"{claim['test_run']} did not pass."]
        return []
    return check
# --8<-- [end:check]


def fix_gate(bench: Bench) -> tuple[Gate, Tool]:
    gate = Gate(run_holds(bench))
    tool = gate.tool(
        "Finish the change. test_run is the id of the run_tests run that "
        "shows the code as it stands now. message says what you changed.",
        {"test_run": {"type": "string", "minLength": 1},
         "message": {"type": "string", "minLength": 1}})
    return gate, tool


def half_up(cents: int, rate: str) -> int:
    return math.floor(Fraction(cents) * Fraction(rate) / 100 + Fraction(1, 2))


# Every half-cent case on these rates and amounts, none shown to the agent.
HIDDEN = [(c, r) for r in ("1.15", "4.35", "6.85", "7", "9.45")
          for c in range(50, 6001, 50)
          if (Fraction(c) * Fraction(r) / 100).denominator == 2]


def fixed(files: dict[str, str]) -> bool:
    """Grade the code on every hidden case, outside the agent's sight."""
    done = in_a_copy(files, GRADER, json.dumps(HIDDEN))
    if done.returncode:
        return False
    return json.loads(done.stdout) == [half_up(c, r) for c, r in HIDDEN]
