"""Per-request wrapper around Ramp's Developer API.

A new RampApiClient is constructed for every tool call from the credentials
read off that request's headers (server.py's ContextVar). Nothing here is
stored at module scope except the OAuth access-token cache, which is keyed by
a hash of the credential pair and carries its own expiry -- the one exception
the SOP allows (vendor-mcp-development SOP SS3.4).
"""

import asyncio
import hashlib
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from ramp_mcp.errors import RampApiError

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 30.0
_MAX_RETRIES = 3
_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_TOKEN_PATH = "/developer/v1/token"
_TOKEN_SCOPE = "transactions:read users:read cards:read reimbursements:read bills:read vendors:read"

# Keyed by sha256(client_id:client_secret) -> (access_token, monotonic expiry).
# A credential-fingerprinted, expiring cache is the one exception the SOP
# allows to "no cross-request caching" (SS3.4) -- it is never looked up or
# stored by anything other than this hash, so two tenants can never collide.
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _token_cache_key(client_id: str, client_secret: str) -> str:
    return hashlib.sha256(f"{client_id}:{client_secret}".encode("utf-8")).hexdigest()


def extract_next_cursor(next_url: Optional[str]) -> Optional[str]:
    """Pull the opaque ``start`` cursor out of a Ramp ``page.next`` URL."""
    if not next_url:
        return None
    query = parse_qs(urlparse(next_url).query)
    values = query.get("start")
    return values[0] if values else None


class RampApiClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")

    async def list_transactions(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._authenticated_get("/developer/v1/transactions", params)

    async def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        return await self._authenticated_get(f"/developer/v1/transactions/{transaction_id}", {})

    async def list_cards(self, card_type: str, params: dict[str, Any]) -> dict[str, Any]:
        path = "/developer/v1/cards/physical" if card_type == "physical" else "/developer/v1/cards/virtual"
        return await self._authenticated_get(path, params)

    async def list_users(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._authenticated_get("/developer/v1/users", params)

    async def list_reimbursements(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._authenticated_get("/developer/v1/reimbursements", params)

    async def list_bills(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._authenticated_get("/developer/v1/bills", params)

    async def list_vendors(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._authenticated_get("/developer/v1/vendors", params)

    # -- internals ---------------------------------------------------------

    async def _authenticated_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        timeout = httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=_READ_TIMEOUT, pool=_READ_TIMEOUT)
        # One httpx client per tool call, reused for both the (possible)
        # token exchange and the resource GET -- SOP SS5 "reuse within a
        # single request", never shared across requests/tenants.
        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as http:
            access_token = await self._get_access_token(http)
            resp = await self._send_with_retry(
                http,
                "GET",
                path,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.json()

    async def _get_access_token(self, http: httpx.AsyncClient) -> str:
        cache_key = _token_cache_key(self._client_id, self._client_secret)
        cached = _TOKEN_CACHE.get(cache_key)
        now = time.monotonic()
        if cached and cached[1] > now:
            return cached[0]

        resp = await self._send_with_retry(
            http,
            "POST",
            _TOKEN_PATH,
            auth=httpx.BasicAuth(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": _TOKEN_SCOPE},
        )
        body = resp.json()
        access_token: str = body["access_token"]
        expires_in = int(body.get("expires_in", 300))
        _TOKEN_CACHE[cache_key] = (access_token, now + max(expires_in - 60, 0))
        return access_token

    async def _send_with_retry(self, http: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await http.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                if attempt >= _MAX_RETRIES:
                    raise RampApiError(status_code=None, message=f"timed out calling Ramp: {exc}", trace_id=None) from exc
                await self._sleep_backoff(attempt, None)
                continue
            except httpx.HTTPError as exc:
                raise RampApiError(status_code=None, message=f"network error calling Ramp: {exc}", trace_id=None) from exc

            if resp.status_code < 400:
                return resp
            if resp.status_code in _RETRY_STATUS_CODES and attempt < _MAX_RETRIES:
                await self._sleep_backoff(attempt, resp.headers.get("Retry-After"))
                continue
            raise self._error_from_response(resp)

        # Unreachable: the loop above always returns or raises.
        raise RampApiError(status_code=None, message="exhausted retries calling Ramp", trace_id=None)

    @staticmethod
    async def _sleep_backoff(attempt: int, retry_after: Optional[str]) -> None:
        delay = 2.0**attempt
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                pass
        await asyncio.sleep(min(delay, 10.0))

    @staticmethod
    def _error_from_response(resp: httpx.Response) -> RampApiError:
        trace_id = resp.headers.get("x-trace-id")
        message = f"Ramp API returned {resp.status_code}"
        try:
            body = resp.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            inner = body.get("error_v2")
            if isinstance(inner, dict) and inner.get("message"):
                message = str(inner["message"])
        return RampApiError(status_code=resp.status_code, message=message, trace_id=trace_id)
