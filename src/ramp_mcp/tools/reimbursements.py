from typing import Any, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ramp_mcp.api_client import extract_next_cursor
from ramp_mcp.errors import RampApiError, envelope_for_api_error, envelope_for_unexpected
from ramp_mcp.tools._common import clamp_page_size, not_configured_envelope, paginated_result

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


class ReimbursementsListOptions(BaseModel):
    state: Optional[str] = Field(default=None, description="Ramp reimbursement state to filter by, e.g. APPROVED, PAID.")
    user_id: Optional[str] = Field(default=None, description="Ramp user id (requester) to filter by.")
    from_date: Optional[str] = Field(default=None, description="ISO-8601 start of the transaction-date range, inclusive.")
    to_date: Optional[str] = Field(default=None, description="ISO-8601 end of the transaction-date range, inclusive.")
    cursor: Optional[str] = Field(default=None, description="Opaque cursor from a previous page's next_cursor.")
    page_size: Optional[int] = Field(default=None, description="Max rows to return (default 50, hard cap 200).")


def _trim(r: dict[str, Any]) -> dict[str, Any]:
    entity_amount = r.get("entity_amount") or {}
    return {
        "id": r.get("id"),
        "state": r.get("state"),
        "merchant": r.get("merchant"),
        "amount": entity_amount.get("value", r.get("merchant_amount")),
        "currency": entity_amount.get("currency"),
        "user_id": r.get("user_id"),
        "user_full_name": r.get("user_full_name"),
        "transaction_date": r.get("transaction_date"),
    }


def register(mcp: Any, client_factory: Any) -> None:
    @mcp.tool(
        description="List Ramp reimbursements. Filter by state, requesting user, or transaction-date range. Paginated.",
        annotations=_READ_ONLY,
    )
    async def ramp_list_reimbursements(options: ReimbursementsListOptions) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            body = await client.list_reimbursements(
                {
                    "state": options.state,
                    "user_id": options.user_id,
                    "from_date": options.from_date,
                    "to_date": options.to_date,
                    "start": options.cursor,
                    "page_size": clamp_page_size(options.page_size),
                }
            )
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:
            return envelope_for_unexpected(exc)

        items = [_trim(r) for r in body.get("data", [])]
        next_cursor = extract_next_cursor((body.get("page") or {}).get("next"))
        return paginated_result(items, next_cursor)
