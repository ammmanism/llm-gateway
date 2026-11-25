# Scaling the gateway

## Horizontal scaling

The HTTP layer can run multiple workers, but not all state is stateless:

- RPM/TPM limits, budgets, and the exact cache can share Redis.
- The FAISS semantic index is per process and needs an external vector store for
  cross-replica semantic hits.
- SQLite cost accounting is local to the configured ledger path; multi-replica
  deployments need a shared database or a central collector.
- The API-key/tenant map is configuration, not a shared virtual-key database.

A two-worker Redis correctness check is committed in
`data/evidence/redis_consistency.csv`; it is not a high-scale load test.

## Multi-region deployment

Multi-region routing is a deployment concern, not implemented by this reference
project. A production design would add a global load balancer, shared durable
state, region-aware provider routing, and collector aggregation.
