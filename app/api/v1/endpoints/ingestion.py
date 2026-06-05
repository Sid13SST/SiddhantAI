import os
from pathlib import Path
from typing import Optional
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from app.services.pipeline import IngestionPipeline, INGESTION_STATUS
from app.core.config import settings
from app.core.logging import logger

router = APIRouter()
pipeline = IngestionPipeline()

class GitHubIngestRequest(BaseModel):
    github_pat: Optional[str] = None
    username: Optional[str] = None

class FullIngestRequest(BaseModel):
    github_pat: Optional[str] = None
    username: Optional[str] = None

def run_ingestion_in_background(resume_path: Optional[str], github_pat: Optional[str], username: Optional[str] = None):
    # Setup username environment if provided override
    orig_username = settings.GITHUB_USERNAME
    if username:
        settings.GITHUB_USERNAME = username
    
    # We run the pipeline synchronously in this background thread context
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(pipeline.run_full_ingestion(resume_path, github_pat))
    except Exception as e:
        logger.error(f"Background ingestion job failed: {e}")
    finally:
        settings.GITHUB_USERNAME = orig_username

@router.post("/resume")
async def ingest_resume(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads a Resume PDF file and triggers background text parsing, chunking, and embedding."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are supported.")
        
    try:
        # Save file locally inside raw data directory
        save_path = settings.raw_data_dir / f"uploaded_{file.filename}"
        with open(save_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        logger.info(f"Resume saved locally at: {save_path}. Starting ingestion in background...")
        
        background_tasks.add_task(
            run_ingestion_in_background,
            resume_path=str(save_path),
            github_pat=None,
            username=None
        )
        
        return {
            "message": "Resume uploaded successfully. Ingestion job started in background.",
            "file_path": str(save_path),
            "status_endpoint": "/api/v1/ingest/status"
        }
    except Exception as e:
        logger.error(f"Failed to ingest resume: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest resume: {str(e)}")

@router.post("/github")
async def ingest_github(background_tasks: BackgroundTasks, request: Optional[GitHubIngestRequest] = None):
    """Triggers GitHub repository, README, commit, and code file scraping in the background."""
    pat = request.github_pat if request else None
    user = request.username if request else None
    
    # Validate token availability
    target_pat = pat or settings.GITHUB_PAT
    if not target_pat:
        raise HTTPException(
            status_code=400, 
            detail="GitHub PAT token must be provided in request body or set in backend .env file."
        )
        
    background_tasks.add_task(
        run_ingestion_in_background,
        resume_path=None,
        github_pat=target_pat,
        username=user
    )
    
    return {
        "message": "GitHub ingestion job queued in the background.",
        "status_endpoint": "/api/v1/ingest/status"
    }

@router.post("/full")
async def ingest_full(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    github_pat: Optional[str] = Form(None),
    username: Optional[str] = Form(None)
):
    """Accepts Resume PDF file and GitHub PAT via multipart Form data, running the full pipeline in the background."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are supported.")
        
    target_pat = github_pat or settings.GITHUB_PAT
    if not target_pat:
        raise HTTPException(
            status_code=400, 
            detail="GitHub PAT token must be provided in form data or set in backend .env file."
        )
        
    try:
        # Save resume PDF
        save_path = settings.raw_data_dir / f"uploaded_{file.filename}"
        with open(save_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        logger.info(f"Resume saved. Starting full background pipeline (Resume + GitHub)...")
        
        background_tasks.add_task(
            run_ingestion_in_background,
            resume_path=str(save_path),
            github_pat=target_pat,
            username=username
        )
        
        return {
            "message": "Full ingestion request received. Processing in background.",
            "resume_path": str(save_path),
            "status_endpoint": "/api/v1/ingest/status"
        }
    except Exception as e:
        logger.error(f"Failed to trigger full ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate full ingestion: {str(e)}")

@router.get("/status")
async def get_status():
    """Returns the execution state and ingestion metrics of the pipeline."""
    return INGESTION_STATUS
