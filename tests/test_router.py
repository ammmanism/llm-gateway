import pytest
from src.router.smart_router import smart_router, ProviderState, EWMATracker, CircuitBreaker

def test_router_selection():
    # Force a scenario
    # Deepseek is cheap and fast. It should win if available.
    decision = smart_router.route(request_tokens=1000)
    # Could be random due to A/B testing (10%), but most likely deepseek.
    assert decision.name in ["deepseek", "gemini", "groq", "openai", "anthropic"]

def test_ewma_tracker():
    tracker = EWMATracker(0.2, 500)
    tracker.update(100)
    assert tracker.value == 0.2 * 100 + 0.8 * 500
    
def test_circuit_breaker():
    cb = CircuitBreaker()
    for _ in range(5):
        cb.record_failure()
    assert cb.state == "OPEN"
