from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

class QARequest(BaseModel):
    question: str = Field(..., description="The user question to Siddhant's AI Representative")
    filter_tags: Optional[List[str]] = Field(None, description="Optional retrieval tags to prioritize")

class EvidenceItem(BaseModel):
    source: str = Field(..., description="The name of the source (e.g., Gradonix README)")
    snippet: str = Field(..., description="The matching text content snippet")

class QAResponse(BaseModel):
    answer: str = Field(..., description="The grounded natural language answer")
    citations: List[str] = Field(default_factory=list, description="List of source citations used (e.g. [Resume Page 1])")
    confidence: float = Field(..., description="The grounding confidence score (0.0 to 1.0)")
    sources: List[EvidenceItem] = Field(default_factory=list, description="Compiled evidence items for the Next.js UI panel")

class SafetyLog(BaseModel):
    question: str
    is_safe: bool
    reason: Optional[str] = None

class ObservabilityLog(BaseModel):
    question: str
    intent: str
    retrieval_latency_ms: float
    generation_latency_ms: float
    total_latency_ms: float
    source_count: int
    confidence_score: float
    timestamp: str
