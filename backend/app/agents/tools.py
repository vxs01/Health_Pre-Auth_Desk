"""
Callable Agent Tools (Requirement A1).
At least three tools:
1. search_corpus(query, filter_doc): Semantic and lexical search over policy wordings and day care schedule.
2. lookup_clause(clause_id): Exact lookup for clauses, waiting period codes, and exclusion sections.
3. get_request_fields(field_name): Dynamic inspection of the pre-authorisation request fields.
"""
from typing import Dict, Any, List, Optional
from backend.app.retrieval.search import get_retriever
from backend.app.retrieval.clause_lookup import get_clause_lookup

def search_corpus_tool(query: str, filter_doc: Optional[str] = None, top_k: int = 4) -> List[Dict[str, Any]]:
    retriever = get_retriever()
    return retriever.search(query, top_k=top_k, filter_doc=filter_doc)

def lookup_clause_tool(clause_id: str) -> List[Dict[str, Any]]:
    lookup = get_clause_lookup()
    return lookup.lookup(clause_id)

def get_request_fields_tool(request_data: Dict[str, Any], field_name: Optional[str] = None) -> Any:
    if field_name:
        return request_data.get(field_name)
    return request_data
