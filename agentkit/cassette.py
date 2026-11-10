"""Record model responses once, replay them offline forever after.

`open_provider(path)` returns the provider a test or example should use. The
mode comes from the `AGENTKIT_MODE` environment variable:

- `replay` (default): answer from the cassette file. No network, no API key.
  A request that differs from the recording raises `CassetteMismatch` with a
  diff; it never falls through to a live call.
- `record`: call the live model and write every request and response to the
  cassette, replacing what was there.
- `live`: call the live model and record nothing.

Recording happens at the provider boundary, not over HTTP, so headers and API
keys never reach a cassette. Re-record only on purpose, in a reviewed commit.

A cassette normally stores each request in full, so a mismatch shows a diff.
With `store="fingerprint"` it keeps a SHA-256 fingerprint of each request and
a short summary instead. Use that when requests are large and are rebuilt
exactly by code, such as a generated 100k-token document: the cassette stays
small, and replay still fails on any change, only without a diff.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agentkit.messages import Request, Response, request_to_dict, response_from_dict, response_to_dict
from agentkit.provider import Provider

__all__ = [
    "MODES",
    "STORES",
    "CassetteMismatch",
    "ReplayProvider",
    "RecordingProvider",
    "current_mode",
    "open_provider",
    "request_fingerprint",
]

MODES = ("replay", "record", "live")
STORES = ("full", "fingerprint")
FORMAT = 1


class CassetteMismatch(Exception):
    """Replay was asked for something that was not recorded."""


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def request_fingerprint(request: Request) -> str:
    """SHA-256 of the request's canonical JSON: equal requests, equal fingerprints."""
    return hashlib.sha256(_dump(request_to_dict(request)).encode("utf-8")).hexdigest()


def _summary(request: Request) -> dict[str, Any]:
    """Enough of a large request to recognise it in a cassette or an error."""
    last = request.messages[-1].text if request.messages else ""
    return {
        "messages": len(request.messages),
        "chars": sum(len(m.text) for m in request.messages),
        "last_message_end": last[-120:],
    }


class ReplayProvider:
    """Answers each request with the next recorded response, if the request matches."""

    name = "replay"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise CassetteMismatch(
                f"{self.path}: cassette not found; record it with AGENTKIT_MODE=record"
            )
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.recorded_with: dict[str, Any] = data.get("recorded_with", {})
        self._interactions: list[dict[str, Any]] = data["interactions"]
        self._next = 0

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name, "cassette": self.path.name, **self.recorded_with}

    def complete(self, request: Request) -> Response:
        number = self._next + 1
        if self._next >= len(self._interactions):
            raise CassetteMismatch(
                f"{self.path.name}: request #{number} was not recorded "
                f"(the cassette holds {len(self._interactions)}); re-record with AGENTKIT_MODE=record"
            )
        recorded = self._interactions[self._next]
        if "request_fingerprint" in recorded:
            if request_fingerprint(request) != recorded["request_fingerprint"]:
                raise CassetteMismatch(
                    f"{self.path.name}: request #{number} differs from the recording "
                    "(fingerprints differ; only a summary was stored)\n"
                    f"recorded:  {json.dumps(recorded.get('request_summary'), ensure_ascii=False)}\n"
                    f"requested: {json.dumps(_summary(request), ensure_ascii=False)}"
                )
            self._next += 1
            return response_from_dict(recorded["response"])
        expected = recorded["request"]
        actual = request_to_dict(request)
        if actual != expected:
            diff = "".join(
                difflib.unified_diff(
                    _dump(expected).splitlines(keepends=True),
                    _dump(actual).splitlines(keepends=True),
                    "recorded",
                    "requested",
                )
            )
            raise CassetteMismatch(f"{self.path.name}: request #{number} differs\n{diff}")
        self._next += 1
        return response_from_dict(self._interactions[number - 1]["response"])

    @property
    def unused(self) -> int:
        """Recorded interactions that replay has not reached yet."""
        return len(self._interactions) - self._next


class RecordingProvider:
    """Passes requests to a live provider and writes each exchange to the cassette."""

    def __init__(self, inner: Provider, path: Path, store: str = "full") -> None:
        if store not in STORES:
            raise ValueError(f"store must be one of {', '.join(STORES)}, not {store!r}")
        self.inner = inner
        self.path = Path(path)
        self.name = inner.name
        self.store = store
        self._interactions: list[dict[str, Any]] = []

    def describe(self) -> dict[str, Any]:
        return self.inner.describe()

    def complete(self, request: Request) -> Response:
        response = self.inner.complete(request)
        if self.store == "fingerprint":
            recorded = {
                "request_fingerprint": request_fingerprint(request),
                "request_summary": _summary(request),
            }
        else:
            recorded = {"request": request_to_dict(request)}
        self._interactions.append({**recorded, "response": response_to_dict(response)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            _dump(
                {
                    "format": FORMAT,
                    "recorded_with": self.inner.describe(),
                    "interactions": self._interactions,
                }
            ),
            encoding="utf-8",
        )
        return response


def current_mode() -> str:
    mode = os.environ.get("AGENTKIT_MODE", "replay")
    if mode not in MODES:
        raise ValueError(f"AGENTKIT_MODE must be one of {', '.join(MODES)}, not {mode!r}")
    return mode


def _default_live() -> Provider:
    from dotenv import load_dotenv

    from agentkit.anthropic_provider import AnthropicProvider

    load_dotenv()
    return AnthropicProvider()


def open_provider(
    path: Path,
    mode: str | None = None,
    live: Callable[[], Provider] = _default_live,
    store: str = "full",
) -> Provider:
    """The provider for one cassette, in the mode `AGENTKIT_MODE` asks for.

    `store` applies when recording: "full" keeps each request, "fingerprint"
    keeps only its SHA-256 and a summary. Replay reads either kind.
    """
    mode = mode or current_mode()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, not {mode!r}")
    if mode == "replay":
        return ReplayProvider(path)
    if mode == "record":
        return RecordingProvider(live(), path, store)
    return live()
