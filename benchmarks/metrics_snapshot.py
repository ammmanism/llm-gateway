"""Drive a few real requests and save the Prometheus exposition.

This proves the metric names and labels populate at runtime. It is a snapshot,
not a load test: the numbers are whatever this deterministic run produced.
"""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm_gateway.billing.cost_ledger import CostLedger
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.core import server
from llm_gateway.utils.embeddings import HashingEmbedder

OUTPUT = Path("data/evidence/prometheus_metrics_snapshot.txt")
LEDGER = Path("data/evidence/metrics_snapshot.sqlite3")
AUTH = {"Authorization": "Bearer sk-demo-tenant"}

REQUESTS = [
    {"prompt": "Explain vector databases", "model": "gpt-4o"},
    {"prompt": "Explain vector databases", "model": "gpt-4o"},
    {"prompt": "Write a haiku about caching", "model": "gpt-4o-mini"},
]


class FakeProvider:
    async def generate(self, prompt: str, **kwargs):
        return {
            "output": f"deterministic answer for: {prompt}",
            "provider": "fake",
            "model": kwargs.get("model", "gpt-4o"),
            "usage": {
                "prompt_tokens": max(1, len(prompt.split())),
                "completion_tokens": 12,
            },
            "mock": True,
        }


def main() -> None:
    LEDGER.unlink(missing_ok=True)
    ledger = CostLedger(str(LEDGER))
    cache = TwoTierCache(
        exact_cache=CacheManager(),
        semantic_index=SemanticIndex(embedder=HashingEmbedder()),
        threshold=0.85,
    )

    with (
        patch.object(server, "cost_ledger", ledger),
        patch.object(server, "two_tier_cache", cache),
        patch.object(
            server.ProviderFactory,
            "get_provider_for_model",
            staticmethod(lambda model: FakeProvider()),
        ),
    ):
        with TestClient(server.app) as client:
            for payload in REQUESTS:
                response = client.post("/generate", json=payload, headers=AUTH)
                body = response.json()
                print(payload["model"], response.status_code, body.get("cache_hit"))
            snapshot = client.get("/metrics")

    lines = [
        line
        for line in snapshot.text.splitlines()
        if line.startswith("llm_gateway_")
        and not line.startswith("llm_gateway_request_duration_ms_bucket")
    ]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {len(lines)} metric lines to {OUTPUT}")
    for key in (
        "llm_gateway_requests_total",
        "llm_gateway_cache_hits_total",
        "llm_gateway_cache_misses_total",
        "llm_gateway_total_cost_usd",
        "llm_gateway_prompt_tokens_count",
    ):
        matches = [line for line in lines if line.startswith(key)]
        print(key, "->", matches[:3])


if __name__ == "__main__":
    main()
