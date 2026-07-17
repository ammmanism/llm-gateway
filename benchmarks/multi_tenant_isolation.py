#!/usr/bin/env python3
"""
Test multi-tenant isolation using the real BudgetEnforcer.
Concurrent simulated tenant traffic with quota enforcement.
"""
import asyncio
import json
import time
from pathlib import Path

from llm_gateway.auth.budget_enforcer import BudgetEnforcer


async def tenant_worker(be, tenant_id, budget, requests_to_make):
    """Simulate a tenant making requests until budget exhausted."""
    made = 0
    for _ in range(requests_to_make):
        ok = await be.check_budget(tenant_id, estimated_cost=0.01)
        if not ok:
            break
        await be.add_cost(tenant_id, cost=0.01)
        made += 1
        await asyncio.sleep(0.01)
    return made


async def main():
    be = BudgetEnforcer(default_budget=1.0)

    tenants = {
        "tenant_a": {"budget": 1.0, "requests": 50},
        "tenant_b": {"budget": 1.0, "requests": 150},
        "tenant_c": {"budget": 2.0, "requests": 80},
    }

    start = time.perf_counter()
    tasks = []
    for tid, cfg in tenants.items():
        tasks.append(tenant_worker(be, tid, cfg["budget"], cfg["requests"]))
    results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    output = {}
    for i, tid in enumerate(tenants):
        cfg = tenants[tid]
        usage = await be.get_spend(tid)
        output[tid] = {
            "quota": cfg["budget"],
            "used": round(usage, 2),
            "requests_made": results[i],
            "requests_attempted": cfg["requests"],
            "within_quota": usage <= cfg["budget"],
        }

    out_file = Path("benchmarks/results/multi_tenant.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
