"""
Text Modality Adapter
Unified interface for text generation, understanding, and code.
"""

import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from omnimodal.modalities.base import BaseModalityAdapter

# Optional dependencies handled gracefully
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None


@dataclass
class TextResponse:
    content: str
    model: str
    provider: str
    tokens_input: int
    tokens_output: int
    cost: float
    from_cache: bool = False
    mime_type: str = "text/plain"


class TextAdapter(BaseModalityAdapter):
    """
    Adapter for text-based AI providers.
    Supports: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini), Local (Ollama)
    """
    
    def __init__(self):
        self.clients = {}
        self._init_clients()
        
        # Cost per 1K tokens
        self.pricing = {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "gemini-pro": {"input": 0.0005, "output": 0.0015},
            "llama-3-70b": {"input": 0.0, "output": 0.0},  # Local
