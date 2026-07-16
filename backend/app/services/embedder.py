import asyncio

from langchain_ollama import OllamaEmbeddings

from app.config import settings

_embeddings_model = None
_embeddings_loop_id = None


def _model_has_prefix(model_name: str) -> str | None:
    name = model_name.lower()
    if "qwen3" in name:
        return "qwen3"
    if "e5" in name:
        return "e5"
    return None


def _get_embeddings():
    global _embeddings_model, _embeddings_loop_id
    loop_id = id(asyncio.get_running_loop())
    if _embeddings_model is None or _embeddings_loop_id != loop_id:
        _embeddings_model = OllamaEmbeddings(
            model=settings.embedding_model_name,
            base_url=settings.ollama_base_url,
        )
        _embeddings_loop_id = loop_id
    return _embeddings_model


async def embed_text(text: str) -> list[float]:
    prefix_type = _model_has_prefix(settings.embedding_model_name)
    if prefix_type == "qwen3":
        text = f"query: {text}"
    elif prefix_type == "e5":
        text = f"query: {text}"
    return await _get_embeddings().aembed_query(text)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    prefix_type = _model_has_prefix(settings.embedding_model_name)
    if prefix_type == "qwen3":
        texts = [f"document: {t}" for t in texts]
    elif prefix_type == "e5":
        texts = [f"passage: {t}" for t in texts]
    return await _get_embeddings().aembed_documents(texts)
