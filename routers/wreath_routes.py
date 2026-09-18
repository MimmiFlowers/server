"""Wreath builder endpoints, mounted under /data so the client's nginx /data/ proxy covers them."""

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from database.dbconfig.dbconfig import get_db_connection
from database.wreath import get_wreath_catalog, get_wreath_design_image, insert_wreath_design
from routers.classes.classes import WreathDesignRequest
from services.wreath import (
    WreathSpecError,
    catalog_for_client,
    decode_png_data_url,
    image_path,
    image_url,
    validate_and_price,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/data/wreath",
    tags=["wreath"],
    responses={404: {"description": "Not found"}},
)

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@router.get("/options")
async def get_options(request: Request, conn=Depends(get_db_connection)):
    """Active sizes, materials, price matrix, bands and decorations, names in the caller's language."""
    lang = request.headers.get("accept-language", "en")[:2]
    try:
        catalog = await get_wreath_catalog(conn)
    except Exception as e:
        logger.error("Failed to load wreath options: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    return catalog_for_client(catalog, lang)


@router.post("/designs")
@limiter.limit("20/minute")
async def create_design(request: Request, data: WreathDesignRequest, conn=Depends(get_db_connection)):
    """Validate + price a design, store it (with the customer's PNG) and return its ID.

    The returned price is informational for the cart; checkout re-prices from the
    live tables and never trusts the client.
    """
    try:
        catalog = await get_wreath_catalog(conn)
    except Exception as e:
        logger.error("Failed to load wreath options: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        priced = validate_and_price(data.spec, catalog)
        image = decode_png_data_url(data.image) if data.image else None
    except WreathSpecError as e:
        raise HTTPException(status_code=400, detail=str(e))

    design_id = str(uuid.uuid4())
    try:
        await insert_wreath_design(conn, design_id, data.spec.model_dump(), priced["price"], image)
    except Exception as e:
        logger.error("Failed to store wreath design: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    return {
        "designID": design_id,
        "price": float(priced["price"]),
        "imagePath": image_path(design_id) if image else None,
        "imageUrl": image_url(design_id) if image else None,
        "summary": priced["summary"],
    }


@router.get("/designs/{design_id}/image")
async def get_design_image(design_id: str, conn=Depends(get_db_connection)):
    """The customer's rendered PNG. UUIDs are unguessable, so no auth; cached forever."""
    if not _UUID_RE.match(design_id):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        image = await get_wreath_design_image(conn, design_id)
    except Exception as e:
        logger.error("Failed to load wreath image %s: %s", design_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
    if image is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
