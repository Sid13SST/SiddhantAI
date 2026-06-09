import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import json

from app.models.document import IngestedDocument, SourceType
from app.services.factory import DocumentFactory
from app.services.chunker import ChunkingService
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.services.profile import PersonaBuilderService
from app.services.parser import ResumeParserService
from app.core.config import settings
from app.core.logging import logger

# --- Real Fallback Data (in case local paths are missing during remote runs) ---

FALLBACK_RESUME = """SIDDHANT PRASAD
(+91)9310079833 | siddhant.prasad8@gmail.com | Portfolio: https://siddhant-prasad.vercel.app/

EDUCATION
Scaler School of Technology (August 2024 - Present)
Birla Institute of Technology Pilani - Bachelor in Science, Computer Science and Engineering (August 2024 - Present)
Amity International School Vasundhara, Ghaziabad (Class XII CBSE: 90.90%, Class X CBSE: 96.60%)

PROJECTS

Gradonix – AI-Powered Subjective Hand-written Evaluation Platform (GitHub: grado_next)
Developed a full-stack AI-based examination system with React, Node.js, and PostgreSQL for automated answer evaluation. Planned AI workflows and implemented role-based authentication, test creation, submission workflows, and result publishing. (https://www.gradonix.com)

Claribot - An AI-powered, RAG-driven Support Widget with Actionable Analytics
ClariBot is an embeddable AI widget that provides hallucination-free, cited answers by using RAG strictly against a project's uploaded documentation. It is built with a Node.js/Hono backend, uses PostgreSQL with pgvector for fast similarity searching, and relies on Google's Gemini API for generating embeddings and context-aware responses. It also features an automated analytics engine to track user frustration and cluster repeated queries.

Attendance Management System using SpringBoot
Developed a RESTful Attendance Management System using Spring Boot and Spring Data JPA with role-based access for teachers and students. Designed advanced features and normalized database schema with unique constraints and optimized queries for attendance tracking. (https://attendance-system-nine-mu.vercel.app/)

TECHNICAL STRENGTHS
Languages: Python, Java, Javascript, C++, Go
Data Analysis: NumPy, Pandas, Matplotlib, Seaborn
Databases: MongoDB, PostgreSQL
Web Technologies: HTML, Tailwind CSS, SpringBoot, React.js, Express.js
Developer Tools: Git, Github, PostMan, Vercel, Render
"""

FALLBACK_CLARIBOT_README = """# 🧠 ClariBot - Embeddable AI Support Widget & Insights Engine
Standard chatbots are commodities. ClariBot is different. It doesn't just answer questions via RAG; it actively monitors conversations to cluster user intent, detect frustration, and identify content gaps, turning customer support chats into actionable product roadmaps.

## Features
- **🚀 Embeddable Widget**: Lightweight React widget encapsulated in a Shadow DOM for style isolation.
- **📚 Smart RAG Engine**: Uses sentence-aware chunking and pgvector for retrieval.
- **🔍 Insights Engine**: Clusters user queries, detects frustration, and highlights knowledge gaps.
- **⚡ Tech Stack**: Hono.js on Node.js, PostgreSQL (`pgvector`), Redis (BullMQ) for async tasks, Google Gemini API.
"""

FALLBACK_FRICTAAI_README = """# 🚀 Fricta AI — AI-Native Autonomous UX Intelligence Platform
Fricta is an AI-native autonomous user experience (UX) testing and simulation platform. It emulates realistic user personas and journeys on target websites to uncover usability friction, visual overlapping, layout defects, cognitive barriers, and onboarding leaks.

## Workspace Breakdown
- **apps/frontend**: Premium dark-mode dashboard built with React, Vite, TypeScript, and Tailwind CSS.
- **apps/backend**: Modular Hono.js REST server handling agent workflows and analytics.
- **packages/report-engine**: Centralized orchestrator compiling scores and executive summaries.
- **packages/ux-intelligence**: Evaluates cognitive fatigue and persona drop-off risk.
"""

