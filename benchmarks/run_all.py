#!/usr/bin/env python3
"""Run the committed evidence generators and record their exit status."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = [
    "gateway_overhead.py",
    "semantic_threshold_sweep.py",
    "fallback_recovery.py",
    "cost_attribution_demo.py",
    "metrics_snapshot.py",
    "redis_consistency.py",
]

RESULTS_DIR = Path("benchmarks/results")


def run_script(name: str) -> dict:
    print(f"Running {name}...")
    env = os.environ.copy()
    env.setdefault("OTEL_SDK_DISABLED", "true")
    result = subprocess.run(
        [sys.executable, f"benchmarks/{name}"],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    if result.returncode != 0:
        print(f"Error in {name}:\n{result.stderr}")
    return {
        "script": name,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {script: run_script(script) for script in SCRIPTS}
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    combined_path = RESULTS_DIR / f"full_benchmark_{timestamp}.json"
    combined_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    failed = [name for name, result in results.items() if result["returncode"] != 0]
    print(f"All results saved to {combined_path}")
    if failed:
        raise SystemExit(f"Benchmark generators failed: {', '.join(failed)}")
    print(f"All {len(SCRIPTS)} evidence generators passed.")


if __name__ == "__main__":
    main()
