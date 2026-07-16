from fastapi import APIRouter

from app.schemas.models import ChatRequest, ChatResponse
from app.services.generator import generate_answer
from app.services.retriever import retrieve_context

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    top_k = max(1, min(request.top_k, 50))
    context = await retrieve_context(request.query, top_k)
    answer = await generate_answer(context, request.query)
    return ChatResponse(
        answer=answer,
        sources=context["texts"],
        images=context["images"],
    )
