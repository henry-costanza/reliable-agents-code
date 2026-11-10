"""The one boundary every model call goes through.

A provider turns a neutral `Request` into a neutral `Response`. The agent loop,
the cassettes and the evals depend only on this protocol, so the same code runs
against a live model, a recorded cassette or a scripted test double.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from agentkit.messages import Request, Response

__all__ = ["Provider", "ProviderError", "ScriptedProvider"]


class ProviderError(Exception):
    """A model call failed. `retryable` says whether trying again may help."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class Provider(Protocol):
    name: str

    def complete(self, request: Request) -> Response: ...

    def describe(self) -> dict[str, Any]:
        """Settings worth recording next to a cassette (model, effort, ...)."""
        ...


class ScriptedProvider:
    """Returns canned responses in order and keeps every request it was given."""

    name = "scripted"

    def __init__(self, responses: Iterable[Response]) -> None:
        self._responses = list(responses)
        self.requests: list[Request] = []

    def complete(self, request: Request) -> Response:
        self.requests.append(request)
        if len(self.requests) > len(self._responses):
            raise ProviderError(
                f"scripted provider has {len(self._responses)} responses, "
                f"got request #{len(self.requests)}",
                retryable=False,
            )
        return self._responses[len(self.requests) - 1]

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name}
