def chunk_pages(
    document_id: str,
    pages: list[dict],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be greater than or equal to 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks = []
    chunk_index = 0

    for page in pages:
        text = str(page.get("text") or "").strip()
        if not text:
            continue

        page_number = page["page"]
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            content = text[start:end].strip()

            if content:
                chunks.append(
                    {
                        "chunk_id": f"{document_id}_chunk_{chunk_index:04d}",
                        "document_id": document_id,
                        "page": page_number,
                        "chunk_index": chunk_index,
                        "content": content,
                    }
                )
                chunk_index += 1

            if end == len(text):
                break

            start = end - chunk_overlap

    return chunks
