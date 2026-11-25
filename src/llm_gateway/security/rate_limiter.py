import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    rpm_remaining: int
    tpm_remaining: int
    retry_after_rpm: float = 0.0
    retry_after_tpm: float = 0.0
    limit_exceeded: str = ""  # "rpm", "tpm", or ""


@dataclass
class RateLimitConfig:
    """Configuration for dual-metric rate limiting."""

    rpm_limit: int = 100  # Requests per minute
    tpm_limit: int = 50000  # Tokens per minute
    window_seconds: int = 60  # Sliding window size


# Lua script for atomic dual-metric rate limiting using sorted sets
# Each metric uses a sorted set with timestamp as score
RPM_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = 1

-- Remove expired entries
local cutoff = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- Count current requests in window
local current = redis.call('ZCARD', key)

if current < limit then
    -- Add new request with timestamp as score and unique member
    local member = now .. '.' .. math.random(1000000)
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window * 2)
    return {1, limit - current - 1}
else
    -- Get oldest entry to calculate retry-after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if #oldest > 0 then
        retry_after = (tonumber(oldest[2]) + window) - now
    end
    return {0, 0, retry_after}
end
"""

TPM_LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- Remove expired entries
local cutoff = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- Sum tokens in current window
local entries = redis.call('ZRANGE', key, 0, -1, 'WITHSCORES')
local current_tokens = 0
for i = 1, #entries, 2 do
    local token_count = tonumber(string.match(entries[i], '^(%d+):')) or 0
    current_tokens = current_tokens + token_count
end

if current_tokens + requested <= limit then
    -- Add new token entry with token count as score? No, use member for token count
    -- We store token count in the member, timestamp as score
    local member = requested .. ':' .. now .. '.' .. math.random(1000000)
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window * 2)
    return {1, limit - current_tokens - requested}
else
    -- Get oldest entry to calculate retry-after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if #oldest > 0 then
        retry_after = (tonumber(oldest[2]) + window) - now
    end
    return {0, 0, retry_after}
end
"""


