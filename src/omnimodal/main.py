"""
OmniModal FastAPI Application
"""

import asyncio
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from .config import settings
from .gateway.router import SemanticRouter
from .gateway.cost_optimizer import CostOptimizer
from .gateway.fallback import FallbackChain
from .modalities.text import TextAdapter
from .modalities.image import ImageAdapter
from .modalities.audio import AudioAdapter
from .modalities.video import VideoAdapter
from .security.rbac import RBACMiddleware, require_role, Role
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.pii_redaction import PIIRedactionMiddleware
from .observability.metrics import MetricsCollector
from .observability.tracing import setup_tracing
from .exceptions import OmniModalError, RateLimitError, AuthenticationError, ProviderError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# LIFESPAN MANAGEMENT
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    # Startup
    app.state.router = SemanticRouter()
    app.state.cost_optimizer = CostOptimizer()
    app.state.fallback = FallbackChain()
    app.state.metrics = MetricsCollector()

    # Initialize modality adapters
    app.state.adapters = {
        "text": TextAdapter(),
        "image": ImageAdapter(),
        "audio": AudioAdapter(),
        "video": VideoAdapter(),
    }

    await app.state.router.warmup()
    logger.info("🌌 OmniModal Gateway ready")
    yield

    # Shutdown
    for adapter in app.state.adapters.values():
        await adapter.close()
    logger.info("👋 OmniModal Gateway shutdown")

app = FastAPI(
    title="OmniModal",
    description="Unified Multimodal AI Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────

# Rate limiting
# app.add_middleware(RateLimitMiddleware, redis_client=...)  # needs redis

# PII Redaction
if settings.security.pii_redaction_enabled:
    app.add_middleware(PIIRedactionMiddleware)

# RBAC
if settings.security.rbac_enabled:
    app.add_middleware(RBACMiddleware, policy_file=settings.security.rbac_policy_file)

# Setup tracing
if settings.observability.enable_opentelemetry:
    setup_tracing(app)

# ─────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────

class ModalityInput(BaseModel):
    type: str = Field(..., description="text | image | audio | video")
    content: str = Field(..., description="URL, base64, or text content")
    role: str = "input"
    mime_type: Optional[str] = None

class GenerationRequest(BaseModel):
    request_id: Optional[str] = None
    inputs: list[ModalityInput]
    output_modality: str = Field(..., description="text | image | audio | video")
    quality: str = "standard"
    max_cost_usd: Optional[float] = None
    max_latency_ms: Optional[int] = None
    stream: bool = False
    metadata: dict = Field(default_factory=dict)

class GenerationResponse(BaseModel):
    request_id: str
    content: str
    content_type: str
    provider_used: str
    cost_usd: float
    latency_ms: int
    cache_hit: bool
    fallback_used: bool

class FusionRequest(BaseModel):
    inputs: list[ModalityInput]
    output_modality: str
    operation: str = "fuse"
    duration_seconds: Optional[int] = None
    constraints: dict = Field(default_factory=dict)

# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/v1/generate", response_model=GenerationResponse)
@require_role(Role.DEVELOPER)
async def generate(request: GenerationRequest, req: Request):
    """
    Single-modality generation with intelligent routing.
    """
    request_id = request.request_id or str(uuid.uuid4())
    start_time = asyncio.get_event_loop().time()

    try:
        adapter = req.app.state.adapters.get(request.output_modality)
        if not adapter:
            raise HTTPException(400, f"Unsupported modality: {request.output_modality}")

        # Get routing decision
        route = await req.app.state.router.select(
            modality=request.output_modality,
            quality=request.quality,
            cost_budget=request.max_cost_usd,
            latency_budget=request.max_latency_ms
        )

        # Execute with fallback
        result = await req.app.state.fallback.execute(
            primary=route,
            operation=lambda r: adapter.generate(request.inputs, r),
            max_attempts=settings.routing.fallback_max_attempts
        )

        latency = int((asyncio.get_event_loop().time() - start_time) * 1000)

        # Track metrics
        req.app.state.metrics.record_request(
            modality=request.output_modality,
            provider=result.provider,
            latency_ms=latency,
            cost_usd=result.cost,
            success=True
        )

        return GenerationResponse(
            request_id=request_id,
            content=result.content,
            content_type=result.mime_type,
            provider_used=result.provider,
            cost_usd=result.cost,
            latency_ms=latency,
            cache_hit=result.from_cache,
            fallback_used=result.fallback_used
        )

    except ProviderError as e:
        logger.error(f"Provider error: {e}")
        raise HTTPException(503, f"Provider unavailable: {str(e)}")
    except RateLimitError as e:
        raise HTTPException(429, str(e))
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(500, f"Generation failed: {str(e)}")

@app.post("/v1/fuse")
@require_role(Role.DEVELOPER)
async def fuse(request: FusionRequest, req: Request):
    """
    Multimodal fusion.
    """
    from .fusion.planner import FusionPlanner

    planner = FusionPlanner()
    dag = planner.plan(request.inputs, request.output_modality, request.constraints)
    result = await dag.execute(req.app.state.adapters)
    return {
        "request_id": str(uuid.uuid4()),
        "output": result.content,
        "stages_executed": len(dag.stages),
        "providers_used": result.providers,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms
    }

@app.post("/v1/generate/stream")
@require_role(Role.DEVELOPER)
async def generate_stream(request: GenerationRequest, req: Request):
    """
    Streaming generation for real-time applications.
    """
    adapter = req.app.state.adapters.get(request.output_modality)
    if not adapter:
        raise HTTPException(400, f"Unsupported modality: {request.output_modality}")

    async def event_stream():
        async for chunk in adapter.generate_stream(request.inputs):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.version,
        "providers": {
            name: {"enabled": cfg.enabled, "regions": cfg.regions}
            for name, cfg in settings.providers.items()
        }
    }

@app.get("/v1/providers")
async def list_providers():
    return {
        "providers": [
            {
                "name": "openai",
                "modalities": ["text", "image", "audio"],
                "models": ["gpt-4o", "gpt-4-turbo", "dall-e-3", "whisper-1"]
            },
            {
                "name": "anthropic",
                "modalities": ["text"],
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
            },
            {
                "name": "google",
                "modalities": ["text", "image", "video"],
                "models": ["gemini-pro", "gemini-ultra"]
            }
        ]
    }

@app.get("/v1/cost_report")
@require_role(Role.BILLING)
async def cost_report(req: Request, days: int = 30):
    tracker = req.app.state.cost_optimizer
    report = tracker.get_savings_report()
    return report

# ─────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────

@app.exception_handler(OmniModalError)
async def omnimodal_exception_handler(request: Request, exc: OmniModalError):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": exc.__class__.__name__}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "type": type(exc).__name__}
    )
