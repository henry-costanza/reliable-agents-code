"""Describe agentkit's public API as plain data, for the contract test.

    cd .
    uv run python -m agentkit._contract           # say whether the API matches the snapshot
    uv run python -m agentkit._contract --write   # rewrite the snapshot (needs an ADR first)
"""

from __future__ import annotations

import argparse
import enum
import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

import agentkit

MODULES = ("messages", "provider", "anthropic_provider", "cassette", "tools", "loop", "budget", "evals")


def snapshot_path(version: str = agentkit.__version__) -> Path:
    major, minor = version.split(".")[:2]
    return Path(__file__).with_name(f"api-v{major}.{minor}.json")


ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")


def _signature(obj: Any) -> str:
    try:
        return ADDRESS.sub("", str(inspect.signature(obj)))
    except (TypeError, ValueError):
        return "(?)"


def _member(value: Any) -> str:
    if isinstance(value, property):
        return "property"
    if isinstance(value, (classmethod, staticmethod)):
        return _signature(value.__func__)
    if callable(value):
        return _signature(value)
    return repr(value)


def describe_object(obj: Any) -> dict[str, Any]:
    if inspect.isclass(obj) and issubclass(obj, enum.Enum):
        return {"kind": "enum", "members": {m.name: m.value for m in obj}}
    if inspect.isclass(obj):
        members = {
            name: _member(value)
            for name, value in vars(obj).items()
            if not name.startswith("_") or name == "__init__"
        }
        fields = getattr(obj, "__dataclass_fields__", {})
        return {
            "kind": "class",
            "signature": _signature(obj),
            "bases": [b.__name__ for b in obj.__bases__],
            "fields": list(fields),
            "members": dict(sorted(members.items())),
        }
    if inspect.isfunction(obj):
        return {"kind": "function", "signature": _signature(obj)}
    return {"kind": "value", "value": repr(obj)}


def describe() -> dict[str, Any]:
    modules = {}
    for name in MODULES:
        module = importlib.import_module(f"agentkit.{name}")
        modules[name] = {item: describe_object(getattr(module, item)) for item in sorted(module.__all__)}
    return {"version": agentkit.__version__, "package": sorted(agentkit.__all__), "modules": modules}


def render(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or rewrite the agentkit API snapshot.")
    parser.add_argument("--write", action="store_true", help="rewrite the snapshot file")
    args = parser.parse_args()
    path = snapshot_path()
    current = render(describe())
    if args.write:
        path.write_text(current, encoding="utf-8")
        print(f"wrote {path.name}")
        return 0
    if path.is_file() and path.read_text(encoding="utf-8") == current:
        print(f"API matches {path.name}")
        return 0
    print(f"API differs from {path.name}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
