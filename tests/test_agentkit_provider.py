"""The Anthropic adapter, tested offline with real SDK response objects."""

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage

from agentkit.anthropic_provider import FALLBACK_BETA, AnthropicProvider, history_blocks
from agentkit.messages import (
    Message,
    Opaque,
    Request,
    StopReason,
    Text,
    ToolResult,
    ToolSpec,
    ToolUse,
)
from agentkit.provider import ProviderError, ScriptedProvider

THINKING = {"type": "thinking", "thinking": "", "signature": "sig"}


def api_message(content, stop_reason="end_turn", iterations=None, model="claude-opus-5-5"):
    usage = {
        "input_tokens": 12,
        "output_tokens": 7,
        "cache_read_input_tokens": 3,
        "cache_creation_input_tokens": None,
    }
    if iterations is not None:
        usage["iterations"] = iterations
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": usage,
        }
    )


class FakeClient:
    """Stands in for anthropic.Anthropic(): records params, returns or raises."""

    def __init__(self, result):
        self.result = result
        self.calls = []
        self.beta = self
        self.messages = self

    def create(self, **params):
        self.calls.append(params)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def provider_with(result, **kwargs):
    client = FakeClient(result)
    return AnthropicProvider(client=client, **kwargs), client


REQUEST = Request(
    (
        Message.user("What is 2 + 3?"),
        Message("assistant", (Opaque("anthropic", THINKING), ToolUse("tu_1", "add", {"a": 2, "b": 3}))),
        Message("user", (ToolResult("tu_1", "5"),)),
    ),
    system="Use the tools.",
    tools=(ToolSpec("add", "Add two numbers.", {"type": "object"}),),
)


def test_request_params_set_model_effort_and_fallback():
    provider, client = provider_with(api_message([{"type": "text", "text": "5"}]))
    provider.complete(REQUEST)
    params = client.calls[0]
    assert params["model"] == "claude-opus-5-5"
    assert params["output_config"] == {"effort": "medium"}
    assert params["betas"] == [FALLBACK_BETA]
    assert params["fallbacks"] == "default"
    assert params["system"] == "Use the tools."
    assert params["tools"][0]["name"] == "add"
    assert "temperature" not in params and "tool_choice" not in params


def test_fallback_can_be_turned_off():
    provider, client = provider_with(api_message([]), fallbacks=False)
    provider.complete(Request((Message.user("hi"),)))
    assert "fallbacks" not in client.calls[0] and "betas" not in client.calls[0]
    assert "system" not in client.calls[0] and "tools" not in client.calls[0]


def test_history_goes_out_in_api_shape_with_thinking_unchanged():
    provider, client = provider_with(api_message([]))
    provider.complete(REQUEST)
    assistant, tool_turn = client.calls[0]["messages"][1:]
    assert assistant["content"][0] == THINKING
    assert assistant["content"][1] == {"type": "tool_use", "id": "tu_1", "name": "add", "input": {"a": 2, "b": 3}}
    assert tool_turn["content"] == [
        {"type": "tool_result", "tool_use_id": "tu_1", "content": "5", "is_error": False}
    ]


def test_other_providers_opaque_blocks_are_not_sent():
    provider, client = provider_with(api_message([]))
    provider.complete(Request((Message("user", (Text("q"), Opaque("other", {"x": 1}))),)))
    assert client.calls[0]["messages"][0]["content"] == [{"type": "text", "text": "q"}]


def test_response_is_converted_to_neutral_types():
    content = [THINKING, {"type": "text", "text": "Adding."}, {"type": "tool_use", "id": "tu_9", "name": "add", "input": {"a": 1}}]
    provider, _ = provider_with(api_message(content, stop_reason="tool_use"))
    response = provider.complete(REQUEST)
    assert response.stop_reason is StopReason.TOOL_USE
    assert response.message.content == (
        Opaque("anthropic", THINKING),
        Text("Adding."),
        ToolUse("tu_9", "add", {"a": 1}),
    )
    assert (response.usage.input_tokens, response.usage.output_tokens) == (12, 7)
    assert response.usage.cache_read_input_tokens == 3
    assert response.usage.cache_creation_input_tokens == 0
    assert response.model == "claude-opus-5-5"
    assert response.fell_back is False


FALLBACK = {"type": "fallback", "from": {"model": "a"}, "to": {"model": "b"}, "trigger": {"type": "refusal"}}
SERVED_BY_FALLBACK = [
    {
        "type": "fallback_message",
        "model": "b",
        "input_tokens": 1,
        "output_tokens": 1,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
]


def test_fallback_reply_keeps_only_text_before_the_boundary():
    content = [
        THINKING,
        {"type": "text", "text": "Partial. "},
        {"type": "tool_use", "id": "tu_old", "name": "add", "input": {}},
        FALLBACK,
        THINKING,
        {"type": "text", "text": "Answer."},
    ]
    provider, _ = provider_with(api_message(content, iterations=SERVED_BY_FALLBACK, model="b"))
    response = provider.complete(REQUEST)
    assert response.message.content == (
        Text("Partial. "),
        Opaque("anthropic", THINKING),
        Text("Answer."),
    )
    assert response.fell_back is True
    assert response.model == "b"


def test_history_blocks_without_fallback_keeps_everything():
    message = api_message([THINKING, {"type": "text", "text": "x"}])
    assert [b.type for b in history_blocks(list(message.content))] == ["thinking", "text"]


def status_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (status_error(anthropic.RateLimitError, 429), True),
        (status_error(anthropic.InternalServerError, 500), True),
        (status_error(anthropic.BadRequestError, 400), False),
        (status_error(anthropic.AuthenticationError, 401), False),
    ],
)
def test_api_errors_become_provider_errors(error, retryable):
    provider, _ = provider_with(error)
    with pytest.raises(ProviderError) as caught:
        provider.complete(REQUEST)
    assert caught.value.retryable is retryable
    assert str(error.status_code) in str(caught.value)


def test_connection_errors_are_retryable():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    provider, _ = provider_with(anthropic.APIConnectionError(request=request))
    with pytest.raises(ProviderError) as caught:
        provider.complete(REQUEST)
    assert caught.value.retryable is True


def test_describe_names_model_and_effort():
    provider, _ = provider_with(None, effort="high")
    assert provider.describe() | {"sdk": "x"} == {
        "provider": "anthropic",
        "model": "claude-opus-5-5",
        "effort": "high",
        "fallbacks": True,
        "sdk": "x",
    }


def test_scripted_provider_replays_in_order_and_runs_out_loudly():
    from agentkit.messages import Response

    reply = Response(Message("assistant", (Text("ok"),)), StopReason.END_TURN)
    scripted = ScriptedProvider([reply])
    assert scripted.complete(REQUEST) is reply
    assert scripted.requests == [REQUEST]
    with pytest.raises(ProviderError, match="has 1 responses, got request #2"):
        scripted.complete(REQUEST)
