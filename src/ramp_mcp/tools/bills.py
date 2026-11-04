from typing import Any, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ramp_mcp.api_client import extract_next_cursor
from ramp_mcp.errors import RampApiError, envelope_for_api_error, envelope_for_unexpected
from ramp_mcp.tools._common import clamp_page_size, not_configured_envelope, paginated_result

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


class BillsListOptions(BaseModel):
    vendor_id: Optional[str] = Field(default=None, description="Ramp vendor id to filter by.")
    payment_status: Optional[str] = Field(default=None, description="Ramp bill payment status to filter by, e.g. PAID, SCHEDULED.")
    from_issued_date: Optional[str] = Field(default=None, description="ISO-8601 start of the issued-date range, inclusive.")
    to_issued_date: Optional[str] = Field(default=None, description="ISO-8601 end of the issued-date range, inclusive.")
    cursor: Optional[str] = Field(default=None, description="Opaque cursor from a previous page's next_cursor.")
    page_size: Optional[int] = Field(default=None, description="Max rows to return (default 50, hard cap 200).")


def _trim(b: dict[str, Any]) -> dict[str, Any]:
    vendor = b.get("vendor") or {}
    return {
        "id": b.get("id"),
        "amount": b.get("amount"),
        "status": b.get("status"),
        "approval_status": b.get("approval_status"),
        "due_at": b.get("due_at"),
        "issued_at": b.get("issued_at"),
        "paid_at": b.get("paid_at"),
        "vendor_id": vendor.get("id") if isinstance(vendor, dict) else None,
        "vendor_name": vendor.get("display_name") if isinstance(vendor, dict) else None,
        "invoice_number": b.get("invoice_number"),
    }


def register(mcp: Any, client_factory: Any) -> None:
    @mcp.tool(
        description="List Ramp AP bills. Filter by vendor, payment status, or issued-date range. Paginated.",
        annotations=_READ_ONLY,
    )
    async def ramp_list_bills(options: BillsListOptions) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            body = await client.list_bills(
                {
                    "vendor_id": options.vendor_id,
                    "payment_status": options.payment_status,
                    "from_issued_date": options.from_issued_date,
                    "to_issued_date": options.to_issued_date,
                    "start": options.cursor,
                    "page_size": clamp_page_size(options.page_size),
                }
            )
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:
            return envelope_for_unexpected(exc)

        items = [_trim(b) for b in body.get("data", [])]
        next_cursor = extract_next_cursor((body.get("page") or {}).get("next"))
        return paginated_result(items, next_cursor)
