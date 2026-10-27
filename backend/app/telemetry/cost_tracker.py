"""
Token & Cost Accounting per Step and per Run (Requirement L5).
Tracks prompt tokens, completion tokens, and dollar cost attributed to each step and run.
Calculates cost per 100 runs and identifies the largest single cost driver.
"""
from typing import Dict, Any

# Standard pricing for LLM calls (e.g. Gemini Flash / GPT-4o-mini tier: $0.15 / 1M prompt, $0.60 / 1M completion)
COST_PER_MILLION_PROMPT_TOKENS = 0.15
COST_PER_MILLION_COMPLETION_TOKENS = 0.60

class CostTracker:
    @staticmethod
    def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
        cost = (prompt_tokens / 1_000_000.0) * COST_PER_MILLION_PROMPT_TOKENS + \
               (completion_tokens / 1_000_000.0) * COST_PER_MILLION_COMPLETION_TOKENS
        return round(cost, 6)

    @classmethod
    def estimate_tokens_from_text(cls, text: str) -> int:
        if not text:
            return 0
        # Average heuristic: 1 token ~= 4 English characters
        return max(1, len(text) // 4)

    @classmethod
    def build_cost_summary(cls, steps: list) -> Dict[str, Any]:
        total_prompt_tokens = sum(s.get("prompt_tokens", 0) for s in steps)
        total_completion_tokens = sum(s.get("completion_tokens", 0) for s in steps)
        total_tokens = total_prompt_tokens + total_completion_tokens
        total_cost_usd = sum(s.get("cost_usd", 0.0) for s in steps)
        
        # Identify largest cost driver
        driver_costs = {}
        for s in steps:
            key = s.get("tool_name") or s.get("agent_name") or s.get("step_type")
            driver_costs[key] = driver_costs.get(key, 0.0) + s.get("cost_usd", 0.0)
            
        largest_driver = max(driver_costs.items(), key=lambda x: x[1])[0] if driver_costs else "none"

        return {
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost_usd, 6),
            "estimated_cost_per_100_runs_usd": round(total_cost_usd * 100.0, 4),
            "largest_cost_driver": largest_driver,
            "pricing_basis": "$0.15/1M input tokens, $0.60/1M output tokens"
        }
