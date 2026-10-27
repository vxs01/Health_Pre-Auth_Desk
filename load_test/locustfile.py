"""
Locust Load Testing Suite (Requirements D6, D7, Demonstration Item 9).
Declared Service Level Objective (SLO):
- Target: Complete end-to-end run p95 latency < 2000 ms at up to 20 concurrent hospital submissions.
- Justification (Section 1): Pre-authorisation TPA desk requires real-time coverage guidance within seconds
  during patient admission triage.
- Measurement Methodology: Measures complete run from submission (POST /requests) through final result polling (GET /runs/{run_id}).
"""
import time
import json
from locust import HttpUser, task, between

SAMPLE_REQUESTS = [
    {
        "policy_number": "POL-LOCUST-101",
        "insured_id": "INS-LOC-01",
        "policy_inception_date": "2025-11-27",
        "policy_expiry_date": "2026-11-26",
        "hospital_name": "Apollo Hospitals",
        "hospital_tier": "network",
        "admission_type": "day-care",
        "procedure_name": "Cataract surgery with IOL",
        "diagnosis": "Senile Cataract",
        "room_category": "day_care_bed",
        "estimated_cost": 42000.0,
        "room_rent_per_day": 0.0,
        "proposed_admission_date": "2026-10-27",
        "prior_coverage_months": 0,
        "declared_pre_existing_conditions": [],
        "clinical_notes": "Planned cataract phacoemulsification."
    },
    {
        "policy_number": "POL-LOCUST-102",
        "insured_id": "INS-LOC-02",
        "policy_inception_date": "2023-01-01",
        "policy_expiry_date": "2026-12-31",
        "hospital_name": "Fortis Healthcare",
        "hospital_tier": "network",
        "admission_type": "day-care",
        "procedure_name": "Tonsillectomy with adenoidectomy",
        "diagnosis": "Recurrent tonsillitis",
        "room_category": "day_care_bed",
        "estimated_cost": 36000.0,
        "room_rent_per_day": 0.0,
        "proposed_admission_date": "2026-10-27",
        "prior_coverage_months": 0,
        "declared_pre_existing_conditions": [],
        "clinical_notes": "Day care ENT surgery."
    }
]

class PreAuthLoadTestUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def submit_and_poll_complete_run(self):
        req_payload = SAMPLE_REQUESTS[int(time.time() * 1000) % len(SAMPLE_REQUESTS)]
        start_t = time.time()

        # 1. Submission
        with self.client.post("/requests", json=req_payload, catch_response=True) as resp:
            if resp.status_code != 202:
                resp.failure(f"Failed to submit: {resp.status_code} - {resp.text}")
                return
            run_id = resp.json().get("run_id")

        # 2. Polling until complete (complete run latency)
        completed = False
        poll_start = time.time()
        max_poll_seconds = 15.0

        while time.time() - poll_start < max_poll_seconds:
            with self.client.get(f"/runs/{run_id}", name="/runs/[run_id]", catch_response=True) as poll_resp:
                if poll_resp.status_code == 200:
                    status = poll_resp.json().get("status")
                    if status in ["completed", "escalated"]:
                        completed = True
                        break
            time.sleep(0.08)

        total_latency_ms = (time.time() - start_t) * 1000.0
        if not completed:
            self.environment.events.request.fire(
                request_type="E2E",
                name="CompleteRun",
                response_time=total_latency_ms,
                response_length=0,
                exception=Exception("Timeout waiting for run completion")
            )
        else:
            self.environment.events.request.fire(
                request_type="E2E",
                name="CompleteRun",
                response_time=total_latency_ms,
                response_length=1,
                exception=None
            )
