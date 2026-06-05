import re
import hashlib
from typing import List, Dict, Any
from app.models.document import IngestedDocument, DocumentChunk, SourceType
from app.core.logging import logger

class ChunkingService:
    # Predefined keyword set for tag generation
    TECH_KEYWORDS = {
        # Security & Auth
        "auth", "jwt", "oauth", "session", "cookie", "login", "register", "security", "encryption",
        # Databases & Cache
        "postgres", "postgresql", "sql", "mysql", "sqlite", "mongodb", "redis", "prisma", "sqlalchemy", "database",
        # Frameworks & Languages
        "fastapi", "flask", "django", "express", "nodejs", "nextjs", "react", "vue", "tailwind", "typescript", "python", "javascript",
        # DevOps & Infrastructure
        "docker", "kubernetes", "aws", "gcp", "azure", "cicd", "github actions", "serverless",
        # AI & Search
        "rag", "embeddings", "llm", "openai", "gemini", "langchain", "vector", "faiss", "agent",
        # Architecture & Protocols
        "api", "rest", "graphql", "grpc", "websocket", "http", "mvc", "middleware"
    }

    @staticmethod
    def extract_tags(text: str, file_path: str = None) -> List[str]:
        """Automatically extracts tech keyword tags from chunk text and path."""
        tags = set()
        text_lower = text.lower()
        
        # 1. Regex word boundary matching on predefined list
        for kw in ChunkingService.TECH_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                tags.add(kw)
        
        # 2. Extract directories as tags from file_path if present
        if file_path:
            parts = re.split(r"[\\/]", file_path)
            for part in parts[:-1]:  # exclude file name itself
                part_clean = part.lower().strip()
                if len(part_clean) > 2 and part_clean not in {"src", "app", "backend", "packages", "apps"}:
                    tags.add(part_clean)
                    
        return list(tags)

    @staticmethod
    def split_by_words(text: str, chunk_size: int, overlap: int) -> List[str]:
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        overlap_word_count = max(1, int(overlap / 5))  # Estimate 5 chars per word
        
        for word in words:
            if current_length + len(word) + 1 > chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                # keep overlap
                current_chunk = current_chunk[-overlap_word_count:] if len(current_chunk) > overlap_word_count else current_chunk
                current_length = sum(len(w) + 1 for w in current_chunk)
                
            current_chunk.append(word)
            current_length += len(word) + 1
            
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    @staticmethod
    def split_markdown(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        # Split by markdown headers
        sections = re.split(r"\n(?=#+ )", text)
        chunks = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            if len(section) <= chunk_size:
                chunks.append(section)
            else:
                chunks.extend(ChunkingService.split_by_words(section, chunk_size, overlap))
        return chunks

    @staticmethod
    @staticmethod
    def split_code(text: str, *args): return [text]
