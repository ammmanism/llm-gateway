"""
Video Modality Adapter
Unified interface for video generation, editing, and understanding.
"""

import base64
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from omnimodal.modalities.base import BaseModalityAdapter

try:
    import replicate
except ImportError:
    replicate = None


@dataclass
class VideoResponse:
    content: str  # Base64 video or URL
    mime_type: str
    model: str
    provider: str
    cost: float
    duration_seconds: int
    width: int
    height: int
    fps: int
    from_cache: bool = False


class VideoAdapter(BaseModalityAdapter):
    """
    Adapter for video-based AI providers.
    Supports: Replicate (Stable Video Diffusion, Sora), Runway, Pika
    """
    
    def __init__(self):
        self.clients = {}
        self._init_clients()
        
        self.pricing = {
            "stable-video-diffusion": {"per_4s": 0.05},
            "sora": {"per_10s": 0.50},
            "runway-gen2": {"per_4s": 0.10},
        }
    
    def _init_clients(self):
        import os
        if replicate is not None and os.getenv("REPLICATE_API_TOKEN"):
            try:
                self.clients["replicate"] = replicate.Client(os.getenv("REPLICATE_API_TOKEN"))
            except Exception:
                pass
    
    async def generate(
        self,
        inputs: List[Any],
        provider: str = "replicate",
        model: Optional[str] = None,
        duration: int = 4,
        width: int = 1024,
        height: int = 576,
        fps: int = 24,
        **kwargs
    ) -> VideoResponse:
        """
        Generate video from text and/or image.
        """
        prompt = self._extract_prompt(inputs)
        model = model or self._default_model(provider)
        
        if provider == "replicate":
            return await self._generate_replicate(
                prompt, model, duration, width, height, fps, inputs
            )
        elif provider == "runway":
            return await self._generate_runway(prompt, model, duration)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _generate_replicate(
        self, prompt, model, duration, width, height, fps, inputs
    ) -> VideoResponse:
