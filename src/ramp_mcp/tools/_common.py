"""Shared response-shaping helpers (SOP SS2.5 token-economy rules)."""

import json
from typing import Any, Optional

from ramp_mcp.errors import error_envelope

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_RESPONSE_CHARS = 20_000


def clamp_page_size(page_size: Optional[int]) -> int:
    if page_size is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(int(page_size), MAX_PAGE_SIZE))


def _dumps(obj: Any) -> str:
    # No indent (pure overhead) and ensure_ascii=False (escaping doubles
    # token cost for any non-ASCII merchant/vendor name) -- SOP SS2.5.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def paginated_result(items: list[dict], next_cursor: Optional[str]) -> str:
    """Serialize {items, next_cursor}, truncating to the 20,000-char budget.

    The char budget wins over page_size when the two conflict (SOP SS2.5):
    if page_size already kept the row count small but individual rows are
    large, this still truncates and flags has_more.
    """
    full = {"items": items, "next_cursor": next_cursor}
    text = _dumps(full)
    if len(text) <= MAX_RESPONSE_CHARS:
        return text

    kept: list[dict] = []
    for item in items:
        candidate = _dumps({"items": kept + [item], "next_cursor": next_cursor, "has_more": True})
        if len(candidate) > MAX_RESPONSE_CHARS and kept:
            break
        kept.append(item)
    return _dumps({"items": kept, "next_cursor": next_cursor, "has_more": True})


def single_result(item: dict) -> str:
    return _dumps(item)


def not_configured_envelope() -> str:
    return error_envelope("not_configured", "Ramp credentials are not available for this request")
