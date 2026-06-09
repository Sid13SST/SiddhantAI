# pyrefly: ignore [missing-import]
import numpy as np
from typing import List
from app.core.logging import logger
import os

class EmbeddingService:
    _model = None
    _mode = None  # 'local' or 'api'

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if EmbeddingService._mode is not None:
            # Already initialized
            return
            
        # Try local model first, fall back to API for low-memory deployments
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local SentenceTransformer model: {model_name}...")
            EmbeddingService._model = SentenceTransformer(model_name)
            EmbeddingService._mode = "local"
            logger.info("SentenceTransformer model loaded successfully (local mode).")
        except (ImportError, Exception) as e:
            logger.info(f"Local SentenceTransformer unavailable ({e}), using HuggingFace Inference API.")
            EmbeddingService._mode = "api"
            EmbeddingService._model = model_name

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generates 384-dim embeddings for a list of text strings."""
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
            
        logger.info(f"Generating embeddings for {len(texts)} chunks ({EmbeddingService._mode} mode)...")
        
        if EmbeddingService._mode == "local":
            embeddings = EmbeddingService._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings.astype(np.float32)
        else:
            return self._generate_via_api(texts)
    
    def _generate_via_api(self, texts: List[str]) -> np.ndarray:
        """Calls HuggingFace free Inference API for embeddings (no API key needed for public models)."""
        import httpx
        
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_id}"
        
        headers = {"Content-Type": "application/json"}
        # Optional: use HF token for higher rate limits
        hf_token = os.environ.get("HF_TOKEN", "")
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        
        all_embeddings = []
        # Process in batches of 8 to avoid payload limits
        batch_size = 8
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = httpx.post(
                    api_url,
                    json={"inputs": batch, "options": {"wait_for_model": True}},
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                batch_embeddings = response.json()
                
                if not isinstance(batch_embeddings, list):
                    raise ValueError(f"Unexpected HuggingFace API response format: {batch_embeddings}")
                
                # API returns list of list of floats — each text gets a list of token embeddings
                # For sentence-transformers models, it returns the pooled embedding directly
                for emb in batch_embeddings:
                    if not emb:
                        all_embeddings.append(np.zeros(384, dtype=np.float32))
                        continue
                    if isinstance(emb[0], list):
                        # Token-level embeddings returned — mean pool them
                        arr = np.array(emb, dtype=np.float32)
                        pooled = arr.mean(axis=0)
                        all_embeddings.append(pooled)
                    else:
                        all_embeddings.append(np.array(emb, dtype=np.float32))
                        
            except Exception as e:
                logger.error(f"HuggingFace API embedding error: {e}")
                # Return zero vectors as fallback
                for _ in batch:
                    all_embeddings.append(np.zeros(384, dtype=np.float32))
        
        return np.array(all_embeddings, dtype=np.float32)
