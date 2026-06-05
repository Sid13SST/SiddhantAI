import os
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
# pyrefly: ignore [missing-import]
from rapidfuzz import fuzz

from app.services.qa_engine import QAEngine
from app.services.booking_orchestrator import BookingOrchestrator
from app.core.config import settings
from app.core.logging import logger

# Paths for transcripts and summaries
TRANSCRIPTS_PATH = Path(settings.DATA_DIR) / "voice_transcripts.jsonl"
SUMMARIES_PATH = Path(settings.DATA_DIR) / "call_summaries.json"
OBSERVABILITY_PATH = Path(settings.DATA_DIR) / "voice_observability.log"

class VoiceConfidenceRecovery:
    TARGETS = ["Gradonix", "FrictaAI", "FastAPI", "Next.js", "sentence-transformers", "RAG", "FAISS", "Siddhant"]
    
    TELEPHONY_MAPPINGS = {
        "grad onion": "Gradonix",
        "gradonics": "Gradonix",
        "gradonix": "Gradonix",
        "red onix": "Gradonix",
        "redonics": "Gradonix",
        "friction ai": "FrictaAI",
        "fricta ai": "FrictaAI",
        "fricta": "FrictaAI",
        "sid": "Siddhant",
        "siddharth": "Siddhant",
        "fast api": "FastAPI",
        "next js": "Next.js",
    }

    @classmethod
    def recover_query(cls, query: str) -> Tuple[str, Optional[str]]:
        """Fuzzily corrects common STT phonetic transcription errors on key terms.
        
        Returns a tuple of: (corrected_query, suggestion_msg).
        If an ambiguous match is corrected, it provides a feedback prompt to speak back to the user.
        """
        if not query or not query.strip():
            return query, None

        q_clean = query.strip()
        q_lower = q_clean.lower()
        suggestion_msg = None
        corrected = False

        # 1. Custom mappings for multi-word phonetic mistakes
        for typo, correction in cls.TELEPHONY_MAPPINGS.items():
            pattern = re.compile(rf"\b{re.escape(typo)}\b", re.IGNORECASE)
            if pattern.search(q_clean):
                q_clean = pattern.sub(correction, q_clean)
                corrected = True
                logger.info(f"Fuzzy Recovery: Replaced telephony typo '{typo}' -> '{correction}'")

        # 2. Word-by-word comparison using rapidfuzz
        words = q_clean.split()
        for idx, word in enumerate(words):
            # Clean word from punctuation
            cleaned = re.sub(r"[^\w\-]", "", word)
            if len(cleaned) <= 3:
                continue

            for target in cls.TARGETS:
                # Calculate similarity score
                score = fuzz.ratio(cleaned.lower(), target.lower())
                if score > 78 and cleaned.lower() != target.lower():
                    words[idx] = target
                    corrected = True
                    logger.info(f"Fuzzy Recovery: Corrected word '{word}' -> '{target}' (Score: {score:.1f}%)")
                    # If score is in a slightly ambiguous range, note it
                    if score < 90:
                        suggestion_msg = f"Did you mean {target}?"
                    break

        final_query = " ".join(words)
        return final_query, suggestion_msg


class VoiceSessionManager:
    """Manages active voice calls and tracks conversational history, topic, and transaction states."""
    
    @classmethod
    def get_or_create_session(cls, call_id: str) -> Dict[str, Any]:
        """Interfaces directly with BookingOrchestrator session cache to maintain a single source of truth."""
        # Use BookingOrchestrator cache to manage session, keeping booking state and locks aligned
        session_id, context = BookingOrchestrator.get_or_create_session(call_id)
        
        # Ensure voice-specific metadata keys exist
        updated = False
        if "active_topic" not in context:
            context["active_topic"] = "General QA"
            updated = True
        if "voice_history" not in context:
            context["voice_history"] = []
            updated = True
            
        if updated:
            BookingOrchestrator.update_session(call_id, context)
            
        return context

    @classmethod
    def update_active_topic(cls, call_id: str, query: str, answer: str) -> str:
        """Determines conversation topic context from turns and updates session metadata."""
        context = cls.get_or_create_session(call_id)
        current_action = context.get("action", "none")
        
        topic = "General QA"
        if current_action == "booking":
            topic = "Interview Scheduling"
        elif current_action == "reschedule":
            topic = "Interview Rescheduling"
        elif current_action == "cancellation":
            topic = "Interview Cancellation"
        else:
            # Infer from keywords
            combined = (query + " " + answer).lower()
            if "gradonix" in combined:
                topic = "Gradonix Project"
            elif "fricta" in combined:
                topic = "FrictaAI Project"
            elif "auth" in combined or "jwt" in combined:
                topic = "Authentication System"
            elif "experience" in combined or "resume" in combined or "skills" in combined:
                topic = "Career Experience"
            elif "why" in combined or "hire" in combined:
                topic = "Hiring Alignment"
                
        context["active_topic"] = topic
        BookingOrchestrator.update_session(call_id, context)
        return topic


