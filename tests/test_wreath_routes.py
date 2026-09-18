"""Tests for /data/wreath/* endpoints. DB helpers are patched; logic is real."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.test_wreath_service import CATALOG, _data_url, _png

CATALOG_PATCH = "routers.wreath_routes.get_wreath_catalog"


def _design_payload(**spec_overrides) -> dict:
    spec = {
        "sizeCode": "s",
        "materialCode": "fir",
        "bandCode": "red-velvet",
        "decorations": [{"slot": 0, "code": "pine-cone"}],
    }
    spec.update(spec_overrides)
    return {"spec": spec, "image": _data_url(_png())}


@pytest.mark.asyncio
async def test_options_resolves_language_and_flattens_prices(client):
    with patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG):
        response = await client.get("/data/wreath/options", headers={"Accept-Language": "sv"})
    assert response.status_code == 200
    body = response.json()
    assert body["sizes"][0] == {"code": "s", "name": "Liten", "diameterCm": 25, "slotCount": 6}
    assert body["basePrices"]["s"]["fir"] == 299.0
    assert body["bands"][0]["price"] == 49.0
    assert body["decorations"][1]["name"] == "Stjärna"


@pytest.mark.asyncio
async def test_options_defaults_to_english(client):
    with patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG):
        response = await client.get("/data/wreath/options")
    assert response.json()["sizes"][0]["name"] == "Small"


@pytest.mark.asyncio
async def test_create_design_stores_server_price_and_image(client):
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.wreath_routes.insert_wreath_design", new_callable=AsyncMock) as insert,
    ):
        response = await client.post("/data/wreath/designs", json=_design_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 363.0  # 299 + 49 + 15
    assert body["imagePath"] == f"/data/wreath/designs/{body['designID']}/image"
    assert body["imageUrl"] == f"http://localhost:3000/data/wreath/designs/{body['designID']}/image"
    assert body["summary"]["decorations"] == [{"slot": 1, "en": "Pine cone", "sv": "Kotte"}]
    insert.assert_awaited_once()
    _, design_id, spec, price, image = insert.await_args.args
    assert design_id == body["designID"]
    assert spec["decorations"] == [{"slot": 0, "code": "pine-cone"}]
    assert str(price) == "363.00"
    assert image == _png()


@pytest.mark.asyncio
async def test_create_design_without_image(client):
    payload = _design_payload()
    del payload["image"]
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.wreath_routes.insert_wreath_design", new_callable=AsyncMock) as insert,
    ):
        response = await client.post("/data/wreath/designs", json=payload)
    assert response.status_code == 200
    assert response.json()["imagePath"] is None
    assert response.json()["imageUrl"] is None
    assert insert.await_args.args[4] is None


@pytest.mark.asyncio
async def test_create_design_rejects_bad_slot(client):
    with patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG):
        response = await client.post(
            "/data/wreath/designs", json=_design_payload(decorations=[{"slot": 6, "code": "pine-cone"}])
        )
    assert response.status_code == 400
    assert "Slot 7" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_design_rejects_bad_image(client):
    payload = _design_payload()
    payload["image"] = "data:image/jpeg;base64,AAAA"
    with patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG):
        response = await client.post("/data/wreath/designs", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_design_rejects_malformed_spec(client):
    payload = _design_payload()
    del payload["spec"]["sizeCode"]
    response = await client.post("/data/wreath/designs", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_design_image_found(client):
    design_id = "123e4567-e89b-42d3-a456-426614174000"
    with patch("routers.wreath_routes.get_wreath_design_image", new_callable=AsyncMock, return_value=_png()):
        response = await client.get(f"/data/wreath/designs/{design_id}/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "immutable" in response.headers["cache-control"]
    assert response.content == _png()


@pytest.mark.asyncio
async def test_design_image_missing(client):
    with patch("routers.wreath_routes.get_wreath_design_image", new_callable=AsyncMock, return_value=None):
        response = await client.get("/data/wreath/designs/123e4567-e89b-42d3-a456-426614174000/image")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_design_image_rejects_non_uuid_without_touching_db(client):
    with patch("routers.wreath_routes.get_wreath_design_image", new_callable=AsyncMock) as get_image:
        response = await client.get("/data/wreath/designs/not-a-uuid/image")
    assert response.status_code == 404
    get_image.assert_not_awaited()
