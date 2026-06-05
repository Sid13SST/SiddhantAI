import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.models.document import IngestedDocument, SourceType

class DocumentFactory:
    @staticmethod
    def create_resume_document(text: str, page_number: int, total_pages: int, source_path: str) -> IngestedDocument:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        doc_id = f"resume_p{page_number}_{content_hash}"
        metadata = {
            "source_type": SourceType.RESUME.value,
            "source_url": f"file:///{source_path.replace('\\', '/')}",
            "page_number": page_number,
            "total_pages": total_pages,
            "source_path": source_path,
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "retrieval_tags": []
        }
        return IngestedDocument(id=doc_id, content=text, metadata=metadata)

    @staticmethod
    def create_github_repo_document(
        repo_name: str, 
        owner: str, 
        stars: int, 
        language: Optional[str], 
        description: Optional[str], 
        topics: List[str]
    ) -> IngestedDocument:
        content = f"Repository: {repo_name}\nDescription: {description or 'No description provided.'}\nLanguage: {language or 'Not specified'}\nStars: {stars}\nTopics: {', '.join(topics) if topics else 'None'}"
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        doc_id = f"gh_repo_{owner}_{repo_name}_{content_hash}"
        metadata = {
            "source_type": SourceType.GITHUB_REPO_METADATA.value,
            "source_url": f"https://github.com/{owner}/{repo_name}",
            "repo_name": repo_name,
            "owner": owner,
            "stars": stars,
            "language": language,
            "description": description,
            "topics": topics,
            "retrieval_tags": topics.copy() if topics else []
        }
        return IngestedDocument(id=doc_id, content=content, metadata=metadata)

    @staticmethod
    def create_github_readme_document(
        repo_name: str, 
        owner: str, 
        readme_text: str, 
        branch: str = "main"
    ) -> IngestedDocument:
        content_hash = hashlib.sha256(readme_text.encode("utf-8")).hexdigest()[:12]
        doc_id = f"gh_readme_{owner}_{repo_name}_{content_hash}"
        metadata = {
            "source_type": SourceType.GITHUB_README.value,
            "source_url": f"https://github.com/{owner}/{repo_name}/blob/{branch}/README.md",
            "repo_name": repo_name,
            "owner": owner,
            "file_path": "README.md",
            "branch": branch,
            "retrieval_tags": ["readme", "documentation", repo_name.lower()]
        }
        return IngestedDocument(id=doc_id, content=readme_text, metadata=metadata)

    @staticmethod
    def create_github_commit_document(
        repo_name: str,
        owner: str,
        commit_sha: str,
        message: str,
        author: str,
        commit_date: str,
        changed_files: List[str]
    ) -> IngestedDocument:
        # Create a rich text description of the commit for indexing
        files_str = "\n".join(f"- {f}" for f in changed_files) if changed_files else "None"
        content = (
            f"Repository: {repo_name}\n"
            f"Commit: {commit_sha[:8]}\n"
            f"Author: {author}\n"
            f"Date: {commit_date}\n"
            f"Message: {message}\n"
            f"Files Changed:\n{files_str}"
        )
        doc_id = f"gh_commit_{repo_name}_{commit_sha[:12]}"
        metadata = {
            "source_type": SourceType.GITHUB_COMMIT.value,
            "source_url": f"https://github.com/{owner}/{repo_name}/commit/{commit_sha}",
            "repo_name": repo_name,
            "owner": owner,
            "commit_sha": commit_sha,
            "author": author,
            "commit_date": commit_date,
            "changed_files": changed_files,
            "retrieval_tags": ["commit", "git", repo_name.lower()]
        }
        return IngestedDocument(id=doc_id, content=content, metadata=metadata)

    @staticmethod
    def create_github_code_document(
        repo_name: str,
        owner: str,
        file_path: str,
        content: str,
        language: str,
        branch: str = "main"
    ) -> IngestedDocument:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        doc_id = f"gh_code_{repo_name}_{content_hash}"
        metadata = {
            "source_type": SourceType.GITHUB_CODE.value,
            "source_url": f"https://github.com/{owner}/{repo_name}/blob/{branch}/{file_path}",
            "repo_name": repo_name,
            "owner": owner,
            "file_path": file_path,
            "branch": branch,
            "language": language,
            "retrieval_tags": ["code", language.lower(), repo_name.lower()]
        }
        return IngestedDocument(id=doc_id, content=content, metadata=metadata)
