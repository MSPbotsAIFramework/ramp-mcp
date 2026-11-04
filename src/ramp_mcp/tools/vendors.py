from typing import Any, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ramp_mcp.api_client import extract_next_cursor
from ramp_mcp.errors import RampApiError, envelope_for_api_error, envelope_for_unexpected
from ramp_mcp.tools._common import clamp_page_size, not_configured_envelope, paginated_result

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


class VendorsListOptions(BaseModel):
    name: Optional[str] = Field(default=None, description="Vendor name to filter by (exact match on Ramp's side).")
    is_active: Optional[bool] = Field(default=None, description="Filter to active (true) or inactive (false) vendors only.")
    cursor: Optional[str] = Field(default=None, description="Opaque cursor from a previous page's next_cursor.")
    page_size: Optional[int] = Field(default=None, description="Max rows to return (default 50, hard cap 200).")


def _trim(v: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": v.get("id"),
        "name": v.get("name") or v.get("display_name"),
        "is_active": v.get("is_active"),
        "state": v.get("state"),
        "vendor_type": v.get("vendor_type"),
        "country": v.get("country"),
    }


def register(mcp: Any, client_factory: Any) -> None:
    @mcp.tool(
        description="List Ramp vendors. Filter by name or active status. Paginated.",
        annotations=_READ_ONLY,
    )
    async def ramp_list_vendors(options: VendorsListOptions) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            body = await client.list_vendors(
                {
                    "name": options.name,
                    "is_active": options.is_active,
                    "start": options.cursor,
                    "page_size": clamp_page_size(options.page_size),
                }
            )
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:
            return envelope_for_unexpected(exc)

        items = [_trim(v) for v in body.get("data", [])]
        next_cursor = extract_next_cursor((body.get("page") or {}).get("next"))
        return paginated_result(items, next_cursor)
