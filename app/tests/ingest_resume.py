import sys
import asyncio
from app.services.pipeline import IngestionPipeline
from app.core.config import settings

async def main():
    if len(sys.argv) < 2:
        print("Usage: .venv\\Scripts\\python.exe app/tests/ingest_resume.py <path_to_resume_pdf>")
        return
    resume_path = sys.argv[1]
    print(f"Starting ingestion for: {resume_path}...")
    pipeline = IngestionPipeline()
    await pipeline.run_full_ingestion(resume_path=resume_path, github_pat=None)
    print("Ingestion completed and FAISS vector database updated successfully!")

if __name__ == "__main__":
    asyncio.run(main())
