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
