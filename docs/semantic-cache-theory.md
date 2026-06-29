# Semantic Cache Theory

## Why Cosine Similarity?

Semantic caching relies on embedding vectors. We use `sentence-transformers/all-MiniLM-L6-v2` which produces a 384-dimensional vector $v \in \mathbb{R}^{384}$.

Cosine similarity between two vectors $A$ and $B$ is defined as:
$$ \text{similarity} = \cos(\theta) = \frac{A \cdot B}{\|A\| \|B\|} $$

By L2-normalizing our vectors before indexing, $\|A\| = \|B\| = 1$, the cosine similarity simplifies to the dot product:
$$ \text{similarity} = A \cdot B $$

This is extremely fast to compute and allows us to use FAISS's `METRIC_INNER_PRODUCT` for optimized search.

## Complexity Analysis

1.  **Embedding Generation:** $O(L^2)$ where $L$ is sequence length (bounded by max 256 tokens). Constant time $O(1)$ relative to cache size.
2.  **HNSW Search:** Hierarchical Navigable Small World graphs provide $O(\log N)$ search time complexity, where $N$ is the number of cached vectors.
3.  **Overall Latency:** embedding (~5ms) + search (~2ms) = <10ms total.

## Cache Hit Rate vs. Exact Match

Let $Q$ be the set of incoming queries.
An exact match cache hits only if $q_i = q_j$.
A semantic cache hits if $\text{sim}(E(q_i), E(q_j)) \geq \tau$, where $\tau$ is the threshold (e.g., 0.92).

Because language is highly variant, the probability $P(\text{sim} \geq \tau) \gg P(q_i = q_j)$. In production workloads, exact match rarely exceeds 5% hit rate, while semantic caching easily achieves 40-60%.
