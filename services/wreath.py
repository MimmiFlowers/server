"""Pure wreath-builder logic: spec validation, pricing, summaries, PNG checks.

No database and no I/O here — everything takes the option catalogue as a dict
(see database/wreath.get_wreath_catalog) so it is trivially unit-testable.

Units: every price in and out of this module is SEK as Decimal. Option prices in
the catalog must already be Decimal (psycopg returns NUMERIC as Decimal); floats
are never coerced here.
"""

import base64
import struct
from decimal import Decimal

from config import SITE_URL
from routers.classes.classes import WreathSpec

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_BYTES = 500_000
MAX_IMAGE_SIDE = 1600
_DATA_URL_PREFIX = "data:image/png;base64,"

# Cart/receipt line name for a custom wreath, by customer locale.
DISPLAY_NAME = {"en": "Custom Christmas wreath", "sv": "Egen julkrans"}


class WreathSpecError(ValueError):
    """The spec references unknown/inactive options or invalid slots.

    The message is safe to return to the client verbatim.
    """


def lang_for(locale: str) -> str:
    return "sv" if locale.startswith("sv") else "en"


def _by_code(rows: list[dict]) -> dict[str, dict]:
    return {row["code"]: row for row in rows}


def _names(row: dict) -> dict[str, str]:
    name = row.get("name") or {}
    return {"en": name.get("en", ""), "sv": name.get("sv") or name.get("en", "")}


def validate_and_price(spec: WreathSpec, catalog: dict) -> dict:
    """Check every option exists and compute the SEK price.

    Returns {"price": Decimal, "summary": {...}} where summary is the bilingual,
    human-readable form stored in orders.items and rendered by email + bot.
    Summary slots are 1-based; spec slots are 0-based.
    Slot i of a size with slotCount n sits at angle (i + 0.5) * 360 / n clockwise
    from the top (the bow); the client's wreathGeometry.ts implements the same rule.
    """
    sizes = _by_code(catalog["sizes"])
    materials = _by_code(catalog["materials"])
    bands = _by_code(catalog["bands"])
    decorations = _by_code(catalog["decorations"])

    size = sizes.get(spec.sizeCode)
    if size is None:
        raise WreathSpecError("Unknown wreath size")
    material = materials.get(spec.materialCode)
    if material is None:
        raise WreathSpecError("Unknown wreath material")
    base = next(
        (p for p in catalog["base_prices"]
         if p["sizeCode"] == spec.sizeCode and p["materialCode"] == spec.materialCode),
        None,
    )
    if base is None:
        raise WreathSpecError("This size and material combination is not available")

    band = None
    if spec.bandCode is not None:
        band = bands.get(spec.bandCode)
        if band is None:
            raise WreathSpecError("Unknown band")

    slot_count = int(size["slotCount"])
    seen: set[int] = set()
    placed: list[tuple[int, dict]] = []
    for placement in sorted(spec.decorations, key=lambda d: d.slot):
        if placement.slot >= slot_count:
            raise WreathSpecError(f"Slot {placement.slot + 1} does not exist on this size")
        if placement.slot in seen:
            raise WreathSpecError(f"Slot {placement.slot + 1} is used twice")
        seen.add(placement.slot)
        decoration = decorations.get(placement.code)
        if decoration is None:
            raise WreathSpecError("Unknown decoration")
        placed.append((placement.slot, decoration))

    price = Decimal(base["price"])
    if band is not None:
        price += Decimal(band["price"])
    for _, decoration in placed:
        price += Decimal(decoration["price"])

    size_names = _names(size)
    summary = {
        "size": {
            "en": f"{size_names['en']} {size['diameterCm']} cm",
            "sv": f"{size_names['sv']} {size['diameterCm']} cm",
            "slotCount": slot_count,
        },
        "material": _names(material),
        "band": _names(band) if band is not None else None,
        "decorations": [{"slot": slot + 1, **_names(decoration)} for slot, decoration in placed],
    }
    return {"price": price, "summary": summary}


