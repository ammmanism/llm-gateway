from fastapi import FastAPI, Request, HTTPException, Response, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
import json
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time
import uuid

from src.config import settings
from src.utils.logger import get_logger, request_id_var
from src.utils.embeddings import embedding_engine
from src.cache.semantic import semantic_cache
from src.router import smart_router, get_fallback_chain
from src.providers import get_provider
from src.billing.tenant import TenantManager
from src.billing.meter import UsageMeter
from src.observability import setup_tracing, dashboard_router
from src.admin.router import router as admin_router
from src.observability.metrics import REQUESTS_TOTAL, REQUEST_DURATION

logger = get_logger(__name__)

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
tenant_manager = None
usage_meter = None

@app.on_event("startup")
async def startup_event():
    global tenant_manager, usage_meter
    logger.info("Starting up Neurocache")
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
        
    request_data = await request.json()
    
    # 2. Rate Limiting
    estimated_tokens = sum(len(m.get("content", "")) // 4 for m in request_data.get("messages", [])) + request_data.get("max_tokens", 100)
    allowed, remaining, reason = await tenant_manager.check_rate_limit(tenant, estimated_tokens)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
        
    model = request_data.get("model", "gpt-4o")
    messages = request_data.get("messages", [])
    
    # Extract last user message for semantic caching (simplification)
    query_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            query_text = msg.get("content", "")
            break
            
    # 3. Semantic Cache Check
    params = {k:v for k,v in request_data.items() if k not in ["model", "messages", "stream"]}
    is_hit, cached_response, similarity = await semantic_cache.check_cache(
        query_text, model, params, tenant.id, threshold=settings.DEFAULT_SIMILARITY_THRESHOLD
    )
    
    start_time = time.time()
    
    if is_hit:
        REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider="cache", model=model, status="200", is_cache_hit="true").inc()
        latency_ms = int((time.time() - start_time) * 1000)
        
        # We assume cost saved is relative to GPT-4o
        cost_saved = usage_meter.calculate_savings(0, 0, 0) # Should use actual token counts from cache
        await usage_meter.log_usage(
            tenant.id, request.state.id, True, "cache", model,
            0, 0, 0.0, latency_ms, cache_similarity=similarity
        )
        
        headers = {
            "X-Cache-Status": "HIT",
            "X-Cache-Similarity": f"{similarity:.4f}",
            "X-Saved-USD": f"{cost_saved:.6f}"
        }
        
        is_stream = request_data.get("stream", False)
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
                    "model": model,
                    "choices": [{"delta": {"content": content}, "index": 0, "finish_reason": None}]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                
                finish_data = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(finish_data)}\n\n"
                yield "data: [DONE]\n\n"
                
            return StreamingResponse(cache_stream_generator(), media_type="text/event-stream", headers=headers)
        else:
            return JSONResponse(content=cached_response, headers=headers)
        
    # 4. Routing Decision
    # If the user specified a specific model, we might try to honor it or map it to a tier.
    # For simplicity, we just use the smart router to pick the best provider based on weights.
    try:
        routing_decision = smart_router.route(estimated_tokens, weights=tenant.routing_weights)
    except Exception as e:
        raise HTTPException(status_code=503, detail="No providers available")
        
    primary_provider_name = routing_decision.name
    fallback_chain = get_fallback_chain("tier_a", primary_provider_name)
    
    is_stream = request_data.get("stream", False)
    
    if is_stream:
        used_provider = primary_provider_name
        provider = get_provider(used_provider)
        # Find closest model match
        p_model = provider.supported_models[0]
        if model in provider.supported_models:
            p_model = model
            
        async def interception_stream():
            full_response_text = ""
            tokens_in = estimated_tokens # Approximation
            tokens_out = 0
            
            try:
                async for chunk in provider.stream(p_model, messages, params):
                    yield chunk
                    # Try to extract content to buffer it
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
                        
                # End of stream reached successfully
                smart_router.providers[used_provider].circuit.record_success()
                
                latency_ms = int((time.time() - start_time) * 1000)
                cost = provider.calculate_cost(p_model, tokens_in, tokens_out)
                
                # We can't await inside a regular generator if it's already closed, 
                # but we are an async generator, so we can await here:
                asyncio.create_task(semantic_cache.store_cache(
                    query_text, model, params, 
                    {"id": "chatcmpl", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": full_response_text}}]}, 
                    tenant.id, used_provider, tokens_in, tokens_out, cost, settings.DEFAULT_CACHE_TTL_HOURS * 3600
                ))
                asyncio.create_task(usage_meter.log_usage(
                    tenant.id, request.state.id, False, used_provider, p_model,
                    tokens_in, tokens_out, cost, latency_ms, routing_reason="smart_route"
                ))
                
            except Exception as e:
                logger.warning(f"Provider {used_provider} stream failed: {e}")
                smart_router.providers[used_provider].circuit.record_failure()
                smart_router.providers[used_provider].ewma_error_rate.update(1.0)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                
        headers = {
            "X-Cache-Status": "MISS",
            "X-Provider": used_provider
        }
        return StreamingResponse(interception_stream(), media_type="text/event-stream", headers=headers)
        
    else:
        # Standard non-streaming completion
        final_response = await provider.complete(p_model, messages, params)
        smart_router.providers[used_provider].circuit.record_success()
        smart_router.providers[used_provider].ewma_latency.update(final_response.latency_ms)
        
        latency_ms = int((time.time() - start_time) * 1000)
        REQUEST_DURATION.labels(tenant_id=tenant.id, provider=used_provider, model=final_response.model).observe(latency_ms / 1000.0)
        REQUESTS_TOTAL.labels(tenant_id=tenant.id, provider=used_provider, model=final_response.model, status="200", is_cache_hit="false").inc()
        
        await semantic_cache.store_cache(
            query_text, model, params, final_response.response, tenant.id,
            used_provider, final_response.tokens_in, final_response.tokens_out,
            final_response.cost_usd, settings.DEFAULT_CACHE_TTL_HOURS * 3600
        )
        
        await usage_meter.log_usage(
            tenant.id, request.state.id, False, used_provider, final_response.model,
            final_response.tokens_in, final_response.tokens_out, final_response.cost_usd,
            latency_ms, routing_reason="smart_route"
        )
        
        headers = {
            "X-Cache-Status": "MISS",
            "X-Provider": used_provider,
            "X-Cost-USD": f"{final_response.cost_usd:.6f}"
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