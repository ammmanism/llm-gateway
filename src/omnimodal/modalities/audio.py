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
