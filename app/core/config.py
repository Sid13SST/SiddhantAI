import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    GITHUB_PAT: str = ""
    GITHUB_USERNAME: str = "Siddhant"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"
    DATA_DIR: str = "data"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    @property
    def vector_db_dir(self) -> Path:
        directory = Path(self.DATA_DIR) / "vector_db"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @property
    def raw_data_dir(self) -> Path:
        directory = Path(self.DATA_DIR) / "raw"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

settings = Settings()
