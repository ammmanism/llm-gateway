"""
Image Modality Adapter
"""

import base64
import io
import logging
from typing import List, Optional, Any
from dataclasses import dataclass
import openai

from .base import BaseModalityAdapter, ModalityResponse
from ..exceptions import ProviderError

logger = logging.getLogger(__name__)

@dataclass
class ImageResponse(ModalityResponse):
    width: int = 0
    height: int = 0

class ImageAdapter(BaseModalityAdapter):
    """
    Adapter for image-based AI providers.
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
        if os.getenv("OPENAI_API_KEY"):
            self.clients["openai"] = openai.AsyncOpenAI()
        # Other clients on-demand

    async def generate(self, inputs: List[Any], provider: str = "openai", **kwargs) -> ImageResponse:
        prompt = self._extract_prompt(inputs)
        model = kwargs.get("model") or self._default_model(provider)
        size = kwargs.get("size", "1024x1024")
        quality = kwargs.get("quality", "standard")
        style = kwargs.get("style")

        if provider == "openai":
            return await self._generate_openai(prompt, model, size, quality, style)
        elif provider == "stability":
            return await self._generate_stability(prompt, model, size)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _generate_openai(self, prompt: str, model: str, size: str, quality: str, style: Optional[str]) -> ImageResponse:
        client = self.clients.get("openai")
        if not client:
            raise ProviderError("OpenAI client not initialized")

        params = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
            "response_format": "b64_json"
        }
        if style:
            params["style"] = style

        try:
            response = await client.images.generate(**params)
            image_data = response.data[0].b64_json
            width, height = map(int, size.split("x"))
            cost = self.pricing.get(model, {}).get(size, 0.04)

            return ImageResponse(
                content=image_data,
                mime_type="image/png",
                model=model,
                provider="openai",
                cost=cost,
                width=width,
                height=height
            )
        except Exception as e:
            raise ProviderError(f"OpenAI image error: {e}")

    async def _generate_stability(self, prompt: str, model: str, size: str) -> ImageResponse:
        # Placeholder for Stability AI
        return ImageResponse(
            content="[base64_placeholder]",
            mime_type="image/png",
            model=model,
            provider="stability",
            cost=0.01,
            width=1024,
            height=1024
