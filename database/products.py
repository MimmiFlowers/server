from decimal import Decimal


async def get_product_prices_by_names(conn, names: list[str]) -> dict[str, Decimal]:
    """Look up product prices by name. Returns {name: price_in_sek}."""
    if not names:
        return {}

    async with conn.cursor() as cur:
        # Use ANY(%s) with a list parameter for safe IN-clause
        await cur.execute(
            "SELECT name, price FROM products WHERE name = ANY(%s)",
            (names,),
        )
        rows = await cur.fetchall()
        return {row[0]: row[1] for row in rows}


async def get_all_products(conn):
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT \
                            productID, \
                            sku, \
                            name, \
                            description, \
                            price, \
                            stock, \
                            category, \
                            collection, \
                            image, \
                            contents \
                        FROM products"
                    )
            products = await cur.fetchall()
            response = [
                {
                    "productID": product[0],
                    "sku": product[1],
                    "name": product[2],
                    "description": product[3],
                    "price": product[4],
                    "stock": product[5],
                    "category": product[6],
                    "collection": product[7],
                    "picture": product[8],
                    "contents": product[9]
                }
                for product in products
            ]
            return response
    except Exception as e:
        await conn.rollback()
        raise e
    

async def get_product_by_id(conn, product_id: int, preferred_langs: list[str]):
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT \
                            productID, \
                            sku, \
                            name, \
                            COALESCE( \
                                description -> %s ->> 'description', \
                                description -> %s ->> 'description' \
                            ) AS description, \
                            price, \
                            stock, \
                            category, \
                            collection, \
                            image, \
                            contents \
                        FROM products \
                        WHERE productID = %s", (
                                                preferred_langs[0],
                                                preferred_langs[1],
                                                product_id,
                                            )
                    )
            product = await cur.fetchone()
            if product:
                return {
                    "productID": product[0],
                    "sku": product[1],
                    "name": product[2],
                    "description": product[3],
                    "price": product[4],
                    "stock": product[5],
                    "category": product[6],
                    "collection": product[7],
                    "picture": product[8],
                    "contents": product[9]
                }
            else:
                return {"error": "Product not found"}
    except Exception as e:
        await conn.rollback()
        raise e
        

async def get_products_by_category(conn, category: str):
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT \
                            productID, \
                            name, \
                            image, \
                            price  \
                        FROM products  \
                        WHERE category ilike %s", 
                ('%' + category + '%',)
            )
            products = await cur.fetchall()
            response = [
                {
                    "productID": product[0],
                    "name": product[1],
                    "picture": product[2],
                    "price": product[3]
                }
                for product in products
            ]
            return response
    except Exception as e:
        await conn.rollback()
        raise e


async def get_collections(conn):
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT \
                            collectionID, \
                            name, \
                            image  \
                        FROM collections"
                    )
            collections = await cur.fetchall()
            response = [
                {
                    "id": collection[0],
                    "name": collection[1],
                    "picture": collection[2]
                }
                for collection in collections
            ]
            return response
    except Exception as e:
        await conn.rollback()
        raise e 