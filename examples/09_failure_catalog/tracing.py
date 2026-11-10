"""Chapter 9: record every model call, then group the calls into conversations.

`Tracer` wraps any provider and keeps each request with its reply. A
chapter's code does not change: it is handed the tracer instead of the
provider. `conversations` then rebuilds who said what to whom. A call
continues a conversation when its messages start with that conversation's
last request and reply; anything else starts a new one, such as a
compaction call, a subagent, or the first turn after compaction.
"""

from dataclasses import dataclass, field
from typing import Any

from agentkit import Provider
from agentkit.messages import Message, Request, Response, ToolResult, ToolUse


@dataclass(frozen=True)
class Call:
    request: Request
    response: Response


# --8<-- [start:tracer]
class Tracer:
    """A provider that passes each request on and keeps a copy."""

    name = "tracer"

    def __init__(self, inner: Provider) -> None:
        self.inner = inner
        self.calls: list[Call] = []

    def complete(self, request: Request) -> Response:
        response = self.inner.complete(request)
        self.calls.append(Call(request, response))
        return response

    def describe(self) -> dict[str, Any]:
        return self.inner.describe()
# --8<-- [end:tracer]


@dataclass
class Conversation:
    calls: list[Call] = field(default_factory=list)

    @property
    def last(self) -> Response:
        return self.calls[-1].response

    @property
    def system(self) -> str:
        return self.calls[0].request.system

    @property
    def messages(self) -> tuple[Message, ...]:
        """Everything said, the last reply included."""
        return self.calls[-1].request.messages + (self.last.message,)

    def continued_by(self, request: Request) -> bool:
        before = self.messages
        return (request.system == self.system
                and len(request.messages) > len(before)
                and request.messages[:len(before)] == before)

    def replies(self) -> list[str]:
        return [m.text for m in self.messages if m.role == "assistant"]

    def tool_uses(self) -> list[ToolUse]:
        return [b for m in self.messages for b in m.content
                if isinstance(b, ToolUse)]

    def tool_results(self) -> list[ToolResult]:
        return [b for m in self.messages for b in m.content
                if isinstance(b, ToolResult)]

    def succeeded(self) -> list[str]:
        """Names of the tool calls whose result was not an error."""
        failed = {r.tool_use_id for r in self.tool_results() if r.is_error}
        return [u.name for u in self.tool_uses() if u.id not in failed]


def conversations(calls: list[Call]) -> list[Conversation]:
    """Group calls into conversations, in the order they started."""
    found: list[Conversation] = []
    for call in calls:
        for conversation in reversed(found):
            if conversation.continued_by(call.request):
                conversation.calls.append(call)
                break
        else:
            found.append(Conversation([call]))
    return found
