from ramp_mcp.errors import RampApiError
from ramp_mcp.tools import transactions
from tests.tools._helpers import call_tool

_CARD_HOLDER = {
    "first_name": "Jane",
    "last_name": "Doe",
    "department_id": "dept-1",
    "department_name": "Engineering",
    "location_id": "loc-1",
    "location_name": "SF",
    "user_id": "user-1",
}


def _tx(id_: str, **overrides) -> dict:
    base = {
        "id": id_,
        "amount": 42.0,
        "currency_code": "USD",
        "state": "CLEARED",
        "merchant_name": "Acme Co",
        "card_holder": dict(_CARD_HOLDER),
        "accounting_categories": [{"display_name": "Travel"}],
    }
    base.update(overrides)
    return base


class _FakeClient:
    def __init__(self, pages=None, detail=None, raise_exc=None):
        self.pages = list(pages or [])
        self.detail = detail
        self.raise_exc = raise_exc
        self.calls: list = []

    async def list_transactions(self, params):
        self.calls.append(params)
        if self.raise_exc:
            raise self.raise_exc
        return self.pages.pop(0)

    async def get_transaction(self, transaction_id):
        self.calls.append(transaction_id)
        if self.raise_exc:
            raise self.raise_exc
        return self.detail


async def test_list_transactions_filters_by_date_range_and_department():
    client = _FakeClient(
        pages=[
            {
                "data": [
                    _tx("tx-1"),
                    _tx("tx-2", card_holder={**_CARD_HOLDER, "department_name": "Sales"}),
                ],
                "page": {"next": None},
            }
        ]
    )
    result = await call_tool(
        transactions.register,
        client,
        "ramp_list_transactions",
        {"options": {"from_date": "2026-01-01", "to_date": "2026-01-31", "department_id": "dept-1"}},
    )

    sent_params = client.calls[0]
    assert sent_params["from_date"] == "2026-01-01"
    assert sent_params["to_date"] == "2026-01-31"
    assert sent_params["department_id"] == "dept-1"

    assert result["next_cursor"] is None
    assert len(result["items"]) == 2
    item = result["items"][0]
    for field in ("id", "amount", "currency", "state", "merchant", "card_holder_name", "department"):
        assert field in item
    assert item["card_holder_name"] == "Jane Doe"
    assert item["department"] == "Engineering"


async def test_list_transactions_pagination_cursor_round_trip():
    client = _FakeClient(
        pages=[
            {"data": [_tx("tx-1")], "page": {"next": "https://api.ramp.com/developer/v1/transactions?start=cursor-abc"}},
            {"data": [_tx("tx-2")], "page": {"next": None}},
        ]
    )
    first = await call_tool(transactions.register, client, "ramp_list_transactions", {"options": {}})
    assert first["next_cursor"] == "cursor-abc"
    first_ids = {item["id"] for item in first["items"]}

    second = await call_tool(
        transactions.register,
        client,
        "ramp_list_transactions",
        {"options": {"cursor": first["next_cursor"]}},
    )
    assert client.calls[1]["start"] == "cursor-abc"
    assert second["next_cursor"] is None
    second_ids = {item["id"] for item in second["items"]}
    assert first_ids.isdisjoint(second_ids)


async def test_get_transaction_unknown_id_returns_not_found_error():
    client = _FakeClient(raise_exc=RampApiError(status_code=404, message="transaction not found", trace_id="trace-1"))
    result = await call_tool(transactions.register, client, "ramp_get_transaction", {"transaction_id": "does-not-exist"})
    assert result["error"]["code"] == "not_found"
    assert result["error"]["retryable"] is False


async def test_rate_limited_upstream_response_maps_to_structured_error():
    client = _FakeClient(raise_exc=RampApiError(status_code=429, message="too many requests", trace_id="trace-2"))
    result = await call_tool(transactions.register, client, "ramp_list_transactions", {"options": {}})
    assert result["error"]["code"] == "rate_limited"
    assert result["error"]["retryable"] is True
    assert "trace-2" in result["error"]["message"]
