# PRD-21292 · Code review

## Round 1 · 2026-11-04 · reviewed dev/PRD-21292 @ 2125c6e (base 645741c)

Verdict: approved

### Findings

1. [suggestion] `src/ramp_mcp/errors.py:22-29` — `_STATUS_TO_CODE` maps both `401` and `403` to `"unauthorized"`, and uses `"invalid_argument"` where the tech design's Data & API contract section names `"forbidden"` (403) and `"invalid_input"` (400/422) as distinct codes. This is a naming deviation from the tech design, not a behavioral defect — the connector is brand new with no existing consumers, and `.ac.json`/tests pin the actual (consistent) behavior. Worth a one-line note in the design doc or a code comment so the next person doesn't re-derive this from scratch, but not worth a round-trip.
2. [suggestion] `src/ramp_mcp/tools/reimbursements.py:28-29` — `amount` falls back from `entity_amount.value` to the flatter `merchant_amount` when `entity_amount` is absent, but `currency` has no equivalent fallback and stays `None` in that case. Already flagged candidly in the Self-test "Deviations" section as a known field-mapping gap pending the exact Reimbursement response schema; low priority since the mocked tests pin the field read that was actually implemented.

No must-fix findings. Spot-checked against `legs/review.md` R3 and the MCP checklist in `mcp-track.md` §4.3:

- **Credentials**: `server.py`'s `RampCredentialsMiddleware` reads only the two `X-Ramp-*` headers (raw ASGI, not `BaseHTTPMiddleware`, so Streamable HTTP isn't buffered), sets a request-scoped `ContextVar`, always `reset()`s it in `finally`. `api_client.py`'s only module-level state is the OAuth token cache, keyed by `sha256(client_id:client_secret)` with an expiry — the one SOP §3.4 exception. Verified via `tests/test_middleware.py::test_concurrent_requests_with_different_credentials_do_not_cross_tenant`: two concurrent calls with distinct credentials each got back only their own tenant's data, and the cache ended up with 2 distinct keys.
- **Tool contract**: 7 tools, names/params/returns match the tech design's "Tool → Ramp endpoint mapping" and `Data & API contract` sections; errors are a structured `{"error": {"code", "message", "retryable"}}` envelope built in `errors.py`, never a raw exception (every tool wraps its `api_client` call in `try/except RampApiError` + a catch-all `except Exception`).
- **Tests**: changed alongside tools (`tests/tools/test_*.py` per resource) and `tests/test_tools.py`/`tests/test_middleware.py`; Self-test section has both the `uv run pytest` result (16 passed) on code synced with `main@645741c`, and a real `tools/list`/`/health`/401 manual HTTP pass (no mocks) against a running process.
- **README**: Connector section verified byte-identical against `~/.claude/skills/vendor-mcp-development/reference/readme-connector-section.md` (`diff` on `README.md:11-81`, exact match); Header table (`X-Ramp-Client-Id`/`X-Ramp-Client-Secret`) present with where-to-obtain text. `grep -rnP '[\x{4e00}-\x{9fff}]'` over the worktree: no output (no Chinese).
- **Cross-repo compatibility (`mcp-track.md` §1.2)**: n/a — single-repo ticket, "release order: no dependency" per the tech design's Rollout & rollback section; no shared contract with another repo to break.
- **SOP §14 checklist**: self-test's own checklist walk-through (Contract, Errors/network, Container/delivery, Agent-facing design, Logging/secrets, Tests) is consistent with what's actually in the diff — spot-checked the two "not verified in this environment" items (`docker build`, `gitleaks`) and both are honestly disclosed rather than silently assumed; Dockerfile is the SOP's unmodified reference sample with only the image/vendor name substituted, which is a reasonable basis for the design's "risk believed low" claim.
- **Reuse/cleanup**: brand-new repo, nothing to reuse or clean up; dependency list (`mcp`, `httpx`, `pydantic-settings`, `uvicorn`, `starlette`) matches the SOP's recommended stack, no unexplained additions.

Status: frozen @ 2125c6e
