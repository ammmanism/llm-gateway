import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import trace as otel_trace
from pydantic import BaseModel, Field

from llm_gateway.auth.admin.router import router as tenant_admin_router
from llm_gateway.auth.budget_enforcer import BudgetEnforcer
from llm_gateway.auth.cached_key_store import CachedVirtualKeyStore
from llm_gateway.auth.key_store import VirtualKeyStore
from llm_gateway.auth.postgres_key_store import PostgresVirtualKeyStore
from llm_gateway.auth.quota_manager import QuotaManager
from llm_gateway.billing.cost_ledger import CostLedger, new_entry
from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.cache.semantic import semantic_cache
from llm_gateway.cache.two_tier import TwoTierCache
from llm_gateway.core.control_plane.fallback_policies import (
    get_fallback_chain_from_policy,
    should_fallback,
)
from llm_gateway.core.control_plane.fallback_policies import router as fallback_router
from llm_gateway.core.control_plane.router import init_admin_deps
from llm_gateway.core.control_plane.router import router as admin_router
from llm_gateway.core.core.batcher import NexusBatcher
from llm_gateway.core.core.cost_tracker import NexusCostTracker
from llm_gateway.core.core.heartbeat import HeartbeatMonitor
from llm_gateway.core.openai_compat import (
    ChatCompletionRequest,
    completion_id,
    completion_response,
    flatten_messages,
)
from llm_gateway.observability.logging_middleware import StructuredLoggingMiddleware
from llm_gateway.observability.metrics.cost_metrics import record_cost
from llm_gateway.observability.metrics.prometheus import (
    failure_counter,
    metrics_endpoint,
    record_budget_rejection,
    record_cache_hit,
    record_cache_miss,
    record_failure,
    record_fallback,
    record_latency,
    record_rate_limit_rejection,
    record_request,
    record_tokens,
    update_budget_remaining,
    update_rate_limit_remaining,
)
from llm_gateway.observability.metrics.prometheus import (
    record_cost as record_cost_metric,
)
from llm_gateway.observability.tracing.open_telemetry import init_tracing, trace_span
from llm_gateway.providers.factory import ProviderFactory
from llm_gateway.reliability.chaos_controller import ChaosMode, chaos
from llm_gateway.routing.adaptive import AdaptiveRouter
from llm_gateway.routing.cost_aware import CostAwareRouter
from llm_gateway.routing.fallback import FallbackRouter
from llm_gateway.routing.latency_aware import LatencyAwareRouter
from llm_gateway.routing.load_balancing.least_busy import LeastBusyBalancer

# Security
from llm_gateway.security.auth import APIKeyAuthMiddleware
from llm_gateway.security.cors import configure_cors
from llm_gateway.security.firewall import SentinelFirewall
from llm_gateway.security.headers import SecurityHeadersMiddleware
from llm_gateway.security.rate_limiter import RateLimiter
from llm_gateway.utils.template_manager import template_manager
from llm_gateway.utils.usage import extract_token_usage

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global components
health_checker = HeartbeatMonitor(check_interval=30)
load_balancer = LeastBusyBalancer()
cache_manager = CacheManager()
two_tier_cache = TwoTierCache.from_config()
cost_ledger = CostLedger(os.environ.get("COST_LEDGER_PATH", "data/cost_ledger.sqlite3"))
quota_manager = QuotaManager()
budget_enforcer = BudgetEnforcer()
rate_limiter = RateLimiter(rpm_limit=100, tpm_limit=50000, window_seconds=60)
adaptive_router = AdaptiveRouter()
request_batcher = NexusBatcher()
cost_tracker = NexusCostTracker()
_key_rate_limiters: dict[tuple[int, int], RateLimiter] = {}
_key_budget_enforcers: dict[float, BudgetEnforcer] = {}


