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
