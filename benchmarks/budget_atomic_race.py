"""Verify atomic budget reservations under concurrent demand."""

import argparse
import asyncio
import csv
import json
import subprocess
import sys
import uuid
from pathlib import Path

from llm_gateway.auth.budget_enforcer import BudgetEnforcer

OUTPUT = Path("data/evidence/budget_atomic_race.csv")
BUDGET_USD = 1.0
ESTIMATED_COST_USD = 0.01
ATTEMPTS_PER_WORKER = 100
WORKERS = 2


async def memory_scenario() -> dict:
    enforcer = BudgetEnforcer(default_budget=BUDGET_USD)
    enforcer.redis_url = None
    results = await asyncio.gather(
        *(
            enforcer.reserve_budget("memory-tenant", ESTIMATED_COST_USD)
            for _ in range(ATTEMPTS_PER_WORKER * WORKERS)
        )
    )
    allowed = sum(result.allowed for result in results)
    spent = await enforcer.get_spend("memory-tenant")
    return row("memory_single_process", 1, allowed, spent)


async def worker(redis_url: str, tenant: str) -> dict:
    enforcer = BudgetEnforcer(default_budget=BUDGET_USD)
    enforcer.redis_url = redis_url
    allowed = 0
    for _ in range(ATTEMPTS_PER_WORKER):
        result = await enforcer.reserve_budget(tenant, ESTIMATED_COST_USD)
        allowed += int(result.allowed)
    return {"allowed": allowed, "spent": await enforcer.get_spend(tenant)}


async def redis_scenario(redis_url: str) -> dict:
    tenant = f"benchmark-budget-{uuid.uuid4().hex}"
    command = [sys.executable, __file__, "--worker", redis_url, tenant]
    processes = [
        subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(WORKERS)
    ]
    results = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        if process.returncode != 0:
            raise RuntimeError(f"budget worker failed: {stderr}")
        results.append(json.loads(stdout))

    allowed = sum(result["allowed"] for result in results)
    spent = max(result["spent"] for result in results)
    return row("redis_two_workers", WORKERS, allowed, spent)


def row(scenario: str, workers: int, allowed: int, spent: float) -> dict:
    operations = ATTEMPTS_PER_WORKER * WORKERS
    overspend = max(0.0, spent - BUDGET_USD)
    return {
        "scenario": scenario,
        "workers": workers,
        "operations": operations,
        "budget_usd": BUDGET_USD,
        "estimated_cost_usd": ESTIMATED_COST_USD,
        "allowed": allowed,
        "rejected": operations - allowed,
        "total_spent_usd": round(spent, 6),
        "overspend_usd": round(overspend, 6),
        "passed": allowed == 100 and overspend <= 1e-12,
    }


async def verify(redis_url: str) -> list[dict]:
    return [await memory_scenario(), await redis_scenario(redis_url)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--worker", nargs=2)
    args = parser.parse_args()

    if args.worker:
        redis_url, tenant = args.worker
        print(json.dumps(asyncio.run(worker(redis_url, tenant))))
        return

    rows = asyncio.run(verify(args.redis_url))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for item in rows:
        print(item)
    print(f"wrote {OUTPUT}")
    if not all(item["passed"] for item in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
