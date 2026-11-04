"""Structured error envelope shared by every v1 tool.

Tools never raise -- every failure path (upstream HTTP error, unexpected
exception) is turned into one of these JSON strings so the calling agent can
branch on ``error.code`` instead of catching a protocol-level exception.
"""

import json
from typing import Literal, Optional

ErrorCode = Literal[
    "not_configured",
    "unauthorized",
    "not_found",
    "invalid_argument",
    "rate_limited",
    "upstream_error",
]

_RETRYABLE_CODES: frozenset[str] = frozenset({"rate_limited", "upstream_error"})

_STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: "invalid_argument",
    401: "unauthorized",
    403: "unauthorized",
    404: "not_found",
    422: "invalid_argument",
    429: "rate_limited",
}


class RampApiError(Exception):
    """Raised by api_client for any Ramp HTTP/network failure.

    ``status_code`` is None for connection-level failures (timeout, DNS,
    refused connection) -- those map to ``upstream_error``.
    """

    def __init__(self, status_code: Optional[int], message: str, trace_id: Optional[str]):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.trace_id = trace_id


def code_for_status(status_code: Optional[int]) -> ErrorCode:
    if status_code is None:
        return "upstream_error"
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "upstream_error"
    return "upstream_error"


def is_retryable(code: ErrorCode) -> bool:
    return code in _RETRYABLE_CODES


def error_envelope(code: ErrorCode, message: str) -> str:
    return json.dumps(
        {"error": {"code": code, "message": message, "retryable": is_retryable(code)}},
        separators=(",", ":"),
        ensure_ascii=False,
    )


def envelope_for_api_error(exc: RampApiError) -> str:
    code = code_for_status(exc.status_code)
    message = exc.message
    if exc.trace_id:
        message = f"{message} (trace_id={exc.trace_id})"
    return error_envelope(code, message)


def envelope_for_unexpected(exc: Exception) -> str:
    return error_envelope("upstream_error", f"unexpected error calling Ramp: {exc}")
