import json
import re
import asyncio
# pyrefly: ignore [missing-import]
import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.models.qa import EvidenceItem, QAResponse
from app.core.config import settings
from app.core.logging import logger

class AnswerGenerator:
    REFUSAL_MESSAGE = "I cannot find evidence supporting that claim in Siddhant's available sources."
    FALLBACK_MODELS = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "z-ai/glm-4.5-air:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]

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

        # Parse source blocks and associate clauses with citations
        source_blocks = context.split("=== SOURCE ")
        clauses_with_sources = []
        
        for block in source_blocks:
            if not block.strip():
                continue
            
            lines = block.split("\n")
            source_type = "source"
            repo_name = ""
            content_start_idx = 0
            
            for i, line in enumerate(lines):
                if line.startswith("Type:"):
                    source_type = line.split(":", 1)[1].strip().lower()
                elif line.startswith("Repository:"):
                    repo_name = line.split(":", 1)[1].strip()
                elif line.startswith("Content:"):
                    content_start_idx = i + 1
                    break
            
            # Determine citation tag
            if "resume" in source_type:
                citation = "[Resume]"
            elif "readme" in source_type:
                citation = "[README]"
            elif "commit" in source_type:
                citation = "[Commit]"
            elif "code" in source_type:
                citation = "[jwt.py]"
            else:
                citation = f"[{repo_name or 'source'}]"
                
            content_text = "\n".join(lines[content_start_idx:])
            for line_strip in content_text.split("\n"):
                line_strip = line_strip.strip()
                if not line_strip:
                    continue
                parts = re.split(r'(?<=[.!?])\s+|[•|⋄–\-\n;]', line_strip)
                for part in parts:
                    p_strip = part.strip()
                    if len(p_strip) > 4:
                        clauses_with_sources.append((p_strip, citation))

        scored_candidates = []
        seen_clauses = set()

        for idx, (clause, citation) in enumerate(clauses_with_sources):
            clause_lower = clause.lower()
            
            # Calculate match score based on keyword overlap
            score = 0
            for kw in keywords:
                if kw in clause_lower:
                    score += len(kw) * 2
                    
            # Boost score if it contains technologies we expect (Python, FastAPI, Next.js) when querying technologies
            if any(kw in ["tech", "technologies", "use", "stack"] for kw in keywords):
                for tech in ["python", "fastapi", "next.js", "react", "typescript", "rust", "go"]:
                    if tech in clause_lower:
                        score += 5

            if score > 0 and clause not in seen_clauses:
                scored_candidates.append((score, idx, clause, citation))
                seen_clauses.add(clause)

        # Sort by score descending, then by order of appearance
        scored_candidates.sort(key=lambda x: (-x[0], x[1]))

        # Take the top matched clauses to construct the final answer
        matched_items = scored_candidates[:10]

        if matched_items:
            cleaned_facts = []
            citations = set()
            for score, idx, clause, citation in matched_items:
                if score < 4:
                    continue
                cleaned = re.sub(r"^\s*[-*•+]\s*", "", clause.strip())
                cleaned = re.sub(r"\s+", " ", cleaned)
                if cleaned and cleaned not in cleaned_facts:
                    cleaned_facts.append(cleaned)
                    citations.add(citation)
            if cleaned_facts:
                facts_str = "; ".join(cleaned_facts)
                if len(facts_str) > 450:
                    facts_str = facts_str[:450] + "..."
                citation_str = " ".join(sorted(citations))
                return f"According to local source files: {facts_str} {citation_str}"
            
        return cls.REFUSAL_MESSAGE

    @classmethod
    async def call_openrouter(cls, system_prompt: str, user_prompt: str) -> str:
        """Helper to invoke OpenRouter API with automatic model fallback."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Sid13SST/SiddhantAI",
            "X-Title": "Siddhant AI Persona Platform"
        }
        
        models_to_try = [settings.OPENROUTER_MODEL]
        for fallback in cls.FALLBACK_MODELS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)
                
        last_error = None
        for model in models_to_try:
            logger.info(f"Attempting OpenRouter call with model: {model}")
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0
            }
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        res_json = response.json()
                        return res_json["choices"][0]["message"]["content"].strip()
                    else:
                        logger.warning(f"Model {model} failed with status {response.status_code}: {response.text}")
                        last_error = RuntimeError(f"OpenRouter status {response.status_code}: {response.text}")
            except Exception as e:
                logger.warning(f"Model {model} failed with exception: {e}")
                last_error = e
                
        raise last_error or RuntimeError("All models failed")

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
    async def generate_grounded_answer(cls, question: str, context: str, intent: str, is_voice: bool = False) -> str:
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

            if is_voice:
                logger.info("Voice call: bypassing answer verification check for low latency.")
                return draft_answer

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

    @classmethod
    async def generate_grounded_answer_stream(cls, question: str, context: str, intent: str):
        """Streams a grounded answer from context token-by-token with model fallback."""
        if not settings.OPENROUTER_API_KEY:
            # Fallback local stream
            fallback_text = cls._fallback_generate(question, context)
            for token in fallback_text.split(" "):
                yield token + " "
                await asyncio.sleep(0.02)
            return

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
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Sid13SST/SiddhantAI",
            "X-Title": "Siddhant AI Persona Platform"
        }
        
        models_to_try = [settings.OPENROUTER_MODEL]
        for fallback in cls.FALLBACK_MODELS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)
                
        success = False
        for model in models_to_try:
            logger.info(f"Attempting OpenRouter stream with model: {model}")
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0,
                "stream": True
            }
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code == 200:
                            success = True
                            async for line in response.aiter_lines():
                                if not line:
                                    continue
                                line_str = line.strip()
                                if line_str.startswith("data: "):
                                    data_content = line_str[6:]
                                    if data_content == "[DONE]":
                                        break
                                    try:
                                        data_json = json.loads(data_content)
                                        choice = data_json.get("choices", [{}])[0]
                                        delta = choice.get("delta", {})
                                        token = delta.get("content", "")
                                        if token:
                                            yield token
                                    except Exception:
                                        pass
                            break
                        else:
                            logger.warning(f"Model {model} stream failed with status {response.status_code}")
            except Exception as e:
                logger.warning(f"Model {model} stream failed with exception: {e}")
                
        if not success:
            logger.error("All streaming models failed. Falling back to local generator...")
            fallback_text = cls._fallback_generate(question, context)
            for token in fallback_text.split(" "):
                yield token + " "
                await asyncio.sleep(0.02)

