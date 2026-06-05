import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.core.config import settings
from app.core.logging import logger

class ContextBuilder:
    @staticmethod
    def calculate_diversity_score(chunks: List[Dict[str, Any]]) -> float:
        """Calculates a source diversity score (0.0 to 1.0) based on represented source types."""
        if not chunks:
            return 0.0
            
        unique_types = set()
        for item in chunks:
            metadata = item.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            unique_types.add(source_type)
            
        # Max of 5 standard source types: resume, github_repo_metadata, github_readme, github_commit, github_code
        return min(1.0, len(unique_types) / 5.0)

    @classmethod
    def build_context(cls, retrieval_results: List[Tuple[Dict[str, Any], float]]) -> Tuple[str, float]:
        """Assembles a structured string context from retrieval chunks and returns it with a diversity score."""
        if not retrieval_results:
            return "No matching evidence found in available sources.", 0.0
            
        context_blocks = []
        chunks_data = [item for item, _ in retrieval_results]
        
        for idx, item in enumerate(chunks_data):
            metadata = item.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            repo_name = metadata.get("repo_name", "N/A")
            file_path = metadata.get("file_path", "N/A")
            commit_sha = metadata.get("commit_sha", "N/A")
            
            block = f"=== SOURCE {idx + 1} ===\n"
            block += f"Type: {source_type.upper()}\n"
            if repo_name != "N/A":
                block += f"Repository: {repo_name}\n"
            if file_path != "N/A":
                block += f"File: {file_path}\n"
            if commit_sha != "N/A":
                block += f"Commit SHA: {commit_sha[:8]}\n"
            block += f"Content:\n{item['text'].strip()}\n"
            
            context_blocks.append(block)
            
        diversity_score = cls.calculate_diversity_score(chunks_data)
        logger.info(f"Assembled context. Source diversity score: {diversity_score:.2f}")
        
        return "\n".join(context_blocks), diversity_score


class HiringFitEngine:
    @staticmethod
    def compile_hiring_context(metadata_path: Path = None, profile_path: Path = None) -> str:
        """Assembles the complete resume, projects README, and persona profile as a rich hiring evaluation context."""
        logger.info("Hiring Fit Engine triggered. Building career evaluation context...")
        
        meta_path = metadata_path or (settings.vector_db_dir / "metadata.json")
        prof_path = profile_path or (settings.vector_db_dir / "persona_profile.json")
        
        resume_texts = []
        readme_texts = []
        persona_profile_str = "{}"
        
        # 1. Load Persona Profile
        if prof_path.exists():
            try:
                with open(prof_path, "r", encoding="utf-8") as f:
                    persona_profile_str = json.dumps(json.load(f), indent=2)
            except Exception as e:
                logger.error(f"Failed to read persona_profile.json: {e}")
                
        # 2. Reconstruct Resume and Gather READMEs from metadata map
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata_map = json.load(f)
                
                # Sort elements by key/chunk_index to reconstruct files in order
                sorted_items = sorted(metadata_map.values(), key=lambda x: (x.get("metadata", {}).get("source_type"), x.get("metadata", {}).get("repo_name", ""), x.get("metadata", {}).get("chunk_index", 0)))
                
                seen_readmes = set()
                
                for item in sorted_items:
                    meta = item.get("metadata", {})
                    source_type = meta.get("source_type")
                    text = item.get("text", "")
                    
                    # Clean prefix headers to keep context size smaller
                    # Text starts with headers like [Document: Resume | Page 1]\n\n
                    clean_text = text
                    if "\n\n" in text:
                        clean_text = text.split("\n\n", 1)[1]
                    
                    if source_type == "resume":
                        resume_texts.append(clean_text)
                    elif source_type == "github_readme":
                        repo = meta.get("repo_name", "")
                        if repo not in seen_readmes:
                            readme_texts.append(f"--- README: {repo} ---\n{clean_text[:1200]}")
                            seen_readmes.add(repo)
            except Exception as e:
                logger.error(f"Failed to parse metadata.json in HiringFitEngine: {e}")

        # Assemble unified text
        unified_context = (
            "=== SYSTEM DATA: PERSONA PROFILE ===\n"
            f"{persona_profile_str}\n\n"
            "=== SYSTEM DATA: RESUME DETAILS ===\n"
            f"{' '.join(resume_texts) if resume_texts else 'No resume parsed.'}\n\n"
            "=== SYSTEM DATA: REPOSITORIES SUMMARY ===\n"
            f"{'\n'.join(readme_texts) if readme_texts else 'No repository readmes parsed.'}"
        )
        
        logger.info(f"Hiring context assembled. Total length: {len(unified_context)} characters.")
        return unified_context
