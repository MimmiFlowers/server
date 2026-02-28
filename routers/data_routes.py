import logging
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from database.dbconfig.dbconfig import get_db_connection
from database.products import get_all_products, \
                            get_product_by_id, \
                            get_products_by_category, \
                            get_collections as db_get_collections

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}}
)


@router.get("/products")
async def get_products(
    limit: int = Query(default=50, ge=1, le=200, description="Max products to return"),
    offset: int = Query(default=0, ge=0, description="Number of products to skip"),
    conn=Depends(get_db_connection),
):
    try:
        products = await get_all_products(conn, limit=limit, offset=offset)
        return {"products": products}
    except Exception as e:
        logger.error("Failed to fetch products: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/products/{product_id}")
async def get_product(product_id: int, request: Request, conn=Depends(get_db_connection)):
    lang = request.headers.get("accept-language", "en")[:2]
    preferred_langs = [lang, "en"] if lang != "en" else ["en", "sv"]

    try:
        product = await get_product_by_id(conn, product_id, preferred_langs)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch product %s: %s", product_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")

    
@router.get("/category/{category}")
async def get_products_by_category_route(category: str, conn=Depends(get_db_connection)):
    try:
        products = await get_products_by_category(conn, category)
        return {"data": products}
    except Exception as e:
        logger.error("Failed to fetch products for category '%s': %s", category, e)
        raise HTTPException(status_code=500, detail="Internal server error")
    

@router.get("/collections")
async def get_collections(conn=Depends(get_db_connection)):
    try:
        collections = await db_get_collections(conn)
        return {"data": collections}
    except Exception as e:
        logger.error("Failed to fetch collections: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
