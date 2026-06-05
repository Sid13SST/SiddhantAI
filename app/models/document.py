from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class SourceType(str, Enum):
    RESUME = "resume"
    GITHUB_REPO_METADATA = "github_repo_metadata"
    GITHUB_README = "github_readme"
    GITHUB_COMMIT = "github_commit"
    GITHUB_CODE = "github_code"

class BaseMetadata(BaseModel):
    source_type: SourceType
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    retrieval_tags: List[str] = Field(default_factory=list)

class ResumeMetadata(BaseMetadata):
    source_type: SourceType = SourceType.RESUME
    page_number: int
    total_pages: int
    source_path: str
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)

class GitHubRepoMetadata(BaseMetadata):
    source_type: SourceType = SourceType.GITHUB_REPO_METADATA
    repo_name: str
    owner: str
    stars: int
    language: Optional[str] = None
    description: Optional[str] = None

class GitHubReadmeMetadata(BaseMetadata):
    source_type: SourceType = SourceType.GITHUB_README
    repo_name: str
    owner: str
    file_path: str = "README.md"
    branch: str = "main"

class GitHubCommitMetadata(BaseMetadata):
    source_type: SourceType = SourceType.GITHUB_COMMIT
    repo_name: str
    owner: str
    commit_sha: str
    author: str
    commit_date: datetime
    changed_files: List[str]

class GitHubCodeMetadata(BaseMetadata):
    source_type: SourceType = SourceType.GITHUB_CODE
    repo_name: str
    owner: str
    file_path: str
    branch: str = "main"
    language: str

class IngestedDocument(BaseModel):
    id: str = Field(description="Unique content-derived or path-derived hash ID")
    content: str = Field(description="Raw text content of the document")
    metadata: Dict[str, Any] = Field(description="Unified metadata dict conforming to SourceType schemas")

class DocumentChunk(BaseModel):
    id: str = Field(description="Unique hash of parent ID + chunk index")
    parent_id: str = Field(description="ID of the parent document")
    text: str = Field(description="Text segment of this chunk")
    chunk_index: int = Field(description="Positional index of chunk within parent document")
    metadata: Dict[str, Any] = Field(description="Merged parent metadata + chunk attributes (includes retrieval_tags)")

class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float = Field(description="FAISS L2/IP search distance score")
    metadata: Dict[str, Any]

# Persona Profile Model
class ProjectSummary(BaseModel):
    name: str
    description: str
    technologies: List[str]
    repo_url: Optional[str] = None

class PersonaProfile(BaseModel):
    name: str = "Siddhant"
    education: List[str] = Field(default_factory=list)
    core_skills: List[str] = Field(default_factory=list, description="Primary programming languages, frameworks, tools")
    top_projects: List[ProjectSummary] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    repository_summary: Dict[str, str] = Field(default_factory=dict, description="Summary description of each repository")
