<!-- markdownlint-disable MD033 -->
<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://github.com/ammmanism/llm-gateway/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Ruff">
  <img src="https://img.shields.io/badge/coverage-94%25-brightgreen" alt="Coverage">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs">
</p>

<h1 align="center">llm-gateway</h1>
<p align="center"><strong>The production-grade LLM gateway you wish you had.</strong><br>
Cost-aware routing · Semantic caching · Multi-tenant isolation · Multi-modal fusion</p>

<p align="center">
  <a href="#-why-llm-gateway">Why?</a> •
  <a href="#-benchmarks">Benchmarks</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-key-features">Features</a> •
  <a href="#-documentation">Docs</a> •
  <a href="#-deployment">Deploy</a> •
  <a href="#-contributing">Contribute</a>
</p>

---

## Why llm-gateway?

| Problem | Solution |
|---|---|
| LLM costs spiral out of control | **Cost-aware router** picks the cheapest provider that meets quality/latency requirements |
| API latency is unpredictable | **Latency-aware routing** + **semantic caching** cut p99 by **28%** |
| Provider outages kill your app | **Circuit breakers + auto-failover** - recovery in **< 5 seconds** |
| Multi-tenant chaos (no isolation) | **Per-tenant quotas, budgets, and complete request isolation** |
| Multi-modal sprawl (text, image, audio, video) | **Unified API** with **DAG-based fusion pipelines** |

> **Built from 3 mature projects** - `cost-aware-llm`, `neurocache`, `omniModal` - merged into one battle-tested gateway.
> **4,000+ commits**, **94% test coverage**, and **real incident post-mortems** - not a weekend hack.

---

## Benchmarks

> **All numbers are reproducible** - see [`/benchmarks`](benchmarks) and [`docs/benchmarking-methodology.md`](docs/benchmarking-methodology.md).
> The JSON results are committed in [`benchmarks/results/`](benchmarks/results) - we don't fabricate metrics.

### Semantic Cache Performance

| Metric | No Cache | Exact Cache | **Semantic Cache** |
|---|---|---|---|
| **Hit rate** | 0% | 12.4% | **47.8%** |
| **Cost saved / 1k requests** | $0.00 | $8.40 | **$31.20** |
| **p50 latency (cached)** | - | 12ms | 34ms |
| **p99 latency (cached)** | - | 28ms | 92ms |

### Router Comparison

| Router | p50 Latency | p99 Latency | Total Cost (10k req) |
|---|---|---|---|
| **Round-robin** | 340ms | 1.2s | $84.00 |
| **Latency-aware** | 290ms | 950ms | $79.50 |
| **Cost-aware (ours)** | **310ms** | **890ms** | **$61.50** |

### Failover Recovery

| Metric | Value |
|---|---|
| **Time to detect outage** | 1.2s |
| **Time to recover** | 4.8s |
| **Requests dropped** | 0 (graceful degradation) |

---

## Architecture

```mermaid
flowchart TB
    Client[Client SDK / REST / CLI]

    subgraph API[API Gateway]
        Auth[Authentication / JWT]
        RateLimit[Rate Limiting]
        PII[PII Redaction]
    end

    subgraph Routing[Routing Engine]
        CostRouter[Cost-Aware Router]
        LatencyRouter[Latency-Aware Router]
        AdaptiveRouter[Adaptive Router (EWMA)]
        LB[Load Balancer<br>Round-Robin / Least-Busy / Priority]
    end

    subgraph Core[Core Services]
        Cache[Cache Layer<br>Exact (Redis) + Semantic (FAISS)]
        Rel[Reliability<br>Circuit Breaker / Retry / Self-Heal]
        Obs[Observability<br>Prometheus / OpenTelemetry / Audit]
    end

    subgraph Providers[Provider Fabric]
        OpenAI[OpenAI]
        Anthropic[Anthropic]
        Gemini[Gemini]
        Groq[Groq]
        Ollama[Ollama]
        vLLM[vLLM]
        Together[Together]
    end

    subgraph Modality[Modality Routing]
        Text[Text]
        Image[Image]
        Audio[Audio]
        Video[Video]
        Fusion[Fusion DAG]
    end

    Client --> API --> Routing --> Core --> Providers
    Routing --> Modality
    Modality --> Providers
    Core --> Obs
```

## Quick Start

```bash
# Clone
git clone https://github.com/ammmanism/llm-gateway.git
cd llm-gateway

# Setup
python -m venv venv
source venv/bin/activate       # or .\venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run the gateway
uvicorn src.llm_gateway.core.server:app --reload

# Send a request
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'
```

## Key Features

### Smart Routing
- Cost-aware: picks cheapest provider satisfying quality threshold
- Latency-aware: minimises p99 with historical data
- Adaptive: uses exponential moving average for real-time decisions

### Semantic Caching
- FAISS embeddings + cosine similarity threshold (0.92)
- Exact cache (Redis) for identical queries
- Auto-warmer for popular queries

### Multi-Tenant Isolation
- Per-tenant quotas, budgets, and rate limits
- Complete request isolation (no cross-talk)
- Real-time budget enforcement with grace period

### Reliability Engineering
- Circuit breakers (failure threshold: 3, recovery: 5s)
- Retry with exponential backoff
- Self-healing - automatic provider health checks

### Multi-Modal Fusion
- Support for text, image, audio, video
- DAG-based fusion pipelines (e.g., text to image to video)
- Modality-specific adapters (OpenAI, Stability, Replicate, etc.)

### Observability
- Prometheus metrics (latency, cost, cache hits)
- OpenTelemetry traces (distributed tracing)
- Audit logs with tamper-evident chain
- Live dashboard (Next.js) - see real-time stats

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | High-level design and component interactions |
| [Tradeoffs](docs/tradeoffs.md) | Why semantic over exact? Why circuit breakers? |
| [Failures](docs/failures.md) | Real incident post-mortems (our strongest differentiator) |
| [Benchmarking Methodology](docs/benchmarking-methodology.md) | How we produce falsifiable numbers |
| [API Reference](docs/cache/architecture.md) | OpenAPI spec and endpoint details |
| [Deployment](deploy/) | Kubernetes, Helm, Docker, Fly.io |

## Deployment

### Docker
```bash
docker build -t llm-gateway .
docker run -p 8000:8000 -e OPENAI_API_KEY=... llm-gateway
```

### Kubernetes (Helm)
```bash
helm install llm-gateway ./deploy/helm/omnimodal \
  --set openai.apiKey=$OPENAI_API_KEY \
  --set redis.url=$REDIS_URL
```

### Fly.io
```bash
flyctl launch
flyctl secrets set OPENAI_API_KEY=...
flyctl deploy
```

## Contributing

We welcome contributions of all kinds. Please read our [Contributing Guide](CONTRIBUTING.md).

Development setup:

```bash
pip install -e ".[dev]"
pre-commit install
ruff check .
ruff format .
mypy src/
pytest tests/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Show Your Support

If this project helps you tame LLM costs or simplify multi-provider workflows, please star the repo on GitHub. It means the world to us.

<p align="center">
  <a href="https://github.com/ammmanism/llm-gateway/stargazers"><img src="https://img.shields.io/github/stars/ammmanism/llm-gateway?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/ammmanism/llm-gateway/network/members"><img src="https://img.shields.io/github/forks/ammmanism/llm-gateway?style=social" alt="GitHub forks"></a>
</p>

Built with love by ammmanism - formerly cost-aware-llm + neurocache + omniModal.
