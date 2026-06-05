# pyrefly: ignore [missing-import]
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStoreService
from app.core.logging import logger

class QARetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    def retrieve_grounded_chunks(
        self, 
        rewritten_query: str, 
        top_k: int = 5, 
        relevance_threshold: float = 1.6,
        max_chunks_per_source: int = 2,
        filter_tags: Optional[List[str]] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Retrieves semantically similar chunks with tag-boosting, deduplication, and source diversity constraints."""
        # 1. Load FAISS index and metadata
        self.vector_store.load()
        if self.vector_store.index is None or self.vector_store.index.ntotal == 0:
            logger.warning("Vector database is empty. No documents to retrieve.")
            return []

        # 2. Embed the rewritten query
        query_vector = self.embedding_service.generate_embeddings([rewritten_query])[0]

        # 3. Retrieve more candidates than top_k to allow diversity filtering
        over_query_k = top_k * 4
        raw_results = self.vector_store.search(query_vector, top_k=over_query_k)

        # 4. Apply Tag Boosting
        boosted_results = []
        for item, dist_score in raw_results:
            metadata = item.get("metadata", {})
            retrieval_tags = metadata.get("retrieval_tags", [])
            
            score = dist_score
            if filter_tags:
                query_tags_set = set(t.lower() for t in filter_tags)
                doc_tags_set = set(t.lower() for t in retrieval_tags)
                intersect = query_tags_set.intersection(doc_tags_set)
                if intersect:
                    # L2 distance boost: lower L2 distance is better
                    score -= 0.15 * len(intersect)
                    
            boosted_results.append((item, score))
            
        # Re-sort after boosting (ascending order of L2 distance)
        boosted_results.sort(key=lambda x: x[1])

        # 5. Apply Relevance Filtering and Source Diversity Cap
        filtered_results = []
        seen_texts = set()
        seen_chunk_ids = set()
        source_counters = {}

        for item, score in boosted_results:
            # Check relevance threshold (skip weak chunks)
            if score > relevance_threshold:
                logger.debug(f"Skipping chunk {item['chunk_id']} due to weak relevance score: {score} > {relevance_threshold}")
                continue

            chunk_id = item["chunk_id"]
            text = item["text"]
            metadata = item.get("metadata", {})
            source_type = metadata.get("source_type", "unknown")
            
            # Identify source file key
            # Resume source key is page number, GitHub keys are repo name + file path or commit sha
            if source_type == "resume":
                source_key = f"resume_p{metadata.get('page_number', 1)}"
            elif source_type == "github_code":
                source_key = f"code_{metadata.get('repo_name')}_{metadata.get('file_path')}"
            elif source_type == "github_commit":
                source_key = f"commit_{metadata.get('repo_name')}_{metadata.get('commit_sha')}"
            elif source_type == "github_readme":
                source_key = f"readme_{metadata.get('repo_name')}"
            else:
                source_key = f"meta_{metadata.get('repo_name', 'unknown')}"

            # Deduplication
            normalized_text = " ".join(text.lower().split())
            if normalized_text in seen_texts or chunk_id in seen_chunk_ids:
                continue

            # Source Diversity Enforcer
            current_count = source_counters.get(source_key, 0)
            if current_count >= max_chunks_per_source:
                logger.debug(f"Source diversity limit reached for {source_key}. Skipping chunk.")
                continue

            # Record chunk
            filtered_results.append((item, score))
            seen_texts.add(normalized_text)
            seen_chunk_ids.add(chunk_id)
            source_counters[source_key] = current_count + 1

            # Check if we have gathered enough top_k items
            if len(filtered_results) >= top_k:
                break

        logger.info(f"Retrieved {len(filtered_results)} unique, diverse, and relevant chunks (threshold={relevance_threshold}).")
        return filtered_results
