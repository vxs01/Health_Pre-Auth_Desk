"""
Command-line runner for the corpus ingestion pipeline.
Idempotent execution: reads raw PDFs, chunks, embeds, creates indexes and manifest.
Usage:
    python -m backend.app.ingestion.run_pipeline
"""
import os
import sys
import time
from backend.app.ingestion.extractor import DocumentExtractor
from backend.app.ingestion.chunker import ClauseAwareChunker
from backend.app.ingestion.indexer import CorpusIndexer
from backend.app.ingestion.manifest import CorpusManifest

RAW_DIR = "data/raw"

def run_ingestion_pipeline():
    start_time = time.time()
    print("=" * 70)
    print("Starting Health Pre-Authorisation Desk Corpus Ingestion Pipeline")
    print("=" * 70)
    
    if not os.path.exists(RAW_DIR):
        raise FileNotFoundError(f"Raw data directory '{RAW_DIR}' does not exist.")
        
    pdf_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(".pdf")]
    if not pdf_files:
        raise FileNotFoundError(f"No PDF documents found in '{RAW_DIR}'.")
        
    print(f"Discovered {len(pdf_files)} PDF document(s): {pdf_files}")
    
    all_chunks = []
    doc_stats = []
    
    for pdf in pdf_files:
        filepath = os.path.join(RAW_DIR, pdf)
        print(f"\nProcessing '{pdf}'...")
        pages = DocumentExtractor.extract_pdf(filepath)
        print(f"  Extracted {len(pages)} pages.")
        
        chunks = ClauseAwareChunker.chunk_documents(pages)
        print(f"  Created {len(chunks)} clause-aware chunks.")
        
        doc_stats.append({
            "document_name": pdf,
            "page_count": len(pages),
            "chunk_count": len(chunks)
        })
        all_chunks.extend(chunks)
        
    print(f"\nTotal chunks to index: {len(all_chunks)}")
    print("Generating embeddings and building FAISS & BM25 indexes...")
    index_res = CorpusIndexer.build_indexes(all_chunks)
    
    duration = time.time() - start_time
    manifest = CorpusManifest.generate_manifest(RAW_DIR, doc_stats, len(all_chunks), duration)
    
    print("\n" + "=" * 70)
    print("Ingestion Pipeline Completed Successfully!")
    print(f"Total documents: {manifest['total_documents']}")
    print(f"Total pages:     {manifest['total_pages']}")
    print(f"Total chunks:    {manifest['total_chunks']}")
    print(f"Duration:        {manifest['index_build_duration_seconds']} seconds")
    print(f"Throughput:      {manifest['pipeline_throughput_pages_per_sec']} pages/sec")
    print(f"Manifest saved:  data/processed/corpus_manifest.json")
    print(f"FAISS index:     {index_res['faiss_path']}")
    print("=" * 70)
    return manifest

if __name__ == "__main__":
    run_ingestion_pipeline()
