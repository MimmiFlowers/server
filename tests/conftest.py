"""Shared fixtures for server tests.

Sets dummy env vars so config.py doesn't sys.exit() on import,
then provides an httpx AsyncClient wired to the FastAPI app.
"""

import os

# Must set env vars BEFORE any application import (config.py reads them at module level)
os.environ.update({
    "ENV": "dev",
    "DB_URL": "postgresql://test:test@localhost:5432/testdb",
    "STRIPE_SECRET_KEY": "sk_test_fake",
    "STRIPE_WEBHOOK_SECRET": "whsec_fake",
    "SUCCESS_URL": "http://localhost:3000/Success/",
    "CANCEL_URL": "http://localhost:3000/Cancel/",
    "ZOHO_SMTP_HOST": "smtp.example.com",
    "ZOHO_SMTP_PORT": "587",
    "ZOHO_SMTP_USER": "test@example.com",
    "ZOHO_SMTP_PASSWORD": "testpass",
    "ZOHO_SMTP_SENDER_NAME": "Test",
})

from collections.abc import AsyncGenerator  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from main import app  # noqa: E402
from database.dbconfig.dbconfig import get_db_connection  # noqa: E402


class FakeCursor:
    """Minimal async cursor that returns canned data."""

    def __init__(self, rows: list[dict] | None = None):
        self._rows = rows or []

    async def execute(self, query: str, params=None):
        pass

    async def fetchone(self):
        return self._rows[0] if self._rows else None

    async def fetchall(self):
        return self._rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeConnection:
    """Minimal async connection that yields FakeCursors."""

    def __init__(self, rows: list[dict] | None = None):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)

    async def commit(self):
        pass

    async def rollback(self):
        pass


@pytest.fixture
def fake_conn():
    """Provide a FakeConnection that can be customised per test."""
    return FakeConnection()


@pytest.fixture
def client(fake_conn) -> AsyncGenerator[AsyncClient, None]:
    """Override the DB dependency and return an httpx test client."""

    async def _override():
        yield fake_conn

    app.dependency_overrides[get_db_connection] = _override

    transport = ASGITransport(app=app)
    async_client = AsyncClient(transport=transport, base_url="http://test")
    yield async_client

    app.dependency_overrides.clear()
