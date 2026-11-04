from ramp_mcp.tools import users
from tests.tools._helpers import call_tool


class _FakeClient:
    def __init__(self, page):
        self.page = page
        self.calls: list = []

    async def list_users(self, params):
        self.calls.append(params)
        return self.page


async def test_list_users_filters_by_email():
    client = _FakeClient(
        {
            "data": [
                {
                    "id": "user-1",
                    "email": "jane@example.com",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "department_id": "dept-1",
                    "location_id": "loc-1",
                    "role": "BUSINESS_USER",
                    "status": "USER_ACTIVE",
                }
            ],
            "page": {"next": None},
        }
    )
    result = await call_tool(users.register, client, "ramp_list_users", {"options": {"email": "jane@example.com"}})

    assert client.calls[0]["email"] == "jane@example.com"
    assert len(result["items"]) == 1
    assert result["items"][0]["email"] == "jane@example.com"
    assert result["items"][0]["id"] == "user-1"
