import asyncio
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from app.models.document import IngestedDocument, SourceType
from app.services.factory import DocumentFactory
from app.services.chunker import ChunkingService
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.profile import PersonaBuilderService
from app.core.logging import logger

# Set up logging for validation script
logger.info("Initializing Ingestion Layer validation script...")

# 1. Create mock data strings
MOCK_RESUME_TEXT = """
Siddhant - Lead AI Systems Engineer
Email: siddhant@example.com | GitHub: github.com/Siddhant

EDUCATION:
Bachelor of Technology in Computer Science & Engineering, GPA 9.8/10
Graduation: May 2024

TECHNICAL SKILLS:
Programming: Python, TypeScript, C++, Rust, Go, SQL
AI/ML: PyTorch, Hugging Face, sentence-transformers, FAISS, LangChain, RAG
Backend: FastAPI, Next.js, Docker, Kubernetes, AWS, PostgreSQL, Redis

EXPERIENCE:
Principal Engineer - AI Systems Group (July 2024 - Present)
- Designed and built high-performance Retrieval-Augmented Generation (RAG) backend systems powering chat and voice agents.
- Optimized vector store retrieval using hybrid search and custom tag pre-filtering, boosting semantic match accuracy by 35%.
- Implemented asynchronous data ingestion pipelines that process PDF resumes, GitHub repositories, and git commit histories.
"""

MOCK_README_TEXT = """
# FrictaAI

FrictaAI is a production-ready system analyzing timing models and collaboration patterns.

## Technologies Used
- Backend: FastAPI, Python 3.11+
- Embedding: sentence-transformers
- Database: Postgres & Redis
- Security: JWT Authentication and role-based permissions (RBAC).

## Setup
Run the main server using `uvicorn app.main:app --reload`.
"""

MOCK_CODE_FILE = """
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt, JWTError
from datetime import datetime, timedelta

router = APIRouter()
SECRET_KEY = "super-secret"
ALGORITHM = "HS256"

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
"""

