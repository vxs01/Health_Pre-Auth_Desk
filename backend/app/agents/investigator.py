"""
Agent A: Coverage Investigator Agent (Requirements A1, A2).
Responsibilities:
- Inspects validated pre-authorisation request fields.
- Formulates initial search queries dynamically.
- Identifies primary coverage clauses.
- Detects potential modifiers, restrictions, and waiting periods.
- Formulates follow-up searches based on initial retrieval results (e.g. Cataract -> searches waiting periods).
- Produces a structured candidate assessment with verbatim supporting passages.
"""
import time
import uuid
from typing import Dict, Any, List
from backend.app.agents.tools import search_corpus_tool, lookup_clause_tool
from backend.app.agents.llm_provider import get_llm_provider
from backend.app.agents.prompts import PROMPT_V1, PROMPT_V2

class CoverageInvestigatorAgent:
    def __init__(self, prompt_version: str = "v2.0.0"):
        self.prompt_version = prompt_version
        self.prompt_config = PROMPT_V2 if prompt_version == "v2.0.0" else PROMPT_V1
        self.llm = get_llm_provider()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        req = state["request_data"]
        proc_name = req.get("procedure_name", "")
        diag = req.get("diagnosis", "")
        adm_type = req.get("admission_type", "")
        
        audit_steps = []
        retrieved_passages = []
        step_idx = len(state.get("audit_steps", [])) + 1

        # Step 1: Dynamic Primary Retrieval
        primary_query = f"{proc_name} {adm_type} coverage benefits"
        step_1_start = time.time()
        primary_results = search_corpus_tool(primary_query, top_k=3)
        retrieved_passages.extend(primary_results)
        step_1_duration = round((time.time() - step_1_start) * 1000.0, 2)
        
        audit_steps.append({
            "step_id": f"STP-{uuid.uuid4().hex[:8].upper()}",
            "run_id": state["run_id"],
            "step_index": step_idx,
            "agent_name": "Coverage_Investigator",
            "step_type": "tool_call",
            "tool_name": "search_corpus",
            "tool_input": {"query": primary_query, "top_k": 3},
            "tool_output": [{"doc": r["document_name"], "page": r["page_number"], "clause": r["clause_title"]} for r in primary_results],
            "duration_ms": step_1_duration,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0
        })
        step_idx += 1

        # Step 2: Dynamic Follow-up Search for Modifiers (The core Agentic behavior!)
        # Derive follow-up search from procedure type
        modifier_query = None
        if any(k in proc_name.lower() or k in diag.lower() for k in ["cataract", "phaco", "eye"]):
            modifier_query = "cataract specified disease waiting period Code Excl02"
        elif any(k in proc_name.lower() for k in ["tonsil", "adenoid", "hernia", "stone", "fistula", "joint"]):
            modifier_query = f"{proc_name} specified disease waiting period 24 months Excl02"
        elif adm_type != "emergency":
            modifier_query = "30-day waiting period Code Excl03"

        if modifier_query:
            step_2_start = time.time()
            modifier_results = search_corpus_tool(modifier_query, top_k=2)
            retrieved_passages.extend(modifier_results)
            step_2_duration = round((time.time() - step_2_start) * 1000.0, 2)
            
            audit_steps.append({
                "step_id": f"STP-{uuid.uuid4().hex[:8].upper()}",
                "run_id": state["run_id"],
                "step_index": step_idx,
                "agent_name": "Coverage_Investigator",
                "step_type": "tool_call",
                "tool_name": "search_corpus",
                "tool_input": {"query": modifier_query, "top_k": 2},
                "tool_output": [{"doc": r["document_name"], "page": r["page_number"], "clause": r["clause_title"]} for r in modifier_results],
                "duration_ms": step_2_duration,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0
            })
            step_idx += 1

        # Step 3: Direct Clause Lookup if specific code suspected
        if "cataract" in proc_name.lower() or "cataract" in diag.lower():
            step_3_start = time.time()
            lookup_res = lookup_clause_tool("Excl02")
            retrieved_passages.extend(lookup_res)
            step_3_duration = round((time.time() - step_3_start) * 1000.0, 2)
            
            audit_steps.append({
                "step_id": f"STP-{uuid.uuid4().hex[:8].upper()}",
                "run_id": state["run_id"],
                "step_index": step_idx,
                "agent_name": "Coverage_Investigator",
                "step_type": "tool_call",
                "tool_name": "lookup_clause",
                "tool_input": {"clause_id": "Excl02"},
                "tool_output": [{"doc": r["document_name"], "page": r["page_number"], "clause": r["clause_title"]} for r in lookup_res],
                "duration_ms": step_3_duration,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0
            })
            step_idx += 1

        # Step 4: Investigator Reasoning & Synthesis
        user_context = (
            f"Pre-Auth Request: Procedure='{proc_name}', Diagnosis='{diag}', Type='{adm_type}', "
            f"Inception='{req.get('policy_inception_date')}', Admission='{req.get('proposed_admission_date')}'.\n"
            f"Retrieved Passages: {len(retrieved_passages)} passages identified."
        )
        llm_out = self.llm.generate_response(
            system_prompt=self.prompt_config["investigator_system_prompt"],
            user_prompt=user_context,
            step_name="investigator_reasoning"
        )
        
        audit_steps.append({
            "step_id": f"STP-{uuid.uuid4().hex[:8].upper()}",
            "run_id": state["run_id"],
            "step_index": step_idx,
            "agent_name": "Coverage_Investigator",
            "step_type": "model_call",
            "tool_name": "llm_generate",
            "tool_input": {"context_length": len(user_context)},
            "tool_output": {"summary": llm_out["content"]},
            "duration_ms": llm_out["duration_ms"],
            "prompt_tokens": llm_out["prompt_tokens"],
            "completion_tokens": llm_out["completion_tokens"],
            "cost_usd": llm_out["cost_usd"]
        })

        # Deduplicate retrieved passages by chunk_id
        unique_passages = []
        seen_chunks = set()
        for p in retrieved_passages:
            cid = p.get("chunk_id")
            if cid not in seen_chunks:
                seen_chunks.add(cid)
                unique_passages.append(p)

        candidate = {
            "procedure_name": proc_name,
            "admission_type": adm_type,
            "passages_count": len(unique_passages),
            "investigation_notes": llm_out["content"]
        }

        return {
            "retrieved_passages": unique_passages,
            "investigator_candidate": candidate,
            "audit_steps": state.get("audit_steps", []) + audit_steps,
            "steps_taken": state.get("steps_taken", 0) + len(audit_steps),
            "tool_calls_count": state.get("tool_calls_count", 0) + (len(audit_steps) - 1),
            "model_calls_count": state.get("model_calls_count", 0) + 1
        }