class VoiceQueryRouter:
    qa_engine = QAEngine()

    @classmethod
    async def route_voice_query(cls, query: str, call_id: str) -> Dict[str, Any]:
        """Routes transcribed inputs through fuzzy recovery, then delegates to QA / Booking Engines."""
        start_time = time.time()
        
        # 1. Fuzzy STT Correction
        corrected_query, suggestion = VoiceConfidenceRecovery.recover_query(query)
        
        # 2. Retrieve caller context
        session = VoiceSessionManager.get_or_create_session(call_id)
        
        # 3. Call ground RAG QAEngine (which automatically routes booking steps to BookingOrchestrator)
        logger.info(f"Voice Router: Routing '{corrected_query}' for Call ID {call_id}")
        qa_response = await cls.qa_engine.answer_question(
            question=corrected_query,
            session_id=call_id,
            booking_context=session
        )
        
        # 4. Sync booking state updates
        next_session = BookingOrchestrator.SESSION_CACHE.get(call_id, session)
        
        # Determine topic updates
        active_topic = VoiceSessionManager.update_active_topic(call_id, corrected_query, qa_response.answer)
        
        # 5. Append message history
        history = next_session.get("voice_history", [])
        history.append({"role": "user", "content": query, "corrected": corrected_query})
        history.append({"role": "assistant", "content": qa_response.answer})
        next_session["voice_history"] = history
        BookingOrchestrator.update_session(call_id, next_session)
        
        latency = (time.time() - start_time) * 1000
        
        # Log voice query event
        ObservabilityLogger.log_voice_query(
            call_id=call_id,
            query=query,
            corrected_query=corrected_query,
            answer=qa_response.answer,
            latency_ms=latency,
            success=True
        )
        
        return {
            "answer": qa_response.answer,
            "suggestion": suggestion,
            "active_topic": active_topic,
            "booking_context": next_session
        }


