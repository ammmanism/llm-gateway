from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
import json
import asyncio
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time
import uuid

from src.config import settings
from src.utils.logger import get_logger, request_id_var
from src.utils.embeddings import embedding_engine
from src.utils.tokenizer import count_tokens, count_message_tokens
from src.cache.semantic import semantic_cache
from src.router import smart_router, get_fallback_chain
from src.router.executor import classify_provider_error, complete_with_fallback
from src.providers import get_provider
from src.providers.capabilities import canonical_model, model_for_provider, provider_supports_request
from src.billing.tenant import TenantManager
from src.billing.meter import UsageMeter
from src.observability import setup_tracing, dashboard_router
from src.admin.router import router as admin_router
from src.observability.metrics import (
    CACHE_HITS,
    CACHE_MISSES,
    COST_USD_TOTAL,
    REQUESTS_TOTAL,
    REQUEST_DURATION,
    ROUTING_DECISIONS,
    PROVIDER_FAILURES,
    SAVINGS_USD_TOTAL,
    TOKENS_TOTAL,
)
from src.schemas import ChatCompletionRequest
from src.security import validate_startup_security

logger = get_logger(__name__)

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup tracing
setup_tracing(app)

# Include routers
app.include_router(dashboard_router)
app.include_router(admin_router)

# Initialize global managers
tenant_manager: TenantManager = None  # type: ignore
usage_meter: UsageMeter = None  # type: ignore

@app.on_event("startup")
async def startup_event():
    global tenant_manager, usage_meter
    logger.info("Starting up Neurocache")
    validate_startup_security()
    embedding_engine.load()
    await semantic_cache.initialize()
    tenant_manager = TenantManager(semantic_cache.redis_client, semantic_cache.pg_pool)
    usage_meter = UsageMeter(semantic_cache.pg_pool)
    app.state.tenant_manager = tenant_manager
    app.state.pg_pool = semantic_cache.pg_pool

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Neurocache")
    await semantic_cache.close()

@app.middleware("http")
async def process_request(request: Request, call_next):
    # 1. Assign Request ID
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_var.set(req_id)
    request.state.id = req_id
    
    start_time = time.time()
    
    # Process
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        response = JSONResponse(status_code=500, content={"error": {"message": "Internal Server Error"}})
        
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} completed in {process_time:.4f}s")
    
    return response

