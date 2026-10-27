"""
State Schema for the LangGraph Multi-Agent Pre-Authorisation Desk (Requirement A1, A2).
"""
from typing import TypedDict, List, Dict, Any, Optional

class PreAuthGraphState(TypedDict):
    request_data: Dict[str, Any]
    trace_id: str
    run_id: str
    prompt_version: str
    
    # Loop bounds and counters
    steps_taken: int
    tool_calls_count: int
    model_calls_count: int
    start_time: float
    max_steps: int
    max_tool_calls: int
    max_model_calls: int
    
    # Investigation findings
    retrieved_passages: List[Dict[str, Any]]
    investigator_candidate: Dict[str, Any]
    
    # Verification findings
    verification_outcome: Dict[str, Any]
    
    # Final routing
    final_route: str # approve-recommended, query-to-hospital, medical-review
    indicative_limit: Optional[float]
    coverage_position: str
    clauses: List[Dict[str, Any]]
    verification_status: str
    escalation_reason: Optional[str]
    explanation: str
    
    # Audit trail
    audit_steps: List[Dict[str, Any]]
    error: Optional[str]
