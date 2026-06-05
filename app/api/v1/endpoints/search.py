import json
# pyrefly: ignore [missing-import]
import numpy as np
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.models.document import SearchResult, PersonaProfile
from app.models.qa import QARequest, QAResponse
from app.services.qa_engine import QAEngine
from app.core.config import settings
from app.core.logging import logger

router = APIRouter()
qa_engine = QAEngine()
embedding_service = EmbeddingService()
vector_store = VectorStoreService()

class SearchRequest(BaseModel):
    query: str = Field(..., description="The query string to match semantically")
    top_k: int = Field(5, description="Number of matches to return")
    filter_tags: Optional[List[str]] = Field(None, description="Optional tags to boost relevance matching")

@router.post("/", response_model=List[SearchResult])
async def search_vector_db(request: SearchRequest):
    """Performs semantic vector search over the ingested knowledge base, with metadata tag boosting."""
    try:
        # Load index from disk (ensures we get fresh updates)
        vector_store.load()
        
        if vector_store.index is None or vector_store.index.ntotal == 0:
            raise HTTPException(
                status_code=400, 
                detail="Vector database is empty. Please run ingestion first."
            )
            
        # 1. Embed Query
        query_vector = embedding_service.generate_embeddings([request.query])[0]
        
        # 2. Vector Search (over-query slightly to allow tag boosting re-ranking)
        over_query_k = request.top_k * 2
        raw_results = vector_store.search(query_vector, top_k=over_query_k)
        
        # 3. Apply Retrieval Tag Boosting
        boosted_results = []
        for item, dist_score in raw_results:
            metadata = item.get("metadata", {})
            retrieval_tags = metadata.get("retrieval_tags", [])
            
            score = dist_score
            # Apply tag boost: reduce L2 distance (making it closer/more relevant) if tags overlap
            if request.filter_tags:
                query_tags_set = set(t.lower() for t in request.filter_tags)
                doc_tags_set = set(t.lower() for t in retrieval_tags)
                intersect = query_tags_set.intersection(doc_tags_set)
                if intersect:
                    # Subtracting from L2 score brings it closer to zero (increasing relevance)
                    score -= 0.15 * len(intersect)
                    
            boosted_results.append(SearchResult(
                chunk_id=item["chunk_id"],
                text=item["text"],
                score=score,
                metadata=metadata
            ))
            
        # Sort by boosted score (ascending order since lower L2 distance is better)
        boosted_results.sort(key=lambda x: x.score)
        
        # Return top_k
        return boosted_results[:request.top_k]
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Search endpoint execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/persona", response_model=PersonaProfile)
async def get_persona_profile():
    """Bypasses vector search and returns the synthesized high-level profile of Siddhant."""
    profile_path = settings.vector_db_dir / "persona_profile.json"
    if not profile_path.exists():
        raise HTTPException(
            status_code=404, 
            detail="Persona profile not generated. Please run full ingestion first."
        )
        
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        return profile_data
    except Exception as e:
        logger.error(f"Failed to read persona profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to load persona profile.")

@router.post("/ask", response_model=QAResponse)
async def ask_question(request: QARequest):
    """Triggers the QAEngine to answer questions grounded in the context with citations and evidence panel."""
    return await qa_engine.answer_question(request.question, request.filter_tags)
