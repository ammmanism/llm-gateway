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
