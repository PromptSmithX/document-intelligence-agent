import os

from app.services.embedding_service import embed_query
from app.services.llm_service import generate_answer
from app.services.vector_store import search_chunks


NO_ANSWER = "I could not find this information in the document."
DEFAULT_MIN_RETRIEVAL_SCORE = 0.35
CITATION_PREVIEW_LENGTH = 300


def _get_min_retrieval_score() -> float:
    raw_score = os.getenv("MIN_RETRIEVAL_SCORE", str(DEFAULT_MIN_RETRIEVAL_SCORE))

    try:
        return float(raw_score)
    except ValueError as exc:
        raise ValueError("MIN_RETRIEVAL_SCORE must be a number") from exc


def _preview_text(text: str, max_length: int = CITATION_PREVIEW_LENGTH) -> str:
    cleaned_text = str(text or "").strip()
    if len(cleaned_text) <= max_length:
        return cleaned_text

    return f"{cleaned_text[: max_length - 3].rstrip()}..."


def _build_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "page": chunk["page"],
            "chunk_id": chunk["chunk_id"],
            "score": float(chunk["score"]),
            "text": _preview_text(chunk["content"]),
        }
        for chunk in chunks
    ]


def _build_prompt(question: str, chunks: list[dict]) -> str:
    context_blocks = []
    for chunk in chunks:
        context_blocks.append(
            "\n".join(
                [
                    f"Page: {chunk['page']}",
                    f"Chunk ID: {chunk['chunk_id']}",
                    f"Score: {chunk['score']:.4f}",
                    f"Content: {chunk['content']}",
                ]
            )
        )

    context = "\n\n---\n\n".join(context_blocks)

    return f"""You are answering questions about a document.

Use only the context below to answer the question.
Do not use outside knowledge.
If the answer is not found in the context, say exactly:
{NO_ANSWER}

Context:
{context}

Question:
{question}

Answer:"""


def answer_question(document_id: str, question: str, top_k: int = 5) -> dict:
    query_embedding = embed_query(question)
    chunks = search_chunks(document_id, query_embedding, top_k)

    if not chunks:
        return {
            "answer": NO_ANSWER,
            "citations": [],
        }

    if chunks[0]["score"] < _get_min_retrieval_score():
        return {
            "answer": NO_ANSWER,
            "citations": [],
        }

    prompt = _build_prompt(question, chunks)
    answer = generate_answer(prompt)

    return {
        "answer": answer or NO_ANSWER,
        "citations": _build_citations(chunks),
    }
