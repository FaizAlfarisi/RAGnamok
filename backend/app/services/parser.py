from unstructured.documents.elements import CompositeElement, Image as UnstructuredImage, Table

from app.config import settings


def parse_pdf(file_path: str) -> dict:
    from unstructured.partition.pdf import partition_pdf

    chunks = partition_pdf(
        filename=file_path,
        languages=["ind"],
        infer_table_structure=True,
        strategy="hi_res",
        extract_image_block_types=["Image"],
        extract_image_block_to_payload=True,
        chunking_strategy="by_title",
        multipage_sections=True,
        max_characters=settings.max_characters,
        combine_text_under_n_chars=settings.combine_text_under_n_chars,
        new_after_n_chars=settings.new_after_n_chars,
    )

    texts = [c for c in chunks if isinstance(c, CompositeElement)]
    tables = [c for c in chunks if isinstance(c, Table)]

    images = []
    for chunk in texts:
        for el in chunk.metadata.orig_elements:
            if isinstance(el, UnstructuredImage):
                images.append({
                    "base64": el.metadata.image_base64,
                    "page_number": getattr(el.metadata, "page_number", 1),
                })

    texts = _merge_small_chunks(texts, settings.min_chunk_size_for_merge)

    return {"texts": texts, "tables": tables, "images": images}


def _merge_small_chunks(chunks, min_size: int = 200):
    merged = []
    for chunk in chunks:
        if merged and len(chunk.text) < min_size:
            merged[-1].text += "\n\n" + chunk.text
        else:
            merged.append(chunk)
    return merged
