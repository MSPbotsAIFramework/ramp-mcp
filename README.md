# ramp-mcp

MCP server for [Ramp](https://ramp.com) (expense management and corporate-card platform). Exposes read-only tools over transactions, cards, users, reimbursements, AP bills, and vendors so any MCP-compatible agent can query a tenant's live Ramp data.

- **Transport**: MCP Streamable HTTP (`POST /mcp`), stateless -- no session affinity required.
- **Stack**: Python 3.12, FastMCP (official `mcp` SDK), httpx, uvicorn/Starlette.
- **License**: Proprietary -- MSPbots internal connector, not for standalone distribution.

---

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Authentication headers

Every `POST /mcp` request must carry both headers below. Credentials are never read from the environment or a config file -- only from these two headers, per request.

| Header | Required | Meaning | Where to obtain |
|---|---|---|---|
| `X-Ramp-Client-Id` | Yes | Ramp OAuth app Client ID (`client_credentials` grant) | Ramp Developer Portal → API connections → your app |
| `X-Ramp-Client-Secret` | Yes | Ramp OAuth app Client Secret | same place |

The app must have the `client_credentials` grant type enabled and the scopes `transactions:read users:read cards:read reimbursements:read bills:read vendors:read`. The server exchanges these for a short-lived Ramp access token (`POST /developer/v1/token`) and caches it in-process, keyed by a hash of the credential pair, until shortly before it expires -- it never caches the credentials themselves or any response data across requests.

Missing either header returns `401` with a body naming which header(s) are missing, before any call reaches Ramp.

## Tools (v1, read-only)

| Tool | Ramp endpoint | Description |
|---|---|---|
| `ramp_list_transactions` | `GET /developer/v1/transactions` | List card/ACH transactions, filtered by date range, department, user, card, amount range, or state. Paginated. |
| `ramp_get_transaction` | `GET /developer/v1/transactions/{id}` | Get a single transaction's full detail by id. |
| `ramp_list_cards` | `GET /developer/v1/cards/physical` or `/cards/virtual` | List physical or virtual cards (`card_type` selects which), with holder and state. Paginated. |
| `ramp_list_users` | `GET /developer/v1/users` | List users, filtered by email, department, location, role, or status. Paginated. |
| `ramp_list_reimbursements` | `GET /developer/v1/reimbursements` | List reimbursements, filtered by state, requesting user, or transaction-date range. Paginated. |
| `ramp_list_bills` | `GET /developer/v1/bills` | List AP bills, filtered by vendor, payment status, or issued-date range. Paginated. |
| `ramp_list_vendors` | `GET /developer/v1/vendors` | List vendors, filtered by name or active status. Paginated. |

All `list` tools accept a single `options` object (so new Ramp filters can be added later without changing the tool's call shape) with an optional `cursor` (pass back the previous page's `next_cursor`) and `page_size` (default 50, hard cap 200). There are no write/mutating tools in v1 -- see "Non-goals" in `docs/tickets/PRD-21292.md` for what was deliberately left out and why.

Errors are returned as a JSON envelope `{"error": {"code", "message", "retryable"}}` with `code` drawn from a fixed vocabulary (`not_configured`, `unauthorized`, `not_found`, `invalid_argument`, `rate_limited`, `upstream_error`); tools never raise.

## Running locally

```bash
uv sync
uv run python -m ramp_mcp
```

Or via Docker:

```bash
docker build --platform linux/amd64 -t ramp-mcp:dev .
docker run --rm -p 8080:8080 ramp-mcp:dev
```

Then, with your own Ramp developer-app credentials:

```bash
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H 'X-Ramp-Client-Id: <your client id>' -H 'X-Ramp-Client-Secret: <your client secret>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

`GET /health` returns `200 {"status": "ok"}` independent of Ramp's own availability.

## Tests

```bash
uv run pytest
```

Unit tests mock Ramp's API (`tests/test_tools.py`, `tests/test_middleware.py`, `tests/tools/test_*.py`); none make real network calls.
