import httpx
import time
from typing import Dict, Any
from src.providers.base import BaseProvider, CompletionResponse
from src.config import settings

class DeepSeekProvider(BaseProvider):
    
    @property
    def name(self) -> str:
        return "deepseek"
        
    @property
    def supported_models(self) -> list[str]:
        return ["deepseek-v3"]
        
    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        prices = {
            "deepseek-v3": {"in": 0.00014 / 1000, "out": 0.00028 / 1000}
        }
        p = prices.get(model, prices["deepseek-v3"])
        return tokens_in * p["in"] + tokens_out * p["out"]

    async def complete(self, model: str, messages: list[Dict[str, Any]], params: Dict[str, Any]) -> CompletionResponse:
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Mapping to actual model name if needed, assuming deepseek-v3 maps to deepseek-chat in API
        api_model = "deepseek-chat" if model == "deepseek-v3" else model
        
        payload = {
            "model": api_model,
            "messages": messages,
            **params
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=60.0)
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
                response=data,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                latency_ms=latency_ms
            )
            
    async def health_check(self) -> bool:
        if not settings.DEEPSEEK_API_KEY:
            return False
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"}
                res = await client.get("https://api.deepseek.com/v1/models", headers=headers, timeout=5.0)
                return res.status_code == 200
        except Exception:
            return False