def describe_summary(summary: dict, locale: str) -> str:
    """One-line description for the Stripe line item, e.g.
    'Small 25 cm · Fir · Red velvet · Pine cone ×2, Star ×1'."""
    lang = lang_for(locale)
    parts = [summary["size"][lang], summary["material"][lang]]
    if summary.get("band"):
        parts.append(summary["band"][lang])
    counts: dict[str, int] = {}
    for decoration in summary.get("decorations", []):
        counts[decoration[lang]] = counts.get(decoration[lang], 0) + 1
    if counts:
        parts.append(", ".join(f"{name} ×{n}" for name, n in counts.items()))
    return " · ".join(parts)


def decode_png_data_url(data_url: str) -> bytes:
    """Turn the browser's PNG data URL into bytes, rejecting anything that is
    not a small PNG. Only the header is inspected — we never decode pixels."""
    if not data_url.startswith(_DATA_URL_PREFIX):
        raise WreathSpecError("Image must be a PNG data URL")
    try:
        raw = base64.b64decode(data_url[len(_DATA_URL_PREFIX):], validate=True)
    except Exception as exc:  # binascii.Error, ValueError
        raise WreathSpecError("Image is not valid base64") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise WreathSpecError("Image is too large")
    # Signature, then the mandatory 13-byte IHDR chunk: length (4) + "IHDR" (4) + data.
    if (
        len(raw) < 24
        or not raw.startswith(PNG_SIGNATURE)
        or raw[8:12] != b"\x00\x00\x00\x0d"
        or raw[12:16] != b"IHDR"
    ):
        raise WreathSpecError("Image is not a PNG")
    width, height = struct.unpack(">II", raw[16:24])
    if not (0 < width <= MAX_IMAGE_SIDE and 0 < height <= MAX_IMAGE_SIDE):
        raise WreathSpecError("Image dimensions are out of range")
    return raw


def image_path(design_id: str) -> str:
    return f"/data/wreath/designs/{design_id}/image"


def image_url(design_id: str) -> str:
    return f"{SITE_URL}{image_path(design_id)}"


def catalog_for_client(catalog: dict, locale: str) -> dict:
    """Language-resolved, float-priced catalogue for GET /data/wreath/options."""
    lang = lang_for(locale)

    def name(row: dict) -> str:
        return _names(row)[lang]

    base_prices: dict[str, dict[str, float]] = {}
    for p in catalog["base_prices"]:
        base_prices.setdefault(p["sizeCode"], {})[p["materialCode"]] = float(p["price"])

    return {
        "sizes": [
            {"code": s["code"], "name": name(s), "diameterCm": s["diameterCm"], "slotCount": s["slotCount"]}
            for s in catalog["sizes"]
        ],
        "materials": [
            {"code": m["code"], "name": name(m), "image": m["image"]} for m in catalog["materials"]
        ],
        "basePrices": base_prices,
        "bands": [
            {"code": b["code"], "name": name(b), "image": b["image"], "price": float(b["price"])}
            for b in catalog["bands"]
        ],
        "decorations": [
            {"code": d["code"], "name": name(d), "image": d["image"], "price": float(d["price"])}
            for d in catalog["decorations"]
        ],
    }


def order_item(design_id: str, priced: dict, quantity: int, locale: str, has_image: bool) -> dict:
    """The server-built entry that replaces the client's wreath line in orders.items.

    `price` is SEK (like every other orders.items[].price); whole numbers stay ints
    so the email/bot "{price * qty:,} kr" formatting prints '378 kr', not '378.0 kr'.
    """
    price: Decimal = priced["price"]
    return {
        "id": f"wreath-{design_id}",
        "name": DISPLAY_NAME[lang_for(locale)],
        "quantity": quantity,
        "price": int(price) if price == price.to_integral_value() else float(price),
        "picture": image_url(design_id) if has_image else "",
        "designID": design_id,
        "wreath": priced["summary"],
    }