async def run_verification():
    # Setup temporary directory for vector database to keep workspace clean during tests
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vector_db"
        db_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Using temp directory for vector DB: {db_path}")
        
        # 1. Document Creation & Normalization (Part 5: DocumentFactory)
        logger.info("\n--- Phase 1: Document Normalization & Factory Verification ---")
        
        resume_doc = DocumentFactory.create_resume_document(
            text=MOCK_RESUME_TEXT,
            page_number=1,
            total_pages=1,
            source_path=str(Path(tmpdir) / "resume.pdf")
        )
        
        repo_doc = DocumentFactory.create_github_repo_document(
            repo_name="FrictaAI",
            owner="Siddhant",
            stars=120,
            language="Python",
            description="Timing models and pattern analysis engine.",
            topics=["fastapi", "rag", "analytics"]
        )
        
        readme_doc = DocumentFactory.create_github_readme_document(
            repo_name="FrictaAI",
            owner="Siddhant",
            readme_text=MOCK_README_TEXT
        )
        
        commit_doc = DocumentFactory.create_github_commit_document(
            repo_name="FrictaAI",
            owner="Siddhant",
            commit_sha="a5b7c8d9e1f2",
            message="Added JWT authentication middleware decoder",
            author="Siddhant",
            commit_date=datetime.utcnow().isoformat(),
            changed_files=["src/auth/jwt.py", "app/main.py"]
        )
        
        code_doc = DocumentFactory.create_github_code_document(
            repo_name="FrictaAI",
            owner="Siddhant",
            file_path="src/auth/jwt.py",
            content=MOCK_CODE_FILE,
            language="Python"
        )
        
        documents = [resume_doc, repo_doc, readme_doc, commit_doc, code_doc]
        
        for doc in documents:
            logger.info(f"Normalized Doc: ID={doc.id} | Source={doc.metadata['source_type']} | URL={doc.metadata.get('source_url')}")
            assert doc.id is not None
            assert doc.content is not None
            
        # 2. Chunking & Tagging (Part 6 & 7: ChunkingService)
        logger.info("\n--- Phase 2: Chunking & Retrieval Tagging Verification ---")
        all_chunks = []
        for doc in documents:
            chunks = ChunkingService.chunk_document(doc)
            all_chunks.extend(chunks)
            
        logger.info(f"Total chunks generated: {len(all_chunks)}")
        
        for idx, chunk in enumerate(all_chunks[:5]):
            logger.info(f"\nChunk #{idx}:")
            logger.info(f"  Parent ID: {chunk.parent_id}")
            logger.info(f"  Snippet: {chunk.text[:120]}...")
            logger.info(f"  Tags: {chunk.metadata.get('retrieval_tags', [])}")
            assert len(chunk.text) > 0
            assert "retrieval_tags" in chunk.metadata
            
        # 3. Embeddings & Storage (Part 8 & 9: EmbeddingService + VectorStoreService)
        logger.info("\n--- Phase 3: Embeddings & FAISS Vector Indexing Verification ---")
        
        # Load local embedding model
        embedding_service = EmbeddingService()
        chunk_texts = [c.text for c in all_chunks]
        
        # Batch encode
        embeddings = embedding_service.generate_embeddings(chunk_texts)
        logger.info(f"Generated embeddings array shape: {embeddings.shape}")
        assert embeddings.shape[0] == len(all_chunks)
        assert embeddings.shape[1] == 384
        
        # Add to vector store
        store = VectorStoreService(db_dir=db_path)
        store.init_new_index()
        store.add_chunks(all_chunks, embeddings)
        store.save()
        
        # Verify persistence files
        assert (db_path / "index.faiss").exists()
        assert (db_path / "metadata.json").exists()
        logger.info("Successfully verified vector database filesystem serialization files.")
        
        # 4. Persona Profile Building (Part 10)
        logger.info("\n--- Phase 4: Persona Profile Builder Synthesis Verification ---")
        profile = await PersonaBuilderService.build_persona_profile(documents)
        profile_path = db_path / "persona_profile.json"
        
        # Copy output to temp vector store directory manually as build_persona_profile writes to settings.vector_db_dir
        # But we also run checks on returned profile
        logger.info(f"Persona Profile Synthesized: Name={profile.get('name')}")
        logger.info(f"Core Skills: {profile.get('core_skills')}")
        logger.info(f"Education: {profile.get('education')}")
        assert profile.get("name") == "Siddhant"
        
        # 5. Search & Retrieval (RAG Compatibility Verification)
        logger.info("\n--- Phase 5: Semantic Retrieval & Tag Boosting Verification ---")
        
        # Create a fresh store instance and load files from temp path
        new_store = VectorStoreService(db_dir=db_path)
        new_store.load()
        
        # Query 1: JWT Authentication
        query_text = "How is authentication implemented?"
        query_vector = embedding_service.generate_embeddings([query_text])[0]
        
        # Vector search (without tag filter)
        results_no_tags = new_store.search(query_vector, top_k=3)
        logger.info(f"\nQuery: '{query_text}' (Vanilla semantic search results):")
        for chunk_data, score in results_no_tags:
            logger.info(f"  [L2 Dist: {score:.4f}] Chunk: {chunk_data['chunk_id']} | Source: {chunk_data['metadata']['source_type']}")
            logger.info(f"  Snippet: {chunk_data['text'][:120]}...")
            
        # Vector search (with tag boost for 'jwt' and 'auth')
        # We simulate tag boosting
        filter_tags = ["jwt", "auth"]
        logger.info(f"\nQuery: '{query_text}' (Semantic search results with tag boosting for {filter_tags}):")
        
        boosted_results = []
        for chunk_data, score in results_no_tags:
            doc_tags = chunk_data["metadata"].get("retrieval_tags", [])
            boosted_score = score
            intersect = set(filter_tags).intersection(set(doc_tags))
            if intersect:
                boosted_score -= 0.15 * len(intersect)
            boosted_results.append((chunk_data, boosted_score))
            
        boosted_results.sort(key=lambda x: x[1])
        for chunk_data, score in boosted_results:
            logger.info(f"  [Boosted Score: {score:.4f}] Chunk: {chunk_data['chunk_id']} | Source: {chunk_data['metadata']['source_type']}")
            logger.info(f"  Snippet: {chunk_data['text'][:120]}...")
            logger.info(f"  Tags: {chunk_data['metadata'].get('retrieval_tags', [])}")

    logger.info("\n=== INGESTION LAYER VERIFICATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(run_verification())
