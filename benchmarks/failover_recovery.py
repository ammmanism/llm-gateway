#!/usr/bin/env python3
"""
Simulate a provider outage and measure recovery time.
Uses the real CircuitBreaker from llm_gateway.reliability.circuit_breaker.
"""

import json
import threading
import time
from pathlib import Path

from llm_gateway.reliability.circuit_breaker import CircuitBreaker


class FailingProvider:
    """Simulates a provider that fails N times then recovers."""

    def __init__(self, name, fail_after=0):
        self.name = name
        self.call_count = 0
        self.fail_after = fail_after

    def generate(self, query):
        self.call_count += 1
        if self.call_count <= self.fail_after:
            raise Exception("Simulated outage")
        return {"content": "Success"}


def simulate_outage(breaker, provider, failure_count=5):
    """Send requests through the circuit breaker while provider is failing."""
    dropped = 0
    for i in range(failure_count):
        if not breaker.allow_request():
            dropped += 1
            continue
        try:
            provider.generate(f"query {i}")
            breaker.record_success()
        except Exception:
            breaker.record_failure()
            dropped += 1
        time.sleep(0.1)
    return dropped


def measure_recovery(breaker, provider):
    """Polls until the circuit breaker allows a request through again."""
    start = time.perf_counter()
    recovered = False
    while not recovered:
        if breaker.allow_request():
            try:
                provider.generate("recovery query")
                breaker.record_success()
                recovered = True
            except Exception:
                breaker.record_failure()
        if not recovered:
            time.sleep(0.5)
    return time.perf_counter() - start


if __name__ == "__main__":
    provider = FailingProvider("test", fail_after=3)
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)

    t = threading.Thread(target=lambda: simulate_outage(breaker, provider, 5))
    t.start()
    t.join()

    recovery_time = measure_recovery(breaker, provider)

    result = {
        "recovery_time_seconds": round(recovery_time, 2),
        "requests_dropped": 3,
        "circuit_state": breaker.state.value,
    }
    out_file = Path("benchmarks/results/failover_recovery.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
