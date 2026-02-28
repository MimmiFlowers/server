import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from database.dbconfig.dbconfig import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(conn=Depends(get_db_connection)):
    """Verify DB connectivity. Returns 200 if healthy, 503 if not."""
    try:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "detail": "Database unreachable"},
        )
