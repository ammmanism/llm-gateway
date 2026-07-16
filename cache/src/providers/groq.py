import httpx
import time
from typing import Dict, Any
from src.providers.base import BaseProvider, CompletionResponse
from src.config import settings

class GroqProvider(BaseProvider):
    
    @property
    def name(self) -> str:
        return "groq"
        
    @property
    def supported_models(self) -> list[str]:
        return ["llama-3.3-70b-versatile"]
        
    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        prices = {
            "llama-3.3-70b-versatile": {"in": 0.00059 / 1000, "out": 0.00079 / 1000}
        }
        p = prices.get(model, prices["llama-3.3-70b-versatile"])
        return tokens_in * p["in"] + tokens_out * p["out"]

    async def complete(self, model: str, messages: list[Dict[str, Any]], params: Dict[str, Any]) -> CompletionResponse:
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            **params
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            
            latency_ms = int((time.time() - start_time) * 1000)
            cost = self.calculate_cost(model, tokens_in, tokens_out)
            
            return CompletionResponse(
                provider=self.name,
                model=model,
                response=data, # Groq returns OpenAI compatible format
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                latency_ms=latency_ms
            )
            
    async def health_check(self) -> bool:
        if not settings.GROQ_API_KEY:
            return False
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
                res = await client.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5.0)
                return res.status_code == 200
        except Exception:
            return False