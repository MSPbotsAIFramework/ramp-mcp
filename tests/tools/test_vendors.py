from ramp_mcp.tools import vendors
from tests.tools._helpers import call_tool


class _FakeClient:
    def __init__(self, page):
        self.page = page
        self.calls: list = []

    async def list_vendors(self, params):
        self.calls.append(params)
        return self.page


async def test_list_vendors_filters_by_name():
    client = _FakeClient(
        {
            "data": [
                {
                    "id": "vendor-1",
                    "name": "Acme Supplies",
                    "is_active": True,
                    "state": "ACTIVE",
                    "vendor_type": "BUSINESS",
                    "country": "US",
                }
            ],
            "page": {"next": None},
        }
    )
    result = await call_tool(vendors.register, client, "ramp_list_vendors", {"options": {"name": "Acme Supplies"}})

    assert client.calls[0]["name"] == "Acme Supplies"
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == "vendor-1"
    assert result["items"][0]["name"] == "Acme Supplies"
