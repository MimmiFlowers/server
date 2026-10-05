"""Cloudflare R2 uploads (S3-compatible API via boto3).

Customer wreath designs are stored as public PNGs under R2_WREATH_DESIGNS_PREFIX
in R2_BUCKET and served from R2_PUBLIC_URL (the bucket's custom domain), so the
cart, Stripe, the order email and the Telegram bot all use the same URL.

boto3 is synchronous; uploads run in a worker thread so the event loop never blocks.
"""

import asyncio
from functools import lru_cache

import boto3
from botocore.config import Config

from config import settings

# Keys are UUIDs and never reused, so a picture can be cached forever.
_CACHE_CONTROL = "public, max-age=31536000, immutable"


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def design_key(design_id: str) -> str:
    """Object key for a design's PNG, e.g. 'wreaths/designs/<uuid>.png'."""
    prefix = settings.R2_WREATH_DESIGNS_PREFIX.strip("/")
    return f"{prefix}/{design_id}.png"


def public_url(key: str) -> str:
    return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"


async def upload_png(key: str, data: bytes) -> str:
    """Upload PNG bytes to `key` and return the public URL. Raises on failure."""
    await asyncio.to_thread(
        _client().put_object,
        Bucket=settings.R2_BUCKET,
        Key=key,
        Body=data,
        ContentType="image/png",
        CacheControl=_CACHE_CONTROL,
    )
    return public_url(key)
