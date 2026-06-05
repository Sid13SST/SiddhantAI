from fastapi import APIRouter
from app.api.v1.endpoints import ingestion, search

api_router = APIRouter()

api_router.include_router(ingestion.router, prefix="/ingest", tags=["ingestion"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
