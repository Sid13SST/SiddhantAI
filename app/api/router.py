from fastapi import APIRouter
from app.api.v1.endpoints import ingestion, search, booking, voice

api_router = APIRouter()

api_router.include_router(ingestion.router, prefix="/ingest", tags=["ingestion"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(booking.router, prefix="/booking", tags=["booking"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])


