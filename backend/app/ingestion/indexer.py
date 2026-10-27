"""
Vector and BM25 indexer.
Embeds text chunks using local all-MiniLM-L6-v2 sentence transformer,
indexes them into a FAISS IndexFlatIP (cosine similarity), and generates
a BM25 index for fast lexical search.
"""
import os
import json
import pickle
import faiss
import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

INDEX_DIR = "data/index"
FAISS_PATH = os.path.join(INDEX_DIR, "corpus.faiss")
METADATA_PATH = os.path.join(INDEX_DIR, "corpus_metadata.json")
BM25_PATH = os.path.join(INDEX_DIR, "bm25_corpus.pkl")

class CorpusIndexer:
    _model = None

    @classmethod
    def get_embedding_model(cls) -> SentenceTransformer:
        if cls._model is None:
            cls._model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        return cls._model

    @classmethod
    def build_indexes(cls, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        os.makedirs(INDEX_DIR, exist_ok=True)
        if not chunks:
            raise ValueError("No chunks provided to index.")
            
        texts = [c["text"] for c in chunks]
        
        # 1. Embeddings & FAISS
        model = cls.get_embedding_model()
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype=np.float32)
        
        dim = embeddings.shape[1]
        faiss_index = faiss.IndexFlatIP(dim) # Inner product with normalized vectors = cosine similarity
        faiss_index.add(embeddings)
        faiss.write_index(faiss_index, FAISS_PATH)
        
        # 2. Metadata storage
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)
            
        # 3. BM25 Lexical Index
        tokenized_corpus = [text.lower().split() for text in texts]
        bm25 = BM25Okapi(tokenized_corpus)
        with open(BM25_PATH, "wb") as f:
            pickle.dump({"bm25": bm25, "chunks": chunks}, f)
            
        return {
            "total_chunks": len(chunks),
            "embedding_dimension": dim,
            "faiss_path": FAISS_PATH,
            "metadata_path": METADATA_PATH,
            "bm25_path": BM25_PATH
        }

    @classmethod
    def load_indexes(cls) -> Tuple[faiss.Index, List[Dict[str, Any]], BM25Okapi]:
        if not os.path.exists(FAISS_PATH) or not os.path.exists(METADATA_PATH):
            raise FileNotFoundError("Corpus indexes not found. Run ingestion pipeline first.")
            
        faiss_index = faiss.read_index(FAISS_PATH)
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            
        bm25 = None
        if os.path.exists(BM25_PATH):
            with open(BM25_PATH, "rb") as f:
                data = pickle.load(f)
                bm25 = data["bm25"]
                
        return faiss_index, chunks, bm25
