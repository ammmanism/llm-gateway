# Routing Algorithm

## Multi-Objective Optimization

Neurocache routes requests based on three objectives:
1. Minimize Cost ($C$)
2. Minimize Latency ($L$)
3. Maximize Reliability ($R$)

Subject to a constraint:
- Quality ($Q$) $\geq \tau_{quality}$

## Weighted Scalarization

We convert the multi-objective problem into a single-objective problem using scalarization:

$$ S_p = w_c (1 - \hat{C}_p) + w_l (1 - \hat{L}_p) + w_r \hat{R}_p $$

Where $\hat{C}_p$ and $\hat{L}_p$ are normalized cost and latency (min-max normalization across all available providers), and $\hat{R}_p$ is the reliability score (1 - error rate).

The router selects $\text{argmax}_p (S_p)$.

## Exploration via Thompson Sampling

To prevent the router from permanently ignoring a provider (which might improve over time), 10% of traffic is routed using Thompson Sampling.

Each provider is modeled as a Beta distribution: $\text{Beta}(\alpha, \beta)$ where $\alpha = \text{successes} + 1$, $\beta = \text{failures} + 1$. We sample from each distribution and pick the maximum, naturally balancing exploration and exploitation.