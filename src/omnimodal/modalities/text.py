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
            "unknown": {"input": 0.0, "output": 0.0}
        }
    
    def _init_clients(self):
        """Initialize provider clients."""
        import os
        if openai is not None and os.getenv("OPENAI_API_KEY"):
            try:
                self.clients["openai"] = openai.AsyncOpenAI()
            except Exception:
                pass
        if anthropic is not None and os.getenv("ANTHROPIC_API_KEY"):
            try:
                self.clients["anthropic"] = anthropic.AsyncAnthropic()
            except Exception:
                pass
    
    async def generate(
        self,
        inputs: List[Any],
        provider: str = "openai",
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> TextResponse:
        """
        Generate text from text inputs.
        """
        prompt = self._extract_prompt(inputs)
        model = model or self._default_model(provider)
        
        if provider == "openai":
            return await self._generate_openai(prompt, model, max_tokens, temperature)
        elif provider == "anthropic":
            return await self._generate_anthropic(prompt, model, max_tokens, temperature)
        elif provider == "google":
            return await self._generate_google(prompt, model, max_tokens, temperature)
        elif provider == "local":
            return await self._generate_local(prompt, model, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def _generate_openai(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> TextResponse:
        """Generate using OpenAI."""
        client = self.clients.get("openai")
        if client is None:
            # Mock fallback
            await asyncio.sleep(0.1)
            return TextResponse(
                content=f"[Mock OpenAI Response for prompt: {prompt[:30]}...]",
                model=model,
                provider="openai",
                tokens_input=10,
                tokens_output=20,
                cost=0.001
            )
        
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
