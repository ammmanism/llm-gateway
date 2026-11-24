"""Generate a real cost-attribution CSV by driving the gateway through TestClient.

The provider is a deterministic fake so the run needs no API keys. Every row in
the output comes from the gateway's own SQLite ledger, not from hand-written
numbers.
"""

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm_gateway.billing.cost_ledger import CostLedger
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache
from llm_gateway.core import server
from llm_gateway.utils.embeddings import HashingEmbedder

OUTPUT = Path("data/evidence/cost_ledger_sample.csv")
LEDGER = Path("data/evidence/cost_ledger_sample.sqlite3")
AUTH = {"Authorization": "Bearer sk-demo-tenant"}

PROMPTS = [
    ("gpt-4o", "Summarize the theory of relativity", False),
    ("gpt-4o", "Summarize the theory of relativity", False),
    ("gpt-4o", "Summarize the theory of relativity", True),
    ("gpt-4o-mini", "List three uses of vector databases", False),
    ("claude-3-haiku-20240307", "Write a haiku about caching", False),
]


class FakeProvider:
    async def generate(self, prompt: str, **kwargs):
        model = kwargs.get("model", "gpt-4o")
        return {
            "output": f"deterministic answer for: {prompt}",
            "provider": "fake",
            "model": model,
            "usage": {
                "prompt_tokens": max(1, len(prompt.split())),
                "completion_tokens": 12,
            },
            "mock": True,
        }


def main() -> None:
    if LEDGER.exists():
        LEDGER.unlink()
    ledger = CostLedger(str(LEDGER))
    cache = TwoTierCache(
        exact_cache=CacheManager(),
        semantic_index=SemanticIndex(embedder=HashingEmbedder()),
        threshold=0.95,
    )

    with patch.object(server, "cost_ledger", ledger), patch.object(
        server, "two_tier_cache", cache
    ), patch.object(
        server.ProviderFactory,
        "get_provider_for_model",
        staticmethod(lambda model: FakeProvider()),
    ):
        with TestClient(server.app) as client:
            for model, prompt, live_data in PROMPTS:
                response = client.post(
                    "/generate",
                    json={
                        "prompt": prompt,
                        "model": model,
                        "live_data": live_data,
                    },
                    headers=AUTH,
                )
                print(model, response.status_code, response.json().get("cache_hit"))

            day = datetime.now(timezone.utc).date().isoformat()
            costs = client.get(f"/v1/costs?date={day}", headers=AUTH)
            print("cost summary:", costs.json()["total_cost_usd"])

    connection = sqlite3.connect(LEDGER)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT request_id, tenant_id, provider, model, prompt_tokens, "
        "completion_tokens, cost_usd, cache_hit, usage_source, occurred_at, day "
        "FROM cost_entries ORDER BY occurred_at"
    ).fetchall()
    connection.close()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "request_id",
                "tenant_id",
                "provider",
                "model",
                "prompt_tokens",
                "completion_tokens",
                "cost_usd",
                "cache_hit",
                "usage_source",
                "occurred_at",
                "day",
            ]
        )
        for row in rows:
            writer.writerow([row[key] for key in row.keys()])
    print(f"wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
