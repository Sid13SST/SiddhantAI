# pyrefly: ignore [missing-import]
import uvicorn
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.models.qa import QARequest, QAResponse
from app.services.qa_engine import QAEngine
from app.core.config import settings
from app.core.logging import logger

qa_engine = QAEngine()

app = FastAPI(
    title="Siddhant AI Persona Platform",
    description="Knowledge Ingestion Layer Backend API",
    version="1.1.0"
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include APIs
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "Welcome to Siddhant AI Persona Platform API",
        "version": "1.1.0",
        "docs_url": "/docs"
    }

@app.post("/ask", response_model=QAResponse)
async def ask_question(request: QARequest):
    """Root-level endpoint to query the Siddhant AI representative."""
    return await qa_engine.answer_question(
        question=request.question,
        filter_tags=request.filter_tags,
        session_id=request.session_id,
        booking_context=request.booking_context
    )

if __name__ == "__main__":
    logger.info(f"Starting API server on {settings.HOST}:{settings.PORT}")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
