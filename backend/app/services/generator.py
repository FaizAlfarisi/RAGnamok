from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.config import settings
from app.services.prompts import SYSTEM_PROMPT
from app.utils.model_checker import ensure_model


def _format_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines = []
    for h in history:
        role = "User" if h["role"] == "user" else "Assistant"
        lines.append(f"{role}: {h['content']}")
    return "\n".join(lines)


_INDONESIAN_KEYWORDS = {
    "apa", "bagaimana", "siapa", "mengapa", "kenapa", "kapan", "dimana",
    "yang", "di", "ke", "dari", "dan", "ini", "itu", "ada",
    "tidak", "bisa", "dengan", "untuk", "dalam", "pada",
    "saya", "kamu", "dia", "kami", "mereka", "saja",
    "sudah", "belum", "akan", "sedang", "telah", "pernah",
    "apakah", "adalah", "ialah", "yakni", "yaitu",
    "agar", "supaya", "karena", "sebab", "meskipun",
    "silakan", "tolong", "mohon", "harap",
}


def _is_indonesian(text: str) -> bool:
    words = text.lower().split()
    if not words:
        return False
    matches = sum(1 for w in words if w in _INDONESIAN_KEYWORDS)
    return matches >= 1 and matches / len(words) > 0.1


def _build_multimodal_prompt(
    context: dict, question: str, history: list[dict] | None = None
) -> list:
    context_text = "\n\n".join(context.get("texts", []))
    history_text = _format_history(history) if history else ""

    parts = []
    if history_text:
        parts.append("Previous conversation:\n" + history_text)
    parts.append("Document context:\n" + context_text)
    parts.append(f"Question: {question}")

    if _is_indonesian(question):
        parts.append("")
        parts.append("FINAL LANGUAGE INSTRUCTION — THIS IS MANDATORY:")
        parts.append("Anda HARUS menjawab dalam Bahasa Indonesia. Seluruh jawaban Anda harus dalam Bahasa Indonesia.")
        parts.append("JANGAN menulis sepatah kata pun dalam bahasa Inggris. JANGAN menulis kata 'based on', 'according to', atau sejenisnya.")
        parts.append("Jika pertanyaan dalam Bahasa Indonesia, jawab dalam Bahasa Indonesia. Ini WAJIB.")

    prompt_text = "\n\n".join(parts)

    content = [{"type": "text", "text": prompt_text}]
    for image_b64 in context.get("images", []):
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                },
            }
        )

    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=content)]


_llm_instance = None
_llm_loop_id = None


def _get_llm():
    global _llm_instance, _llm_loop_id
    import asyncio
    loop_id = id(asyncio.get_running_loop())
    if _llm_instance is None or _llm_loop_id != loop_id:
        _llm_instance = ChatOllama(
            model=settings.generation_model,
            temperature=settings.generation_temperature,
            base_url=settings.ollama_base_url,
            timeout=900,
        )
        _llm_loop_id = loop_id
    return _llm_instance


async def generate_answer(
    context: dict, question: str, history: list[dict] | None = None
) -> str:
    await ensure_model("generation_model")
    llm = _get_llm()
    messages = _build_multimodal_prompt(context, question, history)
    response = await llm.ainvoke(messages)
    return response.content
