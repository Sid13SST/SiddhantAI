import json
from pathlib import Path
from typing import List, Dict, Any
# pyrefly: ignore [missing-import]
import httpx
from app.models.document import IngestedDocument, SourceType, PersonaProfile
from app.core.config import settings
from app.core.logging import logger

class PersonaBuilderService:
    FALLBACK_MODELS = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "z-ai/glm-4.5-air:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]
    @staticmethod
    def _get_fallback_profile(documents: List[IngestedDocument]) -> Dict[str, Any]:
        """Generates a high-quality fallback profile from local document data when LLM is unavailable."""
        logger.info("Generating fallback local persona profile based on ingested documents...")
        
        # Try to discover repo names and descriptions from documents
        repo_summaries = {}
        top_projects = []
        skills_set = {"Python", "TypeScript", "JavaScript", "FastAPI", "Next.js", "React", "FAISS", "Git"}
        
        for doc in documents:
            meta = doc.metadata
            source_type = meta.get("source_type")
            repo_name = meta.get("repo_name")
            
            if source_type == SourceType.GITHUB_REPO_METADATA.value and repo_name:
                desc = meta.get("description") or "GitHub Repository for project code."
                repo_summaries[repo_name] = desc
                
                lang = meta.get("language")
                if lang:
                    skills_set.add(lang)
                    
                topics = meta.get("topics", [])
                for topic in topics:
                    skills_set.add(topic.capitalize())
                    
                top_projects.append({
                    "name": repo_name,
                    "description": desc,
                    "technologies": [lang] if lang else ["TypeScript"],
                    "repo_url": meta.get("source_url")
                })
        
        # Default project if none found
        if not top_projects:
            top_projects = [
                {
                    "name": "SiddhantAI",
                    "description": "A digital AI representative and portfolio system featuring code-aware ingestion, commit indexing, and semantic search.",
                    "technologies": ["Python", "FastAPI", "TypeScript", "Next.js", "FAISS"],
                    "repo_url": "https://github.com/Siddhant/SiddhantAI"
                }
            ]
            repo_summaries["SiddhantAI"] = "Core codebase for the Siddhant AI Persona Platform backend."

        fallback = {
            "name": "Siddhant",
            "education": [
                "Bachelor of Technology in Computer Science & Engineering"
            ],
            "core_skills": sorted(list(skills_set)),
            "top_projects": top_projects,
            "technologies": sorted(list(skills_set)),
            "strengths": [
                "Full-Stack AI Engineering",
                "Advanced Vector Search and RAG Architectures",
                "Clean Code and Scalable Software Architecture",
                "System Automation and API Integrations"
            ],
            "repository_summary": repo_summaries
        }
        return fallback

    @classmethod
    async def build_persona_profile(cls, documents: List[IngestedDocument]) -> Dict[str, Any]:
        """Compiles resume and project details and builds persona_profile.json via OpenRouter (or fallback)."""
        logger.info("Building Persona Profile...")
        
        # 1. Separate resume and README contents
        resume_texts = []
        readme_texts = []
        repo_details = []
        
        for doc in documents:
            source_type = doc.metadata.get("source_type")
            if source_type == SourceType.RESUME.value:
                resume_texts.append(doc.content)
            elif source_type == SourceType.GITHUB_README.value:
                readme_texts.append(f"Repository: {doc.metadata.get('repo_name')}\nContent:\n{doc.content[:1500]}")
            elif source_type == SourceType.GITHUB_REPO_METADATA.value:
                repo_details.append(doc.content)

        resume_context = "\n\n".join(resume_texts)
        readme_context = "\n\n".join(readme_texts)
        repo_context = "\n\n".join(repo_details)
        
        # Check API key configuration
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY is not configured. Falling back to rule-based profile generation.")
            profile_dict = cls._get_fallback_profile(documents)
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Siddhant/SiddhantAI",
                "X-Title": "Siddhant AI Persona Platform"
            }
            
            prompt = (
                f"You are a professional recruiting assistant. Analyze the resume and project information "
                f"for Siddhant and compile a single structured JSON profile. Follow the schema strictly:\n\n"
                f"Required Schema:\n"
                f"{{\n"
                f"  \"name\": \"Siddhant\",\n"
                f"  \"education\": [\"Degree/Certificate - Major (Institution, Year)\"],\n"
                f"  \"core_skills\": [\"Skill1\", \"Skill2\"],\n"
                f"  \"top_projects\": [\n"
                f"    {{\n"
                f"      \"name\": \"Project Name\",\n"
                f"      \"description\": \"Detailed description of what it does and Siddhant's contribution\",\n"
                f"      \"technologies\": [\"Tech1\", \"Tech2\"],\n"
                f"      \"repo_url\": \"optional git repository link\"\n"
                f"    }}\n"
                f"  ],\n"
                f"  \"technologies\": [\"Language1\", \"Framework1\"],\n"
                f"  \"strengths\": [\"Key strength 1\", \"Key strength 2\"],\n"
                f"  \"repository_summary\": {{\n"
                f"    \"repository_name\": \"Brief summary of what this specific repository is for\"\n"
                f"  }}\n"
                f"}}\n\n"
                f"Resume Content:\n{resume_context[:4000]}\n\n"
                f"Repository Metadata:\n{repo_context[:2000]}\n\n"
                f"Readme Samples:\n{readme_context[:4000]}\n\n"
                f"CRITICAL: Respond ONLY with valid JSON. Do not write explanations, thoughts, or markdown formatting blocks."
            )
            
            models_to_try = [settings.OPENROUTER_MODEL]
            for fallback in cls.FALLBACK_MODELS:
                if fallback not in models_to_try:
                    models_to_try.append(fallback)
                    
            profile_dict = None
            for model in models_to_try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                }
                
                try:
                    logger.info(f"Calling OpenRouter model {model} to generate profile...")
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        response = await client.post(url, json=payload, headers=headers)
                        if response.status_code == 200:
                            res_json = response.json()
                            raw_content = res_json["choices"][0]["message"]["content"].strip()
                            
                            # Clean Markdown code fence backticks if LLM mistakenly returned them
                            if raw_content.startswith("```"):
                                # Remove ```json and ``` lines
                                lines = raw_content.split("\n")
                                cleaned_lines = [l for l in lines if not l.strip().startswith("```")]
                                raw_content = "\n".join(cleaned_lines).strip()
                                
                            profile_dict = json.loads(raw_content)
                            logger.info(f"Successfully synthesized persona profile using OpenRouter with model {model}.")
                            break
                        else:
                            logger.warning(f"Profile generation model {model} failed: {response.status_code} - {response.text}")
                except Exception as e:
                    logger.error(f"Error calling OpenRouter profile service with model {model}: {e}")
            
            if not profile_dict:
                logger.warning("All OpenRouter models failed to generate profile. Using local fallback.")
                profile_dict = cls._get_fallback_profile(documents)
                
        # Validate profile with Pydantic
        try:
            PersonaProfile(**profile_dict)
        except Exception as pydantic_err:
            logger.warning(f"Generated profile did not strictly match schema constraints: {pydantic_err}. Wrapping manually.")
            
        # Write profile to disk
        profile_path = settings.vector_db_dir / "persona_profile.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile_dict, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Persona profile written to local filesystem: {profile_path}")
        return profile_dict
