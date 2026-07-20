import logging

from fastapi import APIRouter

from app.schemas.models import ChatRequest, ChatResponse
from app.services.generator import generate_answer
from app.services.retriever import retrieve_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    top_k = max(1, min(request.top_k, 50))
    try:
        context = await retrieve_context(request.query, top_k)
        answer = await generate_answer(context, request.query)
    except Exception as e:
        logger.error("Chat failed: %s", e)
        context = {"texts": [], "images": []}
        answer = "_Maaf, gagal memproses pertanyaan. Coba lagi nanti._"
    return ChatResponse(
        answer=answer,
        sources=context["texts"],
        images=context["images"],
    )
