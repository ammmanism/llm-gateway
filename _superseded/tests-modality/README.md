# Superseded modality test suite

This suite targets an earlier `llm_gateway.routing` design (`SemanticRouter`,
`CostOptimizer`, `FallbackChain`, `RouteDecision`) that no longer exists in the
current tree. Importing it aborted collection for the whole test run, so it is
quarantined here instead of being silently deleted.

Current coverage for the replacement components lives in:

- `tests/reliability/test_circuit_breaker.py` (circuit breaker state machine)
- `tests/routing/` (routing, fallback, gateway integration)
- `tests/cache/` (exact/semantic cache, analytics, warmer)

Do not re-enable this directory without porting it to the current routing API.
