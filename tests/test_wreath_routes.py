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
    assert body["baseImages"] == {"s": {"fir": "https://images-stg.mimmiflowers.se/wreath/base-s-fir.png"}}
    assert body["bands"][0]["price"] == 49.0
    assert body["decorations"][1]["name"] == "Stjärna"


@pytest.mark.asyncio
async def test_options_defaults_to_english(client):
    with patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG):
        response = await client.get("/data/wreath/options")
    assert response.json()["sizes"][0]["name"] == "Small"


UPLOAD_PATCH = "routers.wreath_routes.upload_png"


async def _fake_upload(key: str, data: bytes) -> str:
    return f"https://images.test/{key}"


@pytest.mark.asyncio
async def test_create_design_uploads_png_to_r2_and_stores_its_url(client):
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch(UPLOAD_PATCH, new_callable=AsyncMock, side_effect=_fake_upload) as upload,
        patch("routers.wreath_routes.insert_wreath_design", new_callable=AsyncMock) as insert,
    ):
        response = await client.post("/data/wreath/designs", json=_design_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == 363.0  # 299 + 49 + 15
    expected_url = f"https://images.test/wreaths/test/designs/{body['designID']}.png"
    assert body["imageUrl"] == expected_url
    assert "imagePath" not in body
    assert body["summary"]["decorations"] == [{"slot": 1, "en": "Pine cone", "sv": "Kotte"}]
    upload.assert_awaited_once_with(f"wreaths/test/designs/{body['designID']}.png", _png())
    insert.assert_awaited_once()
    _, design_id, spec, price, image_url = insert.await_args.args
    assert design_id == body["designID"]
    assert spec["decorations"] == [{"slot": 0, "code": "pine-cone"}]
    assert str(price) == "363.00"
    assert image_url == expected_url


@pytest.mark.asyncio
async def test_create_design_without_image(client):
    payload = _design_payload()
    del payload["image"]
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch(UPLOAD_PATCH, new_callable=AsyncMock) as upload,
        patch("routers.wreath_routes.insert_wreath_design", new_callable=AsyncMock) as insert,
    ):
        response = await client.post("/data/wreath/designs", json=payload)
    assert response.status_code == 200
    assert response.json()["imageUrl"] is None
    upload.assert_not_awaited()
    assert insert.await_args.args[4] is None


@pytest.mark.asyncio
async def test_create_design_survives_an_r2_failure_without_a_picture(client):
    """Like a failed browser export: the design (and the order) still go through."""
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch(UPLOAD_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("R2 down")),
        patch("routers.wreath_routes.insert_wreath_design", new_callable=AsyncMock) as insert,
    ):
        response = await client.post("/data/wreath/designs", json=_design_payload())
    assert response.status_code == 200
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
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch(UPLOAD_PATCH, new_callable=AsyncMock) as upload,
    ):
        response = await client.post("/data/wreath/designs", json=payload)
    assert response.status_code == 400
    upload.assert_not_awaited()  # never upload what failed validation


@pytest.mark.asyncio
async def test_create_design_rejects_malformed_spec(client):
    payload = _design_payload()
    del payload["spec"]["sizeCode"]
    response = await client.post("/data/wreath/designs", json=payload)
    assert response.status_code == 422


# ── DB failures never leak exception text ─────────────────────────

@pytest.mark.asyncio
async def test_options_db_failure_is_500(client):
    with patch(CATALOG_PATCH, new_callable=AsyncMock, side_effect=RuntimeError("db down")):
        response = await client.get("/data/wreath/options")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


@pytest.mark.asyncio
async def test_create_design_db_failure_is_500(client):
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch(
            "routers.wreath_routes.insert_wreath_design",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ),
    ):
        response = await client.post("/data/wreath/designs", json=_design_payload())
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


# ── Rate limiting ─────────────────────────────────────────────────

@pytest.fixture
def fresh_design_limiter():
    """Clear the in-memory rate-limit storage before and after, so this test
    neither inherits hits from earlier POSTs nor leaves 20 hits for later ones."""
    from routers.wreath_routes import limiter

    limiter.reset()
    yield limiter
    limiter.reset()


@pytest.mark.asyncio
async def test_create_design_is_rate_limited(client, fresh_design_limiter):
    with (
        patch(CATALOG_PATCH, new_callable=AsyncMock, return_value=CATALOG),
        patch("routers.wreath_routes.insert_wreath_design", new_callable=AsyncMock),
    ):
        statuses = [
            (await client.post("/data/wreath/designs", json=_design_payload())).status_code
            for _ in range(21)
        ]
    assert statuses[:20] == [200] * 20
    assert statuses[20] == 429


@pytest.mark.asyncio
async def test_design_image_endpoint_is_gone(client):
    """Pictures are served by R2 now; the old server endpoint must not linger."""
    response = await client.get("/data/wreath/designs/123e4567-e89b-42d3-a456-426614174000/image")
    assert response.status_code in (404, 405)
