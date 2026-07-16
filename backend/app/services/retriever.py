from app.db.connection import async_session
from app.db.crud import vector_search
from app.services.embedder import embed_text
from app.utils.file_handler import get_image_path
from app.utils.image_formatter import image_to_base64


async def retrieve_context(query: str, top_k: int = 5) -> dict:
    query_vector = await embed_text(query)
    async with async_session() as session:
        results = await vector_search(session, query_vector, top_k)

    texts = []
    images = []
    for row in results:
        if row["element_type"] == "Image":
            image_path = get_image_path(row["original_content"])
            if image_path.exists():
                images.append(image_to_base64(image_path))
        else:
            texts.append(row["original_content"])

    return {"texts": texts, "images": images}
