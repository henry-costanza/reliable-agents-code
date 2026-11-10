"""Provider-neutral message types.

Every provider adapter converts to and from these types, so the agent loop,
the cassettes and the evals never see an SDK object. Blocks a provider needs
back unchanged (thinking blocks, for example) travel as `Opaque`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

__all__ = ["StopReason", "Text", "ToolUse", "ToolResult", "Opaque", "Block", "Message", "Usage", "ToolSpec", "Request", "Response", "block_to_dict", "block_from_dict", "message_to_dict", "message_from_dict", "request_to_dict", "response_to_dict", "response_from_dict"]


class StopReason(StrEnum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    PAUSE_TURN = "pause_turn"
    REFUSAL = "refusal"
    CONTEXT_WINDOW_EXCEEDED = "model_context_window_exceeded"


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class Opaque:
    """A block only its provider understands. Sent back exactly as received."""

    provider: str
    data: dict[str, Any]


Block = Text | ToolUse | ToolResult | Opaque


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: tuple[Block, ...]

    @classmethod
    def user(cls, text: str) -> Message:
        return cls("user", (Text(text),))

    @property
    def text(self) -> str:
        return "".join(block.text for block in self.content if isinstance(block, Text))

    @property
    def tool_uses(self) -> tuple[ToolUse, ...]:
        return tuple(block for block in self.content if isinstance(block, ToolUse))


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class Request:
    messages: tuple[Message, ...]
    system: str = ""
    tools: tuple[ToolSpec, ...] = ()
    max_tokens: int = 16000


@dataclass(frozen=True)
class Response:
    message: Message
    stop_reason: StopReason
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    fell_back: bool = False
    """True when a fallback model served the reply after the requested model declined."""


# --- Plain-dict form, used by cassettes ---------------------------------------


def block_to_dict(block: Block) -> dict[str, Any]:
    match block:
        case Text(text):
            return {"type": "text", "text": text}
        case ToolUse(id, name, input):
            return {"type": "tool_use", "id": id, "name": name, "input": input}
        case ToolResult(tool_use_id, content, is_error):
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
                "is_error": is_error,
            }
        case Opaque(provider, data):
            return {"type": "opaque", "provider": provider, "data": data}
    raise TypeError(f"not a block: {block!r}")


def block_from_dict(data: dict[str, Any]) -> Block:
    kind = data.get("type")
    if kind == "text":
        return Text(data["text"])
    if kind == "tool_use":
        return ToolUse(data["id"], data["name"], data["input"])
    if kind == "tool_result":
        return ToolResult(data["tool_use_id"], data["content"], data.get("is_error", False))
    if kind == "opaque":
        return Opaque(data["provider"], data["data"])
    raise ValueError(f"unknown block type {kind!r}")


def message_to_dict(message: Message) -> dict[str, Any]:
    return {"role": message.role, "content": [block_to_dict(b) for b in message.content]}


def message_from_dict(data: dict[str, Any]) -> Message:
    return Message(data["role"], tuple(block_from_dict(b) for b in data["content"]))


def request_to_dict(request: Request) -> dict[str, Any]:
    return {
        "system": request.system,
        "max_tokens": request.max_tokens,
        "tools": [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in request.tools
        ],
        "messages": [message_to_dict(m) for m in request.messages],
    }


def response_to_dict(response: Response) -> dict[str, Any]:
    usage = response.usage
    return {
        "message": message_to_dict(response.message),
        "stop_reason": response.stop_reason.value,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        },
        "model": response.model,
        "fell_back": response.fell_back,
    }


def response_from_dict(data: dict[str, Any]) -> Response:
    return Response(
        message=message_from_dict(data["message"]),
        stop_reason=StopReason(data["stop_reason"]),
        usage=Usage(**data["usage"]),
        model=data.get("model", ""),
        fell_back=data.get("fell_back", False),
    )
