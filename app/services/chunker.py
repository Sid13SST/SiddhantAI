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
    def split_code(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
        # Split code by class or function boundaries
        pattern = r"\n(?=(?:def |class |function |export |const [a-zA-Z0-9_]+ = \())"
        blocks = re.split(pattern, text)
        chunks = []
        
        current_chunk = []
        current_len = 0
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            if len(block) > chunk_size:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                
                # Split line-by-line if a single block is huge
                lines = block.split("\n")
                sub_chunk = []
                sub_len = 0
                for line in lines:
                    if sub_len + len(line) + 1 > chunk_size:
                        if sub_chunk:
                            chunks.append("\n".join(sub_chunk))
                        line_overlap = max(1, int(overlap / 40))  # Estimate 40 chars/line
                        sub_chunk = sub_chunk[-line_overlap:] if len(sub_chunk) > line_overlap else sub_chunk
                        sub_len = sum(len(l) + 1 for l in sub_chunk)
                    sub_chunk.append(line)
                    sub_len += len(line) + 1
                if sub_chunk:
                    chunks.append("\n".join(sub_chunk))
            else:
                if current_len + len(block) + 1 > chunk_size:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [block]
                    current_len = len(block)
                else:
                    current_chunk.append(block)
                    current_len += len(block) + 1
                    
        if current_chunk:
            chunks.append("\n".join(current_chunk))
            
        return chunks

    @classmethod
    def chunk_document(cls, doc: IngestedDocument) -> List[DocumentChunk]:
        source_type = doc.metadata.get("source_type")
        repo_name = doc.metadata.get("repo_name", "Unknown")
        
        raw_chunks = []
        
        # Apply specialized splitting strategies
        if source_type == SourceType.RESUME.value:
            # 500 chars, 50 overlap
            page_num = doc.metadata.get("page_number", 1)
            prefix = f"[Document: Resume | Page {page_num}]\n\n"
            split_texts = cls.split_by_words(doc.content, 500, 50)
            raw_chunks = [(txt, prefix) for txt in split_texts]
            
        elif source_type == SourceType.GITHUB_README.value:
            # Markdown header aware
            prefix = f"[Repository: {repo_name}]\n[Source: README]\n\n"
            split_texts = cls.split_markdown(doc.content, 1000, 100)
            raw_chunks = [(txt, prefix) for txt in split_texts]
            
        elif source_type == SourceType.GITHUB_CODE.value:
            # Code structure aware
            file_path = doc.metadata.get("file_path", "Unknown")
            prefix = f"[Repository: {repo_name}]\n[Source: CODE | File: {file_path}]\n\n"
            split_texts = cls.split_code(doc.content, 800, 100)
            raw_chunks = [(txt, prefix) for txt in split_texts]
            
        elif source_type == SourceType.GITHUB_COMMIT.value:
            # 1 commit = 1 chunk
            commit_sha = doc.metadata.get("commit_sha", "Unknown")
            prefix = f"[Repository: {repo_name}]\n[Source: Commit | SHA: {commit_sha[:8]}]\n\n"
            raw_chunks = [(doc.content, prefix)]
            
        elif source_type == SourceType.GITHUB_REPO_METADATA.value:
            # 1 repo metadata record = 1 chunk
            prefix = f"[Repository: {repo_name}]\n[Source: Repo Metadata]\n\n"
            raw_chunks = [(doc.content, prefix)]
            
        else:
            # Fallback character recursive chunking
            prefix = f"[Source: {source_type.upper() if source_type else 'General'}]\n\n"
            split_texts = cls.split_by_words(doc.content, 500, 50)
            raw_chunks = [(txt, prefix) for txt in split_texts]

        chunks = []
        for idx, (text, prefix) in enumerate(raw_chunks):
            chunk_text = f"{prefix}{text}"
            
            # Generate tags
            file_path = doc.metadata.get("file_path")
            tags = cls.extract_tags(text, file_path)
            
            # Merge parent metadata and add retrieval_tags + chunk_index
            merged_metadata = doc.metadata.copy()
            merged_metadata["retrieval_tags"] = list(set(merged_metadata.get("retrieval_tags", []) + tags))
            merged_metadata["chunk_index"] = idx
            
            # Generate unique chunk ID
            chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]
            chunk_id = f"{doc.id}_c{idx}_{chunk_hash}"
            
            chunks.append(DocumentChunk(
                id=chunk_id,
                parent_id=doc.id,
                text=chunk_text,
                chunk_index=idx,
                metadata=merged_metadata
            ))
            
        return chunks
