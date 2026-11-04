from typing import Any, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ramp_mcp.api_client import extract_next_cursor
from ramp_mcp.errors import RampApiError, envelope_for_api_error, envelope_for_unexpected
from ramp_mcp.tools._common import clamp_page_size, not_configured_envelope, paginated_result, single_result

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


class TransactionsListOptions(BaseModel):
    from_date: Optional[str] = Field(default=None, description="ISO-8601 start of the date range, inclusive.")
    to_date: Optional[str] = Field(default=None, description="ISO-8601 end of the date range, inclusive.")
    department_id: Optional[str] = Field(default=None, description="Ramp department id to filter by.")
    user_id: Optional[str] = Field(default=None, description="Ramp user id (card holder) to filter by.")
    card_id: Optional[str] = Field(default=None, description="Ramp card id to filter by.")
    min_amount: Optional[float] = Field(default=None, description="Minimum transaction amount, inclusive.")
    max_amount: Optional[float] = Field(default=None, description="Maximum transaction amount, inclusive.")
    state: Optional[str] = Field(
        default=None,
        description="One of Ramp's transaction states: ALL, CLEARED, COMPLETION, DECLINED, ERROR, PENDING, PENDING_INITIATION.",
    )
    cursor: Optional[str] = Field(default=None, description="Opaque cursor from a previous page's next_cursor.")
    page_size: Optional[int] = Field(default=None, description="Max rows to return (default 50, hard cap 200).")


def _trim_list_item(tx: dict[str, Any]) -> dict[str, Any]:
    card_holder = tx.get("card_holder") or {}
    name = " ".join(filter(None, [card_holder.get("first_name"), card_holder.get("last_name")])) or None
    return {
        "id": tx.get("id"),
        "amount": tx.get("amount"),
        "currency": tx.get("currency_code"),
        "state": tx.get("state"),
        "merchant": tx.get("merchant_name"),
        "card_holder_name": name,
        "department": card_holder.get("department_name"),
        "accounting_categories": [
            c.get("display_name") or c.get("name") for c in (tx.get("accounting_categories") or [])
        ],
    }


def _trim_detail(tx: dict[str, Any]) -> dict[str, Any]:
    card_holder = tx.get("card_holder") or {}
    name = " ".join(filter(None, [card_holder.get("first_name"), card_holder.get("last_name")])) or None
    return {
        "id": tx.get("id"),
        "amount": tx.get("amount"),
        "currency": tx.get("currency_code"),
        "state": tx.get("state"),
        "merchant": tx.get("merchant_name"),
        "merchant_category": tx.get("merchant_category_code_description"),
        "card_holder": {
            "user_id": card_holder.get("user_id"),
            "name": name,
            "department_id": card_holder.get("department_id"),
            "department_name": card_holder.get("department_name"),
            "location_id": card_holder.get("location_id"),
            "location_name": card_holder.get("location_name"),
        },
        "accounting_categories": [
            c.get("display_name") or c.get("name") for c in (tx.get("accounting_categories") or [])
        ],
        "memo": tx.get("memo"),
        "user_transaction_time": tx.get("user_transaction_time"),
        "settlement_date": tx.get("settlement_date"),
        "policy_violation_count": len(tx.get("policy_violations") or []),
    }


def register(mcp: Any, client_factory: Any) -> None:
    @mcp.tool(
        description=(
            "List Ramp card/ACH transactions, newest first. Filter by date range, "
            "department, user, card, amount range, or state. Paginated: pass the "
            "previous page's next_cursor back as cursor to get the next page."
        ),
        annotations=_READ_ONLY,
    )
    async def ramp_list_transactions(options: TransactionsListOptions) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            body = await client.list_transactions(
                {
                    "from_date": options.from_date,
                    "to_date": options.to_date,
                    "department_id": options.department_id,
                    "user_id": options.user_id,
                    "card_id": options.card_id,
                    "min_amount": options.min_amount,
                    "max_amount": options.max_amount,
                    "state": options.state,
                    "start": options.cursor,
                    "page_size": clamp_page_size(options.page_size),
                }
            )
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:  # tools never raise -- SOP SS4.1
            return envelope_for_unexpected(exc)

        items = [_trim_list_item(tx) for tx in body.get("data", [])]
        next_cursor = extract_next_cursor((body.get("page") or {}).get("next"))
        return paginated_result(items, next_cursor)

    @mcp.tool(
        description="Get a single Ramp transaction by id, with full merchant, card-holder, and accounting-category detail.",
        annotations=_READ_ONLY,
    )
    async def ramp_get_transaction(transaction_id: str) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            tx = await client.get_transaction(transaction_id)
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:
            return envelope_for_unexpected(exc)
        return single_result(_trim_detail(tx))
