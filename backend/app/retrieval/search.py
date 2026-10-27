"""
Hybrid Retrieval Engine.
Combines dense semantic vector search (FAISS IndexFlatIP) with sparse lexical search (BM25Okapi)
using Reciprocal Rank Fusion (RRF) to return verifiable policy passages with full provenance.
"""
import os
import json
import numpy as np
from typing import List, Dict, Any, Optional
from backend.app.ingestion.indexer import CorpusIndexer

class HybridRetriever:
    def __init__(self):
        self.faiss_index, self.chunks, self.bm25 = CorpusIndexer.load_indexes()
        self.model = CorpusIndexer.get_embedding_model()

    def search(self, query: str, top_k: int = 5, filter_doc: Optional[str] = None) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        # 1. Dense Semantic Search
        q_emb = self.model.encode([query], normalize_embeddings=True)
        q_emb = np.array(q_emb, dtype=np.float32)
        
        # Retrieve top 20 candidates from FAISS
        num_candidates = min(20, len(self.chunks))
        scores, indices = self.faiss_index.search(q_emb, num_candidates)
        
        dense_ranks = {}
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx >= 0:
                dense_ranks[idx] = (rank + 1, float(score))

        # 2. Sparse BM25 Search
        bm25_ranks = {}
        if self.bm25:
            tokenized_q = query.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_q)
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:num_candidates]
            for rank, idx in enumerate(bm25_top_indices):
                score = bm25_scores[idx]
                if score > 0:
                    bm25_ranks[idx] = (rank + 1, float(score))

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_score(d) = sum(1 / (k + rank))
        rrf_k = 60
        combined_scores = {}
        all_candidate_indices = set(dense_ranks.keys()).union(set(bm25_ranks.keys()))

        for idx in all_candidate_indices:
            score = 0.0
            if idx in dense_ranks:
                score += 1.0 / (rrf_k + dense_ranks[idx][0])
            if idx in bm25_ranks:
                score += 1.0 / (rrf_k + bm25_ranks[idx][0])
            combined_scores[idx] = score

        # Sort by RRF score descending
        sorted_indices = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for idx, rrf_score in sorted_indices:
            chunk = self.chunks[idx]
            if filter_doc and filter_doc.lower() not in chunk["document_name"].lower():
                continue

            dense_sim = dense_ranks.get(idx, (None, 0.0))[1]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "document_name": chunk["document_name"],
                "page_number": chunk["page_number"],
                "clause_id": chunk["clause_id"],
                "clause_title": chunk["clause_title"],
                "text": chunk["text"],
                "dense_similarity": round(dense_sim, 4),
                "rrf_score": round(rrf_score, 4)
            })

            if len(results) >= top_k:
                break

        return results

_retriever_instance = None

def get_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance
