import pytest

from agentkit.messages import (
    Message,
    Opaque,
    Request,
    Response,
    StopReason,
    Text,
    ToolResult,
    ToolSpec,
    ToolUse,
    Usage,
    block_from_dict,
    block_to_dict,
    request_to_dict,
    response_from_dict,
    response_to_dict,
)

BLOCKS = [
    Text("hi"),
    ToolUse("tu_1", "add", {"a": 1, "b": 2}),
    ToolResult("tu_1", "3"),
    ToolResult("tu_2", "boom", is_error=True),
    Opaque("anthropic", {"type": "thinking", "thinking": "", "signature": "sig"}),
]


@pytest.mark.parametrize("block", BLOCKS)
def test_blocks_round_trip(block):
    assert block_from_dict(block_to_dict(block)) == block


def test_unknown_block_type_is_an_error():
    with pytest.raises(ValueError, match="unknown block type 'image'"):
        block_from_dict({"type": "image"})


def test_response_round_trips():
    response = Response(
        Message("assistant", tuple(BLOCKS[:2])),
        StopReason.TOOL_USE,
        Usage(10, 5, 2, 1),
        model="m",
        fell_back=True,
    )
    assert response_from_dict(response_to_dict(response)) == response


def test_request_dict_is_plain_data():
    request = Request(
        (Message.user("q"),), system="s", tools=(ToolSpec("t", "d", {"type": "object"}),)
    )
    assert request_to_dict(request) == {
        "system": "s",
        "max_tokens": 16000,
        "tools": [{"name": "t", "description": "d", "input_schema": {"type": "object"}}],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "q"}]}],
    }


def test_usage_adds_up():
    assert Usage(1, 2, 3, 4) + Usage(10, 20, 30, 40) == Usage(11, 22, 33, 44)


def test_message_text_and_tool_uses():
    message = Message("assistant", (Text("a"), ToolUse("1", "t", {}), Text("b")))
    assert message.text == "ab"
    assert [u.name for u in message.tool_uses] == ["t"]


def test_new_stop_reason_is_known():
    assert StopReason("model_context_window_exceeded") is StopReason.CONTEXT_WINDOW_EXCEEDED
