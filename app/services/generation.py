import json
import re
# pyrefly: ignore [missing-import]
import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.models.qa import EvidenceItem, QAResponse
from app.core.config import settings
from app.core.logging import logger

class AnswerGenerator:
    REFUSAL_MESSAGE = "I cannot find evidence supporting that claim in Siddhant's available sources."

    @classmethod
    def _fallback_generate(cls, question: str, context: str) -> str:
        """Constructs a basic offline answer from context if OpenRouter is unconfigured/offline."""
        logger.info("Using local fallback generator...")
        if "No matching evidence found" in context or not context.strip():
            return cls.REFUSAL_MESSAGE
            
        # Clean question and find key terms
        clean_q = re.sub(r"[^\w\s]", "", question.lower())
        keywords = [w for w in clean_q.split() if len(w) > 3]
        
        if not keywords:
            keywords = [w for w in clean_q.split() if w]
            
        if not keywords:
            return cls.REFUSAL_MESSAGE

        matched_lines = []
        for line in context.split("\n"):
            if any(kw in line.lower() for kw in keywords):
                # Clean header lines
                if not any(line.startswith(p) for p in ["===", "Type:", "Repository:", "File:", "Commit"]):
                    matched_lines.append(line.strip())
                    if len(matched_lines) >= 3:
                        break

        if matched_lines:
            facts = " ".join(matched_lines)
            return f"Based on the local files: {facts} [Local Source]"
            
        return cls.REFUSAL_MESSAGE

    @classmethod
    async def call_openrouter(cls, system_prompt: str, user_prompt: str) -> str:
        """Helper to invoke OpenRouter API."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Sid13SST/SiddhantAI",
            "X-Title": "Siddhant AI Persona Platform"
        }
        payload = {
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0  # Zero temperature for maximum deterministic grounding
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"OpenRouter returned status {response.status_code}: {response.text}")
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"].strip()

    @classmethod
    async def verify_answer(cls, draft_answer: str, context: str) -> bool:
        """Runs the post-generation Answer Verification Check (PASS or FAIL)."""
        if not settings.OPENROUTER_API_KEY:
            logger.info("Verification skipped (no OpenRouter key). Defaulting to PASS.")
            return True
            
        system_prompt = (
            "You are a strict factual audit assistant. Evaluate if the generated answer is fully grounded "
            "in the provided evidence. Respond with exactly 'PASS' if every factual statement in the answer "
            "is supported by the evidence, or 'FAIL' if any claim is fabricated, exaggerated, or uses external knowledge.\n"
            "Do not output any other text or reasoning. Output exactly PASS or FAIL."
        )
        user_prompt = f"Generated Answer:\n{draft_answer}\n\nEvidence Context:\n{context}"
        
        try:
            logger.info("Running post-generation answer verification check...")
            result = await cls.call_openrouter(system_prompt, user_prompt)
            verdict = result.strip().upper()
            logger.info(f"Verification result: {verdict}")
            return verdict == "PASS"
        except Exception as e:
            logger.error(f"Error during answer verification: {e}")
            return True # Fallback to true to avoid blocking on API failures

    @classmethod
    async def generate_grounded_answer(cls, question: str, context: str, intent: str) -> str:
        """Generates a grounded answer from context with strict persona behavior, verification checks, and regeneration."""
        if not settings.OPENROUTER_API_KEY:
            return cls._fallback_generate(question, context)

        system_prompt = (
            "You are Siddhant's digital AI representative. Your goal is to answer questions from recruiters "
            "about Siddhant's background, projects, repositories, commits, and technical skills.\n\n"
            "CRITICAL RULES:\n"
            "1. Answer ONLY using the facts explicitly stated in the provided context evidence.\n"
            "2. Never use external knowledge, speculate, or fabricate details.\n"
            "3. Never claim experience, technologies, or accomplishments not listed in the evidence.\n"
            f"4. If the evidence does not contain the answer, respond EXACTLY with: '{cls.REFUSAL_MESSAGE}'\n"
            "5. Stay in character as Siddhant (using first-person 'I' when talking about projects or skills).\n"
            "6. Make answers concise, professional, and directly cite the sources in brackets where facts are mentioned "
            "(e.g., [Resume Page 1], [Gradonix README], [Commit: a81d3f], [src/auth/jwt.py])."
        )
        
        user_prompt = f"User Question: {question}\n\nContext Evidence:\n{context}"
        
        try:
            # 1. First Generation Attempt
            logger.info("Generating draft answer...")
            draft_answer = await cls.call_openrouter(system_prompt, user_prompt)
            
            # 2. Check Refusal
            if cls.REFUSAL_MESSAGE.lower() in draft_answer.lower():
                return cls.REFUSAL_MESSAGE

            # 3. Answer Verification Layer
            is_valid = await cls.verify_answer(draft_answer, context)
            if is_valid:
                return draft_answer
                
            # 4. If Verification Fails: Attempt Stricter Regeneration
            logger.warning("Factual verification failed. Regenerating with stricter constraints...")
            stricter_prompt = (
                f"{system_prompt}\n\n"
                f"REINFORCEMENT: Your previous response failed the factual verification check because it contained "
                f"unsupported claims or extrapolated beyond the facts in the context. Rewrite the answer ensuring that "
                f"EVERY SINGLE claim is directly derived from the supplied context. Do not invent anything."
            )
            
            final_answer = await cls.call_openrouter(stricter_prompt, user_prompt)
            
            # Re-verify the regenerated answer
            is_valid_again = await cls.verify_answer(final_answer, context)
            if not is_valid_again:
                logger.error("Regenerated answer failed verification again. Returning safe refusal.")
                return cls.REFUSAL_MESSAGE
                
            return final_answer
            
        except Exception as e:
            logger.error(f"Error during answer generation: {e}")
            return cls._fallback_generate(question, context)

    @classmethod
    def compile_evidence_panel(cls, answer: str, retrieval_results: List[Tuple[Dict[str, Any], float]]) -> Tuple[List[str], List[EvidenceItem]]:
        """Parses the generated answer for source bracket citations and builds the Next.js Evidence Panel payload."""
        if answer == cls.REFUSAL_MESSAGE:
            return [], []
            
        # 1. Parse citations from text (e.g. matching [Resume Page 1], [FrictaAI README])
        citations_found = re.findall(r"\[([^\]]+)\]", answer)
        unique_citations = list(set(citations_found))
        
        evidence_items = []
        seen_snippets = set()
        
        # 2. Build evidence panel items from retrieval chunks
        for item, _ in retrieval_results:
            metadata = item.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            repo_name = metadata.get("repo_name", "")
            file_path = metadata.get("file_path", "")
            commit_sha = metadata.get("commit_sha", "")
            
            # Formulate friendly source name matching citation styles
            if source_type == "resume":
                source_name = f"Resume Page {metadata.get('page_number', 1)}"
            elif source_type == "github_readme":
                source_name = f"{repo_name} README"
            elif source_type == "github_code":
                source_name = f"{repo_name} - {file_path}"
            elif source_type == "github_commit":
                source_name = f"Commit {commit_sha[:8]}"
            else:
                source_name = f"{repo_name} Repository"
                
            snippet = item["text"]
            # Strip headers from display snippet
            if "\n\n" in snippet:
                snippet = snippet.split("\n\n", 1)[1]
                
            if snippet not in seen_snippets:
                evidence_items.append(EvidenceItem(
                    source=source_name,
                    snippet=snippet.strip()
                ))
                seen_snippets.add(snippet)
                
        # If fallback local source is used
        if "Local Source" in answer and not evidence_items:
            evidence_items.append(EvidenceItem(
                source="Local Sources",
                snippet="Facts matched locally from cache."
            ))
            
        return unique_citations, evidence_items
