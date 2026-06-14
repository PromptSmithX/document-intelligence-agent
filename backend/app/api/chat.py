from fastapi import APIRouter

from app.models.schemas import ChatRequest, ChatResponse


router = APIRouter()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer="Chat endpoint is ready. RAG is not implemented yet.",
        sources=[],
    )
