"""Chapter 1's opening failure: an agent that makes one round trip."""

from agentkit import Message, Provider, Request, Tool


# --8<-- [start:naive]
def one_round_trip(
    provider: Provider, prompt: str, *, system: str, tools: list[Tool]
) -> str:
    """Ask, run the tools asked for, ask again, return the text."""
    by_name = {tool.name: tool for tool in tools}
    specs = tuple(tool.spec for tool in tools)
    messages = [Message.user(prompt)]

    request = Request(tuple(messages), system, specs)
    first = provider.complete(request)
    messages.append(first.message)
    calls = first.message.tool_uses
    results = tuple(by_name[c.name].run(c) for c in calls)
    messages.append(Message("user", results))

    request = Request(tuple(messages), system, specs)
    second = provider.complete(request)
    return second.message.text
# --8<-- [end:naive]
