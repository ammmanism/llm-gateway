# Lessons learned

Engineering notes from the five-phase overhaul. Each item is something that
changed a decision in this repo, not a generic best practice.

## 1. Measure the gateway, not the console

The first overhead run reported **240 ms p50**. The gateway was not slow:
`StructuredLoggingMiddleware` was writing a JSON line per request to a Windows
console, and `httpx` was logging every call. Disabling console logging and
re-running gave **10.5 ms p50**. Benchmarks now set `logging.disable(CRITICAL)`
and the methodology says so. A number that measures terminal I/O is not a
gateway number.

## 2. Paired samples beat sequential blocks on a noisy machine

Running 200 direct calls and then 200 gateway calls lets CPU frequency and
background load drift between the two blocks. The benchmark now interleaves one
direct sample and one gateway sample, then takes the **per-pair difference**.
The result reproduced within 0.1 ms across runs (10.476 vs 10.486 ms).

## 3. Report concurrency separately — it tells a different story

Sequential p50 is **10.5 ms**. At 8 concurrent requests the p50 is **60.7 ms**
and throughput is **114.7 req/s** on this Windows dev box. Both live in the same
CSV with a `concurrency` column. Publishing only the flattering number would
have been dishonest; publishing only the concurrent number would have obscured
where the per-request cost comes from.

## 4. A benchmark CSV schema is an API — define every column precisely

The first fallback CSV reported `successful_failover_rate = 0.0` for every
scenario because it divided successes by *all* events, including poll
rejections. `requests_failed_during_switch` was counting rejected probes, not
failed switches. The rewritten schema separates:

- `time_to_detect_ms` — start to circuit OPEN
- `time_to_switch_ms` — OPEN to recovered CLOSED
- `requests_failed_before_open` — real provider failures that tripped the breaker
- `requests_rejected_while_open` — fail-fast rejections (expected behaviour)
- `recovery_probe_attempts` / `recovery_probe_success_rate`

If a column name needs a paragraph to explain, rename the column.

## 5. Fix bad attribution at the source

`CircuitBreaker.allow_request()` raised `CircuitOpenError("unknown", ...)`.
Providers patched `e.provider` after catching, but the exception message — and
therefore every timeline event — still said `unknown`. The breaker now takes a
`name` and constructions pass it. One-line fix, but only after noticing that
every "provider" in the evidence was the same useless string.

## 6. Defaults must be data-driven

The semantic cache shipped with `similarity_threshold: 0.95`. On 24 labelled
paraphrases it matched **zero**. The sweep moved the default to `0.85`, which
kept a 29.2% hit rate with no false positives on the same set. A plausible
default is not the same as a measured one.

## 7. Easy negatives hide the real failure mode

With only unrelated-domain distractors, every threshold showed **0% false
positives** — the sweep looked perfect and proved nothing. Adding hard negatives
(near-domain, different-intent queries) exposed the actual risk: at `0.80`,
"capital of Germany" is answered from the "capital of France" entry. That is the
kind of error semantic caching is dangerous for, and it only appears when the
test set contains it.

## 8. Move durability off the request path

Per-entry SQLite commits measured **15–25 ms** each. The ledger now enqueues
entries and a background worker writes batches with WAL and `busy_timeout`.
The request path only enqueues; `flush()`/`close()` wait for durability when a
caller actually needs it.

## 9. Idempotency keys need the attempt number

A fallback chain can produce several attempts for one logical request. Keying
the ledger on `request_id` alone would make attempt 2 overwrite attempt 1. The
primary key is `(request_id, attempt)`.

## 10. Cache hits are still requests

It is tempting to omit cache hits from usage accounting because they cost
nothing. That makes request counts wrong. Hits are recorded with `cost_usd=0`,
`cache_hit=True`, and `usage_source="cache"`, so `/v1/costs` counts them while
reporting zero spend.

## 11. Quarantine tests with a written reason

`tests/modality` targeted `SemanticRouter`, `CostOptimizer`, and `FallbackChain`
APIs that no longer exist. Deleting it would erase the signal that this work is
unfinished. It moved to `_superseded/tests-modality/` with a README explaining
the mismatch and what would be needed to revive it.

## 12. Every figure must read a committed CSV

`benchmarks/plot_evidence.py` has no hard-coded data. It parses
`data/evidence/*.csv` and renders the PNGs. If the CSV is wrong, the chart is
wrong in the same way and the mistake is visible in review. Numbers in prose are
copied from the CSV, never from memory.

## 13. Read the component before blaming it

The 240 ms latency looked like batching. `NexusBatcher.submit` is a pass-through
that awaits the executor directly. Reading 30 lines saved a rewrite of a
component that was not on the critical path.

## 14. Honest gaps are more credible than a perfect scorecard

The README no longer claims 42% coverage, a 96% cost reduction, or "7 pass / 2
fail". It states the measured overhead, the measured cache trade-off, the
measured recovery times, the real test count, and links `GAP_ANALYSIS.md` for
what is missing (Grafana screenshot, trace export, Redis load tests). Reviewers
trust a scorecard that admits its holes.

## 15. Keep lint debt from hiding new debt

`ruff check .` was already red on legacy long lines. Running focused
`ruff check` on each new file kept the new code clean while the legacy cleanup
stays a separate, reviewable task.
