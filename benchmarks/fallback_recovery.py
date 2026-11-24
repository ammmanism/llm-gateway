#!/usr/bin/env python3
"""
Simulate a provider outage and measure recovery time.
Uses the real CircuitBreaker from llm_gateway.reliability.circuit_breaker.

Generates CSV evidence for fallback recovery timeline.
"""
import csv
import json
import time
from pathlib import Path

from llm_gateway.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
)


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


def simulate_outage(breaker, provider, failure_count=5, events=None):
    """Send requests through the circuit breaker while provider is failing."""
    dropped = 0
    for i in range(failure_count):
        timestamp = time.time()
        try:
            breaker.allow_request()
        except CircuitOpenError as e:
            e.provider = provider.name
            dropped += 1
            if events is not None:
                events.append({
                    "timestamp": timestamp,
                    "event": "request_rejected",
                    "circuit_state": breaker.get_state().value,
                    "error": str(e),
                    "provider": e.provider
                })
            continue

        try:
            provider.generate(f"query {i}")
            breaker.record_success()
            if events is not None:
                events.append({
                    "timestamp": timestamp,
                    "event": "request_success",
                    "circuit_state": breaker.get_state().value,
                    "provider": provider.name
                })
        except Exception as e:
            breaker.record_failure()
            dropped += 1
            if events is not None:
                events.append({
                    "timestamp": timestamp,
                    "event": "request_failed",
                    "circuit_state": breaker.get_state().value,
                    "error": str(e),
                    "provider": provider.name
                })
        time.sleep(0.05)
    return dropped


def measure_recovery(breaker, provider, events=None):
    """Polls until the circuit breaker allows a request through again."""
    start = time.perf_counter()
    recovered = False
    poll_count = 0
    while not recovered:
        poll_count += 1
        timestamp = time.time()
        try:
            breaker.allow_request()
        except CircuitOpenError as e:
            e.provider = provider.name
            if events is not None:
                events.append({
                    "timestamp": timestamp,
                    "event": "recovery_poll_rejected",
                    "circuit_state": breaker.get_state().value,
                    "error": str(e),
                    "poll_count": poll_count
                })
            time.sleep(0.1)
            continue

        try:
            provider.generate("recovery query")
            breaker.record_success()
            recovered = True
            if events is not None:
                events.append({
                    "timestamp": timestamp,
                    "event": "recovery_success",
                    "circuit_state": breaker.get_state().value,
                    "poll_count": poll_count,
                    "provider": provider.name
                })
        except Exception as e:
            breaker.record_failure()
            if events is not None:
                events.append({
                    "timestamp": timestamp,
                    "event": "recovery_probe_failed",
                    "circuit_state": breaker.get_state().value,
                    "error": str(e),
                    "poll_count": poll_count
                })
            time.sleep(0.1)
    return time.perf_counter() - start


def run_scenario(name, failure_threshold, recovery_timeout, fail_after, max_probes=3):
    """Run a single failover scenario and return results."""
    events = []

    provider = FailingProvider(name, fail_after=fail_after)
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        max_half_open_probes=max_probes,
        name=name,
    )

    # Record initial state
    events.append({
        "timestamp": time.time(),
        "event": "scenario_start",
        "circuit_state": breaker.get_state().value,
        "scenario": name,
        "failure_threshold": failure_threshold,
        "recovery_timeout": recovery_timeout,
        "max_half_open_probes": max_probes
    })

    # Simulate outage
    dropped = simulate_outage(breaker, provider, failure_count=fail_after + 2, events=events)

    # Measure recovery
    recovery_time = measure_recovery(breaker, provider, events=events)

    events.append({
        "timestamp": time.time(),
        "event": "scenario_end",
        "circuit_state": breaker.get_state().value,
        "recovery_time_seconds": recovery_time,
        "requests_dropped": dropped
    })

    return {
        "scenario": name,
        "recovery_time_seconds": round(recovery_time, 3),
        "requests_dropped": dropped,
        "final_circuit_state": breaker.get_state().value,
        "events": events
    }


