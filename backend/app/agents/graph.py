"""
LangGraph Multi-Agent Orchestration Engine (Requirements A1, A2, A3).
Orchestrates Agent A (Investigator) and Agent B (Verifier) with explicit hand-offs,
bounded execution (steps, tool calls, model calls, wall-clock time),
graceful degradation on mid-run failure, and full audit persistence.
"""
import time
import uuid
from typing import Dict, Any, Literal, Optional, List
from langgraph.graph import StateGraph, END
from backend.app.agents.state import PreAuthGraphState
from backend.app.agents.investigator import CoverageInvestigatorAgent
from backend.app.agents.verifier import EvidenceVerificationAgent
from backend.app.telemetry.cost_tracker import CostTracker
from backend.app.telemetry.metrics import (
    PREAUTH_REQUESTS_TOTAL,
    PREAUTH_AGENT_STEPS_TOTAL,
    PREAUTH_TOOL_CALLS_TOTAL,
    PREAUTH_RUN_LATENCY_SECONDS,
    PREAUTH_TOKENS_TOTAL,
    PREAUTH_COST_USD_TOTAL
)
from backend.app.storage.database import StorageService

MAX_STEPS = 12
MAX_TOOL_CALLS = 8
MAX_MODEL_CALLS = 6
WALL_CLOCK_TIMEOUT_SEC = 25.0

def investigator_node(state: PreAuthGraphState) -> PreAuthGraphState:
    agent = CoverageInvestigatorAgent(prompt_version=state.get("prompt_version", "v2.0.0"))
    result = agent.run(state)
    return {**state, **result}

def verifier_node(state: PreAuthGraphState) -> PreAuthGraphState:
    agent = EvidenceVerificationAgent(prompt_version=state.get("prompt_version", "v2.0.0"))
    result = agent.run(state)
    return {**state, **result}

def should_continue(state: PreAuthGraphState) -> Literal["investigate", "__end__"]:
    # Bounded execution checks
    elapsed = time.time() - state.get("start_time", time.time())
    if elapsed > WALL_CLOCK_TIMEOUT_SEC:
        return END
    if state.get("steps_taken", 0) >= state.get("max_steps", MAX_STEPS):
        return END
    if state.get("tool_calls_count", 0) >= state.get("max_tool_calls", MAX_TOOL_CALLS):
        return END
    if state.get("model_calls_count", 0) >= state.get("max_model_calls", MAX_MODEL_CALLS):
        return END

    # If verification passed or deterministic decision was made, end
    if state.get("final_route"):
        return END

    return END

def build_preauth_graph() -> StateGraph:
    builder = StateGraph(PreAuthGraphState)
    builder.add_node("investigate", investigator_node)
    builder.add_node("verify", verifier_node)

    builder.set_entry_point("investigate")
    builder.add_edge("investigate", "verify")
    builder.add_conditional_edges("verify", should_continue, {
        "investigate": "investigate",
        END: END
    })

    return builder.compile()

class PreAuthAgentOrchestrator:
    def __init__(self):
        self.graph = build_preauth_graph()

    def execute_run(
        self,
        req_data: Dict[str, Any],
        prompt_version: str = "v2.0.0",
        injection_detected: bool = False,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        run_id = run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"
        trace_id = trace_id or f"TRC-{uuid.uuid4().hex[:12].upper()}"
        req_id = req_data.get("request_id") or f"REQ-{uuid.uuid4().hex[:8].upper()}"
        req_data["request_id"] = req_id

        initial_state: PreAuthGraphState = {
            "request_data": req_data,
            "trace_id": trace_id,
            "run_id": run_id,
            "prompt_version": prompt_version,
            "steps_taken": 0,
            "tool_calls_count": 0,
            "model_calls_count": 0,
            "start_time": start_time,
            "max_steps": MAX_STEPS,
            "max_tool_calls": MAX_TOOL_CALLS,
            "max_model_calls": MAX_MODEL_CALLS,
            "retrieved_passages": [],
            "investigator_candidate": {},
            "verification_outcome": {},
            "final_route": "",
            "indicative_limit": None,
            "coverage_position": "",
            "clauses": [],
            "verification_status": "unverified",
            "escalation_reason": None,
            "explanation": "",
            "audit_steps": [],
            "error": None
        }

        # If prompt injection was flagged at boundary, attach to initial state
        initial_state["injection_detected"] = injection_detected

        try:
            # Execute LangGraph
            final_state = self.graph.invoke(initial_state)
        except Exception as e:
            # Graceful degradation fallback on agent failure (Requirement A5, F7)
            duration_ms = round((time.time() - start_time) * 1000.0, 2)
            fallback_run = {
                "run_id": run_id,
                "request_id": req_data.get("request_id", "UNKNOWN"),
                "trace_id": trace_id,
                "status": "escalated",
                "route": "medical-review",
                "indicative_limit": None,
                "coverage_position": "Escalated to human review due to unexpected agent pipeline failure.",
                "clauses": [],
                "applicable_waiting_periods": [],
                "applicable_exclusions": [],
                "room_eligibility_status": "Unverified",
                "verification_status": "escalated",
                "escalation_reason": f"Agent graph exception: {str(e)}",
                "explanation": "A system exception occurred during automated investigation. Safely routed to Medical Officer.",
                "prompt_version": prompt_version,
                "processing_duration_ms": duration_ms,
                "cost_breakdown": {"total_tokens": 0, "estimated_cost_usd": 0.0},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            StorageService.save_run(fallback_run)
            return fallback_run

        duration_ms = round((time.time() - start_time) * 1000.0, 2)
        audit_steps = final_state.get("audit_steps", [])
        cost_summary = CostTracker.build_cost_summary(audit_steps)

        # Build clean output
        run_record = {
            "run_id": run_id,
            "request_id": req_data.get("request_id"),
            "trace_id": trace_id,
            "status": "completed",
            "route": final_state.get("final_route", "medical-review"),
            "indicative_limit": final_state.get("indicative_limit"),
            "coverage_position": final_state.get("coverage_position", "Under Medical Review"),
            "clauses": final_state.get("clauses", []),
            "applicable_waiting_periods": final_state.get("verification_outcome", {}).get("applicable_waiting_periods", []),
            "applicable_exclusions": final_state.get("verification_outcome", {}).get("applicable_exclusions", []),
            "room_eligibility_status": final_state.get("verification_outcome", {}).get("room_eligibility_status", "Approved"),
            "verification_status": final_state.get("verification_status", "verified"),
            "escalation_reason": final_state.get("escalation_reason"),
            "explanation": final_state.get("explanation", ""),
            "prompt_version": prompt_version,
            "processing_duration_ms": duration_ms,
            "cost_breakdown": cost_summary,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        # Persist to database
        StorageService.save_run(run_record)
        for s in audit_steps:
            StorageService.save_audit_step(s)

        # Record metrics
        PREAUTH_REQUESTS_TOTAL.labels(status="completed", route=run_record["route"]).inc()
        PREAUTH_RUN_LATENCY_SECONDS.observe(duration_ms / 1000.0)
        PREAUTH_TOKENS_TOTAL.labels(token_type="prompt").inc(cost_summary["total_prompt_tokens"])
        PREAUTH_TOKENS_TOTAL.labels(token_type="completion").inc(cost_summary["total_completion_tokens"])
        PREAUTH_COST_USD_TOTAL.inc(cost_summary["estimated_cost_usd"])

        return run_record

_orchestrator = None

def get_orchestrator() -> PreAuthAgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PreAuthAgentOrchestrator()
    return _orchestrator
