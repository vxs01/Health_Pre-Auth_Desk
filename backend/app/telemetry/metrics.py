"""
Prometheus Metrics & Observability (Requirement D5, A6).
Exposes standard metrics for scrapers, tracking request rates, route distribution,
quarantines, agent steps, tool calls, latency percentiles, and token usage.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Counters
PREAUTH_REQUESTS_TOTAL = Counter(
    "preauth_requests_total",
    "Total pre-authorisation requests received",
    ["status", "route"]
)

PREAUTH_QUARANTINED_TOTAL = Counter(
    "preauth_quarantined_total",
    "Total requests quarantined at ingestion boundary",
    ["reason"]
)

PREAUTH_AGENT_STEPS_TOTAL = Counter(
    "preauth_agent_steps_total",
    "Total steps executed by agents",
    ["agent_name", "step_type"]
)

PREAUTH_TOOL_CALLS_TOTAL = Counter(
    "preauth_tool_calls_total",
    "Total tool calls executed by agents",
    ["tool_name"]
)

PREAUTH_CIRCUIT_BREAKER_TRIPS = Counter(
    "preauth_circuit_breaker_trips_total",
    "Total times the model provider circuit breaker tripped to OPEN"
)

PREAUTH_TOKENS_TOTAL = Counter(
    "preauth_tokens_total",
    "Total tokens consumed",
    ["token_type"] # prompt, completion
)

PREAUTH_COST_USD_TOTAL = Counter(
    "preauth_cost_usd_total",
    "Estimated total cost in USD for model calls"
)

# Histograms
PREAUTH_RUN_LATENCY_SECONDS = Histogram(
    "preauth_run_latency_seconds",
    "Complete request execution latency from submission to completion",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0]
)

PREAUTH_STEP_LATENCY_SECONDS = Histogram(
    "preauth_step_latency_seconds",
    "Latency of individual agent and tool steps",
    ["step_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# Gauges
PREAUTH_CORPUS_FRESHNESS_TIMESTAMP = Gauge(
    "preauth_corpus_freshness_timestamp",
    "Unix timestamp when the active corpus index was built"
)

PREAUTH_CIRCUIT_BREAKER_STATE = Gauge(
    "preauth_circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=HALF-OPEN, 2=OPEN)"
)

def get_metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
