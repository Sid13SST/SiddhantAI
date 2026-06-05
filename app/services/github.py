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

    async def ingest_all_repositories(self) -> list:
        return []
