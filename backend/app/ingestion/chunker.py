"""
Clause-aware document chunker.
Splits extracted document text into logical clauses, sections, and definitions,
preserving structural integrity, clause identifiers, and page references.
"""
import re
import hashlib
from typing import List, Dict, Any

class ClauseAwareChunker:
    CLAUSE_PATTERNS = [
        # Policy wording section headers
        r"(Section\s+[A-Z]\.\s+[^\n]+)",
        r"(\d+\.\s+Standard\s+Waiting\s+Periods)",
        r"(ii\.\s+Specified\s+disease/procedure\s+waiting\s+period[^\n]*)",
        r"(i\.\s+30-day\s+waiting\s+period[^\n]*)",
        r"(iii\.\s+Pre-Existing\s+Diseases[^\n]*)",
        r"(\d+\.\s+Standard\s+Exclusions)",
        r"(Annexure\s+I\s+[^\n]+)",
        r"(Schedule\s+of\s+benefits[^\n]*)",
        r"(Def\.\s+\d+\.[^\n]+)",
        # Day Care procedure categories
        r"(\d+\.\s+[A-Za-z0-9,\s&/\(\)]+\((?:ENT|Ophthalmology|Day\s+Care|Proctology)\))",
        r"(\d+\.\s+[A-Z][A-Za-z\s&]+(?:Procedures|Surgeries|Interventions))",
        r"(General\s+Day\s+Care\s+Conditions[^\n]*)"
    ]

    @classmethod
    def chunk_page(cls, page_data: Dict[str, Any], chunk_size: int = 800, chunk_overlap: int = 150) -> List[Dict[str, Any]]:
        text = page_data["raw_text"]
        doc_name = page_data["document_name"]
        page_num = page_data["page_number"]
        
        if not text.strip():
            return []
            
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        
        current_chunk = []
        current_len = 0
        current_clause_id = f"Page_{page_num}"
        current_clause_title = f"Page {page_num} General Terms"
        
        # Check if page has prominent headers
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            for pat in cls.CLAUSE_PATTERNS:
                m = re.match(pat, line, re.IGNORECASE)
                if m:
                    current_clause_title = m.group(1).strip()
                    # Clean identifier
                    current_clause_id = re.sub(r"[^A-Za-z0-9_\.]+", "_", current_clause_title)[:40].strip("_")
                    break
        
        # Build chunks respecting paragraph boundaries
        for p in paragraphs:
            # Check if paragraph introduces a specific sub-clause
            for pat in cls.CLAUSE_PATTERNS:
                m = re.search(pat, p, re.IGNORECASE)
                if m:
                    current_clause_title = m.group(1).strip()
                    current_clause_id = re.sub(r"[^A-Za-z0-9_\.]+", "_", current_clause_title)[:40].strip("_")
                    break
                    
            p_len = len(p)
            if current_len + p_len > chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunk_id = hashlib.sha256(f"{doc_name}_{page_num}_{chunk_text[:100]}".encode()).hexdigest()[:16]
                chunks.append({
                    "chunk_id": chunk_id,
                    "document_name": doc_name,
                    "page_number": page_num,
                    "clause_id": current_clause_id,
                    "clause_title": current_clause_title,
                    "text": chunk_text,
                    "char_count": len(chunk_text)
                })
                current_chunk = []
                current_len = 0
                
            current_chunk.append(p)
            current_len += p_len
            
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunk_id = hashlib.sha256(f"{doc_name}_{page_num}_{chunk_text[:100]}".encode()).hexdigest()[:16]
            chunks.append({
                "chunk_id": chunk_id,
                "document_name": doc_name,
                "page_number": page_num,
                "clause_id": current_clause_id,
                "clause_title": current_clause_title,
                "text": chunk_text,
                "char_count": len(chunk_text)
            })
            
        return chunks

    @classmethod
    def chunk_documents(cls, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        all_chunks = []
        for p in pages_data:
            all_chunks.extend(cls.chunk_page(p))
        return all_chunks
