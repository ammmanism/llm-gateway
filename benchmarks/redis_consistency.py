"""Verify Redis-backed rate limiting, cache sharing, and budget aggregation."""

import argparse
import asyncio
import csv
import json
import subprocess
import sys
import uuid
from pathlib import Path

from llm_gateway.auth.budget_enforcer import BudgetEnforcer
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.security.rate_limiter import RateLimiter

OUTPUT = Path("data/evidence/redis_consistency.csv")
CACHE_KEY = "benchmark:shared-cache"
ATTEMPTS_PER_WORKER = 10
RPM_LIMIT = 10
BUDGET_COST = 0.1


async def worker(role: str, redis_url: str, run_id: str) -> dict:
    tenant = f"benchmark-{run_id}"
    limiter = RateLimiter(
        rpm_limit=RPM_LIMIT,
        tpm_limit=1_000_000,
        window_seconds=60,
    )
    limiter.redis_url = redis_url
    allowed = 0
    for _ in range(ATTEMPTS_PER_WORKER):
        result = await limiter.check_and_reserve(tenant, estimated_tokens=1)
        allowed += int(result.allowed)

    cache = CacheManager(redis_url=redis_url)
    if role == "writer":
        await cache.set(CACHE_KEY, {"worker": role, "run_id": run_id}, ttl=60)
        cache_read = None
    else:
        cache_read = None
        for _ in range(50):
            cache_read = await cache.get(CACHE_KEY)
            if cache_read is not None:
                break
            await asyncio.sleep(0.05)

    budget = BudgetEnforcer(default_budget=100.0)
    budget.redis_url = redis_url
    for _ in range(ATTEMPTS_PER_WORKER):
        await budget.add_cost(tenant, BUDGET_COST)
    spend = await budget.get_spend(tenant)

    return {
        "role": role,
        "allowed": allowed,
        "cache_read": cache_read,
        "budget_spend": spend,
    }


async def verify(redis_url: str) -> list[dict]:
    run_id = uuid.uuid4().hex
    command = [sys.executable, __file__, "--worker"]
    processes = [
        subprocess.Popen(
            [*command, role, redis_url, run_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for role in ("writer", "reader")
    ]
    results = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        if process.returncode != 0:
            raise RuntimeError(f"worker failed: {stderr}")
        results.append(json.loads(stdout))

    allowed = sum(result["allowed"] for result in results)
    reader = next(result for result in results if result["role"] == "reader")
    cache_shared = int(
        reader["cache_read"] is not None
        and reader["cache_read"].get("run_id") == run_id
    )
    budget_total = max(result["budget_spend"] for result in results)
    expected_budget = BUDGET_COST * ATTEMPTS_PER_WORKER * len(processes)

    return [
        {
            "check": "shared_rpm_limit",
            "workers": len(processes),
            "operations": ATTEMPTS_PER_WORKER * len(processes),
            "expected": RPM_LIMIT,
            "actual": allowed,
            "passed": allowed == RPM_LIMIT,
        },
        {
            "check": "cross_worker_exact_cache",
            "workers": len(processes),
            "operations": 1,
            "expected": 1,
            "actual": cache_shared,
            "passed": cache_shared == 1,
        },
        {
            "check": "concurrent_budget_increments",
            "workers": len(processes),
            "operations": ATTEMPTS_PER_WORKER * len(processes),
            "expected": round(expected_budget, 6),
            "actual": round(budget_total, 6),
            "passed": abs(budget_total - expected_budget) < 1e-9,
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--worker", nargs=3)
    args = parser.parse_args()

    if args.worker:
        role, redis_url, run_id = args.worker
        print(json.dumps(asyncio.run(worker(role, redis_url, run_id))))
        return

    rows = asyncio.run(verify(args.redis_url))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)
    print(f"wrote {OUTPUT}")
    if not all(row["passed"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
