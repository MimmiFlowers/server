"""Centralized configuration — single source of truth for all env vars.

Import this module early (it's imported by main.py at startup).
It loads the correct .env file once, validates that all required
variables are present, and exports typed constants.

Usage in other modules:
    from config import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY
    pool = AsyncConnectionPool(conninfo=settings.DB_URL, ...)
"""

import os
import sys
import logging
from dataclasses import dataclass, fields
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Determine environment and load the correct .env file
# ---------------------------------------------------------------------------
ENV: str = os.environ.get("ENV", "dev")

_env_files = {
    "dev": ".env.dev",
    "stg": ".env.stg",
    "prod": ".env.prod",
}

_env_file = _env_files.get(ENV)
if _env_file is None:
    sys.exit(f"FATAL: Unknown ENV value '{ENV}'. Expected one of: {', '.join(_env_files)}")

# override=False means real env vars (e.g. from Docker/systemd) take
# precedence over the file, which is the correct production behaviour.
load_dotenv(_env_file, override=False)
logger.info("Loaded environment from %s (ENV=%s)", _env_file, ENV)


# ---------------------------------------------------------------------------
# 2. Settings dataclass — every required env var is declared here
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Settings:
    """All environment variables required by the application.

    Each field corresponds to an env var of the same name.
    Add new vars here and they will be validated automatically.
    """

    # Database
    DB_URL: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    SUCCESS_URL: str = ""
    CANCEL_URL: str = ""

    # SMTP (Zoho)
    ZOHO_SMTP_HOST: str = ""
    ZOHO_SMTP_PORT: str = ""
    ZOHO_SMTP_USER: str = ""
    ZOHO_SMTP_PASSWORD: str = ""
    ZOHO_SMTP_SENDER_NAME: str = ""


# ---------------------------------------------------------------------------
# 3. Build settings from environment and validate
# ---------------------------------------------------------------------------
def _load_settings() -> Settings:
    """Read every Settings field from os.environ and validate completeness."""
    values: dict[str, str] = {}
    missing: list[str] = []

    for f in fields(Settings):
        val = os.environ.get(f.name)
        if val is None or val.strip() == "":
            missing.append(f.name)
        else:
            values[f.name] = val

    if missing:
        sys.exit(
            f"FATAL: Missing required environment variables: {', '.join(missing)}.\n"
            f"       Loaded env file: {_env_file} (ENV={ENV}).\n"
            f"       Set them in the env file or as real environment variables."
        )

    return Settings(**values)


settings: Settings = _load_settings()
