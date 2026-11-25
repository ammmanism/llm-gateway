import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.smart_router import smart_router


def run_benchmark():
    num_routes = 10000

    print(f"Running {num_routes} routing decisions...")
    start = time.time()

    for _ in range(num_routes):
        # Simulate varying token counts
        smart_router.route(request_tokens=500)

    end = time.time()
    duration = end - start

    report = {
        "benchmark": "router",
        "routes": num_routes,
        "total_seconds": round(duration, 4),
        "average_latency_ms": round((duration / num_routes) * 1000, 4),
        "throughput_routes_per_sec": round(num_routes / duration, 2),
    }
    Path("benchmarks/reports").mkdir(parents=True, exist_ok=True)
    Path("benchmarks/reports/router.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_benchmark()
