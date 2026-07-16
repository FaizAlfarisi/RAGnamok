import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
_checked: set[str] = set()


async def ensure_model(model_key: str) -> None:
    if model_key in _checked:
        return
    model = getattr(settings, model_key)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            available = [m["name"] for m in data.get("models", [])]
            if model not in available:
                logger.warning(
                    "Model '%s' (%s) not found in Ollama.\n"
                    "  Available: %s\n"
                    "  Fix: run 'make pull-models %s' or edit .env",
                    model,
                    model_key,
                    ", ".join(sorted(available)) if available else "(none)",
                    model,
                )
    except Exception as exc:
        logger.debug("Could not verify model '%s': %s", model, exc)
    _checked.add(model_key)
