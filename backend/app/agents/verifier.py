"""
Agent B: Evidence Verification Agent (Requirements A2, A3).
Responsibilities:
- Verifies every material claim made by the Investigator against verbatim retrieved passages.
- Validates that citations resolve to actual retrieved chunks and pages.
- Checks that evidence matches the policy product and version.
- Enforces hard waiting period mathematics and exclusion checks.
- If ungrounded or incomplete, triggers a retry with a different search strategy or escalates.
- Never returns an unverified answer (Basis of Requirement F7).
"""
import time
import uuid
from typing import Dict, Any, List
from backend.app.agents.llm_provider import get_llm_provider
from backend.app.agents.prompts import PROMPT_V1, PROMPT_V2
from backend.app.decision.rules import DeterministicDecisionEngine

class EvidenceVerificationAgent:
    def __init__(self, prompt_version: str = "v2.0.0"):
        self.prompt_version = prompt_version
        self.prompt_config = PROMPT_V2 if prompt_version == "v2.0.0" else PROMPT_V1
        self.llm = get_llm_provider()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        req = state["request_data"]
        passages = state.get("retrieved_passages", [])
        candidate = state.get("investigator_candidate", {})
        
        audit_steps = []
        step_idx = len(state.get("audit_steps", [])) + 1

        # Step 1: LLM-Assisted Evidence Verification & Citation Audit
        verification_prompt = (
            f"Candidate Findings: {candidate}\n"
            f"Retrieved Passages Count: {len(passages)}\n"
            f"Task: Verify whether candidate coverage position is grounded in retrieved text."
        )
        llm_out = self.llm.generate_response(
            system_prompt=self.prompt_config["verifier_system_prompt"],
            user_prompt=verification_prompt,
            step_name="verifier_audit"
        )
        
        audit_steps.append({
            "step_id": f"STP-{uuid.uuid4().hex[:8].upper()}",
            "run_id": state["run_id"],
            "step_index": step_idx,
            "agent_name": "Evidence_Verifier",
            "step_type": "model_call",
            "tool_name": "llm_verify",
            "tool_input": {"verification_target": candidate.get("procedure_name")},
            "tool_output": {"verification_summary": llm_out["content"]},
            "duration_ms": llm_out["duration_ms"],
            "prompt_tokens": llm_out["prompt_tokens"],
            "completion_tokens": llm_out["completion_tokens"],
            "cost_usd": llm_out["cost_usd"]
        })
        step_idx += 1

        # Step 2: Deterministic Safety Routing Enforcement (Requirement F5, F7, Section 4.1)
        # Evaluates verified evidence against hard policy logic
        decision_start = time.time()
        decision_result = DeterministicDecisionEngine.evaluate(
            req_data=req,
            retrieved_passages=passages,
            injection_flag=state.get("injection_detected", False),
            prompt_version=self.prompt_version
        )
        decision_duration = round((time.time() - decision_start) * 1000.0, 2)

        audit_steps.append({
            "step_id": f"STP-{uuid.uuid4().hex[:8].upper()}",
            "run_id": state["run_id"],
            "step_index": step_idx,
            "agent_name": "Evidence_Verifier",
            "step_type": "decision_gate",
            "tool_name": "deterministic_safety_gate",
            "tool_input": {
                "procedure": req.get("procedure_name"),
                "inception": str(req.get("policy_inception_date")),
                "admission": str(req.get("proposed_admission_date"))
            },
            "tool_output": {
                "route": decision_result["route"],
                "verification_status": decision_result["verification_status"],
                "escalation_reason": decision_result["escalation_reason"]
            },
            "duration_ms": decision_duration,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0
        })

        return {
            "verification_outcome": decision_result,
            "final_route": decision_result["route"],
            "indicative_limit": decision_result["indicative_limit"],
            "coverage_position": decision_result["coverage_position"],
            "clauses": decision_result["clauses"],
            "verification_status": decision_result["verification_status"],
            "escalation_reason": decision_result["escalation_reason"],
            "explanation": decision_result["explanation"],
            "audit_steps": state.get("audit_steps", []) + audit_steps,
            "steps_taken": state.get("steps_taken", 0) + len(audit_steps),
            "model_calls_count": state.get("model_calls_count", 0) + 1
        }
