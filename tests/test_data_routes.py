"""Tests for health and data endpoints."""

import pytest
from tests.conftest import FakeConnection


@pytest.mark.asyncio
async def test_health_ok(client):
    """GET /health returns 200 when DB is reachable."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_products_returns_list(client, fake_conn):
    """GET /data/products returns a products list."""
    fake_conn._rows = [
        {"productID": "1", "sku": "SKU1", "name": "Rose Bouquet", "category": "romantic",
         "collection": "Season", "description": "Beautiful roses", "picture": "https://img/rose.jpg",
         "price": 299, "contents": None, "type": "flower"},
    ]
    response = await client.get("/data/products")
    assert response.status_code == 200
    data = response.json()
    assert "products" in data


@pytest.mark.asyncio
async def test_products_pagination_params(client, fake_conn):
    """GET /data/products accepts limit and offset query params."""
    fake_conn._rows = []
    response = await client.get("/data/products?limit=5&offset=10")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_products_invalid_limit(client):
    """GET /data/products rejects limit < 1."""
    response = await client.get("/data/products?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_collections_endpoint(client, fake_conn):
    """GET /data/collections returns data."""
    fake_conn._rows = [
        {"collectionID": 1, "name": "Summer", "image": "https://img/summer.jpg"},
    ]
    response = await client.get("/data/collections")
    assert response.status_code == 200
    assert "data" in response.json()


class _RecordingCursor:
    """Captures the SQL + params so the localisation wiring can be asserted."""

    def __init__(self, sink: list):
        self._sink = sink

    async def execute(self, query: str, params=None):
        self._sink.append((query, params))

    async def fetchone(self):
        return {"productID": 1, "name": "Endless Passion", "contents": ["Ros"]}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_product_contents_localised_from_flowers():
    """get_product_by_id maps contents codes through `flowers` in the
    requested language order (db/init/06-flowers.sql)."""
    from database.products import get_product_by_id

    calls: list = []
    conn = FakeConnection()
    conn.cursor = lambda: _RecordingCursor(calls)

    row = await get_product_by_id(conn, 1, ["sv", "en"])

    query, params = calls[0]
    assert "LEFT JOIN flowers f ON f.code = u.code" in query
    assert "WITH ORDINALITY" in query
    assert params == ("sv", "en", "sv", "en", 1)
    assert row["contents"] == ["Ros"]
