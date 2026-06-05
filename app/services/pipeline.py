import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.document import IngestedDocument, DocumentChunk
from app.services.parser import ResumeParserService
from app.services.github import GitHubIngestionService
from app.services.chunker import ChunkingService
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.profile import PersonaBuilderService
from app.core.config import settings
from app.core.logging import logger

# In-memory status tracker for the ingestion pipeline
INGESTION_STATUS = {
    "status": "idle",  # idle, running, completed, failed
    "last_run": None,
    "error": None,
    "metrics": {
        "resume_documents": 0,
        "github_documents": 0,
        "total_documents": 0,
        "total_chunks": 0,
        "execution_time_seconds": 0
    }
}

class IngestionPipeline:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    async def run_full_ingestion(self, resume_path: Optional[str] = None, github_pat: Optional[str] = None) -> Dict[str, Any]:
        global INGESTION_STATUS
        
        # Resolve GITHUB_PAT if not provided
        if not github_pat and settings.GITHUB_PAT:
            github_pat = settings.GITHUB_PAT
            logger.info("Using GITHUB_PAT from settings/env configurations.")

        # Resolve resume_path if not provided
        if not resume_path:
            potential_paths = [
                Path("resume.pdf"),
                settings.raw_data_dir / "resume.pdf",
            ]
            if settings.raw_data_dir.exists():
                for f in settings.raw_data_dir.glob("*.pdf"):
                    potential_paths.append(f)
            
            for p in potential_paths:
                if p.exists():
                    resume_path = str(p.absolute())
                    logger.info(f"Automatically detected resume PDF at: {resume_path}")
                    break
        
        start_time = time.time()
        INGESTION_STATUS["status"] = "running"
        INGESTION_STATUS["error"] = None
        INGESTION_STATUS["last_run"] = datetime.utcnow().isoformat()
        
        logger.info("Starting full ingestion pipeline...")
        all_documents: List[IngestedDocument] = []
        resume_count = 0
        github_count = 0
        
        try:
            # 1. Resume Ingestion
            if resume_path:
                try:
                    resume_docs = ResumeParserService.parse_resume(resume_path)
                    all_documents.extend(resume_docs)
                    resume_count = len(resume_docs)
                except Exception as e:
                    logger.error(f"Error parsing resume during full ingestion: {e}")
                    # Raise if resume path is specified but parsing failed
                    raise e
                    
            # 2. GitHub Ingestion (Repos, READMEs, Commits, Code)
            if github_pat:
                gh_service = GitHubIngestionService(pat=github_pat)
                try:
                    gh_docs = await gh_service.ingest_all_repositories()
                    all_documents.extend(gh_docs)
                    github_count = len(gh_docs)
                finally:
                    await gh_service.close()

            total_docs = len(all_documents)
            if total_docs == 0:
                raise ValueError("No documents were ingested. Ensure at least a resume path or GitHub token is supplied.")

            logger.info(f"Ingested {total_docs} total documents. (Resume: {resume_count}, GitHub: {github_count})")

            # 3. Chunking & Tagging
            logger.info("Chunking and tagging documents...")
            all_chunks: List[DocumentChunk] = []
            for doc in all_documents:
                doc_chunks = ChunkingService.chunk_document(doc)
                all_chunks.extend(doc_chunks)
                
            total_chunks = len(all_chunks)
            logger.info(f"Generated {total_chunks} total chunks from {total_docs} documents.")

            # 4. Generate Embeddings
            chunk_texts = [chunk.text for chunk in all_chunks]
            embeddings = self.embedding_service.generate_embeddings(chunk_texts)

            # 5. Vector Indexing & Persistence
            self.vector_store.init_new_index()
            self.vector_store.add_chunks(all_chunks, embeddings)
            self.vector_store.save()

            # 6. Generate Persona Profile
            await PersonaBuilderService.build_persona_profile(all_documents)

            execution_time = time.time() - start_time
            
            # Update metrics
            INGESTION_STATUS["status"] = "completed"
            INGESTION_STATUS["metrics"] = {
                "resume_documents": resume_count,
                "github_documents": github_count,
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "execution_time_seconds": round(execution_time, 2)
            }
            logger.info(f"Ingestion pipeline completed successfully in {execution_time:.2f} seconds.")
            return INGESTION_STATUS
            
        except Exception as e:
            execution_time = time.time() - start_time
            INGESTION_STATUS["status"] = "failed"
            INGESTION_STATUS["error"] = str(e)
            INGESTION_STATUS["metrics"]["execution_time_seconds"] = round(execution_time, 2)
            logger.error(f"Ingestion pipeline failed: {e}")
            raise e
