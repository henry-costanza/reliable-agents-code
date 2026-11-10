"""Provider adapter for the Anthropic Messages API (`anthropic` SDK 2.x).

Choices made here, so the rest of agentkit does not have to know them:

- The model and the effort level are set explicitly. On Claude Opus 5.5
  thinking cannot be switched off; effort is the only control.
- Server-side refusal fallback is on by default. When the requested model
  declines, the API re-runs the request on a fallback model in the same call.
  `Response.fell_back` reports when that happened.
- Blocks the loop does not understand (thinking, for example) come back as
  `Opaque` and are sent back unchanged on the next request.
"""

from __future__ import annotations

from typing import Any

import anthropic

from agentkit.messages import (
    Message,
    Opaque,
    Request,
    Response,
    StopReason,
    Text,
    ToolResult,
    ToolUse,
    Usage,
)
from agentkit.provider import ProviderError

__all__ = ["AnthropicProvider", "DEFAULT_MODEL", "DEFAULT_EFFORT", "FALLBACK_BETA", "from_api_message", "history_blocks", "to_api_message"]

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
RETRYABLE_STATUS = {408, 409, 429}


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = DEFAULT_EFFORT,
        fallbacks: bool = True,
        client: Any = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.fallbacks = fallbacks
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = anthropic.Anthropic()
        return self._client

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "effort": self.effort,
            "fallbacks": self.fallbacks,
            "sdk": anthropic.__version__,
        }

    def request_params(self, request: Request) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "messages": [to_api_message(m) for m in request.messages],
            "output_config": {"effort": self.effort},
        }
        if request.system:
            params["system"] = request.system
        if request.tools:
            params["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in request.tools
            ]
        if self.fallbacks:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def complete(self, request: Request) -> Response:
        try:
            message = self.client.beta.messages.create(**self.request_params(request))
        except anthropic.APIStatusError as error:
            retryable = error.status_code in RETRYABLE_STATUS or error.status_code >= 500
            raise ProviderError(
                f"anthropic API error {error.status_code}: {error.message}", retryable=retryable
            ) from error
        except anthropic.APIConnectionError as error:
            raise ProviderError(f"anthropic connection error: {error}", retryable=True) from error
        return from_api_message(message)


def to_api_message(message: Message) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for block in message.content:
        match block:
            case Text(text):
                content.append({"type": "text", "text": text})
            case ToolUse(id, name, input):
                content.append({"type": "tool_use", "id": id, "name": name, "input": input})
            case ToolResult(tool_use_id, text, is_error):
                content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": text,
                        "is_error": is_error,
                    }
                )
            case Opaque("anthropic", data):
                content.append(data)
            case Opaque():
                pass  # another provider's internal block; this API cannot read it
    return {"role": message.role, "content": content}


def history_blocks(content: list[Any]) -> list[Any]:
    """The blocks of a reply that belong in the history sent back next turn.

    After a fallback, only text blocks from before the last `fallback` marker
    are echoed; everything after it is the fallback model's own reply. The
    marker itself is an audit note and is dropped.
    """
    boundary = max((i for i, b in enumerate(content) if b.type == "fallback"), default=None)
    if boundary is None:
        return content
    kept = [b for b in content[:boundary] if b.type == "text"]
    return kept + [b for b in content[boundary + 1 :] if b.type != "fallback"]


def from_api_message(message: Any) -> Response:
    blocks: list[Any] = []
    for block in history_blocks(list(message.content)):
        if block.type == "text":
            blocks.append(Text(block.text))
        elif block.type == "tool_use":
            blocks.append(ToolUse(block.id, block.name, dict(block.input)))
        else:
            data = block.model_dump(mode="json", by_alias=True, exclude_none=True)
            blocks.append(Opaque("anthropic", data))

    try:
        stop_reason = StopReason(message.stop_reason)
    except ValueError:
        raise ProviderError(f"unknown stop reason {message.stop_reason!r}", retryable=False)

    usage = message.usage
    iterations = getattr(usage, "iterations", None) or []
    return Response(
        message=Message("assistant", tuple(blocks)),
        stop_reason=stop_reason,
        usage=Usage(
            usage.input_tokens or 0,
            usage.output_tokens or 0,
            usage.cache_read_input_tokens or 0,
            usage.cache_creation_input_tokens or 0,
        ),
        model=message.model,
        fell_back=any(i.type == "fallback_message" for i in iterations),
    )
