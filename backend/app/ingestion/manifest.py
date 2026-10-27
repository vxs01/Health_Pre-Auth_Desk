"""
Corpus Manifest Manager.
Tracks ingested document versions, checksums, page counts, chunk counts,
data freshness, and pipeline throughput.
"""
import os
import json
import hashlib
import time
from datetime import datetime
from typing import Dict, Any, List

MANIFEST_PATH = "data/processed/corpus_manifest.json"

DOCUMENT_CATALOG = [
    {
        "file_name": "hdfc_ergo_optima_restore_policy_wording.pdf",
        "product_name": "HDFC ERGO Optima Restore",
        "uin": "HDFHLIP22193V072122",
        "version_date": "2021-07-21",
        "source_url": "https://customer-portal-assets.hdfcergo.com/documents/13.optima-restore-old-109940947605.pdf",
        "description": "Full Retail Policy Wording with Inpatient Benefits, Waiting Periods, Exclusions, and Schedule of Benefits."
    },
    {
        "file_name": "hdfc_ergo_day_care_procedures_list.pdf",
        "product_name": "HDFC ERGO Day Care Procedures Schedule",
        "uin": "HDFHLIP22193V072122",
        "version_date": "2022-01-01",
        "source_url": "https://www.hdfcergo.com/downloads/day-care-procedures",
        "description": "Comprehensive Categorized Schedule of Day Care Procedures matching Optima Restore / Health Suraksha."
    }
]

class CorpusManifest:
    @staticmethod
    def compute_sha256(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def generate_manifest(cls, raw_dir: str, doc_stats: List[Dict[str, Any]], total_chunks: int, duration_sec: float) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
        manifest_docs = []
        total_pages = sum(d["page_count"] for d in doc_stats)
        
        for meta in DOCUMENT_CATALOG:
            filepath = os.path.join(raw_dir, meta["file_name"])
            if not os.path.exists(filepath):
                continue
                
            stat = next((s for s in doc_stats if s["document_name"] == meta["file_name"]), None)
            sha = cls.compute_sha256(filepath)
            
            manifest_docs.append({
                "document_name": meta["file_name"],
                "product_name": meta["product_name"],
                "uin": meta["uin"],
                "version_date": meta["version_date"],
                "source_url": meta["source_url"],
                "description": meta["description"],
                "file_checksum_sha256": sha,
                "file_size_bytes": os.path.getsize(filepath),
                "page_count": stat["page_count"] if stat else 0,
                "chunk_count": stat["chunk_count"] if stat else 0,
                "extraction_method": "PyMuPDF-TextLayer",
                "ocr_applied": False,
                "processing_status": "INDEXED"
            })
            
        manifest = {
            "corpus_name": "HDFC ERGO Retail Health Policy Corpus",
            "last_built_at": datetime.utcnow().isoformat() + "Z",
            "total_documents": len(manifest_docs),
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "index_build_duration_seconds": round(duration_sec, 3),
            "pipeline_throughput_pages_per_sec": round(total_pages / max(duration_sec, 0.001), 2),
            "embedding_model": "all-MiniLM-L6-v2",
            "vector_dimension": 384,
            "index_type": "FAISS-IndexFlatIP + BM25Okapi",
            "documents": manifest_docs
        }
        
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            
        return manifest

    @classmethod
    def load_manifest(cls) -> Dict[str, Any]:
        if not os.path.exists(MANIFEST_PATH):
            return {}
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
