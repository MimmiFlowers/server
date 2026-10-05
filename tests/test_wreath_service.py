"""Unit tests for services/wreath.py — pure functions, no DB."""

import base64
import struct
import zlib
from decimal import Decimal

import pytest

from routers.classes.classes import WreathSpec
from services.wreath import (
    WreathSpecError,
    catalog_for_client,
    decode_png_data_url,
    describe_summary,
    order_item,
    validate_and_price,
)

# Shape mirrors database.wreath.get_wreath_catalog(): dict rows, Decimal prices, JSONB names.
CATALOG = {
    "sizes": [
        {"code": "s", "name": {"en": "Small", "sv": "Liten"}, "diameterCm": 25, "slotCount": 6},
        {"code": "m", "name": {"en": "Medium", "sv": "Mellan"}, "diameterCm": 35, "slotCount": 8},
    ],
    "materials": [
        {"code": "fir", "name": {"en": "Fir", "sv": "Gran"}, "image": "/wreath/base-fir.svg"},
        {"code": "moss", "name": {"en": "Moss", "sv": "Mossa"}, "image": "/wreath/base-moss.svg"},
    ],
    "bases": [
        {"sizeCode": "s", "materialCode": "fir", "price": Decimal("299.00"),
         "image": "https://images-stg.mimmiflowers.se/wreath/base-s-fir.png"},
        {"sizeCode": "s", "materialCode": "moss", "price": Decimal("349.00"), "image": None},
        {"sizeCode": "m", "materialCode": "fir", "price": Decimal("399.00")},  # no image key at all
        # deliberately no (m, moss) row
    ],
    "bands": [
        {"code": "red-velvet", "name": {"en": "Red velvet", "sv": "Röd sammet"},
         "image": "/wreath/band-red-velvet.svg", "price": Decimal("49.00")},
    ],
    "decorations": [
        {"code": "pine-cone", "name": {"en": "Pine cone", "sv": "Kotte"},
         "image": "/wreath/deco-pine-cone.svg", "price": Decimal("15.00")},
        {"code": "star", "name": {"en": "Star", "sv": "Stjärna"},
         "image": "/wreath/deco-star.svg", "price": Decimal("25.00")},
    ],
}


def _spec(**overrides) -> WreathSpec:
    base = {
        "sizeCode": "s",
        "materialCode": "fir",
        "bandCode": "red-velvet",
        "decorations": [{"slot": 5, "code": "pine-cone"}, {"slot": 0, "code": "pine-cone"}],
    }
    base.update(overrides)
    return WreathSpec(**base)


