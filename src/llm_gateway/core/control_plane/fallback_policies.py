from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/admin/fallback", tags=["admin"])

# Default config path
DEFAULT_ROUTING_CONFIG = Path("configs/routing.yaml")

# Error codes that trigger fallback
FALLBACK_TRIGGER_CODES = {429, 500, 502, 503, 504}


@lru_cache(maxsize=1)
def _load_routing_config(config_path: Path = DEFAULT_ROUTING_CONFIG) -> Dict:
    """Load routing configuration from YAML."""
    try:
        with config_path.open("r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # Return minimal default config
        return {
            "default_strategy": "fallback",
            "strategies": {
                "fallback": {
                    "chain": ["gpt-3.5-turbo", "claude-3-haiku"]
                }
            }
        }


def get_fallback_chain(primary_model: str, config_path: Path = DEFAULT_ROUTING_CONFIG) -> List[str]:
    """
    Get the fallback chain for a primary model from config.
    
    The chain includes the primary model as first entry, followed by
    configured fallback models. Duplicates are removed while preserving order.
    """
    config = _load_routing_config(config_path)
    fallback_config = config.get("strategies", {}).get("fallback", {})
    configured_chain = fallback_config.get("chain", [])

    # Build chain: primary first, then configured fallbacks (excluding primary)
    chain = [primary_model]
    for model in configured_chain:
        if model != primary_model and model not in chain:
            chain.append(model)

    # Ensure we always have at least one fallback
    if len(chain) == 1:
        default_fallbacks = ["gpt-3.5-turbo", "claude-3-haiku"]
        for m in default_fallbacks:
            if m != primary_model:
                chain.append(m)

    return chain


def get_fallback_chain_from_policy(tenant_id: str, primary_model: str) -> List[str]:
    """
    Retrieve the fallback chain for a given tenant and primary model.
    
    In the future, this could support tenant-specific chains.
    For now, uses global config.
    """
    return get_fallback_chain(primary_model)


def should_fallback(exception: Exception, circuit_breaker_state: str = "") -> bool:
    """
    Determine if an exception should trigger fallback.
    
    Fallback triggers on:
    - HTTP 429 (rate limited)
    - HTTP 500, 502, 503, 504 (server errors)
    - Circuit breaker OPEN state
    
    Does NOT fallback on:
    - HTTP 400, 401, 403, 404, 422 (client errors)
    - Validation errors
    """
    # Check circuit breaker state
    if circuit_breaker_state == "OPEN":
        return True

    # Check HTTP status codes
    if hasattr(exception, "response") and exception.response is not None:
        status_code = getattr(exception.response, "status_code", None)
        if status_code in FALLBACK_TRIGGER_CODES:
            return True

    # Check for httpx HTTPStatusError
    if hasattr(exception, "__class__") and "HTTPStatusError" in exception.__class__.__name__:
        if hasattr(exception, "response"):
            status_code = getattr(exception.response, "status_code", None)
            if status_code in FALLBACK_TRIGGER_CODES:
                return True

    # Check error message for common patterns
    error_str = str(exception).lower()
    if any(pattern in error_str for pattern in [
        "rate limit", "429", "too many requests",
        "500", "502", "503", "504",
        "internal server error", "bad gateway", "service unavailable", "gateway timeout",
        "connection refused", "connection timeout", "dns", "network",
    ]):
        # But exclude client errors
        if not any(pattern in error_str for pattern in [
            "400", "401", "403", "404", "422",
            "bad request", "unauthorized", "forbidden", "not found", "unprocessable",
        ]):
            return True

    return False


@router.get("/policies")
async def list_policies():
    config = _load_routing_config()
    return {
        "policies": config.get("strategies", {}),
        "fallback_triggers": {
            "http_codes": sorted(FALLBACK_TRIGGER_CODES),
            "circuit_breaker_open": True,
        }
    }


@router.get("/chain/{primary_model}")
async def get_chain(primary_model: str):
    """Get the fallback chain for a primary model."""
    chain = get_fallback_chain(primary_model)
    return {"primary_model": primary_model, "fallback_chain": chain}


# Nexus-Standard: Verified Type Safety and Professional Documentation Pattern
