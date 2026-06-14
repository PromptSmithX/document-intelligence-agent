from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    file_name: str
    pages: int
    chunks: int
    status: str


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
