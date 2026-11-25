import os
import uuid

import pytest
import redis.asyncio as redis

from llm_gateway.security.rate_limiter import RateLimiter

REDIS_URL = os.environ.get("REDIS_URL")
pytestmark = pytest.mark.skipif(
    not REDIS_URL, reason="REDIS_URL is required for Redis integration tests"
)


async def cleanup(tenant_id: str) -> None:
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.delete(f"ratelimit:rpm:{tenant_id}", f"ratelimit:tpm:{tenant_id}")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_redis_tpm_script_sums_token_members():
    tenant = f"test-tpm-{uuid.uuid4().hex}"
    limiter = RateLimiter(rpm_limit=10, tpm_limit=10, window_seconds=60)
    limiter.redis_url = REDIS_URL
    try:
        first = await limiter.check_and_reserve(tenant, estimated_tokens=4)
        second = await limiter.check_and_reserve(tenant, estimated_tokens=4)
        third = await limiter.check_and_reserve(tenant, estimated_tokens=4)

        assert first.allowed is True
        assert first.tpm_remaining == 6
        assert second.allowed is True
        assert second.tpm_remaining == 2
        assert third.allowed is False
        assert third.limit_exceeded == "tpm"
    finally:
        await cleanup(tenant)


@pytest.mark.asyncio
async def test_redis_rpm_limit_is_enforced():
    tenant = f"test-rpm-{uuid.uuid4().hex}"
    limiter = RateLimiter(rpm_limit=1, tpm_limit=100, window_seconds=60)
    limiter.redis_url = REDIS_URL
    try:
        first = await limiter.check_and_reserve(tenant, estimated_tokens=1)
        second = await limiter.check_and_reserve(tenant, estimated_tokens=1)

        assert first.allowed is True
        assert second.allowed is False
        assert second.limit_exceeded == "rpm"
    finally:
        await cleanup(tenant)


@pytest.mark.asyncio
async def test_redis_token_reconciliation_adds_excess_usage():
    tenant = f"test-reconcile-{uuid.uuid4().hex}"
    limiter = RateLimiter(rpm_limit=10, tpm_limit=10, window_seconds=60)
    limiter.redis_url = REDIS_URL
    try:
        await limiter.check_and_reserve(tenant, estimated_tokens=4)
        await limiter.reconcile_tokens(tenant, estimated_tokens=4, actual_tokens=12)
        result = await limiter.check_and_reserve(tenant, estimated_tokens=1)

        assert result.allowed is False
        assert result.limit_exceeded == "tpm"
    finally:
        await cleanup(tenant)
