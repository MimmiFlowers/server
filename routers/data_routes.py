from fastapi import APIRouter, Request, Depends
from database.dbconfig.dbconfig import get_db_connection
from database.products import get_all_products, \
                            get_product_by_id, \
                            get_products_by_category

router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}}
)


@router.get("/products")
async def get_products(conn=Depends(get_db_connection)):
    try:
        products = await get_all_products(conn)
        return {"products": products}
    except Exception as e:
        return {"error": str(e)}


@router.get("/products/{product_id}")
async def get_product(product_id: int, request: Request, conn=Depends(get_db_connection)):
    lang = request.headers.get("accept-language", "en")[:2]
    preferred_langs = [lang, "en"] if lang != "en" else ["en", "sv"]

    try:
        product = await get_product_by_id(conn, product_id, preferred_langs)
        return product
    except Exception as e:
        return {"error": str(e)}

    
@router.get("/category/{category}")
async def get_favorites(category: str, conn=Depends(get_db_connection)):
    try:
        products = await get_products_by_category(conn, category)
        return {"data": products}
    except Exception as e:
        return {"error": str(e)}
    

@router.get("/collections")
async def get_collections(conn=Depends(get_db_connection)):
    try:
        collections = await get_collections(conn)
        return {"data": collections}
    except Exception as e:
        return {"error": str(e)}