def _request_limiters(req: Request, tenant_id: str):
    key_id = getattr(req.state, "key_id", None)
    scope = tenant_id
    if key_id and key_id != "demo":
        scope = f"{tenant_id}:{key_id}"

    rpm_limit = getattr(req.state, "rpm_limit", None)
    tpm_limit = getattr(req.state, "tpm_limit", None)
    if rpm_limit and tpm_limit:
        limits = (int(rpm_limit), int(tpm_limit))
        limiter = _key_rate_limiters.setdefault(
            limits, RateLimiter(rpm_limit=limits[0], tpm_limit=limits[1])
        )
    else:
        limiter = rate_limiter

    budget_usd = getattr(req.state, "budget_usd", None)
    if budget_usd is not None:
        budget = float(budget_usd)
        enforcer = _key_budget_enforcers.setdefault(
            budget, BudgetEnforcer(default_budget=budget)
        )
    else:
        enforcer = budget_enforcer
    return scope, limiter, enforcer


# Initialize admin dependencies
init_admin_deps(cache_manager, quota_manager, budget_enforcer, health_checker)


async def _create_virtual_key_store():
    database_url = os.environ.get("DATABASE_URL", "")
    pool = None
    if database_url.startswith("postgresql://") or database_url.startswith(
        "postgres://"
    ):
        pool = await asyncpg.create_pool(database_url)
        store = PostgresVirtualKeyStore(pool)
        await store.initialize()
    else:
        store = VirtualKeyStore(os.environ.get("API_KEY_DB_PATH"))

    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        store = CachedVirtualKeyStore(
            store,
            redis.from_url(redis_url, decode_responses=True),
        )
    return store, pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting LLM Gateway...")
    key_store, key_store_pool = await _create_virtual_key_store()
    app.state.virtual_key_store = key_store
    app.state.key_store_pool = key_store_pool
    # Initialize OpenTelemetry
    init_tracing(app, service_name="llm-gateway")
    ProviderFactory.get_all_providers()
    try:
        await semantic_cache.initialize()
    except Exception as exc:
        logger.warning("Legacy semantic cache unavailable: %s", exc)
    await health_checker.start()
    logger.info("Gateway ready")
    yield
    await health_checker.stop()
    try:
        await cost_ledger.close()
    except Exception as exc:
        logger.warning("Cost ledger shutdown failed: %s", exc)
    if key_store_pool is not None:
        await key_store_pool.close()
    logger.info("Gateway shutdown")


app = FastAPI(title="LLM Gateway", version="6.0.0", lifespan=lifespan)

# Security middleware stack
configure_cors(app)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    APIKeyAuthMiddleware,
    exclude_paths={"/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/admin"},
)
app.add_middleware(StructuredLoggingMiddleware)

# Include routers
app.include_router(admin_router)
app.include_router(tenant_admin_router)
app.include_router(fallback_router)

# Routers
cost_router = CostAwareRouter()
latency_router = LatencyAwareRouter()
fallback_router_logic = FallbackRouter()


