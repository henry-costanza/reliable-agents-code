"""Tools the model can call: a name, a JSON schema and a Python function.

Inputs are checked against the schema before the function runs, and every
failure comes back to the model as an error result instead of crashing the
loop or being silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from agentkit.messages import ToolResult, ToolSpec, ToolUse

__all__ = ["Tool"]

NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    function: Callable[..., Any]

    def __post_init__(self) -> None:
        if not NAME.match(self.name):
            raise ValueError(f"tool name {self.name!r} must match {NAME.pattern}")
        Draft202012Validator.check_schema(self.input_schema)

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.input_schema)

    def errors(self, arguments: dict[str, Any]) -> list[str]:
        """Schema violations in `arguments`, as readable messages."""
        validator = Draft202012Validator(self.input_schema)
        return sorted(
            f"{'/'.join(map(str, e.absolute_path)) or 'input'}: {e.message}"
            for e in validator.iter_errors(arguments)
        )

    def run(self, call: ToolUse) -> ToolResult:
        problems = self.errors(call.input)
        if problems:
            return ToolResult(call.id, "invalid input: " + "; ".join(problems), is_error=True)
        try:
            output = self.function(**call.input)
        except Exception as error:  # the model sees the failure and can recover
            return ToolResult(call.id, f"{type(error).__name__}: {error}", is_error=True)
        return ToolResult(call.id, str(output))
