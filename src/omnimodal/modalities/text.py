"""
Text Modality Adapter
"""

import asyncio
import logging
from typing import List, Optional, Any
from dataclasses import dataclass
import openai
import anthropic

from .base import BaseModalityAdapter, ModalityResponse
from ..config import settings
from ..exceptions import ProviderError

logger = logging.getLogger(__name__)

@dataclass
class TextResponse(ModalityResponse):
    tokens_input: int = 0
    tokens_output: int = 0

class TextAdapter(BaseModalityAdapter):
    """
    Adapter for text-based AI providers.
    """

    def __init__(self):
        self.clients = {}
        self._init_clients()

        self.pricing = {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "gemini-pro": {"input": 0.0005, "output": 0.0015},
            "llama-3-70b": {"input": 0.0, "output": 0.0},
            "meta-llama/Llama-2-70b-chat-hf": {"input": 0.0001, "output": 0.0002},
            "amazon.titan-tg1-large": {"input": 0.001, "output": 0.002},
            "mistral-large-latest": {"input": 0.0003, "output": 0.001},
        }

    def _init_clients(self):
        import os
        if os.getenv("OPENAI_API_KEY"):
            self.clients["openai"] = openai.AsyncOpenAI()
        if os.getenv("ANTHROPIC_API_KEY"):
            self.clients["anthropic"] = anthropic.AsyncAnthropic()
