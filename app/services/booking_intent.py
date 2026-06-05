import re
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.generation import AnswerGenerator

class BookingIntentService:
    @classmethod
    async def classify_booking_intent(cls, question: str) -> Optional[Dict[str, Any]]:
        """Classifies the booking intent from a question. Returns dict with intent/confidence, or None if not booking-related."""
        q_lower = question.lower()

        # Regex patterns for direct heuristics
        cancel_patterns = [
            r"\bcancel\b", r"\bcancellation\b", r"\bdelete my (slot|meeting|interview|booking)\b"
        ]
        reschedule_patterns = [
            r"\breschedule\b", r"\bchange (my|our) (time|meeting|interview|slot)\b", r"\bmove (my|our) (time|meeting|interview|slot)\b"
        ]
        booking_patterns = [
            r"\bbook\b", r"\bschedule\b", r"\breserve\b", r"\bconfirm booking\b", r"\bschedule (an|our) interview\b"
        ]
        availability_patterns = [
            r"\bavailability\b", r"\bavailable (times|slots|hours)\b", r"\bwhen are you free\b", r"\bfree slots\b", r"\bshow availability\b"
        ]

        if any(re.search(pat, q_lower) for pat in cancel_patterns):
            return {"intent": "cancellation_request", "confidence": 1.0}
            
        if any(re.search(pat, q_lower) for pat in reschedule_patterns):
            return {"intent": "reschedule_request", "confidence": 1.0}
            
        if any(re.search(pat, q_lower) for pat in booking_patterns):
            # Make sure it isn't just checking availability
            if any(re.search(pat, q_lower) for pat in availability_patterns):
                return {"intent": "availability_check", "confidence": 0.9}
            return {"intent": "booking_request", "confidence": 1.0}
            
        if any(re.search(pat, q_lower) for pat in availability_patterns):
            return {"intent": "availability_check", "confidence": 1.0}

        # Fallback to LLM if there are ambiguous scheduling words (e.g. "free", "time", "interview", "calendar", "meeting")
        ambiguous_keywords = ["free", "time", "interview", "calendar", "meeting", "slot", "date"]
        if any(kw in q_lower for kw in ambiguous_keywords):
            if settings.OPENROUTER_API_KEY:
                try:
                    logger.info("Ambiguous booking keyword detected. Calling LLM for booking intent classification...")
                    system_prompt = (
                        "You are an intent classifier for a scheduling assistant. Analyze the user's message and determine if they want to:\n"
                        "- check availability ('availability_check')\n"
                        "- book/schedule a new interview ('booking_request')\n"
                        "- reschedule an existing interview ('reschedule_request')\n"
                        "- cancel a booking ('cancellation_request')\n"
                        "- or if it is unrelated to scheduling ('none')\n\n"
                        "Respond with exactly one word from this list: [availability_check, booking_request, reschedule_request, cancellation_request, none]"
                    )
                    result = await AnswerGenerator.call_openrouter(system_prompt, f"User message: '{question}'")
                    result_clean = result.strip().lower()
                    if result_clean in ["availability_check", "booking_request", "reschedule_request", "cancellation_request"]:
                        return {"intent": result_clean, "confidence": 0.8}
                except Exception as e:
                    logger.error(f"Error classifying booking intent via LLM: {e}")
            
        return None
