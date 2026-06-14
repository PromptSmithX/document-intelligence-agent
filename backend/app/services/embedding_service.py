import os
from functools import lru_cache


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIMENSION = 1024


def _get_embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL


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
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_get_embedding_model_name())


def _zero_vector() -> list[float]:
    return [0.0] * _get_embedding_dimension()


def _to_python_vectors(embeddings) -> list[list[float]]:
    if hasattr(embeddings, "tolist"):
        return embeddings.tolist()

    return [list(embedding) for embedding in embeddings]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    cleaned_texts = [str(text or "").strip() for text in texts]
    vectors: list[list[float] | None] = [None] * len(cleaned_texts)
    non_empty_texts = []
    non_empty_indexes = []

    for index, text in enumerate(cleaned_texts):
        if text:
            non_empty_texts.append(text)
            non_empty_indexes.append(index)
        else:
            vectors[index] = _zero_vector()

    if non_empty_texts:
        model = get_embedding_model()
        try:
            embeddings = model.encode(non_empty_texts, normalize_embeddings=True)
        except TypeError:
            embeddings = model.encode(non_empty_texts)

        for index, vector in zip(non_empty_indexes, _to_python_vectors(embeddings)):
            vectors[index] = vector

    return [vector if vector is not None else _zero_vector() for vector in vectors]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
