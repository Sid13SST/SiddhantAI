import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from app.models.qa import ObservabilityLog
from app.core.config import settings
from app.core.logging import logger

class ObservabilityService:
    @classmethod
    def log_query_metrics(
        cls,
        question: str,
        intent: str,
        retrieval_latency_ms: float,
        generation_latency_ms: float,
        total_latency_ms: float,
        source_count: int,
        confidence_score: float
    ):
        """Logs QA execution metrics to data/observability.log for audit and analysis."""
        log_file = settings.raw_data_dir.parent / "observability.log"
        
        log_entry = ObservabilityLog(
            question=question,
            intent=intent,
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            generation_latency_ms=round(generation_latency_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
            source_count=source_count,
            confidence_score=round(confidence_score, 2),
            timestamp=datetime.utcnow().isoformat()
        )
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry.model_dump(), ensure_ascii=False) + "\n")
            logger.info(f"Observability metrics saved to log file: {log_file}")
        except Exception as e:
            logger.error(f"Failed to write observability metrics to log file: {e}")

    @classmethod
    def log_booking_event(cls, event_type: str, status: str, latency_ms: float, detail: Optional[str] = None):
        """Logs booking execution details (cancellations, reschedules, creations) to data/booking_observability.log."""
        log_file = settings.raw_data_dir.parent / "booking_observability.log"
        log_entry = {
            "event_type": event_type,
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "detail": detail,
            "timestamp": datetime.utcnow().isoformat()
        }
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            logger.info(f"Booking observability log saved: {log_file}")
        except Exception as e:
            logger.error(f"Failed to write booking metrics: {e}")