if __name__ == "__main__":
    # Run multiple scenarios
    scenarios = [
        ("fast_recovery", 3, 0.5, 3),
        ("standard_recovery", 3, 2.0, 3),
        ("slow_recovery", 3, 5.0, 3),
        ("high_threshold", 5, 2.0, 5),
        ("limited_probes", 3, 1.0, 3, 1),  # max_probes=1
    ]

    all_results = []
    all_events = []

    for scenario in scenarios:
        name = scenario[0]
        print(f"Running scenario: {name}")
        result = run_scenario(*scenario)
        all_results.append(result)
        all_events.extend(result["events"])
        print(f"  Recovery time: {result['recovery_time_seconds']}s")
        print(f"  Requests dropped: {result['requests_dropped']}")
        print(f"  Final state: {result['final_circuit_state']}")

    # Write JSON summary
    out_file = Path("benchmarks/results/failover_recovery.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)

    # Write CSV evidence for fallback recovery timeline
    csv_file = Path("data/evidence/fallback_recovery.csv")
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "scenario",
            "failure_threshold",
            "recovery_timeout_s",
            "time_to_detect_ms",
            "time_to_switch_ms",
            "requests_failed_before_open",
            "requests_rejected_while_open",
            "recovery_probe_attempts",
            "recovery_probe_success_rate",
            "recovered",
        ])

        for result in all_results:
            events = result["events"]
            start_time = None
            open_time = None
            closed_time = None
            failed_before_open = 0
            rejected_while_open = 0
            probe_attempts = 0
            probe_successes = 0

            for e in events:
                if e["event"] == "scenario_start":
                    start_time = e["timestamp"]
                elif e["event"] == "request_failed":
                    if e["circuit_state"] == "OPEN" and open_time is None:
                        open_time = e["timestamp"]
                    else:
                        failed_before_open += 1
                elif e["event"] == "request_rejected":
                    rejected_while_open += 1
                elif e["event"] == "recovery_poll_rejected":
                    probe_attempts += 1
                elif e["event"] == "recovery_probe_failed":
                    probe_attempts += 1
                elif e["event"] == "recovery_success":
                    probe_attempts += 1
                    probe_successes += 1
                    if closed_time is None:
                        closed_time = e["timestamp"]

            time_to_detect = 0.0
            time_to_switch = 0.0
            if start_time and open_time:
                time_to_detect = (open_time - start_time) * 1000
            if open_time and closed_time:
                time_to_switch = (closed_time - open_time) * 1000

            probe_rate = (
                probe_successes / probe_attempts if probe_attempts else 0.0
            )
            recovered = 1 if closed_time is not None else 0

            writer.writerow([
                result["scenario"],
                events[0].get("failure_threshold", ""),
                events[0].get("recovery_timeout", ""),
                round(time_to_detect, 1),
                round(time_to_switch, 1),
                failed_before_open,
                rejected_while_open,
                probe_attempts,
                round(probe_rate, 4),
                recovered,
            ])

    # Write detailed event timeline for chart generation
    timeline_file = Path("data/evidence/fallback_timeline_events.csv")
    with open(timeline_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "scenario",
            "relative_time_ms",
            "event",
            "circuit_state",
            "provider",
            "details"
        ])

        for result in all_results:
            scenario = result["scenario"]
            events = result["events"]
            if not events:
                continue
            base_time = events[0]["timestamp"]
            for e in events:
                rel_time = (e["timestamp"] - base_time) * 1000
                writer.writerow([
                    scenario,
                    round(rel_time, 1),
                    e["event"],
                    e.get("circuit_state", ""),
                    e.get("provider", ""),
                    e.get("error", "") or str(e.get("poll_count", "")) or str(e.get("recovery_time_seconds", ""))
                ])

    print(f"\nResults written to {out_file}")
    print(f"CSV evidence written to {csv_file}")
    print(f"Timeline events written to {timeline_file}")
