# Routing tradeoffs

- **Memory vs Redis:** in-memory state is per process; Redis enables shared rate
  limits, budgets, and exact-cache entries.
- **Semantic vs exact:** semantic lookup recovers paraphrases but can mis-route
  adjacent intents; exact lookup is deterministic.
- **Latency vs cost:** cheaper models may be slower or less capable.
- **Exploration vs exploitation:** Thompson sampling explores uncertain models
  and converges toward observed reliable models.

Measured cache and failover trade-offs are committed under `data/evidence/`.
