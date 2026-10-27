"""
Worker Process Runner (Requirements A4, A7, D3).
Can be launched independently and scaled to multiple instances (e.g. --scale agent-worker=3).
Continuously pops and processes pre-authorisation jobs from the queue.
"""
import time
import os
from backend.app.worker.queue import get_task_queue
from backend.app.agents.graph import get_orchestrator

def start_worker():
    worker_id = os.environ.get("HOSTNAME", f"worker-{os.getpid()}")
    print(f"[{worker_id}] Starting Health Pre-Authorisation Agent Worker...")
    queue = get_task_queue()
    orchestrator = get_orchestrator()

    while True:
        try:
            job = queue.pop_job(timeout_sec=3)
            if job:
                run_id = job.get("run_id")
                req_id = job.get("request_data", {}).get("request_id")
                print(f"[{worker_id}] Processing Job run_id={run_id} (req={req_id})...")
                res = orchestrator.execute_run(
                    req_data=job["request_data"],
                    prompt_version=job.get("prompt_version", "v2.0.0"),
                    injection_detected=job.get("injection_detected", False),
                    run_id=run_id,
                    trace_id=job.get("trace_id")
                )
                print(f"[{worker_id}] Completed run_id={run_id} -> Route: {res['route']} ({res['processing_duration_ms']}ms)")
            else:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print(f"[{worker_id}] Worker stopped by user.")
            break
        except Exception as e:
            print(f"[{worker_id}] Worker error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    start_worker()
