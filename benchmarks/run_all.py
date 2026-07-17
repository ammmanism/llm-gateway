#!/usr/bin/env python3
"""
Run all benchmarks and aggregate results into results/.
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SCRIPTS = [
    "cache_hit_rate.py",
    "routing_vs_naive.py",
    "failover_recovery.py",
    "multi_tenant_isolation.py",
    "modality_routing_overhead.py",
]

RESULTS_DIR = Path("benchmarks/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def run_script(name):
    print(f"Running {name}...")
    result = subprocess.run([sys.executable, f"benchmarks/{name}"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error in {name}:\n{result.stderr}")
        return None
    try:
        data = json.loads(result.stdout)
        return data
    except json.JSONDecodeError:
        print(f"Invalid JSON from {name}: {result.stdout}")
        return None

def main():
    all_results = {}
    for script in SCRIPTS:
        data = run_script(script)
        if data is not None:
            key = script.replace(".py", "")
            all_results[key] = data

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    combined_path = RESULTS_DIR / f"full_benchmark_{timestamp}.json"
    with open(combined_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"All results saved to {combined_path}")
    print("Individual results are in benchmarks/results/ as well.")

if __name__ == "__main__":
    main()
