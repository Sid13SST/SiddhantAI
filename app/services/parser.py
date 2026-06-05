import hashlib
from datetime import datetime
from pathlib import Path
from typing import List
# pyrefly: ignore [missing-import]
from pypdf import PdfReader
from app.models.document import IngestedDocument, SourceType, ResumeMetadata
from app.core.logging import logger

class ResumeParserService:
    @staticmethod
    def parse_resume(file_path: str) -> List[IngestedDocument]:
        logger.info(f"Parsing resume PDF at path: {file_path}")
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume file not found at: {file_path}")

        reader = PdfReader(path)
        total_pages = len(reader.pages)
        documents = []

        for idx, page in enumerate(reader.pages):
            page_number = idx + 1
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue

            # Create stable deterministic ID
            content_hash = hashlib.sha256(f"resume_{page_number}_{text[:200]}".encode("utf-8")).hexdigest()
            doc_id = f"resume_p{page_number}_{content_hash[:12]}"

            # Generate metadata conforming to ResumeMetadata schema
            metadata = ResumeMetadata(
                source_type=SourceType.RESUME,
                page_number=page_number,
                total_pages=total_pages,
                source_path=str(path.absolute()),
                source_url=f"file:///{path.absolute().as_posix()}",
                extraction_timestamp=datetime.utcnow()
            )

            documents.append(IngestedDocument(
                id=doc_id,
                content=text,
                metadata=metadata.model_dump()
            ))

        logger.info(f"Successfully extracted {len(documents)} document pages from resume PDF.")
        return documents
