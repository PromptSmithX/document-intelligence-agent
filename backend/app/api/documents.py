import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.models.schemas import DocumentUploadResponse, MessageResponse


router = APIRouter()


@router.get("", response_model=MessageResponse)
def list_documents() -> MessageResponse:
    return MessageResponse(message="Documents router is ready")


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

    return DocumentUploadResponse(
        document_id=document_id,
        file_name=file_name,
        status="uploaded",
    )
