# Architecture

Neurocache is built with a modern, async-first Python stack using FastAPI and OpenTelemetry.

## Components

1.  **FastAPI Gateway**: Handles incoming requests, auth, rate limiting, and routing.
2.  **Semantic Cache Layer**:
    *   **FAISS**: In-memory HNSW index for ultra-fast vector similarity search.
    *   **Redis**: Hot cache for storing the actual JSON responses and TTL management.
    *   **PostgreSQL (pgvector)**: Persistent storage for all cache entries, used for cold-start recovery and analytics.
3.  **Smart Router**: Evaluates providers based on EWMA of latency, error rates, and static costs.
4.  **Billing & Observability**: Tracks every request, calculates savings, and exports traces to Jaeger and metrics to Prometheus.

## Request Flow
1. Middleware validates API Key and Rate Limits.
2. Query is embedded using local `all-MiniLM-L6-v2`.
3. FAISS searches for nearest neighbors.
4. If hit (cosine similarity > threshold) AND metadata hash matches, return from Redis.
5. If miss, Smart Router selects best provider.
6. Request sent to provider.
7. Response returned to user.
8. Background task updates FAISS, Redis, and Postgres.
