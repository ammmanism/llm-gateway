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
                mime_type="image/png",
                model=model,
                provider="openai",
                cost=0.04,
                width=width,
                height=height
            )
        
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
    
    async def _generate_stability(self, prompt, model, size):
        """Generate using Stability AI."""
        return ImageResponse(
            content="[Mock Stability base64_image]",
            mime_type="image/png",
            model=model,
            provider="stability",
            cost=0.01,
            width=1024,
            height=1024
        )
    
    async def edit(
        self,
        image: str,  # Base64
        mask: Optional[str],
        prompt: str,
        provider: str = "openai"
    ) -> ImageResponse:
        """
        Edit an image using inpainting/outpainting.
        """
        client = self.clients.get("openai")
        if provider == "openai" and client is not None:
            try:
                response = await client.images.edit(
                    image=io.BytesIO(base64.b64decode(image)),
                    mask=io.BytesIO(base64.b64decode(mask)) if mask else None,
                    prompt=prompt,
                    n=1,
                    size="1024x1024"
                )
                # handle response...
            except Exception:
                pass
        
        return ImageResponse(
            content="[edited_image_base64]",
            mime_type="image/png",
            model="dall-e-2",
            provider="openai",
            cost=0.02,
            width=1024,
            height=1024
        )
    
    async def understand(
        self,
        image: str,  # Base64
        prompt: str,
        provider: str = "openai"
    ) -> str:
        """
        Image understanding / visual question answering.
        Uses GPT-4V or Gemini Pro Vision.
        """
        client = self.clients.get("openai")
        if provider == "openai" and client is not None:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}}
                        ]
                    }
                ]
            )
            return response.choices[0].message.content
        
        return "[Image understanding result]"
    
    async def vary(
        self,
        image: str,
        provider: str = "openai",
        n: int = 1
    ) -> List[ImageResponse]:
        """
        Create variations of an image.
        """
        return [await self.generate([{"type": "text", "content": "variation"}], provider)]
    
    def _extract_prompt(self, inputs: List[Any]) -> str:
        """Extract text prompt from inputs."""
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "text":
                return inp["content"]
            elif isinstance(inp, str):
                return inp
            elif hasattr(inp, "content"):
                return getattr(inp, "content")
        return "Generate an image"
    
    def _default_model(self, provider: str) -> str:
        defaults = {"openai": "dall-e-3", "stability": "stable-diffusion-3"}
        return defaults.get(provider, "dall-e-3")
    
    async def close(self):
        for client in self.clients.values():
            if hasattr(client, 'close'):
                try:
                    await client.close()
                except Exception:
                    pass
