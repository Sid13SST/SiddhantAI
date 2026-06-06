# pyrefly: ignore [missing-import]
import numpy as np
from typing import List
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer
from app.core.logging import logger

class EmbeddingService:
    _model = None

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if EmbeddingService._model is None:
            logger.info(f"Loading local SentenceTransformer model: {model_name}...")
            EmbeddingService._model = SentenceTransformer(model_name)
            logger.info("SentenceTransformer model loaded successfully.")
        self.model = EmbeddingService._model

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generates high-dimensional embeddings for a list of text strings in batch."""
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
            
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        # encode returns a numpy array. Ensure output is float32 for FAISS compatibility.
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.astype(np.float32)
