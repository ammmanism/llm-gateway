"""
Audio Modality Adapter
Unified interface for audio generation, transcription, and speech.
"""

import base64
import asyncio
from typing import List, Optional, Any
from dataclasses import dataclass
from omnimodal.modalities.base import BaseModalityAdapter

try:
    import openai
except ImportError:
    openai = None


@dataclass
class AudioResponse:
    content: str  # Base64 audio
    mime_type: str
    model: str
    provider: str
    cost: float
    duration_seconds: float
    from_cache: bool = False


class AudioAdapter(BaseModalityAdapter):
    """
    Adapter for audio-based AI providers.
    Supports: OpenAI (Whisper, TTS), ElevenLabs, Google (Text-to-Speech)
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
        if openai is not None and os.getenv("OPENAI_API_KEY"):
            try:
                self.clients["openai"] = openai.AsyncOpenAI()
            except Exception:
                pass
    
    async def transcribe(
        self,
        audio: str,  # Base64 or URL
        provider: str = "openai",
        model: str = "whisper-1",
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> AudioResponse:
        """
        Speech-to-text transcription.
        """
        client = self.clients.get("openai")
        if provider == "openai" and client is not None:
            # Decode base64 to file-like object
            audio_bytes = base64.b64decode(audio)
            
            response = await client.audio.transcriptions.create(
                model=model,
                file=("audio.mp3", audio_bytes),
                language=language,
                prompt=prompt,
                response_format="text"
            )
            
            return AudioResponse(
                content=response,  # Transcribed text
                mime_type="text/plain",
                model=model,
                provider="openai",
                cost=0.006,  # Approximate for 1 min
                duration_seconds=60.0
            )
        
        return AudioResponse(
            content="[Mock Transcription of audio file]",
            mime_type="text/plain",
            model=model,
            provider=provider,
            cost=0.0,
            duration_seconds=0.0
        )
    
    async def synthesize(
        self,
        text: str,
        provider: str = "openai",
        model: str = "tts-1",
        voice: str = "alloy",
        speed: float = 1.0,
        **kwargs
    ) -> AudioResponse:
        """
        Text-to-speech synthesis.
        """
        client = self.clients.get("openai")
        if provider == "openai" and client is not None:
            response = await client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed
            )
            
            audio_bytes = await response.aread()
            audio_b64 = base64.b64encode(audio_bytes).decode()
            
