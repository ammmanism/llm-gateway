"""Compare token/cost accounting for OpenAI sync and streaming requests."""

import csv
import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ALLOW_DEMO_KEYS", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.pop("REDIS_URL", None)

from fastapi.testclient import TestClient  # noqa: E402

from llm_gateway.auth.budget_enforcer import BudgetEnforcer  # noqa: E402
from llm_gateway.auth.quota_manager import QuotaManager  # noqa: E402
from llm_gateway.billing.cost_ledger import CostLedger  # noqa: E402
from llm_gateway.cache.cache_manager import CacheManager  # noqa: E402
from llm_gateway.cache.two_tier import SemanticIndex, TwoTierCache  # noqa: E402
from llm_gateway.core import server  # noqa: E402
from llm_gateway.routing.adaptive import AdaptiveRouter  # noqa: E402
from llm_gateway.security.rate_limiter import RateLimiter  # noqa: E402
from llm_gateway.utils.embeddings import HashingEmbedder  # noqa: E402
from llm_gateway.utils.tokenizer import count_tokens  # noqa: E402

OUTPUT = Path("data/evidence/streaming_accounting.csv")
LEDGER = Path("data/evidence/streaming_accounting.sqlite3")
AUTH = {"Authorization": "Bearer sk-stream-evidence"}
REQUESTS = 20
MODEL = "gpt-4o"
OUTPUT_TEXT = "one two three four"


class FakeProvider:
    async def generate(self, prompt, **kwargs):
        return {
            "output": OUTPUT_TEXT,
            "provider": "openai",
            "model": MODEL,
            "usage": {
                "prompt_tokens": count_tokens(MODEL, prompt),
                "completion_tokens": count_tokens(MODEL, OUTPUT_TEXT),
            },
            "mock": True,
        }

    async def stream_generate(self, prompt, **kwargs):
        words = OUTPUT_TEXT.split()
        for index, word in enumerate(words):
            yield word + (" " if index < len(words) - 1 else "")


def parse_stream(text: str) -> tuple[int, int]:
    usage = None
    for line in text.splitlines():
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        payload = json.loads(line[6:])
        if payload.get("usage"):
            usage = payload["usage"]
    if usage is None:
        raise RuntimeError("stream response missing usage chunk")
    return int(usage["prompt_tokens"]), int(usage["completion_tokens"])


def main() -> None:
    LEDGER.unlink(missing_ok=True)
    ledger = CostLedger(str(LEDGER))
    cache = TwoTierCache(
        CacheManager(), SemanticIndex(HashingEmbedder()), threshold=1.0
    )
    provider = FakeProvider()
    records = []

    with (
        patch.object(server, "cost_ledger", ledger),
        patch.object(server, "two_tier_cache", cache),
        patch.object(server, "budget_enforcer", BudgetEnforcer(default_budget=100.0)),
        patch.object(server, "rate_limiter", RateLimiter(10**6, 10**9)),
        patch.object(server, "quota_manager", QuotaManager()),
        patch.object(server, "adaptive_router", AdaptiveRouter()),
        patch.object(
            server.ProviderFactory,
            "get_provider_for_model",
            staticmethod(lambda model: provider),
        ),
    ):
        with TestClient(server.app) as client:
            for index in range(REQUESTS):
                messages = [{"role": "user", "content": f"parity request {index}"}]
                sync = client.post(
                    "/v1/chat/completions",
                    headers=AUTH,
                    json={"model": MODEL, "messages": messages},
                )
                stream = client.post(
                    "/v1/chat/completions",
                    headers=AUTH,
                    json={"model": MODEL, "messages": messages, "stream": True},
                )
                if sync.status_code != 200 or stream.status_code != 200:
                    raise RuntimeError(sync.text + stream.text)
                sync_body = sync.json()
                stream_tokens = parse_stream(stream.text)
                records.append(
                    {
                        "request_index": index,
                        "mode": "non_streaming",
                        "prompt_tokens": sync_body["usage"]["prompt_tokens"],
                        "completion_tokens": sync_body["usage"]["completion_tokens"],
                    }
                )
                records.append(
                    {
                        "request_index": index,
                        "mode": "streaming",
                        "prompt_tokens": stream_tokens[0],
                        "completion_tokens": stream_tokens[1],
                    }
                )

    connection = sqlite3.connect(LEDGER)
    connection.row_factory = sqlite3.Row
    try:
        entries = connection.execute(
            "SELECT cost_usd, usage_source FROM cost_entries ORDER BY occurred_at"
        ).fetchall()
    finally:
        connection.close()
    if len(entries) != len(records):
        raise RuntimeError(f"expected {len(records)} ledger rows, got {len(entries)}")

    rows = []
    for record, entry in zip(records, entries):
        pair = records[record["request_index"] * 2 : record["request_index"] * 2 + 2]
        parity = (
            pair[0]["prompt_tokens"] == pair[1]["prompt_tokens"]
            and pair[0]["completion_tokens"] == pair[1]["completion_tokens"]
        )
        rows.append(
            {
                **record,
                "total_tokens": record["prompt_tokens"] + record["completion_tokens"],
                "cost_usd": f"{entry['cost_usd']:.10f}",
                "usage_source": entry["usage_source"],
                "parity_pass": parity,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUTPUT}")
    print(f"parity passed: {all(row['parity_pass'] for row in rows)}")
    LEDGER.unlink(missing_ok=True)
    if not all(row["parity_pass"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
