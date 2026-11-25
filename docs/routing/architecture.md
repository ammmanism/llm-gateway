# Routing architecture

The active request path is:

1. FastAPI middleware validates the API key and attaches a tenant.
2. The firewall validates and sanitizes the prompt.
3. `RateLimiter` atomically reserves RPM and TPM capacity (Redis Lua or memory).
4. Quota and budget checks run before provider dispatch.
5. A router selects an ordered model list:
   - `CostAwareRouter` for cost constraints,
   - `LatencyAwareRouter` for latency constraints,
   - `AdaptiveRouter` for Thompson-sampling selection.
6. The two-tier cache is checked before generation.
7. The fallback policy advances only for 429/5xx errors or an open circuit.
8. Provider usage, cost, metrics, traces, and ledger rows are recorded per
   attempt.

See `docs/tradeoffs.md` and `docs/evidence/architecture/` for verified details.
