# Architecture

`llm-gateway` is a modular, event-driven LLM gateway. It consists of:

1. **API Layer** - FastAPI server, handles authentication, rate limiting, PII redaction.
2. **Routing Engine** - Multi-objective routers (cost, latency, quality) with fallback.
3. **Caching Layer** - Two-tier: exact (Redis) and semantic (FAISS). Auto-warmer for popular queries.
4. **Reliability Layer** - Circuit breakers, retries, self-healing health checks.
5. **Provider Fabric** - Adapters for OpenAI, Anthropic, Gemini, Groq, Ollama, vLLM, Together.
6. **Modality Router** - Detects content type and routes to appropriate modality handler (text, image, audio, video).
7. **Observability** - Prometheus metrics, OpenTelemetry traces, audit logs.

Each component is **pluggable** - you can replace caching backends, add new providers, or implement custom routing strategies.
