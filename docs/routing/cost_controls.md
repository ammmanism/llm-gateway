# Cost Controls

The gateway protects tenant budgets before and after provider calls:

- `NexusCostTracker` loads model prices from `configs/models.yaml`.
- `CostAwareRouter` can filter candidates with `allowed_models` and `max_cost_per_1k_tokens`.
- `BudgetEnforcer` rejects requests that would exceed the tenant budget.
- Successful provider calls record actual spend through the budget enforcer and Prometheus metrics.

## Pricing Config

Each model should include a stable name and `cost_per_1k_tokens`:

```yaml
models:
  - name: claude-3-haiku
    provider: anthropic
    cost_per_1k_tokens: 0.00025
    latency_ms: 500
```

Models without pricing are ignored by the cost-aware router. Models without
latency are skipped by the latency-aware router instead of forcing the whole
router into defaults.

## Budget Settings

Set the default tenant budget in `.env`:

```bash
DEFAULT_BUDGET_USD=10.0
BUDGET_REDIS_TTL_SECONDS=2592000
```

If `REDIS_URL` is set, reservations and spend use Redis Lua/`INCRBYFLOAT`.
Without Redis, an `asyncio.Lock` protects the in-memory path. Reservations are
atomic: concurrent requests cannot all spend the same remaining budget.

## Request Lifecycle

1. The gateway sanitizes the prompt and selects candidate models.
2. After a cache miss, it atomically reserves the estimated cost for the next
   provider attempt.
3. On success, it replaces the reservation with actual provider cost.
4. On failure, it releases the reservation before trying a fallback model.
5. If the reservation is denied, the gateway returns `402` without calling the
   provider.

Evidence: `data/evidence/budget_atomic_race.csv` (200 concurrent reservations,
zero overspend).
