"""
Image Modality Adapter
Unified interface for image generation, editing, and understanding.
"""

import base64
import io
from typing import List, Optional, Union, Any
from dataclasses import dataclass
from omnimodal.modalities.base import BaseModalityAdapter

try:
    import openai
except ImportError:
    openai = None


@dataclass
class ImageResponse:
    content: str  # Base64 encoded image
    mime_type: str
    model: str
    provider: str
    cost: float
    width: int
    height: int
    from_cache: bool = False


class ImageAdapter(BaseModalityAdapter):
    """
    Adapter for image-based AI providers.
    Supports: OpenAI (DALL-E), Stability AI (SDXL), Google (Imagen)
    """
    
    def __init__(self):
        self.clients = {}
        self._init_clients()
        
        self.pricing = {
            "dall-e-3": {"1024x1024": 0.04, "1024x1792": 0.08, "1792x1024": 0.08},
            "dall-e-2": {"1024x1024": 0.02},
            "stable-diffusion-3": {"standard": 0.01},
        }
    
    def _init_clients(self):
        import os
        if openai is not None and os.getenv("OPENAI_API_KEY"):
            try:
                self.clients["openai"] = openai.AsyncOpenAI()
            except Exception:
                pass
    
    async def generate(
        self,
        inputs: List[Any],
        provider: str = "openai",
        model: Optional[str] = None,
        size: str = "1024x1024",
        quality: str = "standard",
        style: Optional[str] = None,
        **kwargs
    ) -> ImageResponse:
        """
        Generate image from text prompt.
        """
        prompt = self._extract_prompt(inputs)
        model = model or self._default_model(provider)
        
        if provider == "openai":
            return await self._generate_openai(prompt, model, size, quality, style)
        elif provider == "stability":
            return await self._generate_stability(prompt, model, size)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _generate_openai(
        self, prompt: str, model: str, size: str, quality: str, style: Optional[str]
    ) -> ImageResponse:
        """Generate using DALL-E."""
        client = self.clients.get("openai")
        if client is None:
            # Mock fallback
            width, height = map(int, size.split("x"))
            return ImageResponse(
                content="[Mock OpenAI base64_image]",
