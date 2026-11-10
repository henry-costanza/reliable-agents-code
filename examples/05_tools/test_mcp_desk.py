"""Chapter 5: tools served over MCP look and behave like local ones."""

import pytest
from desk import Desk
from desk_tools import good_tools, poor_tools
from mcp_desk import connect, serve

from agentkit import ToolUse

CALLS = {
    good_tools: [
        ("find_customers", {"name": "orion"}),
        ("list_invoices", {"customer_id": "CUS-104", "month": "2026-10"}),
        ("get_invoice", {"invoice_id": "INV-9"}),
        ("refund_invoice", {"invoice_id": "INV-2207", "amount_cents": 920_000}),
        ("refund_invoice", {"invoice_id": "INV-2207", "amount_cents": 9200}),
        ("list_invoices", {"customer_id": "CUS-104", "month": "Oct"}),
    ],
    poor_tools: [
        ("search", {"query": "Orion"}),
        ("get", {"id": "INV-9"}),
        ("refund", {"id": "INV-2207", "amount": 9200}),
        ("refund", {"id": "INV-2207", "amount": 92}),
    ],
}


# --8<-- [start:mcp-test]
@pytest.mark.parametrize("make", [good_tools, poor_tools])
def test_mcp_tools_match_local_tools(make):
    local_desk, remote_desk = Desk(), Desk()
    local = {t.name: t for t in make(local_desk)}
    with connect(serve("desk", make(remote_desk))) as tools:
        assert [t.spec for t in tools] == [t.spec for t in local.values()]
        remote = {t.name: t for t in tools}
        for name, arguments in CALLS[make]:
            call = ToolUse("t1", name, arguments)
            assert remote[name].run(call) == local[name].run(call)
    assert remote_desk.refunds == local_desk.refunds
# --8<-- [end:mcp-test]
