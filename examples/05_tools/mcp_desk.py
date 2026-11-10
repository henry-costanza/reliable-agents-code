"""Chapter 5: the support desk's tools served over MCP, and a client for them.

`serve` puts agentkit tools behind an MCP server: tools/list sends their
names, descriptions and schemas, and tools/call runs them, reporting
failures as error results. `connect` is the other side: it lists a
server's tools and wraps each one as an agentkit Tool whose calls go over
MCP. The agent loop cannot tell the difference, and neither can the model.

Tested with mcp 2.3.0. Client connects to a Server in-process here; the
same Client accepts a URL or a command to launch, for a real deployment.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import mcp_types as types
from anyio.from_thread import start_blocking_portal
from desk import DeskError
from mcp import Client
from mcp.server.lowlevel import Server

from agentkit import Tool, ToolUse


# --8<-- [start:serve]
def serve(name: str, tools: list[Tool]) -> Server:
    """An MCP server that lists `tools` and runs them on request."""
    by_name = {tool.name: tool for tool in tools}

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[
            types.Tool(name=t.name, description=t.description,
                       input_schema=t.input_schema) for t in tools])

    async def call_tool(ctx, params) -> types.CallToolResult:
        tool = by_name[params.name]
        call = ToolUse("mcp", params.name, params.arguments or {})
        result = tool.run(call)  # checks the schema, catches errors
        text = types.TextContent(type="text", text=result.content)
        return types.CallToolResult(
            content=[text], is_error=result.is_error)

    return Server(name, on_list_tools=list_tools,
                  on_call_tool=call_tool)
# --8<-- [end:serve]


# --8<-- [start:connect]
@contextmanager
def connect(server: Server) -> Iterator[list[Tool]]:
    """The server's tools, as agentkit Tools that call it over MCP."""
    with start_blocking_portal() as portal:
        session = portal.wrap_async_context_manager(Client(server))
        with session as client:
            listed = portal.call(client.list_tools).tools
            yield [remote(portal, client, spec) for spec in listed]


def remote(portal, client: Client, spec: types.Tool) -> Tool:
    def call(**arguments) -> str:
        result = portal.call(client.call_tool, spec.name, arguments)
        text = "".join(part.text for part in result.content)
        if result.is_error:  # raise it again, as the server saw it
            raise DeskError(text.removeprefix("DeskError: "))
        return text

    schema = dict(spec.input_schema)
    return Tool(spec.name, spec.description or "", schema, call)
# --8<-- [end:connect]
