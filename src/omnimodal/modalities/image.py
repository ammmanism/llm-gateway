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
