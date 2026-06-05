import asyncio
import os
from datetime import datetime
from pathlib import Path
from app.models.document import IngestedDocument, SourceType
from app.services.factory import DocumentFactory
from app.services.chunker import ChunkingService
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.profile import PersonaBuilderService
from app.core.config import settings
from app.core.logging import logger

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
- Developed Gradonix, a stateful calendar orchestrator that connects directly to Google Calendar and automates slots booking.
"""

MOCK_README_TEXT = """
# FrictaAI & Gradonix Calendar Orchestrator

Gradonix is a system developed by Siddhant to automate interview scheduling. It is a multi-agent calendar tool that interfaces directly with Google Calendar API to rank, book, and prevent double bookings using locks.

## Technologies Used
- Backend: FastAPI, Python 3.12+
- Fronted: Next.js 15, TypeScript, Tailwind CSS
- Embedding: sentence-transformers/all-MiniLM-L6-v2
- Database: FAISS vector database & mock cache
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

async def run_population():
    db_path = settings.vector_db_dir
    db_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Populating vector DB at: {db_path}")

    # 1. Document Creation & Normalization
    resume_doc = DocumentFactory.create_resume_document(
        text=MOCK_RESUME_TEXT,
        page_number=1,
        total_pages=1,
        source_path=str(db_path / "resume.pdf")
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

    # 2. Chunking & Tagging
    all_chunks = []
    for doc in documents:
        chunks = ChunkingService.chunk_document(doc)
        all_chunks.extend(chunks)
        
    logger.info(f"Total chunks generated: {len(all_chunks)}")

    # 3. Embeddings & Storage
    embedding_service = EmbeddingService()
    chunk_texts = [c.text for c in all_chunks]
    
    logger.info("Generating embeddings (this may take a few seconds)...")
    embeddings = embedding_service.generate_embeddings(chunk_texts)
    
    store = VectorStoreService(db_dir=db_path)
    store.init_new_index()
    store.add_chunks(all_chunks, embeddings)
    store.save()
    
    logger.info("Vector DB successfully populated and saved to disk.")

    # 4. Synthesize Persona Profile
    logger.info("Synthesizing persona profile...")
    profile = await PersonaBuilderService.build_persona_profile(documents)
    
    # Save profile manually to make sure it exists
    import json
    profile_path = db_path / "persona_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Persona profile updated at {profile_path}")

if __name__ == "__main__":
    asyncio.run(run_population())
