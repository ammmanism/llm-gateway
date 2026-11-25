# Active cache architecture

The active implementation is `src/llm_gateway/cache/two_tier.py`.

1. **Exact tier** — SHA-256 of the prompt plus a namespace hash over tenant,
   model, and generation parameters. Values live in Redis when `REDIS_URL` is
   configured, otherwise in a TTL-aware in-process dictionary.
2. **Semantic tier** — a per-namespace FAISS HNSW index using inner product over
   normalized embeddings. The default embedder is
   `sentence-transformers/all-MiniLM-L6-v2`; a deterministic hashing embedder is
   used when the optional model is unavailable.
3. **Lookup order** — exact first, then semantic. A semantic hit must meet the
   configured threshold and be unexpired.
4. **Bypass** — `live_data=true` skips both reads and writes.

The legacy PostgreSQL/pgvector `SemanticCache` still exists under
`src/llm_gateway/cache/semantic.py`, but it is not the active two-tier lookup
path. See `docs/evidence/architecture/caching_design.md` for the verified design
and `data/evidence/semantic_threshold_sweep.csv` for measured trade-offs.
