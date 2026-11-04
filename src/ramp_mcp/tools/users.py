from typing import Any, Optional

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ramp_mcp.api_client import extract_next_cursor
from ramp_mcp.errors import RampApiError, envelope_for_api_error, envelope_for_unexpected
from ramp_mcp.tools._common import clamp_page_size, not_configured_envelope, paginated_result

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True)


class UsersListOptions(BaseModel):
    email: Optional[str] = Field(default=None, description="Exact email address to filter by.")
    department_id: Optional[str] = Field(default=None, description="Ramp department id to filter by.")
    location_id: Optional[str] = Field(default=None, description="Ramp location id to filter by.")
    role: Optional[str] = Field(default=None, description="Ramp role to filter by, e.g. BUSINESS_ADMIN.")
    status: Optional[str] = Field(default=None, description="Ramp user status to filter by, e.g. ACTIVE, INVITE_PENDING.")
    cursor: Optional[str] = Field(default=None, description="Opaque cursor from a previous page's next_cursor.")
    page_size: Optional[int] = Field(default=None, description="Max rows to return (default 50, hard cap 200).")


def _trim(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "department_id": user.get("department_id"),
        "location_id": user.get("location_id"),
        "role": user.get("role"),
        "status": user.get("status"),
    }


def register(mcp: Any, client_factory: Any) -> None:
    @mcp.tool(
        description="List Ramp users. Filter by email, department, location, role, or status. Paginated.",
        annotations=_READ_ONLY,
    )
    async def ramp_list_users(options: UsersListOptions) -> str:
        client = client_factory()
        if client is None:
            return not_configured_envelope()
        try:
            body = await client.list_users(
                {
                    "email": options.email,
                    "department_id": options.department_id,
                    "location_id": options.location_id,
                    "role": options.role,
                    "status": options.status,
                    "start": options.cursor,
                    "page_size": clamp_page_size(options.page_size),
                }
            )
        except RampApiError as exc:
            return envelope_for_api_error(exc)
        except Exception as exc:
            return envelope_for_unexpected(exc)

        items = [_trim(user) for user in body.get("data", [])]
        next_cursor = extract_next_cursor((body.get("page") or {}).get("next"))
        return paginated_result(items, next_cursor)
