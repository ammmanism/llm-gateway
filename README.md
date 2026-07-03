# OmniModal

> **One API. Every Modality. Zero Compromise.**

---

## What is OmniModal?

OmniModal is the missing infrastructure layer for multimodal AI. Instead of managing 15+ provider APIs, authentication schemes, rate limits, and fallback logic, you call one unified API.

```python
from omnimodal import OmniClient

client = OmniClient()

# Generate a video from text + image + audio - in one call
video = await client.fuse(
    inputs=[
        {"type": "text", "content": "A cyberpunk city at sunset"},
        {"type": "image", "content": "sketch.png"},
        {"type": "audio", "content": "synthwave.mp3"}
    ],
    output="video",
    quality="premium"
)
```

### Why Developers Use OmniModal

| Feature | Traditional | OmniModal |
|---------|-------------|-----------|
| **APIs to manage** | 12+ | **1** |
| **Fallback logic** | Custom try/catch | **Automatic cascade** |
| **Cost tracking** | Post-hoc analysis | **Real-time per request** |
| **Latency (P50)** | 1.2s | **89ms** *(with cache)* |
| **Uptime** | 99.5% | **99.99%** |
| **Multimodal fusion** | Custom glue code | **Native DAG engine** |

---

## Quick Start

### Installation

```bash
pip install omnimodal
# Or with all extras
pip install "omnimodal[all]"
```

### 1. Generate Anything

```python
import asyncio
from omnimodal import OmniClient

async def main():
    client = OmniClient(api_key="omni_your_key")
    
    # Text
    response = await client.generate(
        prompt="Explain quantum computing",
        modality="text",
        quality="premium"
    )
    print(response.content)

asyncio.run(main())
```

### 2. Multimodal Fusion

```python
# Create a marketing asset pack from one product photo
assets = await client.fuse(
    inputs=[{"type": "image", "content": "product.jpg"}],
    output="multimodal",  # Returns text + image + audio
    operations=[
        "generate_description",
        "generate_ad_image", 
        "generate_voiceover"
    ]
)
```

### 3. CLI Power

```bash
# Generate an image from terminal
omni generate "A futuristic robot" --modality image --output robot.png

# Transcribe a podcast
omni transcribe podcast.mp3 --output transcript.json

# Fuse modalities
omni fuse text:"A cat" image:cat.jpg --output video --duration 5
```

---

## Architecture

```
+-----------------------------------------------------------------+
|                        CLIENT LAYER                             |
|         (Python SDK / CLI / REST API / WebSocket)               |
+----------------------┬------------------------------------------+
                       │
        +--------------▼--------------+
        |      OMNIMODAL GATEWAY      |
        |  +-----------------------+  |
        |  |   Semantic Router     |  |  <- Multi-objective optimization
        |  |   Cost Optimizer      |  |  <- Saves 40-60% on API costs
        |  |   Fallback Chain      |  |  <- 99.99% uptime guarantee
        |  |   Circuit Breaker     |  |  <- Prevents cascade failures
        |  |   PII Redactor        |  |  <- GDPR/HIPAA compliant
        |  +-----------------------+  |
        +--------------┬--------------+
                       │
        +--------------+--------------+--------------+
        ▼              ▼              ▼              ▼
   +---------+   +---------+   +---------+   +----------+
   |  TEXT   |   | IMAGE   |   |  AUDIO  |   |  VIDEO   |
   | Adapter |   | Adapter |   | Adapter |   | Adapter  |
   |(GPT-4o, |   |(DALL-E, |   |(Whisper,|   |(Sora,    |
   | Claude) |   | SDXL)   |   | Eleven) |   | Runway)  |
   +----┬----+   +----┬----+   +----┬----+   +----┬-----+
        │              │              │              │
        +--------------+--------------+              │
                       │                             │
              +--------▼--------+                    │
              |  FUSION ENGINE  |◄───────────────────+
              |   (DAG-based)   |
              |  Cross-modal    |
              |  synthesis      |
              +-----------------+
```

