"""Missing-header 401 and per-request credential isolation (SOP SS3.2/SS3.3)."""

import asyncio
import json

from ramp_mcp.server import _credentials
from tests.conftest import mcp_request, parse_sse_or_json


def test_missing_header_returns_401_before_calling_ramp(client, monkeypatch):
    import ramp_mcp.api_client as api_client_module

    calls = []

    async def _record(self, *args, **kwargs):
        calls.append(args)
        raise AssertionError("Ramp must not be called when a required header is missing")

    monkeypatch.setattr(api_client_module.RampApiClient, "_authenticated_get", _record)

    response = mcp_request(client, "tools/call", {"name": "ramp_list_users", "arguments": {"options": {}}}, headers={"X-Ramp-Client-Secret": ""})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
    assert "X-Ramp-Client-Secret" in body["missing_headers"]
    assert calls == []


def test_both_headers_missing_names_both_in_body(client):
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 401
    body = response.json()
    assert set(body["missing_headers"]) == {"X-Ramp-Client-Id", "X-Ramp-Client-Secret"}


def test_concurrent_requests_with_different_credentials_do_not_cross_tenant(client, monkeypatch):
    import ramp_mcp.api_client as api_client_module

    seen_credentials: list[tuple[str, str]] = []

    async def _fake_get(self, path, params):
        # Record which credential pair this instance was constructed with,
        # then pause so two concurrent calls genuinely overlap in time.
        seen_credentials.append((self._client_id, self._client_secret))
        await asyncio.sleep(0.01)
        return {"data": [{"id": self._client_id}], "page": {"next": None}}

    monkeypatch.setattr(api_client_module.RampApiClient, "_authenticated_get", _fake_get)

    async def call(client_id: str, client_secret: str) -> dict:
        from starlette.testclient import TestClient

        # Each TestClient.post is sync; run both via asyncio.to_thread so they
        # genuinely overlap inside the ASGI app.
        def _do():
            return mcp_request(
                client,
                "tools/call",
                {"name": "ramp_list_users", "arguments": {"options": {}}},
                headers={"X-Ramp-Client-Id": client_id, "X-Ramp-Client-Secret": client_secret},
            )

        return await asyncio.to_thread(_do)

    async def run_both():
        return await asyncio.gather(call("tenant-a-id", "tenant-a-secret"), call("tenant-b-id", "tenant-b-secret"))

    responses = asyncio.run(run_both())
    for response in responses:
        assert response.status_code == 200

    results = [parse_sse_or_json(r)["result"] for r in responses]
    texts = [json.loads(r["content"][0]["text"]) for r in results]
    returned_ids = {item["items"][0]["id"] for item in texts}
    assert returned_ids == {"tenant-a-id", "tenant-b-id"}

    cache_keys = {api_client_module._token_cache_key(cid, secret) for cid, secret in seen_credentials}
    assert len(cache_keys) == 2

    # The ContextVar must not leak a value after both requests finished.
    assert _credentials.get() is None
