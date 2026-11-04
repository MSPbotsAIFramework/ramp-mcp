"""tools/list snapshot and health independence (SOP SS10 minimal set)."""

from ramp_mcp.server import build_mcp
from tests.conftest import mcp_request, parse_sse_or_json


EXPECTED_TOOL_NAMES = {
    "ramp_list_transactions",
    "ramp_get_transaction",
    "ramp_list_cards",
    "ramp_list_users",
    "ramp_list_reimbursements",
    "ramp_list_bills",
    "ramp_list_vendors",
}


async def test_tools_list_returns_the_seven_v1_tools():
    mcp = build_mcp()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOL_NAMES
    for tool in tools:
        assert tool.description, f"{tool.name} has no description"
        assert tool.inputSchema, f"{tool.name} has no parameter schema"


def test_health_does_not_depend_on_ramp(client, monkeypatch):
    # Force any Ramp call to blow up -- /health must stay green regardless.
    import ramp_mcp.api_client as api_client_module

    async def _boom(self, *args, **kwargs):
        raise RuntimeError("Ramp is unreachable")

    monkeypatch.setattr(api_client_module.RampApiClient, "_authenticated_get", _boom)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tools_list_over_http_returns_seven_tools(client):
    response = mcp_request(client, "tools/list")
    assert response.status_code == 200
    payload = parse_sse_or_json(response)
    names = {t["name"] for t in payload["result"]["tools"]}
    assert names == EXPECTED_TOOL_NAMES
