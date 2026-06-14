import time

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ChatRequest, ChatResponse, RAGChatRequest, RAGChatResponse
from app.services.rag_pipeline import answer_question


router = APIRouter()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer="Chat endpoint is ready. RAG is not implemented yet.",
        sources=[],
    )


@router.post("/query", response_model=RAGChatResponse)
def query_document(request: RAGChatRequest) -> RAGChatResponse:
    document_id = request.document_id.strip()
    question = request.question.strip()

    if not document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id is required",
        )
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question is required",
        )
    if request.top_k < 1 or request.top_k > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="top_k must be between 1 and 10",
        )

    started_at = time.perf_counter()
    try:
        result = answer_question(document_id, question, request.top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not answer question",
        ) from exc

    latency_seconds = round(time.perf_counter() - started_at, 2)

    return RAGChatResponse(
        answer=result["answer"],
        citations=result["citations"],
        latency_seconds=latency_seconds,
    )
