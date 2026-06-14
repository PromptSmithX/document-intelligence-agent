from fastapi import FastAPI

from app.api import chat, documents
from app.core.config import settings
from app.models.schemas import HealthResponse


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
