#!/usr/bin/env python3
"""
Test multi-tenant isolation: concurrent tenants with quotas.
"""
import json
import threading
import time
from pathlib import Path

class TenantManager:
    def __init__(self):
        self.tenants = {}
    def create_tenant(self, tenant_id, quota):
        self.tenants[tenant_id] = {"quota": quota, "usage": 0.0}
    def check_quota(self, tenant_id):
        if tenant_id not in self.tenants:
            return False
        return self.tenants[tenant_id]["usage"] < self.tenants[tenant_id]["quota"]
    def log_request(self, tenant_id, cost):
        if tenant_id in self.tenants:
            self.tenants[tenant_id]["usage"] += cost
    def get_usage(self, tenant_id):
        if tenant_id in self.tenants:
            return self.tenants[tenant_id]["usage"]
        return 0

tm_global = TenantManager()
lock = threading.Lock()

def tenant_worker(tenant_id, quota, requests_to_make):
    for _ in range(requests_to_make):
        with lock:
            if tm_global.check_quota(tenant_id):
                tm_global.log_request(tenant_id, cost=0.01)
            else:
                return False
        time.sleep(0.01)
    return True

if __name__ == "__main__":
    tenants = {
        "tenant_a": {"quota": 100, "requests": 50},
        "tenant_b": {"quota": 100, "requests": 150},
        "tenant_c": {"quota": 200, "requests": 80},
    }
    for tid, cfg in tenants.items():
        tm_global.create_tenant(tid, quota=cfg["quota"])

    threads = []
    for tid, cfg in tenants.items():
        t = threading.Thread(target=tenant_worker, args=(tid, cfg["quota"], cfg["requests"]))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    results = {}
    for tid in tenants:
        usage = tm_global.get_usage(tid)
        results[tid] = {
            "quota": tenants[tid]["quota"],
            "used": round(usage, 2),
            "within_quota": usage <= tenants[tid]["quota"],
        }

    out_file = Path("benchmarks/results/multi_tenant.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
