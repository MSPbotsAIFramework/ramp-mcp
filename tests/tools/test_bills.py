from ramp_mcp.tools import bills
from tests.tools._helpers import call_tool


class _FakeClient:
    def __init__(self, page):
        self.page = page
        self.calls: list = []

    async def list_bills(self, params):
        self.calls.append(params)
        return self.page


async def test_list_bills_filters_by_vendor_and_payment_status():
    client = _FakeClient(
        {
            "data": [
                {
                    "id": "bill-1",
                    "amount": 1000.0,
                    "status": "OPEN",
                    "approval_status": "APPROVED",
                    "due_at": "2026-02-01",
                    "issued_at": "2026-01-01",
                    "paid_at": None,
                    "vendor": {"id": "vendor-1", "display_name": "Acme Supplies"},
                    "invoice_number": "INV-001",
                }
            ],
            "page": {"next": None},
        }
    )
    result = await call_tool(
        bills.register,
        client,
        "ramp_list_bills",
        {"options": {"vendor_id": "vendor-1", "payment_status": "SCHEDULED"}},
    )

    assert client.calls[0]["vendor_id"] == "vendor-1"
    assert client.calls[0]["payment_status"] == "SCHEDULED"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == "bill-1"
    assert item["vendor_id"] == "vendor-1"
    assert item["vendor_name"] == "Acme Supplies"