class GenerateRequest(BaseModel):
    prompt: Optional[str] = None
    template_id: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = "default"
    use_cache: bool = True
    live_data: bool = False
    prefer_latency: bool = False
    model: Optional[str] = None
    stream: bool = False
    max_tokens: int = Field(default=1024, ge=1, le=128000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    model: str
    output: str
    provider: str
    latency_ms: float
    mock: bool = False
    cache_hit: bool = False
    cache_tier: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


def build_cache_key(
    tenant_id: str,
    prompt: str,
    model: str = "default",
    params: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a stable, model/parameter-aware key without storing prompt text."""
    payload = json.dumps(
        {
            "tenant": tenant_id,
            "model": model,
            "params": params or {},
            "prompt": prompt,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"cache:{hashlib.sha256(payload.encode()).hexdigest()}"


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "providers": {
            name: status.value for name, status in health_checker.status.items()
        },
        "chaos": chaos.get_mode(),
    }


@app.get("/metrics")
async def get_metrics():
    return metrics_endpoint()


@app.get("/v1/costs")
async def get_costs(
    req: Request,
    date: Optional[str] = None,
    model: Optional[str] = None,
):
    """Return tenant-scoped cost attribution for one UTC day."""
    tenant_id = getattr(req.state, "tenant_id", "default")
    day = date or datetime.now(timezone.utc).date().isoformat()
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD") from exc
    return await cost_ledger.summarize(tenant_id, day, model)


@app.get("/v1/cache/stats")
async def cache_stats(req: Request):
    """Return cache hit/miss analytics for the authenticated tenant."""
    from llm_gateway.cache.analytics import get_cache_analytics

    tenant_id = getattr(req.state, "tenant_id", "default")
    pg_pool = getattr(req.app.state, "pg_pool", None)
    return await get_cache_analytics(pg_pool, tenant_id)


@app.post("/v1/cache/warm")
async def warm_cache(req: Request, file: UploadFile = File(...)):
    """Warm the semantic cache from an uploaded JSONL file."""
    from llm_gateway.cache.warmer import warm_cache_from_jsonl

    tenant_id = getattr(req.state, "tenant_id", "default")
    content = (await file.read()).decode("utf-8")
    count = await warm_cache_from_jsonl(content, tenant_id)
    return {"status": "success", "entries_warmed": count}


@app.post("/admin/chaos/{mode}")
async def set_chaos_mode(mode: str, failure_rate: float = 0.1, latency_ms: int = 100):
    """Enable chaos mode for testing (admin only)."""
    if mode == "off":
        chaos.disable()
    elif mode == "failure":
        chaos.enable(ChaosMode.FAILURE, failure_rate=failure_rate)
    elif mode == "latency":
        chaos.enable(ChaosMode.LATENCY, base_latency_ms=latency_ms)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")
    return {"chaos_mode": chaos.get_mode()}


@app.post("/generate")
@trace_span("generate_request")
async def generate(request: GenerateRequest, req: Request):
    start_time = time.perf_counter()

    if hasattr(req.state, "tenant_id"):
        request.tenant_id = req.state.tenant_id
    limit_scope, active_rate_limiter, active_budget_enforcer = _request_limiters(
        req, request.tenant_id
    )

    # Get current span for attribute enrichment
    current_span = otel_trace.get_current_span()
    request_id = getattr(req.state, "request_id", None) or str(uuid.uuid4())

    # Templating resolution
    prompt_text = request.prompt
    if request.template_id:
        try:
            prompt_text = template_manager.render(
                request.template_id, request.variables or {}
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not prompt_text:
        raise HTTPException(
            status_code=400, detail="Either 'prompt' or 'template_id' must be provided"
        )

    # Validation & Sanitization
    is_valid, error_msg = SentinelFirewall.validate(prompt_text, request.tenant_id)
    if not is_valid:
        record_failure(request.tenant_id, "validation")
        if current_span:
            current_span.set_attribute("error.type", "validation")
            current_span.set_attribute("error.message", error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    prompt_sanitized = SentinelFirewall.sanitize(prompt_text)

    # Set common span attributes early
    if current_span:
        current_span.set_attribute("tenant_id", request.tenant_id)
        current_span.set_attribute("prompt_length", len(prompt_sanitized))
        current_span.set_attribute("use_cache", request.use_cache)

    # Rate limiting - estimate tokens for TPM check
    # Rough estimate: prompt tokens + max completion tokens (default 1024)
    estimated_prompt_tokens = len(prompt_sanitized.split())
    estimated_completion_tokens = 1024  # default max_tokens
    estimated_total_tokens = estimated_prompt_tokens + estimated_completion_tokens

    rate_limit_result = await active_rate_limiter.check_and_reserve(
        limit_scope,
        estimated_tokens=estimated_total_tokens,
    )
    if not rate_limit_result.allowed:
        record_failure(request.tenant_id, "rate_limit")
        record_rate_limit_rejection(request.tenant_id, rate_limit_result.limit_exceeded)
        update_rate_limit_remaining(
            request.tenant_id, "rpm", rate_limit_result.rpm_remaining
        )
        update_rate_limit_remaining(
            request.tenant_id, "tpm", rate_limit_result.tpm_remaining
        )
        if current_span:
            current_span.set_attribute("error.type", "rate_limit")
            current_span.set_attribute(
                "rate_limit.exceeded", rate_limit_result.limit_exceeded
            )
        retry_after = max(
            rate_limit_result.retry_after_rpm, rate_limit_result.retry_after_tpm
        )
        limit_type = rate_limit_result.limit_exceeded.upper()
        raise HTTPException(
            status_code=429,
            detail=f"{limit_type} rate limit exceeded",
            headers={
                "X-RateLimit-RPM-Remaining": str(rate_limit_result.rpm_remaining),
                "X-RateLimit-TPM-Remaining": str(rate_limit_result.tpm_remaining),
                "Retry-After": str(int(retry_after) + 1),
            },
        )

    # Multi-tenant quota
    if not await quota_manager.check_quota(
        request.tenant_id, tokens=len(prompt_sanitized.split())
    ):
        record_failure(request.tenant_id, "quota")
        raise HTTPException(status_code=429, detail="Quota exceeded")

    # Adaptive Routing Toggle
    use_adaptive = os.environ.get("ADAPTIVE_ROUTING", "true").lower() == "true"
    if request.model:
        models = [request.model]
    elif use_adaptive:
        models = await adaptive_router.select_models({"prompt": prompt_sanitized})
    else:
        models = await cost_router.select_models({"prompt": prompt_sanitized})

    if not models:
        record_failure(request.tenant_id, "provider")
        raise HTTPException(status_code=503, detail="No models available for request")

    # Get fallback chain from dynamic policy
    fallback_models = get_fallback_chain_from_policy(request.tenant_id, models[0])

    # Cache check (exact tier first, then semantic tier)
    cache_model = request.model or models[0]
    cache_params = {
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }
    cache_enabled = request.use_cache and not request.live_data
    if cache_enabled:
        cached = await two_tier_cache.get(
            prompt_sanitized,
            tenant_id=request.tenant_id,
            model=cache_model,
            params=cache_params,
        )
        if cached:
            latency = (time.perf_counter() - start_time) * 1000
            cached_value = cached.value
            record_latency(
                request.tenant_id,
                cached_value["model"],
                cached_value["provider"],
                latency,
            )
            record_cache_hit(request.tenant_id, cached.tier)
            record_request(
                request.tenant_id,
                cached_value["model"],
                cached_value["provider"],
                "cache_hit",
            )
            if current_span:
                current_span.set_attribute("cache_hit", True)
                current_span.set_attribute("cache_tier", cached.tier)
                current_span.set_attribute("cache_similarity", cached.similarity)
                current_span.set_attribute("model", cached_value["model"])
                current_span.set_attribute("provider", cached_value["provider"])
                current_span.set_attribute("latency_ms", latency)
                current_span.set_attribute("cost_usd", 0.0)

            await cost_ledger.record(
                new_entry(
                    request_id=request_id,
                    attempt=0,
                    tenant_id=request.tenant_id,
                    provider=cached_value["provider"],
                    model=cached_value["model"],
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    cache_hit=True,
                    usage_source="cache",
                )
            )

            return GenerateResponse(
                model=cached_value["model"],
                output=cached_value["output"],
                provider=cached_value["provider"],
                latency_ms=latency,
                mock=cached_value.get("mock", False),
                cache_hit=True,
                cache_tier=cached.tier,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
            )

    # Inner generation with batching support
    async def execute_generation(m_name, p_text):
        provider = ProviderFactory.get_provider_for_model(m_name)
        if not provider:
            raise Exception(f"No provider for {m_name}")

        # Inject Chaos
        if chaos.should_fail(provider.__class__.__name__):
            raise Exception("Chaos injected failure")
        await chaos.inject_latency(provider.__class__.__name__)

        return await provider.generate(
            prompt=p_text,
            model=m_name,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

    # Try models in chain
    last_error = None
    for m_name in fallback_models:
        attempt_estimated_cost = cost_tracker.estimate_text_cost(
            m_name, prompt_sanitized
        )
        reservation = await active_budget_enforcer.reserve_budget(
            limit_scope, attempt_estimated_cost
        )
        if not reservation.allowed:
            record_failure(request.tenant_id, "budget")
            record_budget_rejection(request.tenant_id)
            update_budget_remaining(request.tenant_id, reservation.remaining_usd)
            raise HTTPException(
                status_code=402,
                detail=(
                    "Budget exceeded; remaining budget is "
                    f"${reservation.remaining_usd:.4f}"
                ),
            )

        budget_settled = False
        try:
            # Wrap with batcher for small requests
            result = await request_batcher.submit(
                m_name,
                prompt_sanitized,
                request.tenant_id,
                execute_generation,
            )
            if result["status"] != "success":
                raise RuntimeError(result.get("message", "Generation failed"))
            latency = (time.perf_counter() - start_time) * 1000

            # Normalize provider-reported usage, with explicit estimation fallback
            prompt_tokens, completion_tokens, usage_source = extract_token_usage(
                result,
                prompt_sanitized,
                result["output"],
            )
            actual_tokens = prompt_tokens + completion_tokens

            # Reconcile TPM reservation with actual usage
            await active_rate_limiter.reconcile_tokens(
                limit_scope,
                estimated_tokens=estimated_total_tokens,
                actual_tokens=actual_tokens,
            )

            cost = cost_tracker.calculate_cost(m_name, actual_tokens)
            spent = await active_budget_enforcer.reconcile_cost(
                limit_scope,
                attempt_estimated_cost,
                cost,
            )
            budget_settled = True
            update_budget_remaining(
                request.tenant_id,
                max(0.0, active_budget_enforcer.default_budget - spent),
            )

            # Record metrics
            record_latency(
                request.tenant_id, result["model"], result["provider"], latency
            )
            record_tokens(
                request.tenant_id, result["model"], prompt_tokens, completion_tokens
            )
            record_cost_metric(
                request.tenant_id, result["model"], result["provider"], cost
            )
            record_request(
                request.tenant_id, result["model"], result["provider"], "success"
            )
            record_cache_miss(request.tenant_id)

            # Record fallback if not first attempt
            attempt_idx = fallback_models.index(m_name)
            if attempt_idx > 0:
                record_fallback(request.tenant_id, fallback_models[0], m_name, "error")
                if current_span:
                    current_span.set_attribute("fallback_attempt", attempt_idx)

            # Set span attributes for observability
            if current_span:
                current_span.set_attribute("cache_hit", False)
                current_span.set_attribute("model", result["model"])
                current_span.set_attribute("provider", result["provider"])
                current_span.set_attribute("prompt_tokens", prompt_tokens)
                current_span.set_attribute("completion_tokens", completion_tokens)
                current_span.set_attribute("cost_usd", cost)
                current_span.set_attribute("latency_ms", latency)

            # Feedback to Adaptive Router
            await adaptive_router.record_result(m_name, True, latency, cost)
            record_cost(request.tenant_id, m_name, result["provider"], cost)

            # Persist cost attribution (one row per attempt, idempotent)
            await cost_ledger.record(
                new_entry(
                    request_id=request_id,
                    attempt=fallback_models.index(m_name),
                    tenant_id=request.tenant_id,
                    provider=result["provider"],
                    model=result["model"],
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                    cache_hit=False,
                    usage_source=usage_source,
                )
            )

            # Cache and Quota
            if cache_enabled:
                await two_tier_cache.set(
                    prompt_sanitized,
                    result,
                    tenant_id=request.tenant_id,
                    model=cache_model,
                    params=cache_params,
                )
            await quota_manager.consume(request.tenant_id, tokens=completion_tokens)

            return GenerateResponse(
                model=result["model"],
                output=result["output"],
                provider=result["provider"],
                latency_ms=latency,
                mock=result.get("mock", False),
                cache_hit=False,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
            )
        except Exception as e:
            logger.warning(f"Model {m_name} failed: {e}")
            if not budget_settled:
                await active_budget_enforcer.release_cost(
                    limit_scope, attempt_estimated_cost
                )

            # Get circuit breaker state for this provider
            provider = ProviderFactory.get_provider_for_model(m_name)
            cb_state = ""
            if provider and hasattr(provider, "circuit_breaker"):
                cb_state = provider.circuit_breaker.get_state().value

            # Determine fallback trigger
            trigger = "error"
            if cb_state == "OPEN":
                trigger = "circuit_open"
            elif hasattr(e, "response") and e.response is not None:
                status = getattr(e.response, "status_code", 0)
                if status == 429:
                    trigger = "rate_limit"
                elif status in (500, 502, 503, 504):
                    trigger = "error_5xx"

            # Check if we should fallback to next model
            if not should_fallback(e, circuit_breaker_state=cb_state):
                logger.info(f"Error does not trigger fallback, stopping chain: {e}")
                last_error = e
                break

            # Record fallback attempt
            attempt_idx = fallback_models.index(m_name)
            if attempt_idx + 1 < len(fallback_models):
                next_model = fallback_models[attempt_idx + 1]
                record_fallback(request.tenant_id, m_name, next_model, trigger)

            # Release token reservation for failed attempt
            await active_rate_limiter.release_reservation(
                limit_scope, estimated_total_tokens
            )
            await adaptive_router.record_result(m_name, False, 5000, 0.0)
            last_error = e
            continue

    record_failure(request.tenant_id, "all_failed")
    record_request(request.tenant_id, fallback_models[0], "unknown", "error")
    if current_span:
        current_span.set_attribute("error.type", "all_providers_failed")
        current_span.set_attribute("error.message", str(last_error))
        current_span.set_attribute("fallback_attempts", len(fallback_models))
    raise HTTPException(status_code=503, detail=f"All providers failed: {last_error}")


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """OpenAI-compatible non-streaming chat completion endpoint."""
    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming is not enabled yet")

    gateway_request = GenerateRequest(
        prompt=flatten_messages(request.messages),
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.effective_max_tokens,
        use_cache=True,
        live_data=False,
        stream=False,
    )
    result = await generate(gateway_request, req)
    return JSONResponse(
        completion_response(
            result.model_dump(),
            completion_id(),
            request.model,
        )
    )


@app.post("/generate/stream")
async def generate_stream(request: GenerateRequest, req: Request):
    """Goat-tier streaming with backpressure and adaptive telemetry."""
    start_time = time.perf_counter()

    if hasattr(req.state, "tenant_id"):
        request.tenant_id = req.state.tenant_id

    # Templating resolution
    prompt_text = request.prompt
    if request.template_id:
        try:
            prompt_text = template_manager.render(
                request.template_id, request.variables or {}
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not prompt_text:
        raise HTTPException(
            status_code=400, detail="Either 'prompt' or 'template_id' must be provided"
        )

    # Validation & Sanitization
    is_valid, error_msg = SentinelFirewall.validate(prompt_text, request.tenant_id)
    if not is_valid:
        record_failure(request.tenant_id, "validation")
        raise HTTPException(status_code=400, detail=error_msg)
    prompt_sanitized = SentinelFirewall.sanitize(prompt_text)

    # Rate limiting for streaming
    estimated_prompt_tokens = len(prompt_sanitized.split())
    estimated_completion_tokens = 1024
    estimated_total_tokens = estimated_prompt_tokens + estimated_completion_tokens

    rate_limit_result = await rate_limiter.check_and_reserve(
        request.tenant_id,
        estimated_tokens=estimated_total_tokens,
    )
    if not rate_limit_result.allowed:
        failure_counter.inc()
        retry_after = max(
            rate_limit_result.retry_after_rpm, rate_limit_result.retry_after_tpm
        )
        limit_type = rate_limit_result.limit_exceeded.upper()
        raise HTTPException(
            status_code=429,
            detail=f"{limit_type} rate limit exceeded",
            headers={
                "X-RateLimit-RPM-Remaining": str(rate_limit_result.rpm_remaining),
                "X-RateLimit-TPM-Remaining": str(rate_limit_result.tpm_remaining),
                "Retry-After": str(int(retry_after) + 1),
            },
        )

    # Model selection
    if request.model:
        models = [request.model]
    else:
        models = await adaptive_router.select_models({"prompt": prompt_sanitized})

    if not models:
        record_failure(request.tenant_id, "provider")
        # Release reservation since we're not making provider call
        await rate_limiter.release_reservation(
            request.tenant_id, estimated_total_tokens
        )
        raise HTTPException(status_code=503, detail="No models available for stream")

    m_name = models[0]
    estimated_cost = cost_tracker.estimate_text_cost(m_name, prompt_sanitized)
    if not await budget_enforcer.check_budget(request.tenant_id, estimated_cost):
        record_failure(request.tenant_id, "budget")
        record_budget_rejection(request.tenant_id)
        await rate_limiter.release_reservation(
            request.tenant_id, estimated_total_tokens
        )
        remaining = await budget_enforcer.get_remaining_budget(request.tenant_id)
        update_budget_remaining(request.tenant_id, remaining)
        raise HTTPException(
            status_code=402,
            detail=f"Budget exceeded; remaining budget is ${remaining:.4f}",
        )

    provider = ProviderFactory.get_provider_for_model(m_name)
    if not provider:
        await rate_limiter.release_reservation(
            request.tenant_id, estimated_total_tokens
        )
        raise HTTPException(status_code=503, detail=f"No provider for {m_name}")

    async def stream_wrapper():
        full_output = []
        stream_span = otel_trace.get_current_span()
        if stream_span:
            stream_span.set_attribute("tenant_id", request.tenant_id)
            stream_span.set_attribute("model", m_name)
            stream_span.set_attribute("provider", provider.__class__.__name__)
            stream_span.set_attribute("streaming", True)

        try:
            async for chunk in provider.stream_generate(
                prompt=prompt_sanitized, model=m_name
            ):
                full_output.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk, 'model': m_name})}\n\n"

            # Post-stream telemetry
            latency = (time.perf_counter() - start_time) * 1000
            prompt_tokens = len(prompt_sanitized.split())
            completion_tokens = len(full_output)
            actual_tokens = prompt_tokens + completion_tokens

            # Reconcile TPM reservation
            await rate_limiter.reconcile_tokens(
                request.tenant_id,
                estimated_tokens=estimated_total_tokens,
                actual_tokens=actual_tokens,
            )

            cost = cost_tracker.calculate_cost(m_name, actual_tokens)

            # Record metrics
            record_latency(
                request.tenant_id, m_name, provider.__class__.__name__, latency
            )
            record_tokens(request.tenant_id, m_name, prompt_tokens, completion_tokens)
            record_cost_metric(
                request.tenant_id, m_name, provider.__class__.__name__, cost
            )
            record_request(
                request.tenant_id, m_name, provider.__class__.__name__, "success"
            )
            record_cache_miss(request.tenant_id)

            if stream_span:
                stream_span.set_attribute("cache_hit", False)
                stream_span.set_attribute("prompt_tokens", prompt_tokens)
                stream_span.set_attribute("completion_tokens", completion_tokens)
                stream_span.set_attribute("cost_usd", cost)
                stream_span.set_attribute("latency_ms", latency)

            await adaptive_router.record_result(m_name, True, latency, cost)
            record_cost(request.tenant_id, m_name, provider.__class__.__name__, cost)
            await budget_enforcer.add_cost(request.tenant_id, cost)

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream failed for {m_name}: {e}")
            record_failure(request.tenant_id, "stream_failed")
            record_request(
                request.tenant_id, m_name, provider.__class__.__name__, "error"
            )
            if stream_span:
                stream_span.set_attribute("error.type", "stream_failed")
                stream_span.set_attribute("error.message", str(e))
            # Release reservation on failure
            await rate_limiter.release_reservation(
                request.tenant_id, estimated_total_tokens
            )
            await adaptive_router.record_result(m_name, False, 5000, 0.0)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream_wrapper(), media_type="text/event-stream")


class TemplateRequest(BaseModel):
    content: str


@app.post("/admin/templates/{template_id}")
async def create_template(template_id: str, request: TemplateRequest):
    """Admin endpoint to create or update a prompt template."""
    template_manager.add_template(template_id, request.content)
    return {"status": "success", "template_id": template_id}


@app.get("/admin/templates")
async def list_templates():
    """Admin endpoint to list all available templates."""
    return {"templates": list(template_manager._templates.keys())}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Nexus-Standard: Verified Type Safety and Professional Documentation Pattern
