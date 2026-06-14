from fastapi import APIRouter

from app.models.schemas import MessageResponse


router = APIRouter()


@router.get("", response_model=MessageResponse)
def list_documents() -> MessageResponse:
    return MessageResponse(message="Documents router is ready")