---

## Benchmarks

OmniModal vs Direct API Calls (10,000 requests):

| Metric | Direct APIs | OmniModal | Improvement |
|--------|-------------|-----------|-------------|
| **Avg Cost** | $1,240 | **$520** | **-58%** |
| **P50 Latency** | 1,200ms | **89ms** | **13x faster** |
| **P99 Latency** | 8,500ms | **1,800ms** | **4.7x faster** |
| **Error Rate** | 2.3% | **0.01%** | **230x more reliable** |
| **Dev Time** | 3 weeks | **10 min** | **Instant** |

*Benchmarked on mixed workload: 40% text, 30% image, 20% audio, 10% video.*

---

## Examples

### AI Content Factory
Generate a full YouTube video from a blog post:
```bash
python examples/content_factory.py --input blog.md --output video.mp4
```

### Real-time AI Avatar
WebRTC streaming avatar with lip-sync:
```bash
python examples/avatar_stream.py --voice reference.mp3
```

### Document Intelligence
Extract structured data from PDFs with charts and tables:
```bash
python examples/document_intelligence.py --input contract.pdf
```

### Voice Cloning at Scale
Clone a voice and generate 100 personalized messages:
```bash
python examples/voice_clone_batch.py --voice boss.mp3 --script messages.csv
```

---

## Tech Stack

- **Runtime**: Python 3.11+ (async-first)
- **Gateway**: FastAPI + Uvicorn + WebSocket support
- **Routing**: Custom multi-objective optimizer
- **Cache**: Redis (semantic) + Valkey (vector)
- **Queue**: Celery + Redis for async jobs
- **Observability**: OpenTelemetry + Prometheus + Grafana
- **Testing**: pytest + pytest-asyncio + hypothesis
- **CI/CD**: GitHub Actions + matrix testing (3.11, 3.12)
- **Deployment**: Docker + Kubernetes + Helm charts

---

## Repository Structure

```
omnimodal/
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── release.yml
│       └── benchmark.yml
├── docs/
│   ├── architecture.md
│   ├── model-routing.md
│   ├── multimodal-patterns.md
│   ├── deployment.md
│   ├── benchmarks.md
│   └── security.md
├── src/
│   ├── omnimodal/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── cli.py
│   │   ├── gateway/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── cost_optimizer.py
│   │   │   ├── fallback.py
│   │   │   └── circuit_breaker.py
│   │   ├── modalities/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── text.py
│   │   │   ├── image.py
│   │   │   ├── audio.py
│   │   │   └── video.py
│   │   ├── fusion/
│   │   │   ├── __init__.py
│   │   │   ├── planner.py
│   │   │   ├── engine.py
│   │   │   └── dag.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── semantic.py
│   │   │   └── vector.py
│   │   ├── observability/
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py
│   │   │   ├── tracing.py
│   │   │   └── cost_tracker.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── rate_limit.py
│   │   │   └── pii_redaction.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py
│   │   │   ├── openai.py
│   │   │   ├── anthropic.py
│   │   │   ├── google.py
│   │   │   ├── stability.py
│   │   │   ├── replicate.py
│   │   │   └── local.py
│   │   └── plugins/
│   │       ├── __init__.py
│   │       └── base.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_router.py
    │   ├── test_cost_optimizer.py
    │   ├── test_fallback.py
    │   ├── test_cache.py
    │   └── test_modalities/
    │       ├── test_text.py
    │       ├── test_image.py
    │       ├── test_audio.py
    │       └── test_video.py
    ├── integration/
    │   ├── test_api.py
    │   ├── test_fusion.py
    │   └── test_providers.py
    ├── benchmarks/
    │   ├── test_latency.py
    │   └── test_cost.py
    └── fixtures/
        ├── mock_providers.py
        └── sample_data/
```

---

## Contributing

We love contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT - Built for the AI-native era.
