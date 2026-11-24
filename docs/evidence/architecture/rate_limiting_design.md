# Dual-Metric Rate Limiting Design

## Overview

This document describes the dual-metric rate limiting implementation in `llm-gateway`. Unlike traditional rate limiters that only track requests per minute (RPM), this implementation simultaneously enforces both RPM and tokens per minute (TPM) limits, which is essential for LLM workloads where token consumption varies dramatically between requests.

## Why Dual-Metric?

LLM API costs and resource consumption are token-based, not request-based. A single request can consume anywhere from a few tokens to hundreds of thousands. RPM-only limiting:
- Allows token-heavy requests to consume disproportionate resources
- Fails to protect upstream providers that enforce TPM limits
- Cannot accurately attribute costs or enforce fair usage

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RateLimiter                              │
├─────────────────────────────────────────────────────────────────┤
│  check_and_reserve(tenant_id, estimated_tokens)                │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────┐    ┌─────────────┐                            │
│  │   RPM       │    │   TPM       │                            │
│  │   Check     │    │   Check     │                            │
│  │ (1 req)     │    │ (N tokens)  │                            │
│  └──────┬──────┘    └──────┬──────┘                            │
│         │                  │                                    │
│         └────────┬─────────┘                                    │
│                  ▼                                              │
│         ┌─────────────────┐                                     │
│         │  Both Allowed?  │                                     │
│         └────────┬────────┘                                     │
│         Yes  │  No                                              │
│           ▼  ▼                                                 │
│      Reserve  │  Reject with                                     │
│      Tokens   │  limit_exceeded: "rpm" or "tpm"                │
└───────────────┴─────────────────────────────────────────────────┘
```

## Data Structures

### Redis (Production)
- **RPM**: Sorted set `ratelimit:rpm:{tenant_id}` with timestamps as scores
- **TPM**: Sorted set `ratelimit:tpm:{tenant_id}` with timestamps as scores, token counts encoded in members
- **Atomicity**: Lua scripts execute check-and-reserve atomically
- **Expiration**: Keys expire at `2 * window_seconds` for automatic cleanup

### In-Memory (Development)
- `Dict[tenant_id, List[timestamp]]` for RPM
- `Dict[tenant_id, List[(timestamp, token_count)]]` for TPM
- Sliding window cleanup on each check

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rpm_limit` | 100 | Maximum requests per minute per tenant |
| `tpm_limit` | 50,000 | Maximum tokens per minute per tenant |
| `window_seconds` | 60 | Sliding window duration |

## Request Flow

1. **Estimate Tokens**: Before provider call, estimate `prompt_tokens + max_completion_tokens`
2. **Check & Reserve**: Atomically check both RPM and TPM, reserve capacity
3. **Provider Call**: Execute request to LLM provider
4. **Reconcile**: Compare actual tokens vs estimate, adjust reservation
5. **Release on Error**: If provider call fails, release reservation

## Error Responses

When rate limit is exceeded, returns HTTP 429 with headers:
```
X-RateLimit-RPM-Remaining: 0
X-RateLimit-TPM-Remaining: 1234
Retry-After: 30
```

Response body identifies which limit was exceeded:
```json
{"detail": "RPM rate limit exceeded"}
{"detail": "TPM rate limit exceeded"}
```

## Token Reconciliation

Since estimates may differ from actual usage:
- **Under-estimate**: Additional tokens reserved automatically
- **Over-estimate**: Excess tokens released back to pool
- **Logged**: Discrepancies logged for monitoring

## Fallback Integration

Rate limiting is checked **once per request**, not per fallback attempt. If the primary provider fails and fallback triggers, the same reservation is used. This prevents a single request from consuming multiple rate limit slots during failover.

## Testing

Unit tests cover:
- RPM-only exhaustion
- TPM-only exhaustion  
- Sliding window expiry
- Tenant isolation
- Token reconciliation
- Redis and in-memory parity

Run tests:
```bash
python -m pytest tests/security/test_rate_limiter.py -v
```

## Evidence

Benchmark results for rate limiting effectiveness:
- `data/evidence/rate_limiting_benchmark.csv` (Phase 3)