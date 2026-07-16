# OmniModal Architecture

> **Design Philosophy**: *Every millisecond and every cent matters. The system must be faster and cheaper than direct provider calls, while being more reliable than any single provider.*

---

## 1. System Overview

OmniModal follows a **Layered Gateway Pattern** with **Modality Adapters** and a **Fusion Engine**. It acts as a smart proxy between your application and the fragmented landscape of AI providers.

### Core Tenets

1. **Provider Abstraction** - No provider-specific code leaks into business logic
2. **Semantic Understanding** - The gateway understands *what* you're asking, not just *where* to send it
3. **Economic Optimization** - Every request has a cost/quality Pareto frontier; we find the optimal point
4. **Resilience by Design** - Circuit breakers, bulkheads, and automatic recovery

---

## 2. High-Level Data Flow

```
+-------------+     +-------------+     +-------------------------------------+
|   Client    |---->|   Load      |---->|         OMNIMODAL CORE              |
|   Request   |     |  Balancer   |     |  +---------+ +---------+ +--------+ |
+-------------+     +-------------+     |  | Request | | Semantic| | Policy | |
                                        |  | Parser  | |Analyzer | | Engine | |
                                        |  +----+----+ +----+----+ +---+----+ |
                                        |       │           │          │      |
                                        |       +-----+-----+          │      |
                                        |             ▼                  ▼      |
                                        |  +---------------------------------+ |
                                        |  |      ROUTING DECISION ENGINE    | |
                                        |  |  +---------+ +---------+ +----+ | |
                                        |  |  | Quality | |  Cost   | |Lat.│ | |
                                        |  |  | Scorer  | |Estimator│ |Est.│ | |
                                        |  |  +----+----+ +----+----+ +─┬──+ | |
                                        |  |       +-----+-----+        │    | |
                                        |  |             ▼              ▼    | |
                                        |  |      +-----------------+        | |
                                        |  |      |  MODEL SELECTOR |        | |
                                        |  |      | (Multi-objective|        | |
                                        |  |      |   optimization) |        | |
                                        |  |      +--------┬--------+        | |
                                        |  +---------------+-----------------+ |
                                        |                  │                   |
                                        |  +---------------+---------------+   |
                                        |  ▼               ▼               ▼   |
                                        | +------+    +--------+    +--------+ |
                                        | |Cache |    |Provider|    | Fallback| |
                                        | |Layer |    | Adapter|    |  Chain  | |
                                        | +--┬---+    +---┬----+    +----┬---+ |
                                        |    │            │              │     |
                                        |    +------------+--------------+     |
                                        |                   │                   |
                                        +-------------------+-------------------+
                                                            ▼
                                                +---------------------+
                                                |   RESPONSE STREAM   |
                                                |  (with metadata)    |
                                                +---------------------+
```

---

## 3. Component Deep Dive

### 3.1 Request Parser & Semantic Analyzer

**Purpose**: Understand the *intent* and *modality requirements* of the request before routing.

```python
class SemanticAnalyzer:
    """
    Decomposes a multimodal request into:
    - Primary modality (text/image/audio/video)
    - Secondary modalities (inputs)
    - Complexity score (1-10)
    - Quality requirements (draft/standard/premium/enterprise)
    - Latency sensitivity (realtime/batch/async)
    """
    
    async def analyze(self, request: OmniRequest) -> RequestProfile:
        # 1. Extract modality signals from inputs
        # 2. Classify task type (generation, editing, transcription, etc.)
        # 3. Estimate token/compute requirements
        # 4. Determine quality tier based on prompt cues
        pass
```

**Key Insight**: A request like *"Generate a cinematic 4K video of a dragon from this sketch and voiceover"* decomposes into:
- Primary: `video_generation`
- Inputs: `image` (sketch) + `audio` (voiceover) + `text` (prompt)
- Complexity: `9/10`
- Quality: `premium`
- Latency: `batch` (video generation is slow)

---

## 3.2 Routing Decision Engine

**The Brain of OmniModal.** Uses multi-objective optimization to select the best provider.

**Decision Factors** (weighted by user policy):

| Factor | Weight | Description |
|--------|--------|-------------|
| **Quality Score** | 0.4 | Historical accuracy/quality rating per task type |
| **Cost** | 0.3 | USD per request (including input/output tokens) |
| **Latency** | 0.2 | Expected time-to-first-byte (TTFB) |
| **Reliability** | 0.1 | Uptime % and error rate over last 1h |

**Algorithm**: Constrained optimization with fallback safety margin.

```python
def select_model(profile: RequestProfile, policy: UserPolicy) -> ProviderRoute:
    candidates = get_eligible_providers(profile.modality, profile.task_type)
    
    # Filter: Must meet minimum quality threshold
    candidates = [c for c in candidates if c.quality_score >= policy.min_quality]
    
    # Filter: Must meet latency SLA
    candidates = [c for c in candidates if c.estimated_latency <= policy.max_latency]
    
    # Score: Weighted multi-objective
    for c in candidates:
        c.score = (
            0.4 * normalize(c.quality_score) +
            0.3 * (1 - normalize(c.cost)) +  # Lower cost = higher score
            0.2 * (1 - normalize(c.estimated_latency)) +
            0.1 * c.reliability_score
        )
    
    return max(candidates, key=lambda c: c.score)
```

---

## 3.3 Cache Layer

**Two-tier caching** for maximum hit rate:

