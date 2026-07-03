"""
Audio Modality Adapter
"""

import base64
import logging
from typing import List, Any, Optional
from dataclasses import dataclass
import openai

from .base import BaseModalityAdapter, ModalityResponse
from ..exceptions import ProviderError

logger = logging.getLogger(__name__)

@dataclass
class AudioResponse(ModalityResponse):
    duration_seconds: float = 0.0

class AudioAdapter(BaseModalityAdapter):
    """
    Adapter for audio-based AI providers.
    """

    def __init__(self):
        self.clients = {}
        self._init_clients()

        self.pricing = {
            "whisper-1": {"per_minute": 0.006},
            "tts-1": {"per_1k_chars": 0.015},
            "tts-1-hd": {"per_1k_chars": 0.030},
        }

    def _init_clients(self):
        import os
        if os.getenv("OPENAI_API_KEY"):
            self.clients["openai"] = openai.AsyncOpenAI()
        # ElevenLabs client initialized on-demand

    async def generate(self, inputs: List[Any], provider: str = "openai", **kwargs) -> AudioResponse:
        prompt = self._extract_prompt(inputs)
        operation = kwargs.get("operation", "synthesize")

        if operation == "transcribe":
            # The 'prompt' is actually audio data
            return await self.transcribe(prompt, provider, **kwargs)
        else:
            return await self.synthesize(prompt, provider, **kwargs)

