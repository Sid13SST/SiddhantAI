import re
# pyrefly: ignore [missing-import]
import httpx
from typing import Dict, Any, List
from app.core.config import settings
from app.core.logging import logger

class QueryProcessor:
    AVAILABILITY_KEYWORDS = ["available", "availability", "free", "calendar", "schedule", "meeting", "slot", "when can we", "time zone"]
    BOOKING_KEYWORDS = ["book", "interview", "schedule interview", "appointment", "calendar link", "reserve"]
    HIRING_FIT_KEYWORDS = ["hire", "hiring", "why you", "fit for", "recruit", "candidate", "scaler", "strengths", "weaknesses", "why should we"]
    RESUME_KEYWORDS = ["resume", "cv", "education", "degree", "gpa", "experience", "job", "career", "college", "university"]
    TECH_KEYWORDS = ["architecture", "decision", "design patterns", "auth", "jwt", "database choice", "postgres vs", "why did you choose", "how did you implement", "code structure"]
    REPO_KEYWORDS = ["github", "repo", "repository", "repositories", "commit", "commits", "history", "codebase"]

    @classmethod
    async def classify_intent(cls, query: str) -> Dict[str, Any]:
        """Classifies the query intent using a fast keyword-matching router with LLM fallback."""
        query_lower = query.lower()
        
        # 1. Keyword-based matching
        if any(kw in query_lower for kw in cls.BOOKING_KEYWORDS):
            return {"intent": "booking_request", "confidence": 1.0}
            
        if any(kw in query_lower for kw in cls.AVAILABILITY_KEYWORDS):
            return {"intent": "availability_question", "confidence": 1.0}
            
        if any(kw in query_lower for kw in cls.HIRING_FIT_KEYWORDS):
            return {"intent": "hiring_fit_question", "confidence": 1.0}
            
        if any(kw in query_lower for kw in cls.TECH_KEYWORDS):
            return {"intent": "technical_decision_question", "confidence": 0.9}
            
        if any(kw in query_lower for kw in cls.REPO_KEYWORDS):
            return {"intent": "repository_question", "confidence": 0.9}
            
        if any(kw in query_lower for kw in cls.RESUME_KEYWORDS):
            return {"intent": "resume_question", "confidence": 0.9}

        # 2. LLM Fallback (if OpenRouter key is set)
        if settings.OPENROUTER_API_KEY:
            logger.info("Keyword matching low confidence. Falling back to OpenRouter for intent classification...")
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            prompt = (
                f"Classify the intent of the following user query. The supported intents are:\n"
                f"1. resume_question (questions about background, jobs, degree)\n"
                f"2. project_question (questions about specific software projects or applications)\n"
                f"3. repository_question (questions about github statistics or file list)\n"
                f"4. technical_decision_question (questions about design choices, libraries, architecture)\n"
                f"5. hiring_fit_question (questions about strengths, hire reason, scaler alignment)\n"
                f"6. availability_question (questions about calendar availability)\n"
                f"7. booking_request (requests to book/schedule a meeting)\n"
                f"8. unknown (general questions)\n\n"
                f"Query: '{query}'\n\n"
                f"Respond ONLY in valid JSON matching this schema: {{\"intent\": \"string\", \"confidence\": float}}"
            )
            
            payload = {
                "model": settings.OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
            
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        import json
                        res = json.loads(raw_content)
                        logger.info(f"OpenRouter classified intent: {res.get('intent')} (confidence: {res.get('confidence')})")
                        return {
                            "intent": res.get("intent", "unknown"),
                            "confidence": float(res.get("confidence", 0.7))
                        }
            except Exception as e:
                logger.error(f"OpenRouter intent classification fallback failed: {e}")

        # Default fallback
        return {"intent": "unknown", "confidence": 0.5}

    @classmethod
    async def rewrite_query(cls, query: str, intent: str) -> str:
        """Rewrites the user query to optimize semantic matches in the vector database."""
        # 1. LLM-based rewriter (if OpenRouter key is set)
        if settings.OPENROUTER_API_KEY:
            logger.info("Using OpenRouter to rewrite query...")
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            prompt = (
                f"You are a search query optimizer. Rewrite the following user query to optimize semantic search matching "
                f"over a local document database containing code, commits, and resume details. "
                f"Expand with relevant technical keywords, synonyms, and architectural terms. "
                f"Ensure the output is a space-separated string of search terms.\n\n"
                f"Original Query: '{query}'\n"
                f"Intent: {intent}\n\n"
                f"Output ONLY the optimized search terms. Do not write explanation, quotes, or markdown code blocks."
            )
            
            payload = {
                "model": settings.OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        rewritten = data["choices"][0]["message"]["content"].strip()
                        # Clean up quotes if returned
                        rewritten = re.sub(r'^["\']|["\']$', '', rewritten)
                        logger.info(f"OpenRouter rewritten query: '{rewritten}'")
                        return rewritten
            except Exception as e:
                logger.error(f"OpenRouter query rewriter failed: {e}")

        # 2. Heuristic rule-based query expansion (Offline fallback)
        logger.info("Using rule-based query expansion...")
        words = query.lower().split()
        stop_words = {"tell", "me", "about", "why", "should", "we", "is", "are", "how", "do", "you", "does", "did", "the", "a", "an", "of"}
        filtered_words = [w for w in words if w not in stop_words]
        
        base_query = " ".join(filtered_words)
        
        # Append intent-specific search boosters
        boosters = {
            "hiring_fit_question": "strengths skills achievements experience scaler hire advantages",
            "technical_decision_question": "architecture design pattern implementation tech decisions choice database auth",
            "repository_question": "github repo repository codebase structure files branches stars",
            "resume_question": "resume cv education degree experience college projects skills background",
            "project_question": "project application technologies stack design features details"
        }
        
        booster = boosters.get(intent, "")
        final_query = f"{base_query} {booster}".strip()
        logger.info(f"Rule-based rewritten query: '{final_query}'")
        return final_query
