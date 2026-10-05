"""Wreath builder endpoints, mounted under /data so the client's nginx /data/ proxy covers them."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from database.dbconfig.dbconfig import get_db_connection
from database.wreath import get_wreath_catalog, insert_wreath_design
from routers.classes.classes import WreathDesignRequest
from services.r2 import design_key, upload_png
from services.wreath import (
    WreathSpecError,
    catalog_for_client,
    decode_png_data_url,
    validate_and_price,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/data/wreath",
    tags=["wreath"],
    responses={404: {"description": "Not found"}},
)

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
    """Validate + price a design, upload the customer's PNG to R2, store the design
    with the picture's public URL and return its ID.

    The returned price is informational for the cart; checkout re-prices from the
    live tables and never trusts the client. If the upload fails the design is still
    saved, without a picture — the same outcome as a failed export in the browser.
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
    image_url = None
    if image is not None:
        try:
            image_url = await upload_png(design_key(design_id), image)
        except Exception as e:
            logger.error("Failed to upload wreath image %s to R2: %s", design_id, e)

    try:
        await insert_wreath_design(conn, design_id, data.spec.model_dump(), priced["price"], image_url)
    except Exception as e:
        logger.error("Failed to store wreath design: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    return {
        "designID": design_id,
        "price": float(priced["price"]),
        "imageUrl": image_url,
        "summary": priced["summary"],
    }

