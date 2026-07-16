# Model Routing & Cost Optimization

> **The Art of Intelligent Dispatch**: How OmniModal decides *where* to send every request, and *why* it saves you money.

---

## 1. Routing Philosophy

**Problem**: Different providers excel at different tasks. GPT-4V is great at document understanding but expensive. Claude 3 Haiku is fast and cheap for simple queries. SDXL is cheap for images but DALL-E 3 follows instructions better.

**Solution**: Treat model selection as a **multi-objective optimization problem** with real-time constraints.

---

## 2. The Routing Stack

```
+---------------------------------------------+
|              ROUTING LAYERS                 |
+---------------------------------------------+
|  Layer 4: Fallback Router                   |
|           (Emergency provider selection)    |
+---------------------------------------------+
|  Layer 3: Cost Optimizer                    |
|           (Pareto-optimal cost/quality)     |
+---------------------------------------------+
|  Layer 2: Quality Scorer                    |
|           (Task-specific model ranking)     |
+---------------------------------------------+
|  Layer 1: Semantic Classifier               |
|           (Intent + modality detection)     |
+---------------------------------------------+
```

---

## 3. Semantic Classifier (Layer 1)

Determines *what* the user is asking for.

**Input**: Raw request (multimodal inputs + text prompt)
**Output**: `TaskProfile` with:
- `primary_modality`: text | image | audio | video
- `task_type`: generation | understanding | editing | transcription | translation | summarization
- `complexity`: 1-10 scale
- `quality_tier`: draft | standard | premium | enterprise

**Implementation**:

```python
class SemanticClassifier:
    async def classify(self, request: OmniRequest) -> TaskProfile:
        # 1. Modality detection from input MIME types
        modalities = detect_modalities(request.inputs)
        
        # 2. Task classification using lightweight classifier
        # (Fine-tuned DistilBERT on 50K labeled multimodal tasks)
        task_type = self.classifier.predict(request.prompt)
        
        # 3. Complexity estimation
        complexity = self.estimate_complexity(modalities, task_type, request.prompt)
        
        # 4. Quality tier from explicit cues or historical preferences
        quality = self.infer_quality_tier(request)
        
        return TaskProfile(modalities, task_type, complexity, quality)
```

**Complexity Heuristics**:

| Signal | Complexity Impact |
|--------|------------------|
| >500 tokens input | +2 |
| Multiple modalities | +2 per extra modality |
| "4K", "photorealistic", "cinematic" | +2 |
| "Quick draft", "rough sketch" | -2 |
| Code generation | +1 |
| Reasoning/math | +2 |

---

## 4. Quality Scorer (Layer 2)

Scores each provider for the specific task type.

**Quality Matrix** (continuously updated from human feedback + automated evals):

| Provider | Text Gen | Image Gen | Doc Understanding | Code | Reasoning |
|----------|----------|-----------|-------------------|------|-----------|
| GPT-4o | 9.5 | 8.5 | 9.2 | 9.0 | 9.3 |
| Claude 3 Opus | 9.3 | - | 9.5 | 8.8 | 9.1 |
| Claude 3 Haiku | 7.5 | - | 7.0 | 7.2 | 7.0 |
| Gemini Pro | 8.8 | 8.0 | 8.5 | 8.5 | 8.7 |
| DALL-E 3 | - | 9.0 | - | - | - |
| SDXL | - | 7.5 | - | - | - |

**Dynamic Scoring**: Quality scores decay if a provider's error rate increases.

```python
def get_dynamic_quality(provider: str, task: TaskType) -> float:
    base = quality_matrix[provider][task]
    reliability_multiplier = provider.current_uptime  # 0.9-1.0
    recent_error_penalty = provider.error_rate * 10   # Subtract up to 1.0
    return base * reliability_multiplier - recent_error_penalty
```

---

## 5. Cost Optimizer (Layer 3)

**The Money-Saving Engine.**

### 5.1 Cost Model

Every provider exposes a `CostModel`:

```python
@dataclass
class CostModel:
    input_token_rate: float      # $ per 1K input tokens
    output_token_rate: float     # $ per 1K output tokens
    fixed_cost: float            # Per-request fee
    image_cost_per_pixel: float  # For image gen
    audio_cost_per_second: float # For audio/video
```

### 5.2 Cost Estimation

Before sending a request, we *estimate* the cost:

```python
class CostEstimator:
    def estimate(self, request: OmniRequest, provider: Provider) -> CostEstimate:
        # 1. Estimate output size based on task complexity
        estimated_output = self.predict_output_size(request)
        
        # 2. Calculate based on provider's cost model
        input_cost = (request.input_tokens / 1000) * provider.cost_model.input_token_rate
        output_cost = (estimated_output / 1000) * provider.cost_model.output_token_rate
        media_cost = self.calculate_media_cost(request, provider)
        
        total = input_cost + output_cost + media_cost + provider.cost_model.fixed_cost
        
        return CostEstimate(total, confidence=0.85)
```

### 5.3 Pareto Optimization

Find the provider that maximizes quality per dollar.

