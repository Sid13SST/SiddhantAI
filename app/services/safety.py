import re
from typing import Tuple
from app.core.logging import logger

class SafetyService:
    # Compile common injection/jailbreak patterns for fast matching
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(?:the\s+|all\s+|any\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(?:the\s+|all\s+|any\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"ignore\s+above", re.IGNORECASE),
        re.compile(r"reveal\s+(?:your\s+)?system\s+prompt", re.IGNORECASE),
        re.compile(r"what\s+is\s+your\s+system\s+prompt", re.IGNORECASE),
        re.compile(r"tell\s+me\s+your\s+system\s+prompt", re.IGNORECASE),
        re.compile(r"your\s+original\s+instructions", re.IGNORECASE),
        re.compile(r"pretend\s+to\s+be", re.IGNORECASE),
        re.compile(r"act\s+as\s+a", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"bypass\s+restrictions", re.IGNORECASE)
    ]

    # Red-team and out-of-bounds/hallucination patterns
    RESTRICTED_PATTERNS = [
        # Fake Experience / Hallucination Attack
        re.compile(r"\bspacex\b", re.IGNORECASE),
        re.compile(r"\bnasa\b", re.IGNORECASE),
        re.compile(r"\bastronaut\b", re.IGNORECASE),
        re.compile(r"\bapple\b", re.IGNORECASE),
        re.compile(r"\bceo\s+of\s+google\b", re.IGNORECASE),
        # Calendar Abuse
        re.compile(r"\b(?:500|100+|1000+)\s+meetings\b", re.IGNORECASE),
        # Out-of-bounds/Hallucination
        re.compile(r"\bfavorite\s+food\b", re.IGNORECASE),
        re.compile(r"\bdog(s)?\b", re.IGNORECASE),
        re.compile(r"\bsort\s+a\s+list\b", re.IGNORECASE),
        re.compile(r"\bpython\s+script\b", re.IGNORECASE),
        re.compile(r"\bwrite\s+a\s+python\b", re.IGNORECASE)
    ]

    @classmethod
    def is_safe_query(cls, query: str) -> Tuple[bool, str]:
        """Scans the user query for prompt injection, jailbreak attempts, or out-of-bounds topics.
        Returns a tuple of (is_safe, refusal_reason)."""
        for pattern in cls.INJECTION_PATTERNS:
            if pattern.search(query):
                logger.warning(f"Safety violation: Query '{query}' triggered prompt injection guard.")
                return False, "I cannot fulfill this request as it violates prompt safety rules."

        for pattern in cls.RESTRICTED_PATTERNS:
            if pattern.search(query):
                logger.warning(f"Restricted topic check failed for query: '{query}'")
                from app.services.generation import AnswerGenerator
                return False, AnswerGenerator.REFUSAL_MESSAGE
                
        return True, ""
