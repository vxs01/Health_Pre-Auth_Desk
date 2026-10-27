"""
Model Provider Circuit Breaker & Fallback Protection (Requirements A5, D6, Demonstration Item 8).
Tracks consecutive model provider failures and transitions between:
- CLOSED: Normal operation, all model requests pass through.
- OPEN: Circuit tripped after failure threshold exceeded; fails fast to graceful degradation fallback.
- HALF-OPEN: Testing recovery after cooldown period expires.
"""
import time
from typing import Callable, Any, Tuple

class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 20.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = time.time()
        self.last_failure_time = 0.0

    def record_success(self):
        self.failure_count = 0
        if self.state != "CLOSED":
            self.state = "CLOSED"
            self.last_state_change = time.time()

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold and self.state == "CLOSED":
            self.state = "OPEN"
            self.last_state_change = time.time()

    def check_state(self) -> str:
        if self.state == "OPEN":
            if time.time() - self.last_state_change > self.cooldown_seconds:
                self.state = "HALF-OPEN"
                self.last_state_change = time.time()
        return self.state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        state = self.check_state()
        if state == "OPEN":
            raise CircuitBreakerOpenException(
                f"Model provider circuit breaker is OPEN (failures={self.failure_count}). "
                f"Cooldown remaining: {max(0, int(self.cooldown_seconds - (time.time() - self.last_state_change)))}s."
            )
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e

_circuit_breaker_instance = None

def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker_instance
    if _circuit_breaker_instance is None:
        _circuit_breaker_instance = CircuitBreaker()
    return _circuit_breaker_instance