def _png(width: int = 8, height: int = 8) -> bytes:
    """Minimal valid RGBA PNG of the given size."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00" * (4 * width) for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


# ── validate_and_price ────────────────────────────────────────────

def test_prices_base_plus_band_plus_each_placement():
    priced = validate_and_price(_spec(), CATALOG)
    assert priced["price"] == Decimal("378.00")  # 299 + 49 + 15 + 15


def test_no_band_and_no_decorations_is_base_price_only():
    priced = validate_and_price(_spec(bandCode=None, decorations=[]), CATALOG)
    assert priced["price"] == Decimal("299.00")
    assert priced["summary"]["band"] is None
    assert priced["summary"]["decorations"] == []


def test_summary_is_bilingual_sorted_by_slot_and_one_based():
    summary = validate_and_price(_spec(), CATALOG)["summary"]
    assert summary["size"] == {"en": "Small 25 cm", "sv": "Liten 25 cm", "slotCount": 6}
    assert summary["material"] == {"en": "Fir", "sv": "Gran"}
    assert summary["band"] == {"en": "Red velvet", "sv": "Röd sammet"}
    assert summary["decorations"] == [
        {"slot": 1, "en": "Pine cone", "sv": "Kotte"},
        {"slot": 6, "en": "Pine cone", "sv": "Kotte"},
    ]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"sizeCode": "xl"}, "Unknown wreath size"),
        ({"materialCode": "gold"}, "Unknown wreath material"),
        ({"sizeCode": "m", "materialCode": "moss"}, "combination is not available"),
        ({"bandCode": "blue"}, "Unknown band"),
        ({"decorations": [{"slot": 0, "code": "unicorn"}]}, "Unknown decoration"),
        ({"decorations": [{"slot": 6, "code": "pine-cone"}]}, "Slot 7 does not exist"),
        ({"decorations": [{"slot": 2, "code": "star"}, {"slot": 2, "code": "pine-cone"}]}, "Slot 3 is used twice"),
    ],
)
def test_rejects_invalid_specs(overrides, message):
    with pytest.raises(WreathSpecError, match=message):
        validate_and_price(_spec(**overrides), CATALOG)


def test_describe_summary_groups_decorations():
    summary = validate_and_price(_spec(decorations=[
        {"slot": 0, "code": "pine-cone"}, {"slot": 1, "code": "star"}, {"slot": 2, "code": "pine-cone"},
    ]), CATALOG)["summary"]
    assert describe_summary(summary, "en") == "Small 25 cm · Fir · Red velvet · Pine cone ×2, Star ×1"
    assert describe_summary(summary, "sv") == "Liten 25 cm · Gran · Röd sammet · Kotte ×2, Stjärna ×1"


# ── decode_png_data_url ───────────────────────────────────────────

def test_decodes_valid_png():
    assert decode_png_data_url(_data_url(_png())) == _png()


def test_rejects_non_png_data_url_prefix():
    with pytest.raises(WreathSpecError, match="PNG"):
        decode_png_data_url("data:image/jpeg;base64," + base64.b64encode(_png()).decode())


def test_rejects_bytes_without_png_signature():
    with pytest.raises(WreathSpecError, match="not a PNG"):
        decode_png_data_url("data:image/png;base64," + base64.b64encode(b"\xff\xd8\xff" + b"0" * 40).decode())


def test_rejects_invalid_base64():
    with pytest.raises(WreathSpecError, match="base64"):
        decode_png_data_url("data:image/png;base64,***not-base64***")


def test_rejects_oversized_dimensions():
    with pytest.raises(WreathSpecError, match="dimensions"):
        decode_png_data_url(_data_url(_png(4000, 1)))


def test_rejects_oversized_payload():
    with pytest.raises(WreathSpecError, match="too large"):
        decode_png_data_url(_data_url(_png() + b"\x00" * 600_000))


def test_rejects_png_whose_first_chunk_is_not_ihdr():
    fake = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"tEXt" + b"\x00" * 13 + b"\x00" * 8
    with pytest.raises(WreathSpecError, match="not a PNG"):
        decode_png_data_url(_data_url(fake))


# ── order_item / catalog_for_client ───────────────────────────────

def test_order_item_uses_int_for_whole_sek_and_float_otherwise():
    priced = validate_and_price(_spec(), CATALOG)
    item = order_item("abc", priced, 2, "sv-SE", image_url="https://images.test/wreaths/test/designs/abc.png")
    assert item == {
        "id": "wreath-abc",
        "name": "Egen julkrans",
        "quantity": 2,
        "price": 378,
        "picture": "https://images.test/wreaths/test/designs/abc.png",
        "designID": "abc",
        "wreath": priced["summary"],
    }
    assert isinstance(item["price"], int)
    fractional = {"price": Decimal("299.50"), "summary": priced["summary"]}
    assert order_item("abc", fractional, 1, "en", image_url=None)["price"] == 299.5
    assert order_item("abc", fractional, 1, "en", image_url=None)["picture"] == ""
    assert order_item("abc", priced, 1, "en", image_url="https://images.test/wreaths/test/designs/abc.png")["name"] == "Custom Christmas wreath"


def test_catalog_for_client_resolves_language_and_nests_bases():
    sv = catalog_for_client(CATALOG, "sv")
    assert sv["sizes"][0] == {"code": "s", "name": "Liten", "diameterCm": 25, "slotCount": 6}
    assert sv["materials"][1]["name"] == "Mossa"
    assert sv["basePrices"] == {"s": {"fir": 299.0, "moss": 349.0}, "m": {"fir": 399.0}}
    # Only bases that have their own picture; the client falls back to the material image.
    assert sv["baseImages"] == {"s": {"fir": "https://images-stg.mimmiflowers.se/wreath/base-s-fir.png"}}
    assert sv["bands"][0] == {"code": "red-velvet", "name": "Röd sammet", "image": "/wreath/band-red-velvet.svg", "price": 49.0}
    assert sv["decorations"][1]["name"] == "Stjärna" and sv["decorations"][1]["price"] == 25.0
    assert catalog_for_client(CATALOG, "en")["sizes"][0]["name"] == "Small"
    assert catalog_for_client(CATALOG, "de")["sizes"][0]["name"] == "Small"  # unknown locale → en
