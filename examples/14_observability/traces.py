"""Chapter 14: one trace per conversation, and what each one cost.

A trace keeps, for every model call, the tokens by kind; for every tool
call, whether it worked, failed or was refused by a guardrail; and what the
conversation left behind: requests for a person, or a handover. It is built
after the run from chapter 9's tracer and the run's own messages, so no
chapter's code has to change.
"""

import json
from dataclasses import asdict, dataclass

import prior_chapters  # noqa: F401  (earlier chapters on the import path)
from tracing import Call

from agentkit import Prices, RunResult
from agentkit.anthropic_provider import AnthropicProvider
from agentkit.messages import Request, ToolResult, ToolUse


# --8<-- [start:trace]
@dataclass
class Trace:
    """One conversation, as the dashboard sees it."""

    conversation: str
    model: str
    customer: str
    calls: list[dict]  # tokens by kind, model, stop reason
    tools: list[dict]  # name, and "ok", "error" or "refused"
    requests: int      # refund requests waiting for a person
    handed_over: bool  # no reply accepted: a person takes over
    cost: float

    def line(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)
# --8<-- [end:trace]


def model_call(call: Call) -> dict:
    usage = call.response.usage
    return {"input": usage.input_tokens,
            "cache_read": usage.cache_read_input_tokens,
            "cache_write": usage.cache_creation_input_tokens,
            "output": usage.output_tokens,
            "model": call.response.model,
            "fell_back": call.response.fell_back,
            "stop": call.response.stop_reason.value}


def tool_calls(result: RunResult) -> list[dict]:
    """Each tool call and how it ended, read from the messages."""
    ended = {b.tool_use_id: b for m in result.messages
             for b in m.content if isinstance(b, ToolResult)}
    found = []
    for use in [b for m in result.messages for b in m.content
                if isinstance(b, ToolUse)]:
        end = ended.get(use.id)
        if end is None or not end.is_error:
            outcome = "ok"
        elif str(end.content).startswith("Blocked:"):
            outcome = "refused"
        else:
            outcome = "error"
        found.append({"name": use.name, "outcome": outcome})
    return found


# --8<-- [start:record]
def record(conversation: str, customer: str, calls: list[Call],
           result: RunResult, requests: int, handed_over: bool,
           prices: Prices) -> Trace:
    model = calls[0].response.model if calls else ""
    return Trace(conversation, model, customer,
                 [model_call(c) for c in calls], tool_calls(result),
                 requests, handed_over,
                 round(prices.cost(result.usage), 6))
# --8<-- [end:record]


def read(lines: str) -> list[Trace]:
    return [Trace(**json.loads(line)) for line in lines.splitlines()
            if line.strip()]


# --8<-- [start:kinds]
def prompt(call: dict) -> int:
    return call["input"] + call["cache_read"] + call["cache_write"]


def tokens_by_kind(trace: Trace) -> dict[str, int]:
    """Each prompt's tokens: new, carried over, or cached."""
    kinds = dict.fromkeys(["new", "carried", "cache read",
                           "cache write", "output"], 0)
    before = 0  # the previous call's prompt starts this one
    for call in trace.calls:
        full = call["input"]
        again = min(full, max(0, before - call["cache_read"]))
        kinds["carried"] += again
        kinds["new"] += full - again
        kinds["cache read"] += call["cache_read"]
        kinds["cache write"] += call["cache_write"]
        kinds["output"] += call["output"]
        before = prompt(call)
    return kinds
# --8<-- [end:kinds]


def dollars_by_kind(trace: Trace, prices: Prices) -> dict[str, float]:
    tokens = tokens_by_kind(trace)
    read = prices.input if prices.cache_read is None else prices.cache_read
    write = (prices.input if prices.cache_write is None
             else prices.cache_write)
    per_million = {"new": prices.input, "carried": prices.input,
                   "cache read": read, "cache write": write,
                   "output": prices.output}
    return {kind: tokens[kind] * per_million[kind] / 1_000_000
            for kind in tokens}


# --8<-- [start:caching]
class CachingProvider(AnthropicProvider):
    """The same provider, asking the API to cache prompts."""

    def request_params(self, request: Request) -> dict:
        params = super().request_params(request)
        mark = {"type": "ephemeral"}  # kept five minutes
        if request.system:  # tools and instructions, shared by all
            block = {"type": "text", "text": request.system}
            params["system"] = [{**block, "cache_control": mark}]
        params["cache_control"] = mark  # and the conversation so far
        return params
# --8<-- [end:caching]
