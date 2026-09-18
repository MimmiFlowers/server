"""The confirmation email renders a custom wreath's option list in both bodies."""

from services.mailing import _build_html_body, _build_plain_text, _wreath_lines

WREATH = {
    "size": {"en": "Small 25 cm", "sv": "Liten 25 cm", "slotCount": 6},
    "material": {"en": "Fir", "sv": "Gran"},
    "band": None,
    "decorations": [
        {"slot": 1, "en": "Pine cone", "sv": "Kotte"},
        {"slot": 4, "en": "Star <b>", "sv": "Stjärna <b>"},
    ],
}


def _order(locale: str) -> dict:
    return {
        "orderID": "ORD-TEST",
        "locale": locale,
        "customer": {"firstName": "Anna", "lastName": "S", "email": "a@example.com", "phone": "1"},
        "recipient": {"address": "Storgatan 1", "date": "2026-12-20", "time": "12:00"},
        "pickup": False,
        "orderForMyself": True,
        "items": [{
            "name": "Custom Christmas wreath", "quantity": 1, "price": 354,
            "picture": "https://stg.mimmiflowers.se/data/wreath/designs/x/image",
            "designID": "x", "wreath": WREATH,
        }],
        "subtotal": 35400, "deliveryFee": 9900, "total": 45300, "moms": 9060,
    }


def test_wreath_lines_sv():
    assert _wreath_lines(WREATH, "sv") == [
        "Storlek: Liten 25 cm",
        "Material: Gran",
        "Band: inget",
        "Dekorationer:",
        "  plats 1 av 6: Kotte",
        "  plats 4 av 6: Stjärna <b>",
    ]


def test_wreath_lines_without_decorations_en():
    lines = _wreath_lines({**WREATH, "decorations": []}, "en")
    assert lines[-1] == "Decorations: none"


def test_html_body_lists_options_escaped():
    html = _build_html_body(_order("en"))
    assert "Size: Small 25 cm" in html
    assert "slot 4 of 6: Star &lt;b&gt;" in html
    assert "Star <b>" not in html


def test_plain_text_lists_options():
    text = _build_plain_text(_order("sv"))
    assert "      Storlek: Liten 25 cm" in text
    assert "        plats 1 av 6: Kotte" in text
