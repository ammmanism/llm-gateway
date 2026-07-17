# Design Tradeoffs

## Semantic vs Exact Cache
- **Exact** is simple and guaranteed correct, but misses paraphrases.
- **Semantic** catches rephrased queries, but adds latency (embedding + FAISS search) and may occasionally return a non-exact match.
- **We chose hybrid**: exact first, then semantic on miss. Threshold tuned to 0.92 - high enough to avoid false positives, low enough to catch most paraphrases.

## Circuit Breaker Threshold
- Failure threshold = 3 consecutive failures. Why not 2? Too sensitive to transient flukes.
- Recovery timeout = 5 seconds. Long enough to let the provider stabilise, short enough to avoid prolonged downtime.

## Cost-Aware vs Latency-Aware
- We weighted cost more heavily (0.7) because LLM costs dominate monthly bills, but we also consider latency (0.3) to maintain user experience.

All parameters are configurable via YAML - we provide sensible defaults but allow tuning per deployment.
