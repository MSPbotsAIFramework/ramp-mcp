"""FastMCP factory and the request-scoped credential middleware.

Every request carries its own Ramp Client-Id/Client-Secret pair on HTTP
headers (SOP SS3.1). This module is the only place that reads those headers;
everything else gets credentials through ``client_factory()``, which reads
the per-request ContextVar set by ``RampCredentialsMiddleware``.
"""

import contextvars
from dataclasses import dataclass
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ramp_mcp.api_client import RampApiClient
from ramp_mcp.config import get_settings
from ramp_mcp.tools import bills, cards, reimbursements, transactions, users, vendors

MCP_PATH = "/mcp"
CLIENT_ID_HEADER = "x-ramp-client-id"
CLIENT_SECRET_HEADER = "x-ramp-client-secret"
CLIENT_ID_HEADER_NAME = "X-Ramp-Client-Id"
CLIENT_SECRET_HEADER_NAME = "X-Ramp-Client-Secret"

INSTRUCTIONS = (
    "Read-only access to a tenant's Ramp account (expense management and "
    "corporate cards): card/ACH transactions, physical and virtual cards, "
    "users, reimbursements, AP bills, and vendors. Typical flow: list a "
    "resource with filters (date range, department, user, state, ...), then "
    "use ramp_get_transaction for a single transaction's full detail. All "
    "list tools are paginated -- pass the previous result's next_cursor back "
    "in the cursor argument to get the next page; next_cursor is null on the "
    "last page. This connector has no write/mutating tools."
)


@dataclass(frozen=True)
class RampCredentials:
    client_id: str
    client_secret: str


_credentials: contextvars.ContextVar[Optional[RampCredentials]] = contextvars.ContextVar(
    "ramp_credentials", default=None
)


def client_factory() -> Optional[RampApiClient]:
    """Build a RampApiClient from this request's credentials, or None.

    Returning None (instead of raising) lets tools answer with the
    ``not_configured`` error envelope -- defensive only, since the live path
    already 401s in the middleware before any tool runs.
    """
    creds = _credentials.get()
    if creds is None:
        return None
    settings = get_settings()
    return RampApiClient(client_id=creds.client_id, client_secret=creds.client_secret, base_url=settings.ramp_base_url)


class RampCredentialsMiddleware:
    """Raw ASGI middleware (not BaseHTTPMiddleware, which buffers streaming
    responses and would break Streamable HTTP) that enforces SOP SS3.2/SS3.3:
    missing header -> 401 before any tool runs; present headers -> set the
    request-scoped ContextVar, always reset() in a finally.
    """

    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != MCP_PATH:
            await self._app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        client_id = headers.get(CLIENT_ID_HEADER)
        client_secret = headers.get(CLIENT_SECRET_HEADER)
        missing = [
            name
            for name, value in (
                (CLIENT_ID_HEADER_NAME, client_id),
                (CLIENT_SECRET_HEADER_NAME, client_secret),
            )
            if not value
        ]
        if missing:
            response = JSONResponse(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": f"missing required header(s): {', '.join(missing)}",
                        "retryable": False,
                    },
                    "missing_headers": missing,
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        token = _credentials.set(RampCredentials(client_id=client_id, client_secret=client_secret))
        try:
            await self._app(scope, receive, send)
        finally:
            _credentials.reset(token)


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        "ramp-mcp",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        streamable_http_path=MCP_PATH,
        # The service sits behind our reverse proxy / gateway, never exposed
        # directly to the internet, so the DNS-rebinding Host check (which
        # would otherwise reject the proxy's Host header) is safe to disable
        # (SOP SS7).
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    transactions.register(mcp, client_factory)
    cards.register(mcp, client_factory)
    users.register(mcp, client_factory)
    reimbursements.register(mcp, client_factory)
    bills.register(mcp, client_factory)
    vendors.register(mcp, client_factory)
    return mcp
