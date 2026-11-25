# Architecture

`llm-gateway` is a modular FastAPI gateway with these active layers:

1. **API and security** — hashed virtual API keys with scopes and per-key limits,
   structured logs, security headers, PII detection, RPM/TPM limiting, quotas,
   and atomic budgets.
2. **Routing** — cost-aware, latency-aware, and Thompson-sampling adaptive
   routers with a policy-driven fallback chain.
3. **Caching** — exact Redis/in-memory cache followed by an in-process FAISS HNSW
   semantic index.
4. **Reliability** — three-state circuit breakers, retry/backoff, and health
   monitoring.
5. **Providers** — OpenAI, Anthropic, Gemini, Groq, Together, Ollama, and vLLM
   adapters.
6. **Observability** — Prometheus metrics, OpenTelemetry traces, and a per-attempt
   SQLite cost ledger.

The legacy multi-modal implementation is quarantined under `_superseded/`; its
documentation is archived under `docs/archive/modality-docs/`.