FALLBACK_GRADONIX_README = """# GradoAI / Gradonix
## AI-Powered Educational Management Platform — Transforming Learning Through Intelligence

GradoAI (GitHub: grado_next) is a comprehensive educational management platform leveraging AI to enhance teaching, learning, and administrative processes (answer extraction, OCR evaluation, student performance monitoring).

## Tech Stack
- **Framework**: Next.js 15, React 19, TypeScript
- **Auth**: Clerk
- **Database**: MongoDB/Mongoose, Upstash Redis & QStash
- **AI/LLM**: Claude AI (Anthropic SDK) & Google Cloud Vision / Gemini
- **Styling**: Tailwind CSS v4, Shadcn-ui, Zustand
"""

async def run_population():
    db_path = settings.vector_db_dir
    db_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Populating vector DB at: {db_path}")

    documents = []

    # 1. Resume Ingestion
    resume_pdf_path = Path(r"C:\Users\Siddhant\Downloads\Resume_SiddhantPrasad_Final.pdf")
    resume_txt_path = Path("app/tests/parsed_resume.txt")
    
    if resume_pdf_path.exists():
        logger.info(f"Loading resume from PDF: {resume_pdf_path}")
        resume_docs = ResumeParserService.parse_resume(str(resume_pdf_path))
        documents.extend(resume_docs)
    elif resume_txt_path.exists():
        logger.info(f"Loading resume from parsed text: {resume_txt_path}")
        with open(resume_txt_path, "r", encoding="utf-8") as f:
            resume_text = f.read()
        doc = DocumentFactory.create_resume_document(
            text=resume_text,
            page_number=1,
            total_pages=1,
            source_path=str(resume_txt_path)
        )
        documents.append(doc)
    else:
        logger.info("Using fallback resume text.")
        doc = DocumentFactory.create_resume_document(
            text=FALLBACK_RESUME,
            page_number=1,
            total_pages=1,
            source_path="resume.txt"
        )
        documents.append(doc)

    # 2. Project READMEs & Metadata
    projects = [
        {
            "name": "ClariBot",
            "owner": "Sid13SST",
            "stars": 12,
            "language": "TypeScript",
            "description": "An AI-powered, RAG-driven Support Widget with Actionable Analytics and query clustering.",
            "topics": ["hono", "pgvector", "gemini-api", "rag", "redis"],
            "readme_path": Path(r"C:\Users\Siddhant\OneDrive\Desktop\ClariBot\README.md"),
            "fallback_readme": FALLBACK_CLARIBOT_README,
            "code_path": Path(r"C:\Users\Siddhant\OneDrive\Desktop\ClariBot\packages\rag-core\src\embeddings\embedding-generator.ts"),
            "fallback_code": "// Gemini Embedding integration\nasync function embedWithGemini(text, apiKey) { ... }",
            "code_file_name": "packages/rag-core/src/embeddings/embedding-generator.ts"
        },
        {
            "name": "FrictaAI",
            "owner": "Sid13SST",
            "stars": 8,
            "language": "TypeScript",
            "description": "AI-Native Autonomous UX Intelligence Platform emulating user personas to detect cognitive fatigue and design flaws.",
            "topics": ["hono", "turborepo", "react", "prisma", "postgresql", "ux-testing"],
            "readme_path": Path(r"C:\Users\Siddhant\OneDrive\Desktop\FrictaAI\README.md"),
            "fallback_readme": FALLBACK_FRICTAAI_README,
            "code_path": Path(r"C:\Users\Siddhant\OneDrive\Desktop\FrictaAI\packages\report-engine\src\timeline.ts"),
            "fallback_code": "export class TimelineCompiler { static compile(actions, thoughts, uxFindings, ...) { ... } }",
            "code_file_name": "packages/report-engine/src/timeline.ts"
        },
        {
            "name": "grado_next",
            "owner": "Sid13SST",
            "stars": 15,
            "language": "TypeScript",
            "description": "Gradonix - AI-Powered Subjective Hand-written Evaluation Platform that automates OCR answer extraction and grading.",
            "topics": ["nextjs", "clerk", "mongodb", "anthropic-sdk", "claude-ai", "ocr"],
            "readme_path": Path(r"C:\Users\Siddhant\OneDrive\Desktop\Gradonix_Main\grado_next\README.md"),
            "fallback_readme": FALLBACK_GRADONIX_README,
            "code_path": Path(r"C:\Users\Siddhant\OneDrive\Desktop\Gradonix_Main\grado_next\src\lib\processing\student-answer-extraction-service.ts"),
            "fallback_code": "class GeminiExtractionProvider implements AnswerExtractionProviderInterface { ... }",
            "code_file_name": "src/lib/processing/student-answer-extraction-service.ts"
        },
        {
            "name": "AttendanceManagementSystem",
            "owner": "Sid13SST",
            "stars": 5,
            "language": "Java",
            "description": "RESTful Attendance Management System with role-based access for teachers and students.",
            "topics": ["springboot", "spring-data-jpa", "postgresql", "java", "attendance-tracking"],
            "readme_path": None,
            "fallback_readme": "RESTful Attendance Management System using Spring Boot, JPA, and PostgreSQL.",
            "code_path": None,
            "fallback_code": "@RestController\n@RequestMapping(\"/api/attendance\")\npublic class AttendanceController { ... }",
            "code_file_name": "src/main/java/com/scaler/attendance/controller/AttendanceController.java"
        }
    ]

    for p in projects:
        # Repo Document
        repo_doc = DocumentFactory.create_github_repo_document(
            repo_name=p["name"],
            owner=p["owner"],
            stars=p["stars"],
            language=p["language"],
            description=p["description"],
            topics=p["topics"]
        )
        documents.append(repo_doc)

        # Readme Document
        readme_content = p["fallback_readme"]
        if p["readme_path"] and p["readme_path"].exists():
            try:
                with open(p["readme_path"], "r", encoding="utf-8") as f:
                    readme_content = f.read()
                logger.info(f"Loaded readme for {p['name']} from {p['readme_path']}")
            except Exception as e:
                logger.warning(f"Failed to read readme for {p['name']}: {e}")
        
        readme_doc = DocumentFactory.create_github_readme_document(
            repo_name=p["name"],
            owner=p["owner"],
            readme_text=readme_content
        )
        documents.append(readme_doc)

        # Code Document
        code_content = p["fallback_code"]
        if p["code_path"] and p["code_path"].exists():
            try:
                with open(p["code_path"], "r", encoding="utf-8") as f:
                    code_content = f.read()
                logger.info(f"Loaded code for {p['name']} from {p['code_path']}")
            except Exception as e:
                logger.warning(f"Failed to read code for {p['name']}: {e}")

        code_doc = DocumentFactory.create_github_code_document(
            repo_name=p["name"],
            owner=p["owner"],
            file_path=p["code_file_name"],
            content=code_content,
            language=p["language"]
        )
        documents.append(code_doc)

        # Commit Document (Mocking a real commits representing features)
        commit_doc = DocumentFactory.create_github_commit_document(
            repo_name=p["name"],
            owner=p["owner"],
            commit_sha="b8f9a2e3d4c5",
            message=f"Hardened production features and optimization pipelines for {p['name']}",
            author="Siddhant Prasad",
            commit_date=datetime.utcnow().isoformat(),
            changed_files=[p["code_file_name"]]
        )
        documents.append(commit_doc)

    # 3. Chunking & Tagging
    all_chunks = []
    for doc in documents:
        chunks = ChunkingService.chunk_document(doc)
        all_chunks.extend(chunks)
        
    logger.info(f"Total chunks generated: {len(all_chunks)}")

    # 4. Embeddings & Storage
    embedding_service = EmbeddingService()
    chunk_texts = [c.text for c in all_chunks]
    
    logger.info("Generating embeddings (this may take a few seconds)...")
    embeddings = embedding_service.generate_embeddings(chunk_texts)
    
    store = VectorStoreService(db_dir=db_path)
    store.init_new_index()
    store.add_chunks(all_chunks, embeddings)
    store.save()
    
    logger.info("Vector DB successfully populated and saved to disk.")

    # 5. Synthesize Persona Profile
    logger.info("Synthesizing persona profile...")
    profile = await PersonaBuilderService.build_persona_profile(documents)
    
    # Save profile manually to make sure it exists
    profile_path = db_path / "persona_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Persona profile updated at {profile_path}")

if __name__ == "__main__":
    asyncio.run(run_population())
