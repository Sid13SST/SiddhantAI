import json
from pathlib import Path
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
import faiss
from typing import List, Dict, Any, Tuple
from app.models.document import DocumentChunk
from app.core.config import settings
from app.core.logging import logger

class VectorStoreService:
    def __init__(self, db_dir: Path = None):
        self.db_dir = db_dir or settings.vector_db_dir
        self.index_path = self.db_dir / "index.faiss"
        self.metadata_path = self.db_dir / "metadata.json"
        self.dimension = 384  # Dimension for all-MiniLM-L6-v2
        
        self.index = None
        self.metadata_map = {}

    def init_new_index(self):
        """Initializes a new empty FAISS IndexFlatL2 index."""
        logger.info(f"Initializing new FAISS IndexFlatL2 index with dimension {self.dimension}.")
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata_map = {}

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: np.ndarray):
        """Adds text chunks and their embeddings to the index and metadata map."""
        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: Chunks count ({len(chunks)}) != Embeddings count ({len(embeddings)})")

        if self.index is None:
            self.init_new_index()

        if len(chunks) == 0:
            logger.warning("No chunks to add to vector store.")
            return

        logger.info(f"Adding {len(chunks)} vectors to FAISS index...")
        
        # Verify vectors are type float32
        vectors = embeddings.astype(np.float32)
        
        # Current index count before adding
        start_id = self.index.ntotal
        
        self.index.add(vectors)
        
        # Save mapping from integer index ID to chunk data
        for i, chunk in enumerate(chunks):
            index_id = str(start_id + i)
            self.metadata_map[index_id] = {
                "chunk_id": chunk.id,
                "text": chunk.text,
                "metadata": chunk.metadata
            }
            
        logger.info(f"Successfully added vectors. Total items in FAISS: {self.index.ntotal}")
