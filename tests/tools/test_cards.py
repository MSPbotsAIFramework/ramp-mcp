from ramp_mcp.tools import cards
from tests.tools._helpers import call_tool


class _FakeClient:
    def __init__(self, physical=None, virtual=None):
        self.physical = physical or {"data": [], "page": {"next": None}}
        self.virtual = virtual or {"data": [], "page": {"next": None}}
        self.calls: list = []

    async def list_cards(self, card_type, params):
        self.calls.append((card_type, params))
        return self.physical if card_type == "physical" else self.virtual


async def test_list_cards_physical_calls_physical_endpoint_only():
    client = _FakeClient(
        physical={
            "data": [
                {
                    "id": "card-1",
                    "display_name": "Jane D.",
                    "cardholder_id": "user-1",
                    "cardholder_name": "Jane Doe",
                    "last_four": "4242",
                    "state": "ACTIVE",
                }
            ],
            "page": {"next": None},
        },
        virtual={"data": [{"id": "should-not-appear"}], "page": {"next": None}},
    )
    result = await call_tool(cards.register, client, "ramp_list_cards", {"options": {"card_type": "physical"}})

    assert [c[0] for c in client.calls] == ["physical"]
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == "card-1"
    assert item["card_type"] == "physical"
    assert item["display_name"] == "Jane D."
    assert item["holder_user_id"] == "user-1"
    assert item["state"] == "ACTIVE"


async def test_list_cards_virtual_calls_virtual_endpoint_only():
    client = _FakeClient(
        physical={"data": [{"id": "should-not-appear"}], "page": {"next": None}},
        virtual={
            "data": [{"id": "vcard-1", "user_id": "user-2", "is_card_suspended": False}],
            "page": {"next": None},
        },
    )
    result = await call_tool(cards.register, client, "ramp_list_cards", {"options": {"card_type": "virtual"}})

    assert [c[0] for c in client.calls] == ["virtual"]
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["id"] == "vcard-1"
    assert item["card_type"] == "virtual"
    assert item["holder_user_id"] == "user-2"
    assert item["state"] == "activated"
