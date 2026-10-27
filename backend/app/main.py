"""
Health Insurance Pre-Authorisation Desk — Production REST API (Requirements F1, F2, F8, D1, D5, L6).
Enforces schema validation at ingestion boundary, quarantines malformed requests,
dispatches asynchronous execution to agent workers, and exposes telemetry and metrics.
"""
import os
import time
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import ValidationError

from backend.app.contracts.preauth import (
    PreAuthRequest,
    PreAuthResponse,
    QuarantineRecord,
    FeedbackRequest,
    FeedbackStats
)
from backend.app.guardrails.injection import PromptInjectionGuard
from backend.app.guardrails.filter import OutputFilter, ToxicityGuard
from backend.app.storage.database import StorageService
from backend.app.worker.queue import get_task_queue
from backend.app.ingestion.manifest import CorpusManifest
from backend.app.telemetry.metrics import (
    get_metrics_payload,
    PREAUTH_REQUESTS_TOTAL,
    PREAUTH_QUARANTINED_TOTAL,
    PREAUTH_CIRCUIT_BREAKER_STATE,
    PREAUTH_CORPUS_FRESHNESS_TIMESTAMP
)
from backend.app.telemetry.circuit_breaker import get_circuit_breaker

app = FastAPI(
    title="Health Insurance Pre-Authorisation Desk API",
    description="Multi-Agent RAG System for Hospital Pre-Authorisation Coverage Triage & Verification",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Update corpus freshness gauge on startup
manifest_data = CorpusManifest.load_manifest()
if manifest_data and "last_built_at" in manifest_data:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(manifest_data["last_built_at"].replace("Z", "+00:00"))
        PREAUTH_CORPUS_FRESHNESS_TIMESTAMP.set(dt.timestamp())
    except Exception:
        pass

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or f"CORR-{uuid.uuid4().hex[:12].upper()}"
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response

@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serves the Health Insurance Pre-Authorisation Desk web client UI (Requirement A8)."""
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return {"message": "Health Pre-Authorisation Desk API online. UI available at /docs"}

@app.get("/health", tags=["System"])
def health_check():
    """Health status endpoint (Requirement F8)."""
    cb = get_circuit_breaker()
    manifest = CorpusManifest.load_manifest()
    
    status_code = "healthy"
    cb_state = cb.check_state()
    if cb_state == "OPEN":
        status_code = "degraded"
        
    return {
        "status": status_code,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "circuit_breaker": cb_state,
        "corpus_loaded": bool(manifest),
        "corpus_documents": manifest.get("total_documents", 0),
        "corpus_chunks": manifest.get("total_chunks", 0),
        "llm_provider": os.environ.get("LLM_PROVIDER", "stub"),
        "stub_mode": os.environ.get("LLM_STUB_MODE", "true").lower() in ["1", "true", "yes"]
    }

@app.get("/metrics", tags=["Observability"])
def metrics():
    """Prometheus metrics scrape endpoint (Requirement D5)."""
    cb = get_circuit_breaker()
    state_code = 0 if cb.state == "CLOSED" else (1 if cb.state == "HALF-OPEN" else 2)
    PREAUTH_CIRCUIT_BREAKER_STATE.set(state_code)
    
    payload, content_type = get_metrics_payload()
    return Response(content=payload, media_type=content_type)

@app.post("/requests", status_code=status.HTTP_202_ACCEPTED, tags=["Pre-Authorisation"])
async def submit_preauth_request(request: Request, prompt_version: Optional[str] = "v2.0.0"):
    """
    Ingestion Boundary (Requirements F1, F2, D1).
    Enforces strict data contracts, range, and cross-field validation.
    Quarantines malformed inputs with field-level errors and halts execution before any agent starts.
    """
    raw_payload = await request.json()
    req_id = raw_payload.get("request_id") or f"REQ-{uuid.uuid4().hex[:8].upper()}"

    # 1. Strict Ingestion Boundary Validation
    try:
        validated_request = PreAuthRequest(**raw_payload)
    except ValidationError as e:
        # Quarantine malformed record immediately (Requirement F2, D1, Demonstration Item 4)
        errors = e.errors()
        field_errors = [{"field": " -> ".join(str(loc) for loc in err["loc"]), "message": err["msg"], "type": err["type"]} for err in errors]
        quarantine_id = f"QRN-{uuid.uuid4().hex[:8].upper()}"
        
        StorageService.save_quarantined_request(
            quarantine_id=quarantine_id,
            request_id=req_id,
            raw_payload=raw_payload,
            errors=field_errors,
            reason="Schema and cross-field constraints validation failed at ingestion boundary."
        )
        PREAUTH_QUARANTINED_TOTAL.labels(reason="validation_error").inc()
        
        return JSONResponse(
            status_code=422,
            content={
                "error": "Request rejected at ingestion boundary.",
                "quarantine_id": quarantine_id,
                "request_id": req_id,
                "field_errors": field_errors,
                "agent_executed": False,
                "message": "Malformed requests are quarantined and never passed to agent reasoning."
            }
        )

    # 2. Prompt Injection & Toxicity Security Guardrails (Requirement L4, Demonstration Item 7)
    clinical_text = f"{validated_request.procedure_name} {validated_request.diagnosis} {validated_request.clinical_notes or ''}"
    is_hostile, hostile_patterns = PromptInjectionGuard.scan_text(clinical_text)
    is_toxic = ToxicityGuard.check_toxicity(clinical_text)
    
    if is_toxic:
        quarantine_id = f"QRN-{uuid.uuid4().hex[:8].upper()}"
        StorageService.save_quarantined_request(
            quarantine_id=quarantine_id,
            request_id=req_id,
            raw_payload=raw_payload,
            errors=[{"field": "clinical_notes", "message": "Harmful or toxic language detected"}],
            reason="Toxicity guardrail triggered."
        )
        PREAUTH_QUARANTINED_TOTAL.labels(reason="toxic_content").inc()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Submission contains inappropriate or toxic terminology.", "quarantine_id": quarantine_id}
        )

    req_dict = validated_request.model_dump()
    StorageService.save_request(req_dict)

    # 3. Asynchronous Job Dispatch (Requirement A4)
    queue = get_task_queue()
    run_id = queue.enqueue(
        payload=req_dict,
        prompt_version=prompt_version or "v2.0.0",
        injection_detected=is_hostile
    )

    return {
        "run_id": run_id,
        "request_id": validated_request.request_id,
        "status": "processing",
        "poll_url": f"/runs/{run_id}",
        "trace_url": f"/runs/{run_id}/trace",
        "prompt_version": prompt_version,
        "security_flags": {"prompt_injection_flagged": is_hostile, "matched_patterns": hostile_patterns},
        "message": "Pre-authorisation request accepted and dispatched to agent worker queue."
    }

@app.get("/runs/{run_id}", tags=["Pre-Authorisation"])
def get_run_status(run_id: str):
    """Returns processing status, verified coverage recommendation, and cited clauses (Requirement F5, F6)."""
    run_data = StorageService.get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run_data

@app.get("/runs/{run_id}/trace", tags=["Observability"])
def get_run_audit_trace(run_id: str):
    """
    Audit & Observability Trace (Requirements A6, D5, Demonstration Item 3).
    Reconstructs entire chronological timeline: tool calls, queries, retrieved passages, latencies, and token costs.
    """
    run_data = StorageService.get_run(run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
        
    steps = StorageService.get_run_audit_steps(run_id)
    return {
        "run_id": run_id,
        "request_id": run_data.get("request_id"),
        "trace_id": run_data.get("trace_id"),
        "final_route": run_data.get("route"),
        "verification_status": run_data.get("verification_status"),
        "total_steps": len(steps),
        "total_duration_ms": run_data.get("processing_duration_ms"),
        "cost_breakdown": run_data.get("cost_breakdown"),
        "prompt_version": run_data.get("prompt_version"),
        "timeline_steps": steps
    }

@app.get("/runs", tags=["Pre-Authorisation"])
def list_recent_runs(limit: int = 50):
    """Lists recent pre-authorisation runs."""
    return StorageService.list_runs(limit=limit)

@app.get("/quarantined", tags=["Security & Quarantine"])
def list_quarantined_requests(limit: int = 50):
    """Lists quarantined malformed or hostile requests with validation errors (Requirement D1)."""
    return StorageService.list_quarantined(limit=limit)

@app.post("/feedback", tags=["Quality & Feedback"])
def submit_feedback(fb: FeedbackRequest):
    """Persists medical officer feedback and reasons (Requirement L6)."""
    fb_id = f"FB-{uuid.uuid4().hex[:8].upper()}"
    StorageService.save_feedback(
        feedback_id=fb_id,
        run_id=fb.run_id,
        satisfactory=fb.satisfactory,
        reason=fb.reason,
        reviewer_id=fb.reviewer_id or "medical-officer-01"
    )
    return {"feedback_id": fb_id, "status": "persisted", "message": "Feedback recorded."}

@app.get("/feedback/stats", tags=["Quality & Feedback"])
def get_feedback_statistics():
    """Returns aggregated feedback satisfaction metrics and recent reviews."""
    return StorageService.get_feedback_stats()

@app.get("/corpus/manifest", tags=["Corpus Management"])
def get_corpus_manifest():
    """Returns the active corpus manifest and data freshness metrics (Requirement D2)."""
    manifest = CorpusManifest.load_manifest()
    if not manifest:
        raise HTTPException(status_code=404, detail="Corpus manifest not found.")
    return manifest

@app.post("/corpus/reindex", tags=["Corpus Management"])
def trigger_corpus_reindexing():
    """Re-runs the corpus ingestion pipeline from the API (Requirement D2)."""
    from backend.app.ingestion.run_pipeline import run_ingestion_pipeline
    manifest = run_ingestion_pipeline()
    return {"status": "success", "manifest": manifest}

@app.get("/circuit-breaker", tags=["Reliability"])
def get_circuit_breaker_status():
    """Returns current circuit breaker state, failure count, and cooldown."""
    cb = get_circuit_breaker()
    return {
        "state": cb.check_state(),
        "failure_count": cb.failure_count,
        "failure_threshold": cb.failure_threshold,
        "cooldown_seconds": cb.cooldown_seconds
    }

@app.post("/circuit-breaker/reset", tags=["Reliability"])
def reset_circuit_breaker():
    """Resets circuit breaker to CLOSED normal operation."""
    cb = get_circuit_breaker()
    cb.record_success()
    return {"status": "reset", "state": cb.state}
