import base64
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
import httpx
from app.models.document import IngestedDocument
from app.services.factory import DocumentFactory
from app.core.logging import logger
from app.core.config import settings

class GitHubIngestionService:
    def __init__(self, pat: str = None, username: str = None):
        self.pat = pat or settings.GITHUB_PAT
        self.username = username or settings.GITHUB_USERNAME
        if not self.pat:
            logger.warning("GitHub Personal Access Token (PAT) not set. Authenticated requests will fail.")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.pat:
            self.headers["Authorization"] = f"Bearer {self.pat}"
        self.client = httpx.AsyncClient(headers=self.headers, timeout=20.0)

    async def close(self):
        await self.client.close()

    async def fetch_repositories(self) -> List[Dict[str, Any]]:
        logger.info("Fetching repositories from GitHub...")
        url = "https://api.github.com/user/repos"
        params = {"type": "owner", "per_page": 100}
        
        try:
            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.error(f"Failed to fetch repositories: {response.status_code} - {response.text}")
                return []
            repos = response.json()
            logger.info(f"Found {len(repos)} repositories.")
            return repos
        except Exception as e:
            logger.error(f"Error fetching repositories: {e}")
            return []

    async def fetch_readme(self, owner: str, repo: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()
                content_base64 = data.get("content", "")
                if content_base64:
                    readme_text = base64.b64decode(content_base64).decode("utf-8", errors="ignore")
                    return readme_text
            elif response.status_code == 404:
                logger.info(f"No README found for {owner}/{repo}")
            else:
                logger.warning(f"Failed to fetch README for {owner}/{repo}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching README for {owner}/{repo}: {e}")
        return None

    async def fetch_commits(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching commits for {owner}/{repo}...")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"author": self.username, "per_page": 15}
        try:
            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch commits for {owner}/{repo}: {response.status_code}")
                return []
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching commits for {owner}/{repo}: {e}")
            return []

    async def fetch_commit_details(self, owner: str, repo: str, sha: str) -> List[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()
                files = data.get("files", [])
                return [f.get("filename", "") for f in files if f.get("filename")]
            else:
                logger.warning(f"Failed to fetch commit details for {sha}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching commit details for {sha}: {e}")
        return []

    async def fetch_code_files(self, owner: str, repo: str, branch: str, max_files: int = 30) -> List[Dict[str, str]]:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
        params = {"recursive": "1"}
        try:
            response = await self.client.get(url, params=params)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch tree for branch {branch} in {owner}/{repo}: {response.status_code}.")
                return []
            
            tree_data = response.json()
            tree = tree_data.get("tree", [])
            
            code_files = []
            allowed_extensions = {".py", ".ts", ".tsx", ".js", ".jsx"}
            allowed_dirs = {"src/", "app/", "backend/"}
            ignored_dirs = {"node_modules/", "dist/", "build/", ".next/", "coverage/"}
            
            for item in tree:
                if item.get("type") == "blob":
                    path = item.get("path", "")
                    
                    ext = Path(path).suffix
                    if ext not in allowed_extensions:
                        continue
                        
                    in_target_dir = any(path.startswith(d) or f"/{d}" in path for d in allowed_dirs)
                    if not in_target_dir:
                        continue
                        
                    in_ignored_dir = any(ignored in path for ignored in ignored_dirs)
                    if in_ignored_dir:
                        continue
                        
                    code_files.append({
                        "path": path,
                        "extension": ext
                    })
                    
                    if len(code_files) >= max_files:
                        logger.info(f"Capping code files for {owner}/{repo} at {max_files}")
                        break
            
            return code_files
        except Exception as e:
            logger.error(f"Error fetching Git tree for {owner}/{repo}: {e}")
            return []

    async def fetch_file_content(self, owner: str, repo: str, file_path: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                data = response.json()
                content_base64 = data.get("content", "")
                if content_base64:
                    clean_b64 = content_base64.replace("\n", "").replace("\r", "")
                    file_text = base64.b64decode(clean_b64).decode("utf-8", errors="ignore")
                    return file_text
            else:
                logger.warning(f"Failed to fetch content for {file_path} in {owner}/{repo}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching content for {file_path} in {owner}/{repo}: {e}")
        return None

    async def ingest_repository_data(self, repo_info: Dict[str, Any]) -> List[IngestedDocument]:
        owner = repo_info["owner"]["login"]
        repo_name = repo_info["name"]
        default_branch = repo_info.get("default_branch", "main")
        stars = repo_info.get("stargazers_count", 0)
        language = repo_info.get("language")
        description = repo_info.get("description")
        topics = repo_info.get("topics", [])
        
        logger.info(f"=== Processing Repository: {owner}/{repo_name} ===")
        documents = []

        repo_doc = DocumentFactory.create_github_repo_document(
            repo_name=repo_name,
            owner=owner,
            stars=stars,
            language=language,
            description=description,
            topics=topics
        )
        documents.append(repo_doc)

        readme_text = await self.fetch_readme(owner, repo_name)
        if readme_text:
            readme_doc = DocumentFactory.create_github_readme_document(
                repo_name=repo_name,
                owner=owner,
                readme_text=readme_text,
                branch=default_branch
            )
            documents.append(readme_doc)

        commits = await self.fetch_commits(owner, repo_name)
        for commit_obj in commits:
            sha = commit_obj.get("sha", "")
            commit_info = commit_obj.get("commit", {})
            message = commit_info.get("message", "No message")
            author_info = commit_info.get("author", {})
            author_name = author_info.get("name", self.username)
            commit_date = author_info.get("date", datetime.utcnow().isoformat())
            
            changed_files = await self.fetch_commit_details(owner, repo_name, sha)
            
            commit_doc = DocumentFactory.create_github_commit_document(
                repo_name=repo_name,
                owner=owner,
                commit_sha=sha,
                message=message,
                author=author_name,
                commit_date=commit_date,
                changed_files=changed_files
            )
            documents.append(commit_doc)

        code_file_indices = await self.fetch_code_files(owner, repo_name, default_branch)
        for cf in code_file_indices:
            file_path = cf["path"]
            ext = cf["extension"]
            
            lang_map = {
                ".py": "Python",
                ".ts": "TypeScript",
                ".tsx": "TSX",
                ".js": "JavaScript",
                ".jsx": "JSX"
            }
            language_name = lang_map.get(ext, "Code")
            
            file_content = await self.fetch_file_content(owner, repo_name, file_path)
            if file_content and file_content.strip():
                if len(file_content) > 100000:
                    logger.warning(f"File {file_path} too large ({len(file_content)} chars), skipping.")
                    continue
                code_doc = DocumentFactory.create_github_code_document(
                    repo_name=repo_name,
                    owner=owner,
                    file_path=file_path,
                    content=file_content,
                    language=language_name,
                    branch=default_branch
                )
                documents.append(code_doc)
                await asyncio.sleep(0.1)

        logger.info(f"Ingested {len(documents)} documents from repository: {owner}/{repo_name}")
        return documents

    async def ingest_all_repositories(self) -> List[IngestedDocument]:
        all_documents = []
        repos = await self.fetch_repositories()
        if not repos:
            logger.warning("No repositories found or failed to authenticate.")
            return []

        for repo in repos:
            try:
                repo_docs = await self.ingest_repository_data(repo)
                all_documents.extend(repo_docs)
            except Exception as e:
                logger.error(f"Error ingesting repository {repo.get('name')}: {e}")
        
        return all_documents
