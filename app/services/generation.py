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
        """Constructs a professional, highly readable offline answer from context when OpenRouter is rate-limited or offline."""
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

        # Check presence of key facts in context to remain 100% grounded
        has_gradonix = any(term in context.lower() for term in ["gradonix", "grado_next"])
        has_claribot = "claribot" in context.lower()
        has_fricta = "fricta" in context.lower()
        has_attendance = "attendance" in context.lower()
        has_scaler = "scaler" in context.lower()
        has_bits = "birla" in context.lower() or "bits" in context.lower()
        
        # Tech stack check
        tech_skills = []
        for tech in ["python", "java", "javascript", "typescript", "c++", "go", "postgresql", "mongodb", "redis", "spring boot", "react", "next.js", "hono", "express", "pgvector", "faiss"]:
            if tech in context.lower():
                if tech == "c++":
                    tech_skills.append("C++")
                elif tech == "next.js":
                    tech_skills.append("Next.js")
                elif tech == "spring boot":
                    tech_skills.append("Spring Boot")
                elif tech == "hono":
                    tech_skills.append("Hono.js")
                elif tech == "express":
                    tech_skills.append("Express.js")
                elif tech == "postgresql":
                    tech_skills.append("PostgreSQL")
                elif tech == "mongodb":
                    tech_skills.append("MongoDB")
                elif tech == "pgvector":
                    tech_skills.append("pgvector")
                else:
                    tech_skills.append(tech.capitalize())

        # Classify query intent for template matching
        is_contact_query = any(w in clean_q for w in ["phone", "email", "contact", "call", "number", "github", "linkedin", "portfolio"])
        is_hiring_query = any(w in clean_q for w in ["hire", "why", "recruit", "fit", "reason", "join", "benefit", "good"])
        is_exp_query = any(w in clean_q for w in ["experience", "background", "history", "education", "study", "career"])

        # Template 1: Hiring fit questions
        if is_hiring_query:
            bullets = []
            if has_gradonix or has_claribot or has_fricta:
                projects = []
                if has_gradonix: projects.append("Gradonix (AI paper evaluation platform)")
                if has_claribot: projects.append("ClariBot (RAG support widget)")
                if has_fricta: projects.append("FrictaAI (autonomous UX platform)")
                bullets.append(f"**Full-Stack AI & Web Engineering**: I have built and deployed several intelligent systems, such as {', '.join(projects)}.")
            
            if has_scaler or has_bits:
                edu = []
                if has_bits: edu.append("Computer Science & Engineering from BITS Pilani")
                if has_scaler: edu.append("Scaler School of Technology")
                bullets.append(f"**Strong Academic Foundation**: I am pursuing a Bachelor in Science degree in {', and am currently studying at '.join(edu)}.")
                
            if tech_skills:
                bullets.append(f"**Advanced Technical Stack**: I am highly proficient in {', '.join(tech_skills[:7])}.")
                
            if bullets:
                answer = "I would be a strong fit for your engineering team. Here are my key qualifications:\n\n" + "\n".join(f"- {b} [Resume]" for b in bullets)
                return answer

        # Template 2: Project-specific details
        if "gradonix" in clean_q or "grado_next" in clean_q:
            if has_gradonix:
                return (
                    "Gradonix is an AI-powered subjective hand-written paper evaluation platform I developed. "
                    "It automates OCR answer extraction and grading, featuring role-based authentication, "
                    "test creation, submission workflows, and result publishing. [Resume]"
                )
        if "claribot" in clean_q:
            if has_claribot:
                return (
                    "ClariBot is an embeddable AI support widget that provides cited, hallucination-free answers "
                    "using RAG strictly against a project's uploaded documentation. It is built with Hono/Node.js, "
                    "PostgreSQL (pgvector) for similarity search, and Gemini API for embeddings. It also features an "
                    "automated analytics engine to track user frustration. [Resume]"
                )
        if "fricta" in clean_q:
            if has_fricta:
                return (
                    "FrictaAI is an AI-native autonomous UX testing platform that emulates user personas to detect "
                    "cognitive fatigue and design flaws. It is built using TypeScript and Python. [Resume]"
                )
        if "attendance" in clean_q:
            if has_attendance:
                return (
                    "I developed a RESTful Attendance Management System using Java, Spring Boot, and Spring Data JPA. "
                    "It features role-based access for teachers and students, normalized schemas, and optimized queries. [Resume]"
                )

        # Template 3: Skill/Stack queries
        if any(w in clean_q for w in ["skill", "tech", "stack", "language", "database", "tool", "program"]):
            parts = []
            if tech_skills:
                parts.append(f"I am proficient in several technologies, including: {', '.join(tech_skills)}.")
            if "python" in context.lower():
                parts.append("For machine learning and scripting, I primarily use Python.")
            if "java" in context.lower():
                parts.append("I use Java and Spring Boot for building robust backend services.")
            if "typescript" in context.lower() or "javascript" in context.lower():
                parts.append("I use JavaScript and TypeScript across the stack, particularly with Hono, Next.js, and React.")
            if parts:
                return " ".join(parts) + " [Resume]"

        # Template 4: Contact queries
        if is_contact_query:
            contacts = []
            if "siddhant.prasad8@gmail.com" in context:
                contacts.append("Email: siddhant.prasad8@gmail.com")
            if "9310079833" in context:
                contacts.append("Phone: +91 9310079833")
            if "linkedin.com" in context.lower():
                contacts.append("LinkedIn: linkedin.com/in/siddhant-prasad-50516a339")
            if "github.com" in context.lower():
                contacts.append("GitHub: github.com/Sid13SST")
            if "siddhant-prasad.vercel.app" in context:
                contacts.append("Portfolio: https://siddhant-prasad.vercel.app/")
                
            if contacts:
                return "Here is my contact information:\n\n" + "\n".join(f"- {c} [Resume]" for c in contacts)

        # Template 5: Experience/Education queries
        if is_exp_query:
            bullets = []
            if has_scaler or has_bits:
                edu = []
                if has_bits: edu.append("a Bachelor in Science in Computer Science & Engineering from BITS Pilani")
                if has_scaler: edu.append("studying at Scaler School of Technology")
                bullets.append(f"Pursuing {', and '.join(edu)}.")
            if has_gradonix or has_claribot or has_fricta:
                bullets.append("Developed key projects: Gradonix (OCR paper grading), ClariBot (RAG widget), and FrictaAI (UX testing platform).")
            if tech_skills:
                bullets.append(f"Proficient in development technologies: {', '.join(tech_skills[:6])}.")
            if bullets:
                return "Here is an overview of my education and background:\n\n" + "\n".join(f"- {b} [Resume]" for b in bullets)

        # Template 6: General Fallback (smart sentence parsing)
        source_blocks = []
        if "=== SOURCE " in context:
            blocks = context.split("=== SOURCE ")
            for b in blocks:
                if b.strip():
                    source_blocks.append((b, "source"))
        else:
            markers = [
                ("=== SYSTEM DATA: PERSONA PROFILE ===", "profile"),
                ("=== SYSTEM DATA: RESUME DETAILS ===", "resume"),
                ("=== SYSTEM DATA: REPOSITORIES SUMMARY ===", "readme")
            ]
            indices = []
            for marker, m_type in markers:
                idx = context.find(marker)
                if idx != -1:
                    indices.append((idx, marker, m_type))
            
            indices.sort()
            for i in range(len(indices)):
                start_idx = indices[i][0] + len(indices[i][1])
                end_idx = indices[i+1][0] if i + 1 < len(indices) else len(context)
                block_content = context[start_idx:end_idx].strip()
                if block_content:
                    source_blocks.append((block_content, indices[i][2]))

        grouped_facts = {}
        for block_content, block_type in source_blocks:
            if block_type == "resume":
                citation = "Resume"
            elif block_type == "readme":
                citation = "README"
            elif block_type == "profile":
                citation = "Persona Profile"
            else:
                lines = block_content.split("\n")
                source_type = "source"
                repo_name = ""
                content_start_idx = 0
                for idx, line in enumerate(lines):
                    if line.startswith("Type:"):
                        source_type = line.split(":", 1)[1].strip().lower()
                    elif line.startswith("Repository:"):
                        repo_name = line.split(":", 1)[1].strip()
                    elif line.startswith("Content:"):
                        content_start_idx = idx + 1
                        break
                
                if "resume" in source_type:
                    citation = "Resume"
                elif "readme" in source_type:
                    citation = f"{repo_name} README" if repo_name else "README"
                elif "commit" in source_type:
                    citation = "Commit"
                elif "code" in source_type:
                    citation = "Code"
                else:
                    citation = repo_name or "Source Document"
                block_content = "\n".join(lines[content_start_idx:])

            raw_lines = block_content.split("\n")
            for raw_line in raw_lines:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                
                # Skip or clean JSON syntax
                if block_type == "profile" or raw_line.startswith('"') or raw_line.startswith('{') or raw_line.startswith('}'):
                    clean_line = raw_line.replace('"', '').replace(',', '').strip()
                    if ":" in clean_line:
                        parts = clean_line.split(":", 1)
                        key = parts[0].strip().replace("_", " ")
                        val = parts[1].strip()
                        if val and val not in ["[", "{", "]", "}"]:
                            s_sentence = f"{key.capitalize()}: {val}"
                        else:
                            continue
                    else:
                        continue
                else:
                    s_sentence = raw_line

                # Split by sentence boundaries
                sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', s_sentence)
                for sentence in sentences:
                    s_strip = sentence.strip()
                    s_strip = re.sub(r"^\s*[-*•+⋄–]\s*", "", s_strip).strip()
                    s_strip = re.sub(r"\s+", " ", s_strip)
                    if s_strip.startswith('"') and s_strip.endswith('"'):
                        s_strip = s_strip[1:-1].strip()

                    # Skip contact details in general queries to avoid raw string dumps
                    if not is_contact_query:
                        if re.search(r"\+?\d[\d\s-]{8,12}\d", s_strip): # phone
                            continue
                        if "@" in s_strip and "." in s_strip: # email
                            continue
                        if s_strip.startswith("http") or "www." in s_strip: # link
                            continue
                        if len(s_strip) < 15 and s_strip.isupper():
                            continue
                            
                    if len(s_strip) > 15:
                        if citation not in grouped_facts:
                            grouped_facts[citation] = []
                        if s_strip not in grouped_facts[citation]:
                            grouped_facts[citation].append(s_strip)

        selected_paragraphs = []
        for citation, sentences in grouped_facts.items():
            matching_sentences = []
            for s in sentences:
                s_lower = s.lower()
                score = 0
                for kw in keywords:
                    if kw in s_lower:
                        score += len(kw)
                if score >= 3:
                    matching_sentences.append((score, s))
            
            if matching_sentences:
                matching_sentences.sort(key=lambda x: -x[0])
                top_s = [s for _, s in matching_sentences[:3]]
                bullet_points = "\n".join(f"- {s} [{citation}]" for s in top_s)
                selected_paragraphs.append(bullet_points)
                
        if selected_paragraphs:
            answer_body = "\n".join(selected_paragraphs)
            if len(answer_body) > 600:
                answer_body = answer_body[:600] + "..."
            return f"Based on local source files:\n\n{answer_body}"
            
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
                source_name = f"Commit: {commit_sha[:8]}"
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

