"""
Image Modality Adapter
"""

import base64
import io
import logging
from dataclasses import dataclass
from typing import Any

import openai

from ..exceptions import ProviderError
from .base import BaseModalityAdapter, ModalityResponse

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

    async def generate(
        self, inputs: list[Any], provider: str = "openai", **kwargs
    ) -> ImageResponse:
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

    async def _generate_openai(
        self, prompt: str, model: str, size: str, quality: str, style: str | None
    ) -> ImageResponse:
        client = self.clients.get("openai")
        if not client:
            raise ProviderError("OpenAI client not initialized")

        params = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
            "response_format": "b64_json",
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
                height=height,
            )
        except Exception as e:
            raise ProviderError(f"OpenAI image error: {e}")

    async def _generate_stability(
        self, prompt: str, model: str, size: str
    ) -> ImageResponse:
        # Placeholder for Stability AI
        return ImageResponse(
            content="[base64_placeholder]",
            mime_type="image/png",
            model=model,
            provider="stability",
            cost=0.01,
            width=1024,
            height=1024,
        )

    async def edit(
        self, image: str, mask: str | None, prompt: str, provider: str = "openai"
    ) -> ImageResponse:
        if provider == "openai":
            client = self.clients.get("openai")
            if not client:
                raise ProviderError("OpenAI client not initialized")
            try:
                response = await client.images.edit(
                    image=io.BytesIO(base64.b64decode(image)),
                    mask=io.BytesIO(base64.b64decode(mask)) if mask else None,
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
                # Parse response...
                return ImageResponse(
                    content=response.data[0].b64_json,
                    mime_type="image/png",
                    model="dall-e-2",
                    provider="openai",
                    cost=0.02,
                    width=1024,
                    height=1024,
                )
            except Exception as e:
                raise ProviderError(f"OpenAI edit error: {e}")
        raise ValueError("Edit not supported for provider")

    async def generate_stream(self, inputs: list[Any], **kwargs):
        # Images are not streamed in chunks; yield whole image
        result = await self.generate(inputs, **kwargs)
        yield result.content

    async def understand(
        self, image: str, prompt: str, provider: str = "openai"
    ) -> str:
        if provider == "openai":
            client = self.clients.get("openai")
            if not client:
                raise ProviderError("OpenAI client not initialized")
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image}"
                                    },
                                },
                            ],
                        }
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                raise ProviderError(f"OpenAI vision error: {e}")
        return "[Image understanding not available]"

    def _extract_prompt(self, inputs: list[Any]) -> str:
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "text":
                return inp["content"]
            elif isinstance(inp, str):
                return inp
        return "Generate an image"

    def _default_model(self, provider: str) -> str:
        defaults = {"openai": "dall-e-3", "stability": "stable-diffusion-3"}
        return defaults.get(provider, "dall-e-3")

    async def close(self):
        for client in self.clients.values():
            if hasattr(client, "close"):
                await client.close()
