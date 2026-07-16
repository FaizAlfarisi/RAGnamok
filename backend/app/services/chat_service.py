import logging

from app.db.crud import (
    get_chat_history,
    save_message,
    touch_session,
)
from app.services.generator import generate_answer
from app.services.retriever import retrieve_context

logger = logging.getLogger(__name__)


async def handle_chat_message(
    db_session, session_id: str, query: str, top_k: int = 5, history_depth: int = 6
) -> dict:
    # 1. Save user message
    await save_message(db_session, session_id, "user", query)

    # 2. Retrieve context
    context = await retrieve_context(query, top_k)

    # 3. Load chat history
    history = await get_chat_history(db_session, session_id, depth=history_depth)

    # 4. Generate answer
    try:
        answer = await generate_answer(context, query, history)
    except Exception as e:
        logger.error("Generation failed for session %s: %s", session_id[:8], e)
        answer = "_Maaf, gagal menghasilkan jawaban. Silakan coba lagi._"

    # 5. Save assistant response
    msg_id = await save_message(
        db_session, session_id, "assistant", answer, context["texts"], context["images"]
    )

    # 6. Update session timestamp
    await touch_session(db_session, session_id)

    logger.info(
        "Session %s: answered (history=%d, sources=%d, images=%d)",
        session_id[:8],
        len(history),
        len(context["texts"]),
        len(context["images"]),
    )

    return {
        "message_id": msg_id,
        "answer": answer,
        "sources": context["texts"],
        "images": context["images"],
    }
