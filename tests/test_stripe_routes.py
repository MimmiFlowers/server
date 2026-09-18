"""Tests for Stripe checkout and webhook endpoints."""

import json
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from tests.conftest import FakeConnection
from tests.test_wreath_service import CATALOG


def _checkout_payload(pickup: bool = False) -> dict:
    """Build a valid checkout request body."""
    return {
        "items": [
            {"name": "Rose Bouquet", "price": 29900, "quantity": 2},
        ],
        "orderData": {
            "orderID": "placeholder",
            "customer": {
                "email": "test@example.com",
                "firstName": "Anna",
                "lastName": "Svensson",
                "phone": "+46701234567",
            },
            "recipient": None if pickup else {
                "firstName": "Bo",
                "lastName": "Andersson",
                "phone": "+46709876543",
                "address": "Storgatan 1, Stockholm",
                "date": "2026-03-10",
                "time": "14:00",
            },
            "pickup": pickup,
            "orderForMyself": False,
            "items": [{"name": "Rose Bouquet", "price": 29900, "quantity": 2}],
            "subtotal": 59800,
            "deliveryFee": 0 if pickup else 9900,
            "total": 59800 if pickup else 69700,
            "moms": 14950 if pickup else 17425,
        },
    }


@pytest.mark.asyncio
async def test_checkout_missing_items(client):
    """POST /stripe/create_checkout_session with empty items returns 422."""
    payload = _checkout_payload()
    payload["items"] = []
    response = await client.post("/stripe/create_checkout_session", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_checkout_invalid_email(client):
    """POST /stripe/create_checkout_session with bad email returns 422."""
    payload = _checkout_payload()
    payload["orderData"]["customer"]["email"] = "not-an-email"
    response = await client.post("/stripe/create_checkout_session", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_checkout_missing_recipient_for_delivery(client):
    """POST /stripe/create_checkout_session delivery without recipient is valid per current model."""
    payload = _checkout_payload(pickup=False)
    payload["orderData"]["recipient"] = None
    # The Pydantic model allows recipient=None (it's Optional), so this should not 422.
    # Actual business validation happens at a higher level. Just verify no 422.
    # The endpoint will fail at DB lookup (mocked), which is expected.
    response = await client.post("/stripe/create_checkout_session", json=payload)
    # Should not be a validation error — it'll fail at get_product_prices_by_names
    assert response.status_code != 422


@pytest.mark.asyncio
async def test_checkout_creates_session(client, fake_conn):
    """POST /stripe/create_checkout_session succeeds with valid data and mocked Stripe."""
    payload = _checkout_payload(pickup=True)

    # Mock get_product_prices_by_names to return DB prices
    mock_prices = {"Rose Bouquet": 299}

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.__getitem__ = lambda self, key: getattr(self, key, None)

    with (
        patch("routers.stripe_routes.get_product_prices_by_names", new_callable=AsyncMock, return_value=mock_prices),
        patch("routers.stripe_routes.insert_order", new_callable=AsyncMock),
        patch("routers.stripe_routes.stripe.checkout.Session.create", return_value=mock_session),
    ):
        response = await client.post("/stripe/create_checkout_session", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "session" in data


@pytest.mark.asyncio
async def test_checkout_unknown_product(client, fake_conn):
    """POST /stripe/create_checkout_session with unknown product returns 400."""
    payload = _checkout_payload()

    # Return empty prices dict — no products found
    with patch("routers.stripe_routes.get_product_prices_by_names", new_callable=AsyncMock, return_value={}):
        response = await client.post("/stripe/create_checkout_session", json=payload)
        assert response.status_code == 400
        assert "Unknown products" in response.json()["detail"]


@pytest.mark.asyncio
async def test_order_status_invalid_id(client):
    """GET /stripe/order/{id}/status with invalid ID format returns 400."""
    response = await client.get("/stripe/order/DROP%20TABLE%20orders/status")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_order_status_not_found(client, fake_conn):
    """GET /stripe/order/{id}/status for nonexistent order returns 404."""
    fake_conn._rows = []  # No rows → None
    response = await client.get("/stripe/order/ORD-abc123/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_order_status_found(client, fake_conn):
    """GET /stripe/order/{id}/status for existing order returns status."""
    fake_conn._rows = [{"status": "paid"}]
    response = await client.get("/stripe/order/ORD-abc123/status")
    assert response.status_code == 200
    assert response.json()["status"] == "paid"


DESIGN_ID = "123e4567-e89b-42d3-a456-426614174000"


def _wreath_design_row() -> dict:
    return {
        "designID": DESIGN_ID,
        "spec": {
            "sizeCode": "s",
            "materialCode": "fir",
            "bandCode": "red-velvet",
            "decorations": [{"slot": 0, "code": "pine-cone"}],
        },
        "price": Decimal("363.00"),
        "hasImage": True,
    }


@pytest.mark.asyncio
async def test_checkout_prices_wreath_from_design_not_client(client):
    """A wreath line is priced from wreath_designs + live options; client name/price are ignored."""
    payload = _checkout_payload(pickup=True)
    payload["items"] = [{"name": "whatever", "price": 100, "quantity": 2, "designID": DESIGN_ID}]
    payload["orderData"]["locale"] = "sv"
    payload["orderData"]["items"] = [
        {"id": f"wreath-{DESIGN_ID}", "name": "hacked", "price": 1, "quantity": 2, "designID": DESIGN_ID}
    ]

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.__getitem__ = lambda self, key: getattr(self, key, None)

    with (
        patch("routers.stripe_routes.get_product_prices_by_names", new_callable=AsyncMock, return_value={}),
        patch("routers.stripe_routes.get_wreath_catalog", new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.stripe_routes.get_wreath_design", new_callable=AsyncMock, return_value=_wreath_design_row()),
        patch("routers.stripe_routes.insert_order", new_callable=AsyncMock) as insert_order,
        patch("routers.stripe_routes.stripe.checkout.Session.create", return_value=mock_session) as create,
    ):
        response = await client.post("/stripe/create_checkout_session", json=payload)

    assert response.status_code == 200
    line = create.call_args.kwargs["line_items"][0]
    assert line["price_data"]["unit_amount"] == 36300          # öre, from the design — not 100
    assert line["quantity"] == 2
    assert line["price_data"]["product_data"]["name"] == "Egen julkrans"
    assert line["price_data"]["product_data"]["description"] == "Liten 25 cm · Gran · Röd sammet · Kotte ×1"

    order_data = insert_order.await_args.args[1]
    assert order_data.subtotal == 72600
    assert order_data.deliveryFee == 0
    wreath_item = order_data.items[0]
    assert wreath_item["name"] == "Egen julkrans"
    assert wreath_item["price"] == 363
    assert wreath_item["quantity"] == 2
    assert wreath_item["designID"] == DESIGN_ID
    assert wreath_item["picture"] == f"http://localhost:3000/data/wreath/designs/{DESIGN_ID}/image"
    assert wreath_item["wreath"]["decorations"] == [{"slot": 1, "en": "Pine cone", "sv": "Kotte"}]


@pytest.mark.asyncio
async def test_checkout_mixes_products_and_wreaths(client):
    payload = _checkout_payload(pickup=True)
    payload["items"].append({"name": "x", "price": 1, "quantity": 1, "designID": DESIGN_ID})
    payload["orderData"]["items"].append({"name": "x", "price": 1, "quantity": 1, "designID": DESIGN_ID})

    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.__getitem__ = lambda self, key: getattr(self, key, None)

    with (
        patch("routers.stripe_routes.get_product_prices_by_names", new_callable=AsyncMock, return_value={"Rose Bouquet": 299}),
        patch("routers.stripe_routes.get_wreath_catalog", new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.stripe_routes.get_wreath_design", new_callable=AsyncMock, return_value=_wreath_design_row()),
        patch("routers.stripe_routes.insert_order", new_callable=AsyncMock) as insert_order,
        patch("routers.stripe_routes.stripe.checkout.Session.create", return_value=mock_session),
    ):
        response = await client.post("/stripe/create_checkout_session", json=payload)

    assert response.status_code == 200
    order_data = insert_order.await_args.args[1]
    assert order_data.subtotal == 2 * 29900 + 36300
    names = [item["name"] for item in order_data.items]
    assert names == ["Rose Bouquet", "Custom Christmas wreath"]


@pytest.mark.asyncio
async def test_checkout_unknown_design_is_400(client):
    payload = _checkout_payload(pickup=True)
    payload["items"] = [{"name": "x", "price": 1, "quantity": 1, "designID": DESIGN_ID}]
    with (
        patch("routers.stripe_routes.get_wreath_catalog", new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.stripe_routes.get_wreath_design", new_callable=AsyncMock, return_value=None),
    ):
        response = await client.post("/stripe/create_checkout_session", json=payload)
    assert response.status_code == 400
    assert "build it again" in response.json()["detail"]


@pytest.mark.asyncio
async def test_checkout_design_with_retired_option_is_400(client):
    row = _wreath_design_row()
    row["spec"]["bandCode"] = "discontinued"
    payload = _checkout_payload(pickup=True)
    payload["items"] = [{"name": "x", "price": 1, "quantity": 1, "designID": DESIGN_ID}]
    with (
        patch("routers.stripe_routes.get_wreath_catalog", new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.stripe_routes.get_wreath_design", new_callable=AsyncMock, return_value=row),
    ):
        response = await client.post("/stripe/create_checkout_session", json=payload)
    assert response.status_code == 400
    assert "no longer available" in response.json()["detail"]
