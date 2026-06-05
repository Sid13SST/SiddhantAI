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

    def save(self):
        """Serializes and saves the FAISS index and metadata map to the local filesystem."""
        if self.index is None:
            logger.warning("Vector store is empty, nothing to save.")
            return

        logger.info(f"Saving vector database files to: {self.db_dir}")
        faiss.write_index(self.index, str(self.index_path))
        
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata_map, f, indent=2, ensure_ascii=False)
            
        logger.info("Successfully persisted index.faiss and metadata.json.")

    def load(self) -> bool:
        """Loads index and metadata from disk. Returns True on success, False if files are missing."""
        if not self.index_path.exists() or not self.metadata_path.exists():
            logger.info("Vector database files do not exist yet. Initializing new empty index.")
            self.init_new_index()
            return False

        try:
            logger.info(f"Loading vector database files from: {self.db_dir}")
            self.index = faiss.read_index(str(self.index_path))
            
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata_map = json.load(f)
                
            logger.info(f"Successfully loaded vector database. Total items: {self.index.ntotal}")
            return True
        except Exception as e:
            logger.error(f"Error loading vector store from disk: {e}. Initializing empty.")
            self.init_new_index()
            return False

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Queries the vector index. Returns list of tuples of (chunk_dict, distance_score)."""
        if self.index is None or self.index.ntotal == 0:
            logger.warning("Search queried but vector index is uninitialized or empty.")
            return []

        # Query vector must be shape (1, dimension)
        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)

        query_vector = query_vector.astype(np.float32)
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            idx_str = str(idx)
            if idx_str in self.metadata_map:
                results.append((self.metadata_map[idx_str], float(dist)))
                
        return results
