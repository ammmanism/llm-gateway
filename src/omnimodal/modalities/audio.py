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

    async def transcribe(self, audio: str, provider: str = "openai", **kwargs) -> AudioResponse:
        if provider == "openai":
            client = self.clients.get("openai")
            if not client:
                raise ProviderError("OpenAI client not initialized")
            model = kwargs.get("model", "whisper-1")
            language = kwargs.get("language")
            prompt = kwargs.get("prompt")

            audio_bytes = base64.b64decode(audio)
            try:
                response = await client.audio.transcriptions.create(
                    model=model,
                    file=("audio.mp3", audio_bytes),
                    language=language,
                    prompt=prompt,
                    response_format="text"
                )
                # Estimate duration: 1 min approx 1 MB, rough
                duration = len(audio_bytes) / (1000 * 60)  # rough
                cost = duration * self.pricing[model]["per_minute"]
                return AudioResponse(
                    content=response,
                    mime_type="text/plain",
                    model=model,
                    provider="openai",
                    cost=round(cost, 6),
                    duration_seconds=duration
                )
            except Exception as e:
                raise ProviderError(f"OpenAI transcription error: {e}")
        raise ValueError(f"Transcription not supported for {provider}")

    async def synthesize(self, text: str, provider: str = "openai", **kwargs) -> AudioResponse:
        if provider == "openai":
            client = self.clients.get("openai")
            if not client:
                raise ProviderError("OpenAI client not initialized")
            model = kwargs.get("model", "tts-1")
            voice = kwargs.get("voice", "alloy")
            speed = kwargs.get("speed", 1.0)

            try:
                response = await client.audio.speech.create(
                    model=model,
                    voice=voice,
                    input=text,
                    speed=speed
                )
                audio_bytes = await response.aread()
