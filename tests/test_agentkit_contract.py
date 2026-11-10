"""Layer 2: agentkit's public API must match its frozen snapshot.

If this fails and the change is intended: write a decision record in
docs/adr/, bump agentkit.__version__ if the change breaks callers, then run
`uv run python -m agentkit._contract --write` from .
"""

import importlib
import json

import agentkit
from agentkit._contract import MODULES, describe, render, snapshot_path

HOW_TO_UPDATE = (
    "agentkit's public API changed. If that is intended, add an ADR, bump __version__ "
    "for breaking changes, and rerun: uv run python -m agentkit._contract --write"
)


def test_public_api_matches_the_frozen_snapshot():
    path = snapshot_path()
    assert path.is_file(), f"{path.name} is missing. {HOW_TO_UPDATE}"
    assert render(describe()) == path.read_text(encoding="utf-8"), HOW_TO_UPDATE


def test_snapshot_is_for_this_version():
    data = json.loads(snapshot_path().read_text(encoding="utf-8"))
    assert data["version"] == agentkit.__version__


def test_every_exported_name_exists():
    for name in agentkit.__all__:
        assert hasattr(agentkit, name), name
    for module_name in MODULES:
        module = importlib.import_module(f"agentkit.{module_name}")
        for name in module.__all__:
            assert hasattr(module, name), f"agentkit.{module_name}.{name}"


def test_describe_is_stable_across_calls():
    assert render(describe()) == render(describe())