```python
def optimize_route(candidates: List[Provider], 
                   policy: CostPolicy,
                   profile: TaskProfile) -> ProviderRoute:
    
    # Filter: Must be within budget
    candidates = [c for c in candidates if c.estimated_cost <= policy.max_budget]
    
    # Filter: Must meet minimum quality
    candidates = [c for c in candidates if c.quality_score >= policy.min_quality]
    
    # Calculate efficiency: quality / cost
    for c in candidates:
        c.efficiency = c.quality_score / (c.estimated_cost + 0.001)  # Avoid div by zero
    
    # Select Pareto-optimal candidates
    pareto_front = compute_pareto_front(candidates)
    
    # Apply user preference: quality-first vs cost-first vs balanced
    if policy.preference == "quality":
        return max(pareto_front, key=lambda c: c.quality_score)
    elif policy.preference == "cost":
        return min(pareto_front, key=lambda c: c.estimated_cost)
    else:  # balanced
        return max(pareto_front, key=lambda c: c.efficiency)
```

### 5.4 Cost Savings Strategies

| Strategy | Savings | Implementation |
|----------|---------|----------------|
| **Semantic Cache** | 35-50% | Hash + vector similarity |
| **Model Downgrade** | 20-30% | Use Haiku for simple tasks detected by classifier |
| **Batching** | 15-25% | Group similar requests, send together |
| **Provider Arbitrage** | 10-20% | Use cheaper provider with same quality for specific task |
| **Token Compression** | 5-10% | Summarize long contexts before sending |

---

## 6. Fallback Router (Layer 4)

**Guarantees 99.99% uptime** even when providers fail.

### 6.1 Fallback Chain

```python
class FallbackChain:
    def __init__(self):
        self.chains = {
            "text_generation": [
                "gpt-4o",
                "claude-3-opus", 
                "gemini-pro",
                "claude-3-haiku",  # Cheap emergency fallback
                "local-llama-3"    # Zero-cost nuclear option
            ],
            "image_generation": [
                "dall-e-3",
                "stable-diffusion-3",
                "midjourney-api",
                "local-sdxl"
            ],
        }
```

### 6.2 Fallback Triggers

A fallback is triggered when:
- HTTP 5xx error from primary
- HTTP 429 (rate limit) + retry exhaustion
- Latency exceeds SLA (timeout)
- Circuit breaker OPEN state
- Content policy violation (try alternative provider with different filters)

### 6.3 Graceful Degradation

If *all* providers fail for a modality:
1. Return cached similar result (if available)
2. Degrade to simpler task (e.g., video -> image + text description)
3. Queue for async retry (return job ID to user)
4. Final: Return error with detailed diagnostics

---

## 7. Routing Configuration

Users can configure routing via policy:

```python
policy = RoutingPolicy(
    # Quality requirements
    min_quality=0.8,           # Minimum acceptable quality (0-1)
    quality_preference="balanced",  # "quality" | "cost" | "balanced" | "latency"
    
    # Cost constraints
    max_budget_usd=0.10,       # Per-request hard cap
    monthly_budget_usd=1000.0, # Soft limit with alerts
    
    # Latency constraints
    max_latency_ms=2000,       # Hard timeout
    preferred_region="us-east",# Data residency
    
    # Provider preferences
    allowed_providers=["openai", "anthropic"],  # Whitelist
    blocked_providers=["provider-x"],           # Blacklist
    
    # Fallback behavior
    enable_fallback=True,
    fallback_max_attempts=3,
    allow_degradation=True     # Allow simpler output if all fail
)
```

---

## 8. Real-World Routing Examples

### Example 1: Simple Text Query
**Input**: "What's the capital of France?"
**Classifier**: Text, QA, complexity=1, quality=standard
**Optimizer**: Claude 3 Haiku ($0.0001, 95% quality) vs GPT-4o ($0.005, 99% quality)
**Decision**: Haiku (35x cheaper, quality sufficient)
**Result**: $0.0001, 200ms

### Example 2: Complex Code Review
**Input**: 3000-line Python file + "Review for security issues"
**Classifier**: Text, code-analysis, complexity=9, quality=premium
**Optimizer**: Only GPT-4o and Claude 3 Opus meet quality threshold
**Decision**: Claude 3 Opus (better at long context, slightly cheaper)
**Result**: $0.12, 8s

### Example 3: Image Generation
**Input**: "A photorealistic dragon breathing fire, 4K, cinematic lighting"
**Classifier**: Image, generation, complexity=8, quality=premium
**Optimizer**: DALL-E 3 ($0.08, 9.0 quality) vs SDXL ($0.02, 7.5 quality)
**Decision**: DALL-E 3 (user specified "photorealistic", quality preference wins)
**Result**: $0.08, 6s

### Example 4: Emergency Fallback
**Input**: Critical business analysis at 3 AM
**Primary**: GPT-4o -> 503 Service Unavailable
**Fallback 1**: Claude 3 Opus -> 429 Rate Limited
**Fallback 2**: Gemini Pro -> Success
**Result**: 1.2s total (with fallback), $0.08, user never knew there was an issue
