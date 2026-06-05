# pyrefly: ignore [missing-import]
import uvicorn
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import logger

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

if __name__ == "__main__":
    logger.info(f"Starting API server on {settings.HOST}:{settings.PORT}")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
