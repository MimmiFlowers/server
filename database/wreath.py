"""SQL for the wreath builder. All prices are SEK Decimals (NUMERIC(10,2))."""

import json
from decimal import Decimal


async def get_wreath_catalog(conn) -> dict:
    """Every ACTIVE option row plus the size×material price matrix keyed by codes.

    Shape (consumed by services.wreath):
      {"sizes": [...], "materials": [...], "base_prices": [{"sizeCode","materialCode","price"}],
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
                'SELECT s.code AS "sizeCode", m.code AS "materialCode", p.price '
                'FROM wreath_base_prices p '
                'JOIN wreath_sizes s ON s."sizeID" = p."sizeID" '
                'JOIN wreath_materials m ON m."materialID" = p."materialID" '
                'WHERE s.active AND m.active'
            )
            base_prices = await cur.fetchall()
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
            "base_prices": [dict(r) for r in base_prices],
            "bands": [dict(r) for r in bands],
            "decorations": [dict(r) for r in decorations],
        }
    except Exception as e:
        await conn.rollback()
        raise e


async def insert_wreath_design(
    conn, design_id: str, spec: dict, price: Decimal, image: bytes | None
) -> None:
    """design_id is minted by the caller (uuid4 in the router), spec is the validated
    `WreathSpec.model_dump()`, price is SEK."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                'INSERT INTO wreath_designs ("designID", spec, price, image) '
                'VALUES (%s::uuid, %s::jsonb, %s, %s)',
                (design_id, json.dumps(spec), price, image),
            )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e


async def get_wreath_design(conn, design_id: str) -> dict | None:
    """Spec + stored price + whether an image exists. Never loads the image bytes."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT "designID"::text AS "designID", spec, price, '
                '(image IS NOT NULL) AS "hasImage" '
                'FROM wreath_designs WHERE "designID" = %s::uuid',
                (design_id,),
            )
            row = await cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        await conn.rollback()
        raise e


async def get_wreath_design_image(conn, design_id: str) -> bytes | None:
    """PNG bytes for GET /data/wreath/designs/{id}/image, or None if the design or
    its image is missing."""
    async with conn.cursor() as cur:
        await cur.execute(
            'SELECT image FROM wreath_designs WHERE "designID" = %s::uuid',
            (design_id,),
        )
        row = await cur.fetchone()
    if not row or row["image"] is None:
        return None
    return row["image"]  # psycopg 3 already returns bytea as bytes