class TranscriptStorageService:
    @classmethod
    def save_call_record(cls, call_id: str, duration: float, history: List[Dict[str, Any]]):
        """Appends the full conversation transcript for auditing."""
        record = {
            "call_id": call_id,
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat(),
            "transcript": history
        }
        
        Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
        try:
            with open(TRANSCRIPTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.info(f"Persisted call transcript to {TRANSCRIPTS_PATH}")
        except Exception as e:
            logger.error(f"Failed to save voice transcript: {e}")

    @classmethod
    def generate_call_summary(cls, call_id: str, duration: float, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesizes the call history and generates a structured summary JSON."""
        # 1. Compile topics discussed from transcript keywords
        topics = set()
        full_text = " ".join([h.get("content", "") for h in history]).lower()
        
        if "gradonix" in full_text:
            topics.add("Gradonix")
        if "fricta" in full_text:
            topics.add("FrictaAI")
        if "auth" in full_text or "jwt" in full_text or "token" in full_text:
            topics.add("Authentication")
        if "schedule" in full_text or "calendar" in full_text or "slot" in full_text or "availability" in full_text:
            topics.add("Interview Availability")
        if "hire" in full_text or "why" in full_text or "recruit" in full_text:
            topics.add("Hiring Alignment")
        if "resume" in full_text or "experience" in full_text or "tech" in full_text:
            topics.add("Career Experience")
            
        if not topics:
            topics.add("General Q&A")

        # 2. Check completed transactions in Booking session cache
        booking_created = False
        booking_id = None
        cancellation_completed = False
        
        # Read directly from session cache
        session = BookingOrchestrator.SESSION_CACHE.get(call_id, {})
        if session:
            booking_created = session.get("last_booking_created", False)
            booking_id = session.get("last_booking_id")
            cancellation_completed = session.get("last_cancellation_completed", False)

        # 3. Format call duration
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

        summary = {
            "call_id": call_id,
            "call_duration": duration_str,
            "topics_discussed": sorted(list(topics)),
            "booking_created": booking_created,
            "booking_id": booking_id,
            "cancellation_completed": cancellation_completed,
            "timestamp": datetime.now().isoformat()
        }

        # 4. Save call summaries list
        try:
            summaries = []
            if SUMMARIES_PATH.exists():
                with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
                    try:
                        summaries = json.load(f)
                        if not isinstance(summaries, list):
                            summaries = []
                    except Exception:
                        summaries = []
                        
            summaries.append(summary)
            with open(SUMMARIES_PATH, "w", encoding="utf-8") as f:
                json.dump(summaries, f, indent=2, ensure_ascii=False)
            logger.info(f"Persisted call summary details to {SUMMARIES_PATH}")
        except Exception as e:
            logger.error(f"Failed to save call summary: {e}")
            
        return summary


class ObservabilityLogger:
    @classmethod
    def log_voice_query(cls, call_id: str, query: str, corrected_query: str, answer: str, latency_ms: float, success: bool):
        log_line = {
            "timestamp": datetime.now().isoformat(),
            "event": "voice_query",
            "call_id": call_id,
            "query": query,
            "corrected_query": corrected_query,
            "latency_ms": round(latency_ms, 2),
            "success": success
        }
        cls._write_log(log_line)

    @classmethod
    def log_call_event(cls, call_id: str, event_type: str, duration: float, booking_success: bool):
        log_line = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "call_id": call_id,
            "duration_seconds": round(duration, 2),
            "booking_success": booking_success
        }
        cls._write_log(log_line)

    @classmethod
    def _write_log(cls, payload: dict):
        Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
        try:
            with open(OBSERVABILITY_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write voice observability log: {e}")


class VapiService:
    """Orchestrates configuration schema generation and webhook event management for Vapi."""
    
    @classmethod
    def get_assistant_configuration(cls, server_url: str) -> Dict[str, Any]:
        """Compiles assistant profile rules and configurations for Vapi."""
        system_prompt = (
            "You are Siddhant's voice-call AI representative. Answer recruiter questions about Siddhant's "
            "career background, repositories, skills, or schedule interviews. Keep answers short, spoken-style, "
            "friendly, and direct. When asked to schedule/book/cancel/reschedule an interview, proceed step-by-step "
            "asking timezone, email, topic, and slot choice."
        )
        
        return {
            "name": "Siddhant AI Representative",
            "model": {
                "provider": "custom-llm",
                "url": f"{server_url}/api/v1/voice/query",
                "model": settings.OPENROUTER_MODEL,
                "systemPrompt": system_prompt,
                "temperature": 0.0
            },
            "voice": {
                "provider": "vapi",
                "voiceId": "jennifer"  # Friendly standard voice
            },
            "firstMessage": "Hello, I am Siddhant's voice representative. How can I help you today?",
            "serverUrl": f"{server_url}/api/v1/voice/webhook"
        }

    @classmethod
    async def process_webhook_event(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manages inbound Vapi Server webhooks, handling initialization and final logging."""
        message = payload.get("message", {})
        msg_type = message.get("type")
        call_id = message.get("call", {}).get("id")
        
        logger.info(f"Vapi Webhook: Received event type '{msg_type}' for Call ID {call_id}")
        
        if msg_type == "assistant-request":
            # Return configuration dynamically if requested
            # Use dynamic serverURL from host
            host_url = message.get("hostUrl", f"http://127.0.0.1:{settings.PORT}")
            return cls.get_assistant_configuration(host_url)
            
        elif msg_type == "end-of-call-report":
            # Extract final duration and transcript
            call = message.get("call", {})
            duration = call.get("duration", 0.0)
            
            # Fetch voice call history from session context cache
            session = BookingOrchestrator.SESSION_CACHE.get(call_id, {})
            history = session.get("voice_history", [])
            
            # Persist records
            TranscriptStorageService.save_call_record(call_id, duration, history)
            summary = TranscriptStorageService.generate_call_summary(call_id, duration, history)
            
            # Observability logging
            booking_success = summary.get("booking_created", False)
            ObservabilityLogger.log_call_event(
                call_id=call_id,
                event_type="call_ended",
                duration=duration,
                booking_success=booking_success
            )
            
            # Clean session from memory to prevent leakages
            with BookingOrchestrator.CACHE_MUTEX:
                BookingOrchestrator.SESSION_CACHE.pop(call_id, None)
                
            return {"status": "success", "summary": summary}
            
        return {"status": "ignored"}
