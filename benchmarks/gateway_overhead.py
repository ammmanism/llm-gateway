"""Measure in-process gateway overhead against a direct provider call.

Method
------
* Direct: call the same fake provider coroutine directly in the event loop.
* Gateway: POST /generate through the real FastAPI app with httpx ASGITransport,
  using `live_data=true` so caching is bypassed.

Both paths run in the same process and event loop. Samples are collected in
interleaved pairs (direct, then gateway) so slow-machine drift affects both
equally; the reported overhead is the per-pair difference. Console logging is
disabled because writing hundreds of synchronous log lines to a Windows console
costs far more than the gateway's own work and is not representative of a
production deployment with async logging.

The result is the gateway's own processing cost (middleware, auth, validation,
rate limiting, routing, provider dispatch, metrics, cost-ledger enqueue) and
excludes upstream provider latency.
"""

import asyncio
import csv
import logging
import statistics
import time
from pathlib import Path
from unittest.mock import patch

import httpx

from llm_gateway.billing.cost_ledger import CostLedger
from llm_gateway.core import server
from llm_gateway.security.rate_limiter import RateLimiter

logging.disable(logging.CRITICAL)

OUTPUT = Path("data/evidence/gateway_overhead_benchmark.csv")
LEDGER = Path("data/evidence/gateway_overhead.sqlite3")
AUTH = {"Authorization": "Bearer sk-overhead"}
WARMUP = 50
REQUESTS = 500
THROUGHPUT_REQUESTS = 200
THROUGHPUT_CONCURRENCY = 8


class FakeProvider:
    async def generate(self, prompt: str, **kwargs):
        return {
            "output": "ok",
            "provider": "fake",
            "model": kwargs.get("model", "gpt-4o"),
            "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            "mock": True,
        }


def percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


async def timed(coro_factory):
    start = time.perf_counter_ns()
    await coro_factory()
    return (time.perf_counter_ns() - start) / 1_000_000


async def main() -> None:
    LEDGER.unlink(missing_ok=True)
    provider = FakeProvider()
    ledger = CostLedger(str(LEDGER))

    with patch.object(
        server.ProviderFactory,
        "get_provider_for_model",
        staticmethod(lambda model: provider),
    ), patch.object(
        server,
        "rate_limiter",
        RateLimiter(rpm_limit=10**6, tpm_limit=10**9, window_seconds=60),
    ), patch.object(
        server, "cost_ledger", ledger
    ):
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://gateway",
            headers=AUTH,
        ) as client:

            async def direct_call():
                await provider.generate("direct probe", model="gpt-4o")

            async def gateway_call(i):
                response = await client.post(
                    "/generate",
                    json={
                        "prompt": f"gateway overhead probe {i}",
                        "model": "gpt-4o",
                        "live_data": True,
                    },
                )
                if response.status_code != 200:
                    raise RuntimeError(response.text)

            for _ in range(WARMUP):
                await direct_call()
                await gateway_call(-1)

            direct = []
            gateway = []
            overhead = []
            for i in range(REQUESTS):
                d = await timed(direct_call)
                g = await timed(lambda i=i: gateway_call(i))
                direct.append(d)
                gateway.append(g)
                overhead.append(g - d)

            # Separate concurrent throughput measurement.
            throughput_latency = []
            semaphore = asyncio.Semaphore(THROUGHPUT_CONCURRENCY)

            async def one(i):
                async with semaphore:
                    throughput_latency.append(await timed(lambda i=i: gateway_call(i)))

            wall_start = time.perf_counter()
            await asyncio.gather(*(one(i) for i in range(THROUGHPUT_REQUESTS)))
            wall = time.perf_counter() - wall_start

    await ledger.close()

    rows = [
        {
            "path": "direct_provider_call",
            "requests": REQUESTS,
            "concurrency": 1,
            "p50_ms": round(statistics.median(direct), 3),
            "p95_ms": round(percentile(direct, 0.95), 3),
            "p99_ms": round(percentile(direct, 0.99), 3),
            "requests_per_second": round(REQUESTS / sum(direct) * 1000, 1),
        },
        {
            "path": "gateway_http",
            "requests": REQUESTS,
            "concurrency": 1,
            "p50_ms": round(statistics.median(gateway), 3),
            "p95_ms": round(percentile(gateway, 0.95), 3),
            "p99_ms": round(percentile(gateway, 0.99), 3),
            "requests_per_second": round(REQUESTS / sum(gateway) * 1000, 1),
        },
        {
            "path": "overhead_delta",
            "requests": REQUESTS,
            "concurrency": 1,
            "p50_ms": round(statistics.median(overhead), 3),
            "p95_ms": round(percentile(overhead, 0.95), 3),
            "p99_ms": round(percentile(overhead, 0.99), 3),
            "requests_per_second": "",
        },
        {
            "path": "gateway_http_concurrent",
            "requests": THROUGHPUT_REQUESTS,
            "concurrency": THROUGHPUT_CONCURRENCY,
            "p50_ms": round(statistics.median(throughput_latency), 3),
            "p95_ms": round(percentile(throughput_latency, 0.95), 3),
            "p99_ms": round(percentile(throughput_latency, 0.99), 3),
            "requests_per_second": round(THROUGHPUT_REQUESTS / wall, 1),
        },
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(row)
    print(f"wrote {OUTPUT}")
    try:
        LEDGER.unlink(missing_ok=True)
    except PermissionError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
