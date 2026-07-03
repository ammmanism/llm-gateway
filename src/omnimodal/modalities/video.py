"""
Video Modality Adapter
"""

import logging
from typing import List, Any, Optional, Dict
from dataclasses import dataclass

from .base import BaseModalityAdapter, ModalityResponse
from ..exceptions import ProviderError

logger = logging.getLogger(__name__)

@dataclass
class VideoResponse(ModalityResponse):
    duration_seconds: int = 0
    width: int = 0
    height: int = 0
    fps: int = 0

class VideoAdapter(BaseModalityAdapter):
    """
    Adapter for video-based AI providers.
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
        if os.getenv("REPLICATE_API_TOKEN"):
            import replicate
            self.clients["replicate"] = replicate.Client(os.getenv("REPLICATE_API_TOKEN"))
        # Runway/Pika clients on-demand

    async def generate(self, inputs: List[Any], provider: str = "replicate", **kwargs) -> VideoResponse:
        prompt = self._extract_prompt(inputs)
        model = kwargs.get("model") or self._default_model(provider)
        duration = kwargs.get("duration", 4)
        width = kwargs.get("width", 1024)
        height = kwargs.get("height", 576)
        fps = kwargs.get("fps", 24)

        if provider == "replicate":
            return await self._generate_replicate(prompt, model, duration, width, height, fps, inputs)
        elif provider == "google":
            return await self._generate_google(prompt, model, duration, width, height, fps)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _generate_replicate(self, prompt: str, model: str, duration: int, width: int, height: int, fps: int, inputs: List[Any]) -> VideoResponse:
        client = self.clients.get("replicate")
        if not client:
            raise ProviderError("Replicate client not initialized")

        # Check for image input
        image_input = None
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "image":
                image_input = inp["content"]

        try:
            if image_input:
                output = client.run(
                    model,
                    input={
                        "image": image_input,
                        "motion_bucket_id": 127,
                        "noise_aug_strength": 0.02,
                        "frames": duration * fps
                    }
                )
            else:
                output = client.run(
                    model,
                    input={"prompt": prompt, "num_frames": duration * fps}
                )
            video_url = output if isinstance(output, str) else output[0]
            cost = self.pricing.get(model, {}).get("per_4s", 0.05) * (duration / 4)
            return VideoResponse(
                content=video_url,
                mime_type="video/mp4",
                model=model,
                provider="replicate",
                cost=round(cost, 4),
                duration_seconds=duration,
                width=width,
                height=height,
                fps=fps
            )
        except Exception as e:
            raise ProviderError(f"Replicate video error: {e}")

    async def _generate_google(self, prompt: str, model: str, duration: int, width: int, height: int, fps: int) -> VideoResponse:
        # Placeholder for Google Video Generation (if available)
        return VideoResponse(
            content="https://example.com/video.mp4",
            mime_type="video/mp4",
            model=model,
            provider="google",
            cost=0.10,
            duration_seconds=duration,
            width=width,
            height=height,
            fps=fps
        )

    async def generate_stream(self, inputs: List[Any], **kwargs):
        # Video streaming not supported yet; yield full video
        result = await self.generate(inputs, **kwargs)
        yield result.content

    def _extract_prompt(self, inputs: List[Any]) -> str:
        for inp in inputs:
            if isinstance(inp, dict) and inp.get("type") == "text":
                return inp["content"]
            elif isinstance(inp, str):
                return inp
        return "Generate a video"

    def _default_model(self, provider: str) -> str:
        defaults = {
            "replicate": "stability-ai/stable-video-diffusion",
            "google": "gemini-pro-vision"
        }
        return defaults.get(provider, "stability-ai/stable-video-diffusion")

    async def close(self):
        pass
