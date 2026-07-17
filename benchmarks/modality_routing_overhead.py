#!/usr/bin/env python3
"""
Measure additional latency introduced by modality detection and routing logic.
"""
import json
import time
from pathlib import Path

def detect_content_type(content):
    if content.startswith("![image]") or content.startswith("data:image"):
        return "image"
    if content.startswith("http") and any(ext in content for ext in [".mp4", ".avi", ".mov"]):
        return "video"
    return "text"

def route_to_modality(content_type, content):
    _ = (content_type, content)
    return content_type

def simulate_request(content, use_routing=True):
    start = time.perf_counter()
    if use_routing:
        content_type = detect_content_type(content)
        route_to_modality(content_type, content)
    return time.perf_counter() - start

if __name__ == "__main__":
    samples = [
        "text only here",
        "![image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==)",
        "https://example.com/video.mp4",
    ]
    overheads = []
    for sample in samples:
        with_routing = simulate_request(sample, use_routing=True)
        without_routing = simulate_request(sample, use_routing=False)
        overheads.append(with_routing - without_routing)

    result = {
        "average_overhead_ms": round(sum(overheads) / len(overheads) * 1000, 2),
        "max_overhead_ms": round(max(overheads) * 1000, 2),
        "samples": len(samples),
    }
    out_file = Path("benchmarks/results/modality_overhead.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
