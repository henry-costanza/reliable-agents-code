"""Chapter 4: did the agent follow the project's rules? Checked in code."""

import ast

RULES = ("function added", "integer money", "test in place", "changelog entry")


def _function(source: str, name: str) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _integer_money(function: ast.FunctionDef) -> bool:
    """No true division, no float() and no float literals."""
    for node in ast.walk(function):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return False
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "float":
            return False
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            return False
    return True


def _unreleased(changelog: str) -> list[str]:
    section = changelog.split("## Unreleased", 1)[-1].split("\n## ", 1)[0]
    return [line.strip() for line in section.splitlines() if line.strip()]


# --8<-- [start:check]
def check(files: dict[str, str], name: str) -> dict[str, bool]:
    """Which of the project's rules the change follows."""
    function = _function(files.get("invoices/totals.py", ""), name)
    tests = files.get("tests/unit/test_totals.py", "")
    entries = _unreleased(files.get("CHANGELOG.md", ""))
    added = function is not None
    line = f"- {name}:"
    return {
        "function added": added,
        "integer money": added and _integer_money(function),
        "test in place": f"def test_{name}_" in tests,
        "changelog entry": any(e.startswith(line) for e in entries),
    }
# --8<-- [end:check]
