import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db.connection import async_session

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check():
    services = {"status": "ok", "services": {}}

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        services["services"]["database"] = "ok"
    except Exception:
        services["services"]["database"] = "error: unreachable"
        services["status"] = "degraded"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
        services["services"]["ollama"] = "ok" if r.is_success else "error"
        if not r.is_success:
            services["status"] = "degraded"
    except Exception:
        services["services"]["ollama"] = "error: unreachable"
        services["status"] = "degraded"

    return services
