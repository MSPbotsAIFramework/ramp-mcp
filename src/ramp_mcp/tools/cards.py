from typing import Any, Literal, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ramp_mcp.api_client import extract_next_cursor
from ramp_mcp.errors import RampApiError, envelope_for_api_error, envelope_for_unexpected
from ramp_mcp.tools._common import clamp_page_size, not_configured_envelope, paginated_result

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


class CardsListOptions(BaseModel):
    card_type: Literal["physical", "virtual"] = Field(description="Which Ramp card endpoint to query.")
    user_id: Optional[str] = Field(default=None, description="Ramp user id (card holder) to filter by.")
    cursor: Optional[str] = Field(default=None, description="Opaque cursor from a previous page's next_cursor.")
    page_size: Optional[int] = Field(default=None, description="Max rows to return (default 50, hard cap 200).")


def _trim_physical(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "card_type": "physical",
        "display_name": card.get("display_name"),
        "holder_user_id": card.get("cardholder_id"),
        "holder_name": card.get("cardholder_name"),
        "last_four": card.get("last_four"),
        "state": card.get("state"),
    }


def _trim_virtual(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card.get("id"),
        "card_type": "virtual",
        "display_name": None,
        "holder_user_id": card.get("user_id"),
        "holder_name": None,
        "last_four": None,
        "state": "suspended" if card.get("is_card_suspended") else "activated",
    }


def register(mcp: Any, client_factory: Any) -> None:
    @mcp.tool(
        description=(
            "List Ramp cards, physical or virtual (card_type selects which). "
            "Each result includes card id, display name (physical only), holder "
            "user id, and activated/suspended state. Paginated."
        ),
        annotations=_READ_ONLY,
    )
    async def ramp_list_cards(options: CardsListOptions) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            body = await client.list_cards(
                options.card_type,
                {
                    "user_id": options.user_id,
                    "start": options.cursor,
                    "page_size": clamp_page_size(options.page_size),
                },
            )
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:
            return envelope_for_unexpected(exc)

        trim = _trim_physical if options.card_type == "physical" else _trim_virtual
        items = [trim(card) for card in body.get("data", [])]
        next_cursor = extract_next_cursor((body.get("page") or {}).get("next"))
        return paginated_result(items, next_cursor)
