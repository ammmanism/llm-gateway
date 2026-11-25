# Competitive analysis: llm-gateway vs LiteLLM, Portkey, and Bifrost

**Scope and honesty disclosure.** This document compares architecture and
documented features, not measured throughput. I did not run LiteLLM, Portkey, or
Bifrost on the same machine, so I make **no performance claims about them**. The
competitor columns summarize their public documentation as of November 2026 and
may be incomplete or out of date; check their docs before making a decision.
The only measured numbers in this repo are the ones in `data/evidence/*.csv`,
produced by the scripts in `benchmarks/` against this codebase.

## Where this project actually sits

`llm-gateway` is a **compact, auditable Python reference implementation** of the
core ideas behind a production AI gateway: dual-metric rate limiting, a real
three-state circuit breaker, data-driven fallback, a two-tier cache with a
measured threshold trade-off, per-attempt cost attribution, and OpenTelemetry /
Prometheus instrumentation.

It is **not** a drop-in replacement for the projects below. LiteLLM has a far
larger provider catalogue and community. Portkey and Bifrost ship hardened,
high-performance gateways with enterprise control planes. This project's value
is that a reviewer can read the whole thing, run the tests, and reproduce every
number from a committed CSV.

## Feature comparison

Legend: ✅ implemented here and tested · 🟡 partial or basic · ➖ not a goal ·
❔ not verified in this repo (check the vendor's docs).

| Capability | llm-gateway | LiteLLM | Portkey | Bifrost |
|---|---|---|---|---|
| Language / runtime | Python (FastAPI) | Python proxy | TypeScript/Node gateway | Go binary |
| Provider breadth | 8 adapters (OpenAI, Anthropic, Gemini, Groq, Together, Ollama, vLLM, DeepSeek) | 100+ providers | 250+ models (1,600+ claimed) | 25+ providers |
| OpenAI-compatible API | Partial (`/generate`, `/generate/stream`) | ✅ | ✅ | ✅ |
| Fallback on 429/5xx / open circuit | ✅ YAML chain, tested | ✅ | ✅ | ✅ |
| Circuit breaker with limited half-open probes | ✅ CLOSED/OPEN/HALF_OPEN, probe cap, tests | ✅ | ✅ | ✅ |
| Dual-metric rate limiting (RPM + TPM) | ✅ per tenant, Redis Lua + in-memory fallback | ✅ | ✅ | ✅ |
| Per-tenant budgets / virtual keys | 🟡 atomic tenant spending cap + API-key tenant map; not a full key database | ✅ virtual keys, budgets | ✅ | ✅ virtual keys, budgets |
| Exact cache | ✅ Redis or in-process TTL | ✅ | ✅ | ✅ |
| Semantic cache | ✅ in-process FAISS HNSW, neural embeddings, measured threshold sweep | ✅ Redis/Valkey-backed | ✅ simple + semantic | ✅ |
| Cache threshold evidence committed | ✅ `semantic_threshold_sweep.csv` incl. hard negatives | ❔ | ❔ | ❔ |
| Per-request cost ledger | ✅ SQLite, one row per `(request_id, attempt)`, cache hits at $0 | ✅ spend tracking | ✅ | ✅ |
| OpenTelemetry spans with token/cost attrs | ✅ | ✅ integrations | ✅ | ✅ |
| Prometheus `/metrics` | ✅ | ✅ | ✅ | ✅ |
| Guardrails / PII firewall | 🟡 regex PII detection + sanitization | 🟡 via integrations | ✅ 60+ guardrails | 🟡 |
| MCP gateway | ➖ | ➖ | ❔ | ✅ |
| Managed UI / control plane | ➖ | 🟡 admin UI | ✅ | ✅ web UI |
| Committed, reproducible evidence artifacts | ✅ every claim maps to a CSV + script | ❔ | ❔ | ❔ |
| Test suite | ✅ 87 passing with Redis (`pytest tests/ -q`) | ✅ | ✅ | ✅ |

## What is genuinely differentiated here

1. **Evidence discipline.** `data/evidence/` contains the CSV behind each claim,
   and `benchmarks/` contains the script that regenerates it. The README quotes
   those files rather than aspirational targets.
2. **Semantic cache trade-off is measured, not asserted.** The sweep includes
   hard negatives (near-domain, different-intent queries) so it shows the real
   risk: at `0.80` one adjacent-intent query is answered from the wrong cache
   entry; at `0.85` that disappears while 29.2% of paraphrases still hit.
   `0.95`, the previous default, matched nothing on the same set.
3. **The circuit breaker is a real state machine.** It caps concurrent
   half-open probes, records provider names in `CircuitOpenError`, and has a
   timeline benchmark that separates detection time from recovery time.
4. **Cost attribution is per attempt.** Fallback attempts get distinct ledger
   rows, and cache hits are recorded at zero cost so request counts stay honest.
5. **Small surface area.** A reviewer can read the core files in an afternoon.

## Where this project is weaker — plainly

- **Provider coverage.** Eight adapters versus dozens to hundreds. Adding a
  provider here means writing and testing an adapter.
- **Deployment maturity.** No Helm chart, no multi-region story, no managed
  control plane. The Redis paths now have a two-worker consistency check, but
  not a high-scale load test.
- **Distributed consistency.** The FAISS semantic index is per process.
  Multi-replica semantic caching needs a shared vector store; exact caching,
  RPM/TPM limiting, and budget counters can use Redis.
- **Auth.** The API-key middleware is a demonstration: it checks a prefix and
  maps keys to tenants via `TENANT_API_KEYS`. It is not a virtual-key database
  with rotation, scopes, or per-key budgets.
- **Guardrails.** Regex PII detection only. Portkey's guardrail catalogue and
  Bifrost's MCP gateway are out of scope here.
- **Coverage.** Branch coverage is **50.21%**. Ruff lint and formatting are green,
  and CI publishes the full coverage report; raising coverage toward 80% is the
  next quality goal.

## When to choose which

- Choose **LiteLLM** for the widest provider coverage, a mature Python proxy,
  and a large integration ecosystem.
- Choose **Portkey** or **Bifrost** for a hardened gateway with a UI, guardrails,
  virtual keys, and a team behind it; Bifrost if a compiled Go data plane
  matters to you.
- Read **llm-gateway** if you want a small, test-backed reference for how the
  pieces fit together, with every benchmark number traceable to a committed CSV.
  It is a portfolio-grade engineering artifact, not a production replacement.
