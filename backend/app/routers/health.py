import logging

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db.connection import async_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check():
    services = {"status": "ok", "services": {}}
    degraded = False

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        services["services"]["database"] = "ok"
    except Exception as exc:
        services["services"]["database"] = f"error: {exc}"
        degraded = True

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{settings.ollama_cloud_base_url}/api/tags",
                headers={"Authorization": f"Bearer {settings.ollama_api_key}"},
            )
        services["services"]["ollama"] = "ok" if r.is_success else f"error: HTTP {r.status_code}"
        if not r.is_success:
            degraded = True
    except Exception as exc:
        services["services"]["ollama"] = f"error: {exc}"
        logger.warning("Ollama health check failed: %s", exc)
        degraded = True

    if degraded:
        services["status"] = "degraded"
    return services
