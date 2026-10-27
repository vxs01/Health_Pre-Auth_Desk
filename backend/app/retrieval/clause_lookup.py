"""
Deterministic Clause Lookup Tool.
Allows the agent to perform pinpoint exact lookups by clause code, section name,
or heading identifier (e.g. Excl02, Cataract, Waiting Periods, Room Rent).
"""
import re
from typing import List, Dict, Any, Optional
from backend.app.ingestion.indexer import CorpusIndexer

class ClauseLookup:
    def __init__(self):
        _, self.chunks, _ = CorpusIndexer.load_indexes()

    def lookup(self, clause_identifier: str) -> List[Dict[str, Any]]:
        if not clause_identifier.strip():
            return []
            
        term = clause_identifier.strip().lower()
        matches = []
        
        # Exact/prefix match on clause_id or clause_title
        for chunk in self.chunks:
            c_id = chunk.get("clause_id", "").lower()
            c_title = chunk.get("clause_title", "").lower()
            text = chunk.get("text", "").lower()
            
            # Direct match on clause ID or title
            if term in c_id or term in c_title:
                matches.append({
                    "chunk_id": chunk["chunk_id"],
                    "document_name": chunk["document_name"],
                    "page_number": chunk["page_number"],
                    "clause_id": chunk["clause_id"],
                    "clause_title": chunk["clause_title"],
                    "text": chunk["text"],
                    "match_type": "exact_clause_match"
                })
            # Substring match in text for codes like 'excl02', 'excl01', 'cataract'
            elif term in text:
                matches.append({
                    "chunk_id": chunk["chunk_id"],
                    "document_name": chunk["document_name"],
                    "page_number": chunk["page_number"],
                    "clause_id": chunk["clause_id"],
                    "clause_title": chunk["clause_title"],
                    "text": chunk["text"],
                    "match_type": "text_keyword_match"
                })

        return matches[:5]

_lookup_instance = None

def get_clause_lookup() -> ClauseLookup:
    global _lookup_instance
    if _lookup_instance is None:
        _lookup_instance = ClauseLookup()
    return _lookup_instance
