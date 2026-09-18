"""Boundary tests for the wreath request models and the derived SITE_URL."""

import pytest
from pydantic import ValidationError

from config import SITE_URL
from routers.classes.classes import CartItem, WreathDesignRequest, WreathSpec

UUID = "123e4567-e89b-42d3-a456-426614174000"


def test_site_url_is_the_origin_of_success_url():
    # conftest sets SUCCESS_URL=http://localhost:3000/Success/
    assert SITE_URL == "http://localhost:3000"


def test_cart_item_design_id_optional_and_validated():
    assert CartItem(name="x", price=1, quantity=1).designID is None
    assert CartItem(name="x", price=1, quantity=1, designID=UUID).designID == UUID
    for bad in ["", "not-a-uuid", UUID + "\n", UUID[:-1]]:
        with pytest.raises(ValidationError):
            CartItem(name="x", price=1, quantity=1, designID=bad)


@pytest.mark.parametrize("code", ["fir", "red-velvet", "a1", "x" * 40])
def test_option_codes_accepted(code):
    assert WreathSpec(sizeCode=code, materialCode=code).sizeCode == code


@pytest.mark.parametrize("code", ["", "FIR", "fir\n", "../x", "a b", "x" * 41])
def test_option_codes_rejected(code):
    with pytest.raises(ValidationError):
        WreathSpec(sizeCode=code, materialCode="fir")


def test_band_code_none_allowed_but_empty_string_rejected():
    assert WreathSpec(sizeCode="s", materialCode="fir", bandCode=None).bandCode is None
    with pytest.raises(ValidationError):
        WreathSpec(sizeCode="s", materialCode="fir", bandCode="")


def test_slot_bounds_and_decoration_count():
    WreathSpec(sizeCode="s", materialCode="fir", decorations=[{"slot": 63, "code": "star"}])
    with pytest.raises(ValidationError):
        WreathSpec(sizeCode="s", materialCode="fir", decorations=[{"slot": 64, "code": "star"}])
    with pytest.raises(ValidationError):
        WreathSpec(sizeCode="s", materialCode="fir", decorations=[{"slot": -1, "code": "star"}])
    too_many = [{"slot": i, "code": "star"} for i in range(65)]
    with pytest.raises(ValidationError):
        WreathSpec(sizeCode="s", materialCode="fir", decorations=too_many)


def test_image_length_cap():
    spec = {"sizeCode": "s", "materialCode": "fir"}
    assert WreathDesignRequest(spec=spec, image=None).image is None
    assert len(WreathDesignRequest(spec=spec, image="a" * 700_000).image) == 700_000
    with pytest.raises(ValidationError):
        WreathDesignRequest(spec=spec, image="a" * 700_001)
