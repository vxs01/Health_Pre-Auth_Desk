"""
Document extractor using PyMuPDF.
Extracts text page-by-page while preserving page numbers and document metadata.
Detects empty or scanned pages and flags OCR requirements.
"""
import os
import pymupdf as fitz
from typing import List, Dict, Any

class DocumentExtractor:
    @staticmethod
    def extract_pdf(file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")
            
        doc = fitz.open(file_path)
        pages_content = []
        doc_name = os.path.basename(file_path)
        
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            raw_text = page.get_text("text")
            
            # Check for scanned page without text layer
            is_scanned = len(raw_text.strip()) < 20
            
            pages_content.append({
                "document_name": doc_name,
                "document_path": file_path,
                "page_number": page_num,
                "raw_text": raw_text,
                "char_count": len(raw_text),
                "is_scanned": is_scanned,
                "needs_ocr": is_scanned
            })
            
        doc.close()
        return pages_content
