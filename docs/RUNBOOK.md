# Operations Runbook — Health Insurance Pre-Authorisation Desk

This runbook provides actionable procedures for operating, diagnosing, and maintaining the Pre-Authorisation Desk in development and production environments.

---

## 1. Quick Operations Reference

| Component | Port | Health / Status Endpoint |
| :--- | :--- | :--- |
| **API Server & UI** | `8000` | `http://localhost:8000/health` |
| **Prometheus Metrics** | `8000` / `9090` | `http://localhost:8000/metrics` |
| **Jaeger Tracing UI** | `16686` | `http://localhost:16686` |
| **Corpus Manifest** | `8000` | `http://localhost:8000/corpus/manifest` |
| **Circuit Breaker Status** | `8000` | `http://localhost:8000/circuit-breaker` |

---

## 2. Startup Procedures

### 2.1 Zero-Dependency Standalone Local Startup
To run without Docker containers using the built-in SQLite database and in-process asynchronous task queue:

```bash
# 1. Activate virtual environment
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# 2. Re-index policy corpus (if not already indexed)
python -m backend.app.ingestion.run_pipeline

# 3. Launch FastAPI server (with embedded worker)
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at `http://localhost:8000/` to access the Pre-Authorisation Desk web interface.

### 2.2 Docker Compose Multi-Service Startup
To launch the full 6-service topology (API, Asynchronous Worker, Redis, PostgreSQL, Prometheus, Jaeger):

```bash
# Launch all containers
docker-compose up -d --build

# Verify container health
docker-compose ps

# Tail logs of the agent worker
docker-compose logs -f agent-worker
```

---

## 3. Failure Mode 1: LLM Provider Timeout / Outage (Circuit Breaker Tripped)

### 3.1 Description & Severity
- **Severity**: HIGH (Automated LLM reasoning unavailable)
- **Root Cause**: Upstream LLM provider API (OpenAI, Gemini, or local Ollama) is returning HTTP 429 (Rate Limit Exceeded), HTTP 503 (Service Unavailable), or experiencing socket timeouts (>30s).
- **System Safeguard**: The system's built-in **Circuit Breaker** trips to the `OPEN` state after 3 consecutive failures to prevent cascade failures and blocking worker threads.

### 3.2 Symptoms
1. Pre-authorisation requests take longer than usual (~30 seconds) before falling back.
2. In the UI, runs complete with an escalation notice: *"LLM Circuit breaker tripped to OPEN state. Request routed to medical-review for manual review."*
3. The Prometheus metric `preauth_circuit_breaker_state` reads `2.0` (OPEN).

### 3.3 Confirmation Steps
1. Query the circuit breaker API endpoint:
   ```bash
   curl -s http://localhost:8000/circuit-breaker
   ```
   **Expected output when tripped**:
   ```json
   {
     "state": "open",
     "failure_count": 3,
     "failure_threshold": 3,
     "recovery_timeout": 60.0,
     "last_failure_time": 1729864200.12
   }
   ```
2. Check Prometheus metrics:
   ```bash
   curl -s http://localhost:8000/metrics | grep preauth_circuit_breaker_state
   ```

### 3.4 Recovery Procedure
1. **Verify Upstream Provider**: Test provider connectivity or verify API key validity and quota:
   ```bash
   curl -I https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
   ```
2. **Switch to Stub/Fallback Mode (if provider is down)**:
   In `.env` or container environment variables, set:
   ```bash
   LLM_PROVIDER=stub
   ```
   Restart worker: `docker-compose restart agent-worker api`
3. **Manual Circuit Breaker Reset**:
   Once the provider is healthy, trigger an immediate manual reset without restarting the server:
   ```bash
   curl -X POST http://localhost:8000/circuit-breaker/reset
   ```
   Verify state returns to `"closed"`:
   ```json
   {"message": "Circuit breaker reset to CLOSED state", "state": "closed"}
   ```

---

## 4. Failure Mode 2: Ingestion Quarantine Spike (Malformed Requests)

### 4.1 Description & Severity
- **Severity**: MEDIUM (Ingestion rejected; patient claims delayed)
- **Root Cause**: A partner hospital or Third-Party Administrator (TPA) software upgrade is sending non-compliant JSON payloads, violating schema boundaries (e.g., negative costs, string dates in invalid formats, or room rent exceeding total cost).

### 4.2 Symptoms
1. Hospital client receives HTTP `422 Unprocessable Entity` responses.
2. The Prometheus metric `preauth_quarantined_total` increases rapidly.
3. No new entries appear in active runs, but entries accumulate in `/quarantined`.

### 4.3 Confirmation Steps
1. Fetch the latest quarantined payloads and error reasons:
   ```bash
   curl -s http://localhost:8000/quarantined?limit=10
   ```
2. Inspect the `errors` array in each quarantined record. Common error patterns:
   - `CROSS_FIELD_VALIDATION_ERROR`: `Room rent (₹12,000) cannot exceed estimated total cost (₹10,000)`.
   - `CROSS_FIELD_VALIDATION_ERROR`: `Policy expiry date (2024-01-01) must be strictly after inception date (2024-06-01)`.
   - `VALUE_OUT_OF_RANGE`: `estimated_cost ₹5,500,000 exceeds maximum allowable limit of ₹5,000,000`.

### 4.4 Recovery & Resolution Procedure
1. **Identify Errant Integration Source**:
   Examine the `hospital_id` and payload fields in the quarantined records.
2. **Contact TPA / Hospital Integration Team**:
   Provide the exact JSON schema and quarantine diagnostic record returned by `GET /quarantined/{quarantine_id}`.
3. **Replaying Corrected Requests**:
   Hospital submits corrected payload via standard `POST /requests`. The quarantine table acts as an immutable audit log and does not need to be manually cleared.

---

## 5. Maintenance Procedures

### 5.1 Corpus Re-Indexing & Verification
When a new policy wording or day-care schedule PDF is added to `data/raw/`:
```bash
# 1. Place new PDFs in data/raw/
# 2. Run indexing CLI
python -m backend.app.ingestion.run_pipeline

# 3. Or trigger via API
curl -X POST http://localhost:8000/corpus/reindex
```
Check `data/processed/corpus_manifest.json` to verify chunk counts, checksums, and indexing latency.

### 5.2 Database Backup (SQLite / PostgreSQL)
- **SQLite**:
  ```bash
  sqlite3 data/preauth_desk.db ".backup 'data/preauth_desk_backup.db'"
  ```
- **PostgreSQL (Docker)**:
  ```bash
  docker-compose exec db pg_dump -U preauth_user preauth_desk > backup_preauth.sql
  ```