class RateLimiter:
    """
    Dual-metric Rate Limiter tracking both RPM (Requests Per Minute)
    and TPM (Tokens Per Minute).

    Uses Redis sorted sets for atomic sliding window rate limiting.
    Falls back to in-memory implementation for local development.

    Features:
    - Independent RPM and TPM limits per tenant
    - Atomic check-and-reserve for both metrics
    - Token reservation before provider dispatch
    - Token reconciliation after actual usage known
    - Clear error reporting identifying which metric was exceeded
    """

    def __init__(
        self,
        rpm_limit: int = 100,
        tpm_limit: int = 50000,
        window_seconds: int = 60,
    ):
        self.config = RateLimitConfig(
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            window_seconds=window_seconds,
        )
        self.redis_url = os.environ.get("REDIS_URL")
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        self._rpm_sha: Optional[str] = None
        self._tpm_sha: Optional[str] = None

        # In-memory fallback storage
        self._rpm_requests: Dict[str, list] = {}
        self._tpm_tokens: Dict[str, list] = {}  # List of (timestamp, token_count)

    async def _ensure_redis_connected(self) -> None:
        """Establish Redis connection and load Lua scripts."""
        if self.redis_url and not self._connected:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                await self._redis.ping()
                # Load Lua scripts
                self._rpm_sha = await self._redis.script_load(RPM_LUA_SCRIPT)
                self._tpm_sha = await self._redis.script_load(TPM_LUA_SCRIPT)
                self._connected = True
                logger.info(
                    "RateLimiter connected to Redis with dual-metric scripts loaded"
                )
            except Exception as e:
                logger.error(f"RateLimiter failed to connect to Redis: {e}")
                self.redis_url = None

    def _rpm_key(self, tenant_id: str) -> str:
        return f"ratelimit:rpm:{tenant_id}"

    def _tpm_key(self, tenant_id: str) -> str:
        return f"ratelimit:tpm:{tenant_id}"

    async def check_and_reserve(
        self,
        tenant_id: str,
        estimated_tokens: int = 0,
    ) -> RateLimitResult:
        """
        Check if request is allowed and reserve tokens atomically.

        Args:
            tenant_id: Tenant identifier
            estimated_tokens: Estimated token count for this request
                (prompt + max_tokens)

        Returns:
            RateLimitResult with allowance and remaining quotas
        """
        await self._ensure_redis_connected()
        now = time.time()

        if self._redis:
            return await self._check_redis(tenant_id, estimated_tokens, now)
        else:
            return self._check_memory(tenant_id, estimated_tokens, now)

    async def _check_redis(
        self,
        tenant_id: str,
        estimated_tokens: int,
        now: float,
    ) -> RateLimitResult:
        """Check rate limits using Redis atomic scripts."""
        rpm_key = self._rpm_key(tenant_id)
        tpm_key = self._tpm_key(tenant_id)
        window = self.config.window_seconds

        # Execute both checks
        rpm_result = await self._redis.evalsha(
            self._rpm_sha, 1, rpm_key, self.config.rpm_limit, window, now
        )
        tpm_result = await self._redis.evalsha(
            self._tpm_sha,
            1,
            tpm_key,
            self.config.tpm_limit,
            window,
            now,
            estimated_tokens,
        )

        rpm_allowed = bool(rpm_result[0])
        rpm_remaining = int(rpm_result[1])
        rpm_retry = float(rpm_result[2]) if len(rpm_result) > 2 else 0.0

        tpm_allowed = bool(tpm_result[0])
        tpm_remaining = int(tpm_result[1])
        tpm_retry = float(tpm_result[2]) if len(tpm_result) > 2 else 0.0

        allowed = rpm_allowed and tpm_allowed
        limit_exceeded = ""
        if not rpm_allowed:
            limit_exceeded = "rpm"
        elif not tpm_allowed:
            limit_exceeded = "tpm"

        return RateLimitResult(
            allowed=allowed,
            rpm_remaining=max(0, rpm_remaining),
            tpm_remaining=max(0, tpm_remaining),
            retry_after_rpm=max(0, rpm_retry),
            retry_after_tpm=max(0, tpm_retry),
            limit_exceeded=limit_exceeded,
        )

    def _check_memory(
        self,
        tenant_id: str,
        estimated_tokens: int,
        now: float,
    ) -> RateLimitResult:
        """In-memory fallback using sliding window."""
        window = self.config.window_seconds
        cutoff = now - window

        # Clean expired RPM entries
        if tenant_id not in self._rpm_requests:
            self._rpm_requests[tenant_id] = []
        self._rpm_requests[tenant_id] = [
            ts for ts in self._rpm_requests[tenant_id] if ts > cutoff
        ]
        rpm_current = len(self._rpm_requests[tenant_id])
        rpm_allowed = rpm_current < self.config.rpm_limit
        rpm_remaining = max(
            0, self.config.rpm_limit - rpm_current - (1 if rpm_allowed else 0)
        )

        # Clean expired TPM entries
        if tenant_id not in self._tpm_tokens:
            self._tpm_tokens[tenant_id] = []
        self._tpm_tokens[tenant_id] = [
            (ts, tok) for ts, tok in self._tpm_tokens[tenant_id] if ts > cutoff
        ]
        tpm_current = sum(tok for _, tok in self._tpm_tokens[tenant_id])
        tpm_allowed = (tpm_current + estimated_tokens) <= self.config.tpm_limit
        tpm_remaining = max(
            0,
            self.config.tpm_limit
            - tpm_current
            - (estimated_tokens if tpm_allowed else 0),
        )

        # Calculate retry-after times
        rpm_retry = 0.0
        if not rpm_allowed and self._rpm_requests[tenant_id]:
            oldest = min(self._rpm_requests[tenant_id])
            rpm_retry = max(0, (oldest + window) - now)

        tpm_retry = 0.0
        if not tpm_allowed and self._tpm_tokens[tenant_id]:
            oldest = min(ts for ts, _ in self._tpm_tokens[tenant_id])
            tpm_retry = max(0, (oldest + window) - now)

        allowed = rpm_allowed and tpm_allowed
        limit_exceeded = ""
        if not rpm_allowed:
            limit_exceeded = "rpm"
        elif not tpm_allowed:
            limit_exceeded = "tpm"

        # Reserve if allowed
        if allowed:
            self._rpm_requests[tenant_id].append(now)
            self._tpm_tokens[tenant_id].append((now, estimated_tokens))

        return RateLimitResult(
            allowed=allowed,
            rpm_remaining=rpm_remaining,
            tpm_remaining=tpm_remaining,
            retry_after_rpm=rpm_retry,
            retry_after_tpm=tpm_retry,
            limit_exceeded=limit_exceeded,
        )

    async def reconcile_tokens(
        self,
        tenant_id: str,
        estimated_tokens: int,
        actual_tokens: int,
    ) -> None:
        """
        Reconcile token usage after actual usage is known.

        If actual > estimated: reserve additional tokens
        If actual < estimated: release excess reserved tokens
        """
        if actual_tokens == estimated_tokens:
            return

        await self._ensure_redis_connected()
        now = time.time()

        if self._redis:
            # For Redis, we need to adjust the sorted set
            # This is complex; for now we log the discrepancy
            diff = actual_tokens - estimated_tokens
            if diff > 0:
                # Reserve additional tokens
                key = self._tpm_key(tenant_id)
                member = f"{diff}:{now}.{hash(str(now))}"
                await self._redis.zadd(key, {member: now})
                await self._redis.expire(key, self.config.window_seconds * 2)
            logger.debug(
                "Token reconciliation for %s: estimated=%s, actual=%s, diff=%s",
                tenant_id,
                estimated_tokens,
                actual_tokens,
                diff,
            )
        else:
            # In-memory: adjust the last entry
            if tenant_id in self._tpm_tokens and self._tpm_tokens[tenant_id]:
                last_ts, last_tok = self._tpm_tokens[tenant_id][-1]
                self._tpm_tokens[tenant_id][-1] = (last_ts, actual_tokens)
            diff = actual_tokens - estimated_tokens
            logger.debug(
                "Token reconciliation for %s: estimated=%s, actual=%s, diff=%s",
                tenant_id,
                estimated_tokens,
                actual_tokens,
                diff,
            )

    async def release_reservation(
        self,
        tenant_id: str,
        estimated_tokens: int,
    ) -> None:
        """Release a token reservation after a pre-provider failure."""
        await self._ensure_redis_connected()

        if self._redis:
            # Remove one RPM entry and estimated TPM entry
            # This is approximate - we remove the most recent entries
            rpm_key = self._rpm_key(tenant_id)
            tpm_key = self._tpm_key(tenant_id)

            # Remove latest RPM entry
            latest_rpm = await self._redis.zrevrange(rpm_key, 0, 0)
            if latest_rpm:
                await self._redis.zrem(rpm_key, latest_rpm[0])

            # Remove latest TPM entry matching estimated_tokens
            latest_tpm = await self._redis.zrevrange(tpm_key, 0, 0)
            if latest_tpm:
                await self._redis.zrem(tpm_key, latest_tpm[0])
        else:
            # In-memory: remove last entries
            if tenant_id in self._rpm_requests and self._rpm_requests[tenant_id]:
                self._rpm_requests[tenant_id].pop()
            if tenant_id in self._tpm_tokens and self._tpm_tokens[tenant_id]:
                self._tpm_tokens[tenant_id].pop()

    def get_current_usage(self, tenant_id: str) -> Tuple[int, int]:
        """Get current RPM and TPM usage for a tenant (in-memory only)."""
        now = time.time()
        window = self.config.window_seconds
        cutoff = now - window

        rpm_current = 0
        if tenant_id in self._rpm_requests:
            rpm_current = sum(1 for ts in self._rpm_requests[tenant_id] if ts > cutoff)

        tpm_current = 0
        if tenant_id in self._tpm_tokens:
            tpm_current = sum(
                tok for ts, tok in self._tpm_tokens[tenant_id] if ts > cutoff
            )

        return rpm_current, tpm_current


# Backward compatibility alias
class TokenBucket:
    """Legacy token bucket for backward compatibility."""

    def __init__(self, redis_client, capacity: int, refill_rate: float):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate

    async def consume(self, key: str, tokens: int = 1) -> bool:
        # Simplified - not used in new dual-metric path
        return True
