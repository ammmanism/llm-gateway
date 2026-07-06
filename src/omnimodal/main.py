"""
OmniModal FastAPI Application
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import settings
from .core.experiments import ExperimentEngine
from .core.green_ai import CarbonBudgetEnforcer, CarbonTracker
from .core.prompt_registry import PromptRegistry
from .core.schema_enforcer import JSONSchemaEnforcer
from .exceptions import (
    OmniModalError,
    ProviderError,
    RateLimitError,
)
from .gateway.cost_optimizer import CostOptimizer
from .gateway.fallback import FallbackChain
from .gateway.router import SemanticRouter
from .middleware.pii_redaction import PIIRedactionMiddleware
from .modalities.audio import AudioAdapter
from .modalities.image import ImageAdapter
from .modalities.text import TextAdapter
from .modalities.video import VideoAdapter
from .observability.metrics import MetricsCollector
from .observability.tracing import setup_tracing
from .security.rbac import RBACMiddleware, Role, require_role

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

    # Phase 2: Core services
    app.state.experiments = ExperimentEngine() if settings.core.enable_experiments else None
    app.state.carbon_tracker = CarbonTracker(default_region=settings.core.carbon_default_region) if settings.core.enable_carbon_tracking else None
    app.state.carbon_budget = CarbonBudgetEnforcer(max_grams_per_day=settings.core.carbon_max_grams_per_day) if settings.core.enable_carbon_tracking else None
    app.state.prompt_registry = PromptRegistry(storage_path=settings.core.prompt_storage_path) if settings.core.enable_prompt_registry else None
    app.state.schema_enforcer = JSONSchemaEnforcer(max_repair_attempts=settings.core.schema_max_repair_attempts) if settings.core.enable_schema_enforcement else None

    # Initialize modality adapters
    app.state.adapters = {
        "text": TextAdapter(),
        "image": ImageAdapter(),
        "audio": AudioAdapter(),
        "video": VideoAdapter(),
    }

    await app.state.router.warmup()
    logger.info("OmniModal Gateway ready")
    yield

    # Shutdown
    for adapter in app.state.adapters.values():
        await adapter.close()
    logger.info("OmniModal Gateway shutdown")

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
    mime_type: str | None = None

class GenerationRequest(BaseModel):
    request_id: str | None = None
    inputs: list[ModalityInput]
    output_modality: str = Field(..., description="text | image | audio | video")
    quality: str = "standard"
    max_cost_usd: float | None = None
    max_latency_ms: int | None = None
    stream: bool = False
    metadata: dict = Field(default_factory=dict)
    experiment_id: str | None = None
    user_id: str | None = None
    schema: dict | None = None
    enable_watermark: bool = False

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
    duration_seconds: int | None = None
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

        # Experiment A/B testing
        if request.experiment_id and req.app.state.experiments:
            exp = req.app.state.experiments.experiments.get(request.experiment_id)
            if exp:
                variant = req.app.state.experiments.get_variant(
                    request.experiment_id,
                    request.user_id or "anonymous"
                )
                if variant:
                    quality = variant.config.get("quality", request.quality)

        # Build prompt text for dedup/concurrency
        prompt_text = " ".join(i.content for i in request.inputs if i.type == "text") if request.inputs else ""

        # Schema injection
        if request.schema and req.app.state.schema_enforcer:
            schema = request.schema
        else:
            schema = None

        # Get routing decision
        route = await req.app.state.router.select(
            modality=request.output_modality,
            quality=request.quality,
            cost_budget=request.max_cost_usd,
            latency_budget=request.max_latency_ms,
            prompt=prompt_text,
            params={"quality": request.quality}
        )

        # Execute with fallback
        result = await req.app.state.fallback.execute(
            primary=route,
            operation=lambda r: adapter.generate(request.inputs, r),
            max_attempts=settings.routing.fallback_max_attempts
        )

        latency = int((asyncio.get_event_loop().time() - start_time) * 1000)

        # Carbon tracking
        if req.app.state.carbon_tracker:
            estimate = req.app.state.carbon_tracker.estimate(
                model=result.model if hasattr(result, 'model') else "unknown",
                tokens_input=len(prompt_text.split()),
                tokens_output=len(result.content.split()) if hasattr(result, 'content') else 100
            )
            req.app.state.carbon_tracker.track(estimate)

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

    except HTTPException as e:
        raise e
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
async def health(req: Request):
    return {
        "status": "healthy",
        "version": settings.version,
        "providers": {
            name: {"enabled": cfg.enabled, "regions": cfg.regions}
            for name, cfg in settings.providers.items()
        },
        "features": {
            "deduplication": settings.core.enable_deduplication,
            "concurrency_limiting": settings.core.enable_concurrency_limiting,
            "experiments": settings.core.enable_experiments,
            "prompt_registry": settings.core.enable_prompt_registry,
            "carbon_tracking": settings.core.enable_carbon_tracking,
            "schema_enforcement": settings.core.enable_schema_enforcement,
            "watermarking": settings.core.enable_watermarking,
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
# PHASE 2: EXPERIMENTS API
# ─────────────────────────────────────────────

class ExperimentCreateRequest(BaseModel):
    name: str
    hypothesis: str
    metric: str
    variants: list[dict]
    min_samples: int = 100

class ExperimentResponse(BaseModel):
    experiment_id: str
    name: str
    status: str

@app.post("/v1/experiments", response_model=ExperimentResponse)
@require_role(Role.DEVELOPER)
async def create_experiment(request: ExperimentCreateRequest, req: Request):
    if not req.app.state.experiments:
        raise HTTPException(503, "Experiment engine not enabled")
    exp = req.app.state.experiments.create_experiment(
        name=request.name,
        hypothesis=request.hypothesis,
        metric=request.metric,
        variants=request.variants,
        min_samples=request.min_samples
    )
    return ExperimentResponse(experiment_id=exp.id, name=exp.name, status=exp.status.value)

@app.post("/v1/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: str, req: Request):
    if not req.app.state.experiments:
        raise HTTPException(503, "Experiment engine not enabled")
    exp = req.app.state.experiments.experiments.get(experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    from .core.experiments import ExperimentStatus
    exp.status = ExperimentStatus.RUNNING
    return {"status": "running"}

@app.get("/v1/experiments/{experiment_id}/results")
async def experiment_results(experiment_id: str, req: Request):
    if not req.app.state.experiments:
        raise HTTPException(503, "Experiment engine not enabled")
    result = req.app.state.experiments.analyze_experiment(experiment_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ─────────────────────────────────────────────
# PHASE 2: PROMPT REGISTRY API
# ─────────────────────────────────────────────

class PromptCreateRequest(BaseModel):
    name: str
    description: str
    initial_prompt: str
    variables: list[str] = []
    model_config: dict = {}

class PromptRenderRequest(BaseModel):
    template_name: str
    variables: dict[str, Any]
    version_id: str | None = None

@app.post("/v1/prompts")
async def create_prompt(request: PromptCreateRequest, req: Request):
    if not req.app.state.prompt_registry:
        raise HTTPException(503, "Prompt registry not enabled")
    tmpl = req.app.state.prompt_registry.create_template(
        name=request.name,
        description=request.description,
        initial_prompt=request.initial_prompt,
        variables=request.variables,
        model_config=request.model_config
    )
    return {"name": tmpl.name, "version_id": tmpl.active_version_id, "status": tmpl.status.value}

@app.post("/v1/prompts/render")
async def render_prompt(request: PromptRenderRequest, req: Request):
    if not req.app.state.prompt_registry:
        raise HTTPException(503, "Prompt registry not enabled")
    try:
        rendered = req.app.state.prompt_registry.render(
            template_name=request.template_name,
            variables=request.variables,
            version_id=request.version_id
        )
        return {"prompt": rendered}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ─────────────────────────────────────────────
# PHASE 2: CARBON REPORTING API
# ─────────────────────────────────────────────

@app.get("/v1/carbon")
async def carbon_report(req: Request):
    if not req.app.state.carbon_tracker:
        raise HTTPException(503, "Carbon tracking not enabled")
    return req.app.state.carbon_tracker.get_report()


# ─────────────────────────────────────────────
# PHASE 2: SCHEMA ENFORCEMENT API
# ─────────────────────────────────────────────

@app.post("/v1/validate")
async def validate_output(body: dict, req: Request):
    if not req.app.state.schema_enforcer:
        raise HTTPException(503, "Schema enforcer not enabled")
    output = body.get("output", "")
    schema = body.get("schema", {})
    result = req.app.state.schema_enforcer.validate(output, schema)
    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "repaired_output": result.repaired_output
    }


# ─────────────────────────────────────────────
# PHASE 2: DEDUP & CONCURRENCY STATS
# ─────────────────────────────────────────────

@app.get("/v1/stats/core")
async def core_stats(req: Request):
    router = req.app.state.router
    return {
        "coalescer": router.get_coalescer_stats(),
        "concurrency": router.get_concurrency_stats(),
        "carbon": req.app.state.carbon_tracker.get_report() if req.app.state.carbon_tracker else {},
    }

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
