import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.models.schemas import (
    DocumentListItem,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentUploadResponse,
)
from app.services.chunker import chunk_pages
from app.services.document_parser import parse_pdf
from app.services.embedding_service import embed_query, embed_texts
from app.services.vector_store import ensure_collection, search_chunks, upsert_chunks


router = APIRouter()


def _metadata_path(document_dir: Path) -> Path:
    return document_dir / "metadata.json"


def _write_document_metadata(
    document_dir: Path,
    document_id: str,
    file_name: str,
    pages: int,
    chunks: int,
) -> None:
    metadata = {
        "document_id": document_id,
        "file_name": file_name,
        "pages": pages,
        "chunks": chunks,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    _metadata_path(document_dir).write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def _read_document_metadata(document_dir: Path) -> DocumentListItem | None:
    metadata_file = _metadata_path(document_dir)
    if not metadata_file.exists():
        return None

    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        return DocumentListItem(**metadata)
    except (OSError, ValueError, TypeError):
        return None


@router.get("", response_model=list[DocumentListItem])
def list_documents() -> list[DocumentListItem]:
    documents = []
    for document_dir in settings.storage_dir.glob("doc_*"):
        if not document_dir.is_dir():
            continue

        metadata = _read_document_metadata(document_dir)
        if metadata is not None:
            documents.append(metadata)

    return sorted(documents, key=lambda document: document.created_at, reverse=True)


@router.post("/search", response_model=DocumentSearchResponse)
def search_documents(request: DocumentSearchRequest) -> DocumentSearchResponse:
    document_id = request.document_id.strip()
    query = request.query.strip()

    if not document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id is required",
        )
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query is required",
        )
    if request.top_k < 1 or request.top_k > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="top_k must be between 1 and 20",
        )

    try:
        query_embedding = embed_query(query)
        results = search_chunks(document_id, query_embedding, request.top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not search document chunks",
        ) from exc

    return DocumentSearchResponse(results=results)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    file_name = Path(file.filename or "").name
    if not file_name or Path(file_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    document_id = f"doc_{uuid.uuid4().hex}"
    document_dir = settings.storage_dir / document_id
    file_path = document_dir / "original.pdf"

    try:
        document_dir.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save uploaded file",
        ) from exc
    finally:
        file.file.close()

    try:
        pages = parse_pdf(str(file_path))
    except ValueError as exc:
        shutil.rmtree(document_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse uploaded PDF",
        ) from exc

    try:
        chunks = chunk_pages(document_id, pages)
    except ValueError as exc:
        shutil.rmtree(document_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not chunk uploaded PDF",
        ) from exc

    try:
        embeddings = embed_texts([chunk["content"] for chunk in chunks])
        ensure_collection()
        upsert_chunks(chunks, embeddings)
        _write_document_metadata(
            document_dir=document_dir,
            document_id=document_id,
            file_name=file_name,
            pages=len(pages),
            chunks=len(chunks),
        )
    except Exception as exc:
        shutil.rmtree(document_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not index uploaded PDF",
        ) from exc

    return DocumentUploadResponse(
        document_id=document_id,
        file_name=file_name,
        pages=len(pages),
        chunks=len(chunks),
        status="indexed",
    )
