"""SQL for the wreath builder. All prices are SEK Decimals (NUMERIC(10,2))."""

import json
from decimal import Decimal


async def get_wreath_catalog(conn) -> dict:
    """Every ACTIVE option row plus the size×material bases (price + optional picture) keyed by codes.

    Shape (consumed by services.wreath):
      {"sizes": [...], "materials": [...], "bases": [{"sizeCode","materialCode","price","image"}],
       "bands": [...], "decorations": [...]}
    """
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT code, name, "diameterCm", "slotCount" FROM wreath_sizes '
                'WHERE active ORDER BY "sortOrder", "sizeID"'
            )
            sizes = await cur.fetchall()
            await cur.execute(
                'SELECT code, name, image FROM wreath_materials '
                'WHERE active ORDER BY "sortOrder", "materialID"'
            )
            materials = await cur.fetchall()
            await cur.execute(
                'SELECT s.code AS "sizeCode", m.code AS "materialCode", b.price, b.image '
                'FROM wreath_bases b '
                'JOIN wreath_sizes s ON s."sizeID" = b."sizeID" '
                'JOIN wreath_materials m ON m."materialID" = b."materialID" '
                'WHERE s.active AND m.active'
            )
            bases = await cur.fetchall()
            await cur.execute(
                'SELECT code, name, image, price FROM wreath_bands '
                'WHERE active ORDER BY "sortOrder", "bandID"'
            )
            bands = await cur.fetchall()
            await cur.execute(
                'SELECT code, name, image, price FROM wreath_decorations '
                'WHERE active ORDER BY "sortOrder", "decorationID"'
            )
            decorations = await cur.fetchall()
        return {
            "sizes": [dict(r) for r in sizes],
            "materials": [dict(r) for r in materials],
            "bases": [dict(r) for r in bases],
            "bands": [dict(r) for r in bands],
            "decorations": [dict(r) for r in decorations],
        }
    except Exception as e:
        await conn.rollback()
        raise e


async def insert_wreath_design(
    conn, design_id: str, spec: dict, price: Decimal, image_url: str | None
) -> None:
    """design_id is minted by the caller (uuid4 in the router), spec is the validated
    `WreathSpec.model_dump()`, price is SEK, image_url the PNG's public R2 URL (or None)."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                'INSERT INTO wreath_designs ("designID", spec, price, "imageUrl") '
                'VALUES (%s::uuid, %s::jsonb, %s, %s)',
                (design_id, json.dumps(spec), price, image_url),
            )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e


async def get_wreath_design(conn, design_id: str) -> dict | None:
    """Spec + stored price + the picture's public URL (None if there is no picture)."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT "designID"::text AS "designID", spec, price, "imageUrl" '
                'FROM wreath_designs WHERE "designID" = %s::uuid',
                (design_id,),
            )
            row = await cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        await conn.rollback()
        raise e

