"""Chapter 4: three ways to brief an agent on Brindle's billing library."""

BASE = (
    "You are a coding agent working on brindle-billing, a Python "
    "project. Use the tools to read and change files. When you are "
    "done, say so briefly."
)

# --8<-- [start:vague]
VAGUE = """\
# AGENTS.md

- Follow the project's conventions.
- Write good tests for new code.
- Keep the changelog up to date.
- Be careful with money.
"""
# --8<-- [end:vague]

# --8<-- [start:specific]
SPECIFIC = """\
# AGENTS.md

- Money is an int number of cents. Never return float or dollars;
  divide with // and say in the docstring that it rounds down.
- Every new function gets a test in tests/unit/test_<module>.py,
  named test_<function>_<case>, e.g. test_total_due_after_payment.
- Every new public function gets one line under "## Unreleased" in
  CHANGELOG.md: "- <function>: <what it does>."
"""
# --8<-- [end:specific]

VARIANTS = {"none": None, "vague": VAGUE, "specific": SPECIFIC}


# --8<-- [start:prompt]
def system_prompt(agents_md: str | None) -> str:
    """What a coding agent sends: base prompt plus AGENTS.md."""
    if agents_md is None:
        return BASE
    header = "Project instructions (AGENTS.md):"
    return f"{BASE}\n\n{header}\n\n{agents_md}"
# --8<-- [end:prompt]
