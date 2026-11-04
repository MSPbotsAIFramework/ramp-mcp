import pytest
from starlette.testclient import TestClient

from ramp_mcp.__main__ import build_app


@pytest.fixture()
def app():
    return build_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


HEADERS = {
    "X-Ramp-Client-Id": "test-client-id",
    "X-Ramp-Client-Secret": "test-client-secret",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def mcp_request(client: TestClient, method: str, params: dict | None = None, headers: dict | None = None, request_id: int = 1):
    body = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    merged_headers = dict(HEADERS)
    if headers is not None:
        merged_headers.update(headers)
    return client.post("/mcp", json=body, headers=merged_headers)


def parse_sse_or_json(response) -> dict:
    """The streamable-http transport may answer with a single SSE event or a
    plain JSON body depending on content negotiation; normalize to a dict."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        import json

        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:") :].strip())
        raise AssertionError(f"no data: line in SSE body: {response.text!r}")
    return response.json()
