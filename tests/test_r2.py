"""Tests for services/r2.py — the boto3 client is replaced, nothing leaves the machine."""

from unittest.mock import MagicMock, patch

import pytest

from services import r2


def test_design_key_uses_the_configured_prefix():
    assert r2.design_key("abc") == "wreaths/test/designs/abc.png"


@pytest.mark.parametrize(
    "prefix, expected",
    [
        ("wreaths/designs/", "wreaths/designs/abc.png"),
        ("wreaths/designs", "wreaths/designs/abc.png"),
        ("/wreaths/dev/designs/", "wreaths/dev/designs/abc.png"),
    ],
)
def test_design_key_tolerates_slashes(prefix, expected):
    with patch("services.r2.settings") as fake:
        fake.R2_WREATH_DESIGNS_PREFIX = prefix
        assert r2.design_key("abc") == expected


def test_public_url_joins_domain_and_key():
    assert r2.public_url("wreaths/test/designs/abc.png") == "https://images.test/wreaths/test/designs/abc.png"
    with patch("services.r2.settings") as fake:
        fake.R2_PUBLIC_URL = "https://images.test/"
        assert r2.public_url("k.png") == "https://images.test/k.png"


@pytest.mark.asyncio
async def test_upload_png_puts_an_immutable_png_and_returns_its_public_url():
    client = MagicMock()
    with patch("services.r2._client", return_value=client):
        url = await r2.upload_png("wreaths/test/designs/abc.png", b"\x89PNG...")
    client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="wreaths/test/designs/abc.png",
        Body=b"\x89PNG...",
        ContentType="image/png",
        CacheControl="public, max-age=31536000, immutable",
    )
    assert url == "https://images.test/wreaths/test/designs/abc.png"


@pytest.mark.asyncio
async def test_upload_png_propagates_failures():
    client = MagicMock()
    client.put_object.side_effect = RuntimeError("R2 down")
    with patch("services.r2._client", return_value=client), pytest.raises(RuntimeError):
        await r2.upload_png("k.png", b"x")
