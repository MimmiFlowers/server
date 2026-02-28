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
        return {row["name"]: row["price"] for row in rows}


async def get_all_products(conn, limit: int = 50, offset: int = 0):
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT "productID", sku, name, description,
                          price, stock, category, collection,
                          image AS picture, contents
                   FROM products
                   ORDER BY "productID"
                   LIMIT %s OFFSET %s""",
                (limit, offset),
            )
            return await cur.fetchall()
    except Exception as e:
        await conn.rollback()
        raise e


async def get_product_by_id(conn, product_id: int, preferred_langs: list[str]):
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT "productID", sku, name,
                          COALESCE(
                              description -> %s ->> 'description',
                              description -> %s ->> 'description'
                          ) AS description,
                          price, stock, category, collection,
                          image AS picture, contents
                   FROM products
                   WHERE "productID" = %s""",
                (preferred_langs[0], preferred_langs[1], product_id),
            )
            return await cur.fetchone()
    except Exception as e:
        await conn.rollback()
        raise e


async def get_products_by_category(conn, category: str):
    try:
        async with conn.cursor() as cur:
            # Escape LIKE metacharacters to prevent injection via search term
            escaped = category.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            await cur.execute(
                """SELECT "productID", name, image AS picture, price
                   FROM products
                   WHERE category ILIKE %s""",
                ("%" + escaped + "%",),
            )
            return await cur.fetchall()
    except Exception as e:
        await conn.rollback()
        raise e


async def get_collections(conn):
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT "collectionID" AS id, name, image AS picture
                   FROM collections"""
            )
            return await cur.fetchall()
    except Exception as e:
        await conn.rollback()
        raise e
