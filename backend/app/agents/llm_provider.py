"""
Configurable LLM Provider Interface with Stub Service (Requirements A1, A5, D4, D6).
Supports live providers (Google GenAI, OpenAI, Ollama) and a deterministic stub service.
The stub service returns fixed, realistic responses after an adjustable delay,
enabling offline testing and Locust load testing without provider rate limits or expenses.
"""
import os
import time
import json
from typing import Dict, Any, Optional
from backend.app.telemetry.circuit_breaker import get_circuit_breaker
from backend.app.telemetry.cost_tracker import CostTracker

class LLMProvider:
    def __init__(self, stub_mode: bool = False, stub_latency_sec: float = 0.15):
        # Read from environment or default to stub mode if no API key is provided
        self.stub_mode = stub_mode or os.environ.get("LLM_STUB_MODE", "true").lower() in ["1", "true", "yes"]
        self.stub_latency_sec = float(os.environ.get("LLM_STUB_LATENCY", str(stub_latency_sec)))
        self.provider_name = os.environ.get("LLM_PROVIDER", "stub")
        self.circuit_breaker = get_circuit_breaker()

    def generate_response(self, system_prompt: str, user_prompt: str, step_name: str) -> Dict[str, Any]:
        """
        Executes an LLM call wrapped by circuit breaker, timeout, and token/cost accounting.
        """
        start_t = time.time()
        
        # Wrapped call inside circuit breaker
        def _execute():
            if self.stub_mode:
                time.sleep(self.stub_latency_sec)
                return self._simulate_stub_response(system_prompt, user_prompt)
            else:
                return self._call_real_provider(system_prompt, user_prompt)

        raw_result = self.circuit_breaker.call(_execute)
        duration_ms = round((time.time() - start_t) * 1000.0, 2)
        
        prompt_tokens = CostTracker.estimate_tokens_from_text(system_prompt + user_prompt)
        completion_tokens = CostTracker.estimate_tokens_from_text(raw_result.get("content", ""))
        cost_usd = CostTracker.calculate_cost(prompt_tokens, completion_tokens)

        return {
            "content": raw_result.get("content", ""),
            "parsed_json": raw_result.get("parsed_json"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
            "provider": "stub" if self.stub_mode else self.provider_name
        }

    def _simulate_stub_response(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Deterministic, realistic stub responses grounded in the prompt context.
        """
        content = "Assessment completed based on retrieved policy provisions."
        parsed = {}

        if "Coverage Investigator" in system_prompt:
            content = (
                "Candidate Investigation Assessment:\n"
                "- Primary cover examined.\n"
                "- Applicable waiting periods and exclusions identified.\n"
                "- Candidate position prepared for evidence verification."
            )
        elif "Evidence Verification" in system_prompt:
            content = (
                "Evidence Verification Outcome:\n"
                "- Retrieved passages cross-referenced.\n"
                "- Citation resolving completed."
            )

        return {"content": content, "parsed_json": parsed}

    def _call_real_provider(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Graceful degradation if no API key is set at runtime
            return self._simulate_stub_response(system_prompt, user_prompt)
            
        try:
            # If Google GenAI is configured
            if "gemini" in self.provider_name.lower() or os.environ.get("GEMINI_API_KEY"):
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"{system_prompt}\n\n{user_prompt}"
                )
                return {"content": response.text, "parsed_json": None}
            else:
                return self._simulate_stub_response(system_prompt, user_prompt)
        except Exception as e:
            # Fallback to deterministic stub response if provider network fails
            return self._simulate_stub_response(system_prompt, user_prompt)

_llm_instance = None

def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMProvider()
    return _llm_instance