#### Tier 1: Semantic Cache (Redis)
- Key: Hash of normalized prompt + modality + quality params
- TTL: 1 hour for generation, 24h for embeddings
- Hit rate: ~35% for repetitive enterprise workloads

#### Tier 2: Vector Cache (Valkey/Redis with Vector Search)
- For similar (not identical) prompts
- Uses embedding similarity threshold (cosine > 0.95)
- Hit rate: ~15% additional
- **Massive cost savings** on near-duplicate requests

---

## 3.4 Provider Adapter Pattern

Every provider implements a unified interface:

```python
class BaseModalityAdapter(ABC):
    @abstractmethod
    async def generate(self, request: ModalityRequest) -> ModalityResponse: ...
    
    @abstractmethod
    async def health_check(self) -> HealthStatus: ...
    
    @abstractmethod
    def estimate_cost(self, request: ModalityRequest) -> CostEstimate: ...
    
    @abstractmethod
    def estimate_latency(self, request: ModalityRequest) -> float: ...
```

**Adapters Implemented**:
- `OpenAITextAdapter`, `OpenAIImageAdapter`, `OpenAIAudioAdapter`
- `AnthropicTextAdapter` (Claude 3 Opus/Sonnet/Haiku)
- `GoogleGeminiAdapter` (multimodal native)
- `StabilityImageAdapter` (SDXL, Stable Diffusion 3)
- `ReplicateVideoAdapter` (video generation models)
- `LocalOllamaAdapter` (fallback for text)

---

## 3.5 Circuit Breaker & Bulkhead

Prevents cascade failures when a provider is down.

```
State Machine:
CLOSED --[5 errors in 60s]--> OPEN --[30s timeout]--> HALF_OPEN --[3 successes]--> CLOSED
                               │
                               └── Returns fallback immediately
```

**Bulkhead**: Per-provider connection pools. If OpenAI is saturated, requests overflow to Anthropic without affecting the OpenAI pool.

---

## 3.6 Fusion Engine

The crown jewel: **cross-modal synthesis**.

**Supported Fusions**:

| Input Modalities | Output | Example |
|-----------------|--------|---------|
| Text + Image | Video | "Animate this sketch with this description" |
| Audio + Text | Image | "Generate album art from lyrics + mood audio" |
| Video + Text | Audio | "Generate sound effects for this scene" |
| Image + Image | Video | "Morph between these two keyframes" |

**Architecture**: Directed Acyclic Graph (DAG) of modality transformations.

```
Input: [Text, Image, Audio]
       │      │      │
       ▼      ▼      ▼
   +---------------------+
   |   Fusion Planner    |  <- Creates DAG of transformations
   +---------------------+
            │
            ▼
   +---------------------+
   |  Stage 1: Text->Image  |  (if needed)
   |  Stage 2: Image+Audio->Video |
   |  Stage 3: Post-process      |
   +---------------------+
```

---

## 4. Data Models

### Request Schema

```python
class OmniRequest(BaseModel):
    request_id: UUID
    timestamp: datetime
    inputs: List[ModalityInput]      # Mixed text/image/audio/video
    output_modality: ModalityType
    constraints: RequestConstraints  # cost, latency, quality
    metadata: Dict[str, Any]         # user_id, project_id, tracing
```

### Response Schema

```python
class OmniResponse(BaseModel):
    request_id: UUID
    content: ModalityOutput          # Unified output wrapper
    provider_used: str
    cost_usd: float
    latency_ms: int
    cache_hit: bool
    fallback_used: bool
    trace_id: str                    # OpenTelemetry trace
```

---

## 5. Deployment Architecture

```
+---------------------------------------------+
|              KUBERNETES CLUSTER              |
|  +-------------+      +-----------------+  |
|  |   API Pods  |<---->|  Redis Cluster  |  |
|  |  (FastAPI)  |      |   (Cache/Queue) |  |
|  +------┬------+      +-----------------+  |
|         │                                   |
|  +------┴------+      +-----------------+  |
|  |  Worker Pods|<---->|  Prometheus/    |  |
|  |  (Celery)   |      |  Grafana        |  |
|  +-------------+      +-----------------+  |
|                                             |
|  +-------------------------------------+   |
|  |      INGRESS (nginx / traefik)      |   |
|  |    Rate Limiting + Auth + TLS       |   |
|  +-------------------------------------+   |
+---------------------------------------------+
```

---

## 6. Performance Benchmarks

| Metric | Target | Strategy |
|--------|--------|----------|
| **P50 Latency** | <100ms | Aggressive caching + connection pooling |
| **P99 Latency** | <2s | Fallback to fast models under load |
| **Cost Reduction** | 40-60% | Semantic cache + cost-aware routing |
| **Uptime** | 99.99% | Multi-provider fallback + circuit breaker |
| **Throughput** | 10K RPS | Horizontal pod autoscaling + async workers |

---

## 7. Security & Compliance

- **PII Redaction**: Automatic detection and masking before sending to providers
- **Audit Logs**: Every request logged with full provenance
- **Data Residency**: Route to region-specific providers (EU data stays in EU)
- **Rate Limiting**: Token bucket per user, per project, per modality
- **API Key Rotation**: Automatic rotation with zero downtime

---

## 8. Extensibility

Adding a new provider takes **<50 lines of code**:

1. Implement `BaseModalityAdapter`
2. Register in `ProviderRegistry`
3. Add cost/latency estimates to `CostOptimizer`

The system automatically gains fallback support, caching, and observability.
