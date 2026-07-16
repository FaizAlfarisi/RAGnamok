from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config import settings
from app.services.prompts import IMAGE_SUMMARY_PROMPT, TEXT_SUMMARY_PROMPT
from app.utils.model_checker import ensure_model


def _create_text_summarizer():
    model = ChatOllama(
        temperature=settings.summarization_temperature,
        model=settings.summarization_model,
        base_url=settings.ollama_base_url,
    )
    prompt = ChatPromptTemplate.from_template(TEXT_SUMMARY_PROMPT)
    return {"element": lambda x: x} | prompt | model | StrOutputParser()


def _create_image_summarizer():
    llm = ChatOllama(model=settings.summarization_model, base_url=settings.ollama_base_url)
    messages = [
        (
            "user",
            [
                {"type": "text", "text": IMAGE_SUMMARY_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,{image}"},
                },
            ],
        )
    ]
    prompt = ChatPromptTemplate.from_messages(messages)
    return prompt | llm | StrOutputParser()


async def summarize_texts(texts: list) -> list[str]:
    await ensure_model("summarization_model")
    chain = _create_text_summarizer()
    return await chain.abatch(
        texts, {"max_concurrency": settings.max_concurrency}
    )


async def summarize_tables(tables: list) -> list[str]:
    await ensure_model("summarization_model")
    chain = _create_text_summarizer()
    html_tables = [getattr(t.metadata, "text_as_html", "") or "" for t in tables]
    return await chain.abatch(
        html_tables, {"max_concurrency": settings.max_concurrency}
    )


async def summarize_images(images: list[str]) -> list[str]:
    await ensure_model("summarization_model")
    chain = _create_image_summarizer()
    return await chain.abatch(
        [{"image": img} for img in images],
        {"max_concurrency": settings.max_concurrency},
    )
