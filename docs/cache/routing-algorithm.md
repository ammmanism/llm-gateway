# Active routing algorithm

`AdaptiveRouter` uses Thompson sampling over a Beta distribution per model:

- $\alpha = 1 + \text{successes}$
- $\beta = 1 + \text{failures}$

For each request it samples $\text{Beta}(\alpha, \beta)$ for every configured
model, sorts the samples descending, and returns that ordered list. New models
start with a uniform prior, so exploration decreases as evidence accumulates.

Statistics are stored in memory by default and in Redis hashes when `REDIS_URL`
is configured. Latency is recorded separately, but the current selection score
is the sampled success probability; the cost/latency weight fields are reserved
for future multi-objective work.

The older weighted-scalarization description was not implemented and has been
removed.
