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
            "picture": "https://images-stg.mimmiflowers.se/wreaths/designs/x.png",
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
    body = _build_html_body(_order("en"))
    assert "Size: Small 25 cm" in body
    assert "slot 4 of 6: Star &lt;b&gt;" in body
    assert "Star <b>" not in body
    # Indented option lines are laid out with padding, and long names may wrap.
    assert "padding-left:12px" in body
    assert "white-space:pre" not in body


def test_plain_text_lists_options():
    text = _build_plain_text(_order("sv"))
    assert "      Storlek: Liten 25 cm" in text
    assert "        plats 1 av 6: Kotte" in text


def test_wreath_with_band_en():
    lines = _wreath_lines({**WREATH, "band": {"en": "Gold", "sv": "Guld"}}, "en")
    assert "Band: Gold" in lines


def test_unknown_locale_falls_back_to_english():
    assert _wreath_lines(WREATH, "de")[0] == "Size: Small 25 cm"


def test_missing_sv_name_falls_back_to_en():
    wreath = {**WREATH, "decorations": [{"slot": 2, "en": "Ribbon"}]}
    assert "  plats 2 av 6: Ribbon" in _wreath_lines(wreath, "sv")


def test_malformed_wreath_does_not_break_email():
    order = _order("sv")
    order["items"] = [
        {"name": "Plain bouquet", "quantity": 1, "price": 100, "wreath": "garbage"},
        {
            "name": "Odd wreath", "quantity": 1, "price": 200,
            "wreath": {"decorations": ["x", None], "size": "big"},
        },
    ]
    body = _build_html_body(order)
    text = _build_plain_text(order)
    for rendered in (body, text):
        assert "Plain bouquet" in rendered
        assert "Odd wreath" in rendered


def test_line_totals_have_no_float_artefacts():
    order = _order("en")
    order["items"] = [
        {"name": "Fractional wreath", "quantity": 7, "price": 449.99},
        {"name": "Whole bouquet", "quantity": 1, "price": 1200},
    ]
    body = _build_html_body(order)
    text = _build_plain_text(order)
    for rendered in (body, text):
        assert "3,149.93 kr" in rendered
        assert "1,200 kr" in rendered
        assert "3149.9299" not in rendered
