# Circuit Breaker State Machine Design

## Overview

This document describes the three-state circuit breaker implementation in `llm-gateway`. The circuit breaker prevents cascading failures by monitoring provider health and failing fast when a provider is degraded.

## States

### CLOSED (Normal Operation)
- Requests flow normally to the provider
- Failures are counted
- Successes reset the failure counter
- **Transition to OPEN**: When `failure_count >= failure_threshold`

### OPEN (Failing Fast)
- All requests are rejected immediately with `CircuitOpenError`
- No requests reach the provider
- **Transition to HALF_OPEN**: After `recovery_timeout` seconds since last failure

### HALF_OPEN (Probing Recovery)
- Limited number of probe requests allowed (`max_half_open_probes`)
- **Transition to CLOSED**: On first successful probe
- **Transition to OPEN**: On any failed probe

## State Transition Diagram

```
                    +------------------+
                    |                  |
                    v                  |
    +--------+   record_failure()    +--------+   recovery_timeout    +----------+
    | CLOSED | --------------------> |  OPEN  | --------------------> | HALF_OPEN|
    +--------+   (threshold reached) +--------+   (timeout elapsed)   +----------+
      ^   |                                                         |    |
      |   | record_success()                                        |    |
      |   +---------------------------------------------------------+    |
      |        (immediate close on success)                          |
      |                                                              |
      |                      record_failure()                        |
      +--------------------------------------------------------------+
                   (immediate re-open on probe failure)
```

## Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failure_threshold` | 3 | Number of failures before tripping to OPEN |
| `recovery_timeout` | 30.0s | Time in OPEN state before allowing probes |
| `max_half_open_probes` | 3 | Max concurrent probe requests in HALF_OPEN |

## Failure Classification

Only the following trigger circuit breaker state changes:
- Network errors (connection timeout, DNS failure)
- HTTP 5xx errors (500, 502, 503, 504)
- HTTP 429 (rate limited) - treated as temporary failure

The following do NOT trigger circuit breaker:
- HTTP 4xx errors (400, 401, 403, 404, 422) - client errors
- Validation errors
- Authentication errors

## Concurrency Semantics

- All state transitions are protected by `threading.RLock`
- `max_half_open_probes` limits concurrent probes in HALF_OPEN state
- Probe counter increments atomically with state check
- First request after timeout counts as probe #1

## Integration with Providers

Each provider (`OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`, `TogetherProvider`, `GroqProvider`, `VLLMProvider`, `OllamaProvider`) maintains its own `CircuitBreaker` instance.

Provider methods (`generate`, `stream_generate`):
1. Call `circuit_breaker.allow_request()` before making API call
2. On success: `circuit_breaker.record_success()`
3. On failure: `circuit_breaker.record_failure()`

The `CircuitOpenError` includes:
- `provider`: Provider identifier for routing decisions
- `retry_after`: Seconds until next probe allowed

## Fallback Integration

When `CircuitOpenError` is raised, the gateway's fallback chain catches it and routes to the next provider in the chain. This is handled in `src/llm_gateway/core/server.py` in the model iteration loop.

## Testing

Unit tests in `tests/reliability/test_circuit_breaker.py` cover:
- All state transitions (CLOSED→OPEN→HALF_OPEN→CLOSED, CLOSED→OPEN→HALF_OPEN→OPEN)
- Probe limiting in HALF_OPEN state
- Thread safety under concurrent access
- Custom clock injection for deterministic testing
- Multiple failure/recovery cycles

Run tests:
```bash
python -m pytest tests/reliability/test_circuit_breaker.py -v
```

## Evidence

Benchmark results for failover recovery are in:
- `benchmarks/results/failover_recovery.json`
- `data/evidence/fallback_recovery.csv` (Phase 3)