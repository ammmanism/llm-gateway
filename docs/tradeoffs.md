# Design tradeoffs

## Exact vs semantic cache

Exact hits cannot be wrong for the same prompt and namespace. Semantic hits can
recover paraphrases but may answer an adjacent-intent query incorrectly. The
gateway therefore checks exact first and uses a measured semantic threshold of
`0.85`; see `data/evidence/semantic_threshold_sweep.csv`.

## Circuit breaker defaults

The default failure threshold is 3 and the default recovery timeout is 30
seconds. Recovery scenarios with 0.5/1/2/5-second timeouts are measured in
`data/evidence/fallback_recovery.csv`.

## Routing

`AdaptiveRouter` currently uses Thompson sampling over observed success/failure
counts. Cost-aware and latency-aware routers are available as alternatives. The
adaptive router's cost/latency weights are reserved for future work; they are not
part of the current selection score.

## Memory vs Redis

In-memory state is simple and fast but per process. Redis backs rate limits,
budgets, and the exact cache when configured. The FAISS semantic index remains
per process. A two-worker Redis correctness check is committed in
`data/evidence/redis_consistency.csv`.