@app.get("/health")
async def health_check():
    """Detailed health check."""
    # In a real app, check Redis, PG, and Providers
    return {
        "status": "ok",
        "cache": {"status": "ok", "index_size": semantic_cache.index.ntotal if semantic_cache.index else 0},
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not api_key:
        api_key = request.headers.get("X-API-Key", "").strip()
        
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
        
    tenant = await tenant_manager.get_tenant_by_key(api_key)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    try:
        request_data = await request.json()
        chat_request = ChatCompletionRequest.model_validate(request_data)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid chat completion request: {exc}")
    
    # 2. Rate Limiting
    requested_model = canonical_model(chat_request.model)
    if tenant.allowed_models and requested_model not in [canonical_model(m) for m in tenant.allowed_models]:
        raise HTTPException(status_code=403, detail=f"Model {requested_model} is not allowed for this tenant")

    messages = chat_request.as_provider_messages()
    params = chat_request.provider_params()
    estimated_tokens = count_message_tokens(requested_model, messages) + (chat_request.max_tokens or 100)
    allowed, remaining, reason = await tenant_manager.check_rate_limit(tenant, estimated_tokens)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    query_text = chat_request.last_user_text()
    is_stream = chat_request.stream
    cache_namespace = request.headers.get(
        "X-Cache-Namespace",
        str(request_data.get("cache_namespace", settings.DEFAULT_CACHE_NAMESPACE)),
    )
    cache_control = request.headers.get("Cache-Control", "").lower()
    cache_mode = request.headers.get("X-Cache-Mode", "").lower()
    no_cache = (
        "no-store" in cache_control
        or "no-cache" in cache_control
        or cache_mode in {"bypass", "no-store", "no-cache"}
        or bool(request_data.get("no_cache", False))
    )
            
    # 3. Semantic Cache Check
    is_hit, cached_response, similarity = (False, None, None)
    if query_text and not no_cache:
        is_hit, cached_response, similarity = await semantic_cache.check_cache(
            query_text,
            requested_model,
            params,
            tenant.id,
            threshold=tenant.cache_threshold,
            namespace=cache_namespace,
        )
    
    start_time = time.time()
    
    if is_hit:
        REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider="cache", model=requested_model, status="200", is_cache_hit="true").inc()
        CACHE_HITS.labels(tenant_id=tenant.id).inc()
        latency_ms = int((time.time() - start_time) * 1000)
        
        # We assume cost saved is relative to GPT-4o
        cost_saved = usage_meter.calculate_savings(0, 0, 0) # Should use actual token counts from cache
        await usage_meter.log_usage(
            tenant.id, request.state.id, True, "cache", requested_model,
            0, 0, 0.0, latency_ms, cache_similarity=similarity
        )
        
        headers = {
            "X-Cache-Status": "HIT",
            "X-Cache-Similarity": f"{similarity:.4f}",
            "X-Saved-USD": f"{cost_saved:.6f}"
        }
        
        if is_stream:
            async def cache_stream_generator():
                # Fake a stream for the cached response
                chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
                # For simplicity, we yield the whole response in one chunk
                content = cached_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                chunk_data = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": requested_model,
                    "choices": [{"delta": {"content": content}, "index": 0, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                
                finish_data = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": requested_model,
                    "choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(finish_data)}\n\n"
                yield "data: [DONE]\n\n"
                
            return StreamingResponse(cache_stream_generator(), media_type="text/event-stream", headers=headers)
        else:
            return JSONResponse(content=cached_response, headers=headers)
        
    else:
        CACHE_MISSES.labels(tenant_id=tenant.id).inc()

    # 4. Routing Decision
    # If the user specified a specific model, we might try to honor it or map it to a tier.
    # For simplicity, we just use the smart router to pick the best provider based on weights.
    try:
        routing_decision = smart_router.route(estimated_tokens, weights=tenant.routing_weights)
    except Exception:
        raise HTTPException(status_code=503, detail="No providers available")
        
    primary_provider_name = routing_decision.name
    fallback_chain = get_fallback_chain("tier_a", primary_provider_name)
    uses_tools = bool(chat_request.tools)
    uses_json_mode = bool(chat_request.response_format)
    ROUTING_DECISIONS.labels(provider=primary_provider_name, reason="smart_route").inc()
    
    if is_stream:
        async def interception_stream():
            last_error = None
            for used_provider in fallback_chain[: settings.MAX_FALLBACK_ATTEMPTS]:
                provider = get_provider(used_provider)
                p_model = model_for_provider(requested_model, used_provider, provider.supported_models)
                if not provider_supports_request(
                    used_provider,
                    p_model,
                    stream=True,
                    uses_tools=uses_tools,
                    uses_json_mode=uses_json_mode,
                ):
                    continue

                full_response_text = ""
                tokens_in = estimated_tokens
                tokens_out = 0
                try:
                    async for chunk in provider.stream(p_model, messages, params):
                        yield chunk
                        try:
                            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                                data = json.loads(chunk[6:])
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_response_text += content
                                    tokens_out += count_tokens(p_model, content)
                        except Exception:
                            pass

                    smart_router.providers[used_provider].circuit.record_success()
                    smart_router.providers[used_provider].ewma_error_rate.update(0.0)

                    latency_ms = int((time.time() - start_time) * 1000)
                    cost = provider.calculate_cost(p_model, tokens_in, tokens_out)
                    REQUEST_DURATION.labels(tenant_id=tenant.id, provider=used_provider, model=p_model).observe(latency_ms / 1000.0)
                    REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=p_model, status="200", is_cache_hit="false").inc()
                    TOKENS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=p_model, direction="in").inc(tokens_in)
                    TOKENS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=p_model, direction="out").inc(tokens_out)
                    COST_USD_TOTAL.labels(tenant_id=tenant.id, provider=used_provider).inc(cost)
                    SAVINGS_USD_TOTAL.labels(tenant_id=tenant.id).inc(usage_meter.calculate_savings(tokens_in, tokens_out, cost))

                    if query_text and not no_cache:
                        asyncio.create_task(semantic_cache.store_cache(
                            query_text, requested_model, params,
                            {"id": "chatcmpl", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": full_response_text}}]},
                            tenant.id, used_provider, tokens_in, tokens_out, cost, tenant.cache_ttl_hours * 3600, namespace=cache_namespace
                        ))
                    asyncio.create_task(usage_meter.log_usage(
                        tenant.id, request.state.id, False, used_provider, p_model,
                        tokens_in, tokens_out, cost, latency_ms, routing_reason="smart_route"
                    ))
                    return
                except Exception as e:
                    last_error = e
                    error_type = classify_provider_error(e)
                    logger.warning(f"Provider {used_provider} stream failed: {error_type}: {e}")
                    PROVIDER_FAILURES.labels(provider=used_provider, error_type=error_type).inc()
                    smart_router.providers[used_provider].circuit.record_failure()
                    smart_router.providers[used_provider].ewma_error_rate.update(1.0)
                    REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=p_model, status="error", is_cache_hit="false").inc()

            yield f"data: {json.dumps({'error': {'message': str(last_error or 'No streaming provider available')}})}\n\n"

        headers = {
            "X-Cache-Status": "MISS",
            "X-Provider": primary_provider_name,
            "X-Cache-Namespace": cache_namespace,
        }
        return StreamingResponse(interception_stream(), media_type="text/event-stream", headers=headers)
        
    else:
        # Standard non-streaming completion
        try:
            result = await complete_with_fallback(
                fallback_chain,
                requested_model,
                messages,
                params,
                stream=False,
                uses_tools=uses_tools,
                uses_json_mode=uses_json_mode,
            )
        except Exception as exc:
            REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider="fallback", model=requested_model, status="error", is_cache_hit="false").inc()
            raise HTTPException(status_code=503, detail=f"All providers failed: {exc}")

        final_response = result.response
        used_provider = result.provider
        
        latency_ms = int((time.time() - start_time) * 1000)
        REQUEST_DURATION.labels(tenant_id=tenant.id, provider=used_provider, model=final_response.model).observe(latency_ms / 1000.0)
        REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=final_response.model, status="200", is_cache_hit="false").inc()
        TOKENS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=final_response.model, direction="in").inc(final_response.tokens_in)
        TOKENS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=final_response.model, direction="out").inc(final_response.tokens_out)
        COST_USD_TOTAL.labels(tenant_id=tenant.id, provider=used_provider).inc(final_response.cost_usd)
        SAVINGS_USD_TOTAL.labels(tenant_id=tenant.id).inc(usage_meter.calculate_savings(final_response.tokens_in, final_response.tokens_out, final_response.cost_usd))
        
        if query_text and not no_cache:
            await semantic_cache.store_cache(
                query_text, requested_model, params, final_response.response, tenant.id,
                used_provider, final_response.tokens_in, final_response.tokens_out,
                final_response.cost_usd, tenant.cache_ttl_hours * 3600, namespace=cache_namespace
            )
        
        await usage_meter.log_usage(
            tenant.id, request.state.id, False, used_provider, final_response.model,
            final_response.tokens_in, final_response.tokens_out, final_response.cost_usd,
            latency_ms, routing_reason="smart_route"
        )
        
        headers = {
            "X-Cache-Status": "MISS",
            "X-Provider": used_provider,
            "X-Cost-USD": f"{final_response.cost_usd:.6f}",
            "X-Fallback-Attempts": ",".join(attempt.provider for attempt in result.attempts),
            "X-Cache-Namespace": cache_namespace,
        }
        
        return JSONResponse(content=final_response.response, headers=headers)

@app.post("/v1/cache/warm")
async def warm_cache(request: Request, file: UploadFile = File(...)):
    from src.cache.warmer import warm_cache_from_jsonl
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not api_key:
        api_key = request.headers.get("X-API-Key", "").strip()
        
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
        
    tenant = await tenant_manager.get_tenant_by_key(api_key)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    contents = await file.read()
    try:
        file_content = contents.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")
        
    entries_warmed = await warm_cache_from_jsonl(file_content, tenant.id)
    return {"status": "success", "entries_warmed": entries_warmed}

@app.get("/v1/cache/stats")
async def cache_stats(request: Request):
    from src.cache.analytics import get_cache_analytics
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not api_key:
        api_key = request.headers.get("X-API-Key", "").strip()
        
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
        
    tenant = await tenant_manager.get_tenant_by_key(api_key)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    stats = await get_cache_analytics(semantic_cache.pg_pool, tenant.id)
    return stats
