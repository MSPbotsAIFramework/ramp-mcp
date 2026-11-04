from ramp_mcp.tools import reimbursements
from tests.tools._helpers import call_tool


class _FakeClient:
    def __init__(self, page):
        self.page = page
        self.calls: list = []

    async def list_reimbursements(self, params):
        self.calls.append(params)
        return self.page


async def test_list_reimbursements_filters_by_state():
    client = _FakeClient(
        {
            "data": [
                {
                    "id": "reimb-1",
                    "state": "APPROVED",
                    "merchant": "Office Depot",
                    "entity_amount": {"value": 51.25, "currency": "USD"},
                    "user_id": "user-1",
                    "user_full_name": "Jane Doe",
                    "transaction_date": "2026-01-05",
                }
            ],
            "page": {"next": None},
        }
    )
    result = await call_tool(
        reimbursements.register, client, "ramp_list_reimbursements", {"options": {"state": "APPROVED"}}
    )

    assert client.calls[0]["state"] == "APPROVED"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == "reimb-1"
    assert item["state"] == "APPROVED"
    assert item["amount"] == 51.25
    assert item["currency"] == "USD"
