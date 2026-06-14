from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str


class DocumentListItem(BaseModel):
    document_id: str
    file_name: str
    pages: int
    chunks: int
    created_at: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    file_name: str
    pages: int
    chunks: int
    status: str


class DocumentSearchRequest(BaseModel):
    document_id: str
    query: str
    top_k: int = 5


class DocumentSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    page: int
    chunk_index: int
    score: float
    content: str


class DocumentSearchResponse(BaseModel):
    results: list[DocumentSearchResult]


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


class RAGChatRequest(BaseModel):
    document_id: str
    question: str
    top_k: int = 5


class RAGCitation(BaseModel):
    page: int
    chunk_id: str
    score: float
    text: str


class RAGChatResponse(BaseModel):
    answer: str
    citations: list[RAGCitation]
    latency_seconds: float
