import os
import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "document_chunks"
DEFAULT_EMBEDDING_DIMENSION = 1024


def _get_qdrant_url() -> str:
    return os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL).strip() or DEFAULT_QDRANT_URL


def _get_collection_name() -> str:
    return os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION).strip() or DEFAULT_QDRANT_COLLECTION


def _get_embedding_dimension() -> int:
    raw_dimension = os.getenv("EMBEDDING_DIMENSION", str(DEFAULT_EMBEDDING_DIMENSION))

    try:
        dimension = int(raw_dimension)
    except ValueError as exc:
        raise ValueError("EMBEDDING_DIMENSION must be an integer") from exc

    if dimension <= 0:
        raise ValueError("EMBEDDING_DIMENSION must be greater than 0")

    return dimension


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=_get_qdrant_url())


def ensure_collection() -> None:
    client = get_qdrant_client()
    collection_name = _get_collection_name()

    if client.collection_exists(collection_name=collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=_get_embedding_dimension(),
            distance=Distance.COSINE,
        ),
    )


def upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")

    if not chunks:
        return

    points = []
    for chunk, embedding in zip(chunks, embeddings):
        points.append(
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunk_id"])),
                vector=embedding,
                payload={
                    "document_id": chunk["document_id"],
                    "chunk_id": chunk["chunk_id"],
                    "page": chunk["page"],
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                },
            )
        )

    get_qdrant_client().upsert(
        collection_name=_get_collection_name(),
        points=points,
        wait=True,
    )


def search_chunks(
    document_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    client = get_qdrant_client()
    collection_name = _get_collection_name()

    if not client.collection_exists(collection_name=collection_name):
        return []

    response = client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            {
                "chunk_id": payload.get("chunk_id", ""),
                "document_id": payload.get("document_id", ""),
                "page": payload.get("page", 0),
                "chunk_index": payload.get("chunk_index", 0),
                "score": float(point.score),
                "content": payload.get("content", ""),
            }
        )

    return results
