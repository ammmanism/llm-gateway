"""
OmniModal FastAPI Application
Entry point for the unified multimodal gateway.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from omnimodal.config import settings
from omnimodal.gateway.router import SemanticRouter
from omnimodal.gateway.cost_optimizer import CostOptimizer
from omnimodal.gateway.fallback import FallbackChain
from omnimodal.modalities.text import TextAdapter
from omnimodal.modalities.image import ImageAdapter
from omnimodal.modalities.audio import AudioAdapter
from omnimodal.modalities.video import VideoAdapter


# ---------------------------------------------
# LIFESPAN MANAGEMENT
# ---------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    # Startup
    app.state.router = SemanticRouter()
    app.state.cost_optimizer = CostOptimizer()
    app.state.fallback = FallbackChain()
    
    # Initialize modality adapters
    app.state.adapters = {
        "text": TextAdapter(),
        "image": ImageAdapter(),
        "audio": AudioAdapter(),
        "video": VideoAdapter(),
    }
    
    await app.state.router.warmup()
    print("OmniModal Gateway ready")
    
    yield
    
    # Shutdown
    for adapter in app.state.adapters.values():
        await adapter.close()
    print("OmniModal Gateway shutdown")


app = FastAPI(
    title="OmniModal",
    description="Unified Multimodal AI Gateway",
    version="1.0.0",
    lifespan=lifespan
)


# ---------------------------------------------
# REQUEST/RESPONSE MODELS
# ---------------------------------------------

class ModalityInput(BaseModel):
    type: str = Field(..., description="text | image | audio | video")
    content: str = Field(..., description="URL, base64, or text content")
    role: str = "input"
    mime_type: Optional[str] = None


class GenerationRequest(BaseModel):
    request_id: Optional[str] = None
    inputs: list[ModalityInput]
    output_modality: str = Field(..., description="text | image | audio | video")
    quality: str = "standard"  # draft | standard | premium | enterprise
    max_cost_usd: Optional[float] = None
    max_latency_ms: Optional[int] = None
    stream: bool = False
    metadata: dict = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    request_id: str
    content: str  # Base64 or text
    content_type: str
    provider_used: str
    cost_usd: float
    latency_ms: int
    cache_hit: bool
    fallback_used: bool


class FusionRequest(BaseModel):
    inputs: list[ModalityInput]
    output_modality: str
    operation: str = "fuse"  # fuse | edit | animate | transcribe
    duration_seconds: Optional[int] = None
    constraints: dict = Field(default_factory=dict)


# ---------------------------------------------
# API ENDPOINTS
# ---------------------------------------------

@app.post("/v1/generate", response_model=GenerationResponse)
async def generate(request: GenerationRequest, req: Request):
    """
    Single-modality generation with intelligent routing.
    """
    request_id = request.request_id or str(uuid.uuid4())
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Route to optimal adapter
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
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")


@app.post("/v1/fuse")
async def fuse(request: FusionRequest, req: Request):
    """
    Multimodal fusion: combine multiple inputs into a single output.
    """
    request_id = str(uuid.uuid4())
    
    # Delegate to fusion engine
    from omnimodal.fusion.planner import FusionPlanner
    
    planner = FusionPlanner()
    dag = planner.plan(request.inputs, request.output_modality, request.constraints)
    
    # Execute DAG
    result = await dag.execute(req.app.state.adapters)
    
    return {
        "request_id": request_id,
        "output": result.content,
        "stages_executed": len(dag.stages),
        "providers_used": result.providers
    }


@app.post("/v1/generate/stream")
async def generate_stream(request: GenerationRequest, req: Request):
    """
    Streaming generation for real-time applications.
    """
    adapter = req.app.state.adapters.get(request.output_modality)
    
    async def event_stream():
