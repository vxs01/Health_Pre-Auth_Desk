"""
Asynchronous Task Queue & Worker Engine (Requirements A4, A7, D3).
Supports distributed Redis-based queue for multi-container scaled workers,
with transparent fallback to a persistent database-backed queue for local development.
"""
import os
import json
import time
import uuid
import threading
from typing import Dict, Any, Optional
from datetime import datetime
from backend.app.storage.database import SessionLocal, DBRun
from backend.app.agents.graph import get_orchestrator
from backend.app.telemetry.metrics import PREAUTH_REQUESTS_TOTAL

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = "preauth_jobs_queue"

class TaskQueue:
    def __init__(self):
        self.redis_client = None
        self.use_redis = False
        
        # Attempt connecting to Redis if configured
        if os.environ.get("USE_REDIS", "false").lower() in ["true", "1"]:
            try:
                import redis
                self.redis_client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2)
                self.redis_client.ping()
                self.use_redis = True
                print(f"[Queue] Connected to Redis queue at {REDIS_URL}")
            except Exception as e:
                print(f"[Queue] Redis unavailable ({e}). Using persistent DB queue.")
                self.use_redis = False

    def enqueue(self, payload: Dict[str, Any], prompt_version: str = "v2.0.0", injection_detected: bool = False) -> str:
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        trace_id = f"TRC-{uuid.uuid4().hex[:12].upper()}"
        job_data = {
            "run_id": run_id,
            "trace_id": trace_id,
            "request_data": payload,
            "prompt_version": prompt_version,
            "injection_detected": injection_detected,
            "enqueued_at": datetime.utcnow().isoformat() + "Z"
        }

        # Initialize pending run in DB
        db = SessionLocal()
        try:
            pending_run = DBRun(
                run_id=run_id,
                request_id=payload.get("request_id", "UNKNOWN"),
                trace_id=trace_id,
                status="processing",
                route="pending",
                verification_status="pending",
                result_json=json.dumps({"run_id": run_id, "status": "processing", "message": "Queued for agent investigation."}),
                prompt_version=prompt_version,
                processing_duration_ms=0.0
            )
            db.merge(pending_run)
            db.commit()
        finally:
            db.close()

        if self.use_redis and self.redis_client:
            self.redis_client.rpush(QUEUE_NAME, json.dumps(job_data))
        else:
            # Persistent in-memory/thread task runner for local single-process mode
            threading.Thread(target=self._process_single_job, args=(job_data,), daemon=True).start()

        return run_id

    def pop_job(self, timeout_sec: int = 2) -> Optional[Dict[str, Any]]:
        if self.use_redis and self.redis_client:
            item = self.redis_client.blpop(QUEUE_NAME, timeout=timeout_sec)
            if item:
                return json.loads(item[1])
        return None

    def _process_single_job(self, job_data: Dict[str, Any]):
        orchestrator = get_orchestrator()
        orchestrator.execute_run(
            req_data=job_data["request_data"],
            prompt_version=job_data.get("prompt_version", "v2.0.0"),
            injection_detected=job_data.get("injection_detected", False),
            run_id=job_data.get("run_id"),
            trace_id=job_data.get("trace_id")
        )

_queue_instance = None

def get_task_queue() -> TaskQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = TaskQueue()
    return _queue_instance
