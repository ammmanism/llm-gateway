import redis.asyncio as redis
from typing import Tuple, Dict, Any, Optional
from pydantic import BaseModel

class TenantConfig(BaseModel):
    id: str
    tier: str
    rate_limit_rpm: int
    rate_limit_tpm: int
    spend_cap_usd: Optional[float]
    alert_threshold: Optional[float]
    routing_weights: Optional[Dict[str, float]]
    allowed_models: Optional[list[str]]

class TenantManager:
    # Lua script for token bucket rate limiting
    LUA_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])

    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(bucket[1]) or capacity
    local last_refill = tonumber(bucket[2]) or now

    -- Refill tokens based on elapsed time (in seconds)
    local elapsed = math.max(0, now - last_refill)
    tokens = math.min(capacity, tokens + elapsed * refill_rate)

    if tokens >= requested then
        tokens = tokens - requested
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) * 2)
        return {1, tokens}  -- allowed, remaining
    else
        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) * 2)
        return {0, tokens}  -- denied, remaining
    end
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._script = self.redis.register_script(self.LUA_SCRIPT)
        
    async def get_tenant_by_key(self, api_key: str) -> Optional[TenantConfig]:
        """Fetch tenant config from DB/Cache based on API key hash. Mocked for now."""
        # In a real system, this would hash the api_key and look up in Postgres/Redis
        if not api_key:
            return None
            
        # Mock tenant mapping
        if api_key == "test_key_free":
            return TenantConfig(id="tenant_free_1", tier="free", rate_limit_rpm=20, rate_limit_tpm=10000, spend_cap_usd=5.0, alert_threshold=4.0, routing_weights=None, allowed_models=None)
        elif api_key == "test_key_pro":
            return TenantConfig(id="tenant_pro_1", tier="pro", rate_limit_rpm=200, rate_limit_tpm=100000, spend_cap_usd=200.0, alert_threshold=150.0, routing_weights={"cost": 0.3, "latency": 0.5, "reliability": 0.2}, allowed_models=None)
            
        return TenantConfig(id="tenant_default", tier="free", rate_limit_rpm=20, rate_limit_tpm=10000, spend_cap_usd=10.0, alert_threshold=8.0, routing_weights=None, allowed_models=None)

    async def check_rate_limit(self, tenant: TenantConfig, estimated_tokens: int = 1000) -> Tuple[bool, int, str]:
        """
        Check both RPM (requests per minute) and TPM (tokens per minute) limits.
        Returns: (allowed, remaining_requests, error_reason)
        """
        import time
        now = int(time.time())
        
        # RPM Bucket
        rpm_key = f"rate_limit:{tenant.id}:rpm"
        rpm_capacity = tenant.rate_limit_rpm
        rpm_refill = rpm_capacity / 60.0 # tokens per second
        
        # TPM Bucket
        tpm_key = f"rate_limit:{tenant.id}:tpm"
        tpm_capacity = tenant.rate_limit_tpm
        tpm_refill = tpm_capacity / 60.0
        
        # Execute scripts
        rpm_result = await self._script(keys=[rpm_key], args=[rpm_capacity, rpm_refill, now, 1])
        tpm_result = await self._script(keys=[tpm_key], args=[tpm_capacity, tpm_refill, now, estimated_tokens])
        
        rpm_allowed, rpm_remaining = rpm_result
        tpm_allowed, tpm_remaining = tpm_result
        
        if not rpm_allowed:
            return False, rpm_remaining, "RPM limit exceeded"
        if not tpm_allowed:
            # Revert RPM token if TPM failed (not implemented in this simplified version)
            return False, rpm_remaining, "TPM limit exceeded"
            
        return True, rpm_remaining, ""
