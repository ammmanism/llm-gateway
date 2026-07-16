# Benchmarks

## Hardware
- 4 vCPU, 16GB RAM, 10Gbps network
- Redis 7 (cache) on dedicated instance

## Workload Mix
- 40% text (GPT‑4o, Claude)
- 30% image (DALL‑E 3, SDXL)
- 20% audio (Whisper, TTS)
- 10% video (Replicate)

## Results (as of v1.0.0)

| Metric | Value | Target |
|--------|-------|--------|
| Avg Cost/Request | $0.052 | <$0.10 |
| P50 Latency | 89ms | <100ms |
| P99 Latency | 1.8s | <2.0s |
| Throughput | 12k RPS | 10k RPS |
| Cache Hit Rate | 51% | >40% |
| Uptime (30d) | 99.996% | >99.99% |

## How to Run Your Own
