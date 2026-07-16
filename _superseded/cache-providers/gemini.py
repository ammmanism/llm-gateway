import httpx
import time
from typing import Dict, Any
from src.providers.base import BaseProvider, CompletionResponse
from src.config import settings

class GeminiProvider(BaseProvider):
    
    @property
    def name(self) -> str:
        return "gemini"
        
    @property
    def supported_models(self) -> list[str]:
        return ["gemini-2.5-flash", "gemini-1.5-flash"]
        
    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        prices = {
            "gemini-2.5-flash": {"in": 0.00015 / 1000, "out": 0.00035 / 1000},
            "gemini-1.5-flash": {"in": 0.00015 / 1000, "out": 0.00035 / 1000}
        }
        p = prices.get(model, prices["gemini-1.5-flash"])
        return tokens_in * p["in"] + tokens_out * p["out"]

    async def complete(self, model: str, messages: list[Dict[str, Any]], params: Dict[str, Any]) -> CompletionResponse:
        start_time = time.time()
        
        # Note: In a real implementation we would map OpenAI format to Gemini format here.
        # Assuming we are using Google's OpenAI compatibility layer or transforming payload.
        # For this design, let's assume we map messages to gemini structure.
        
        # Simplified mapping for demonstration
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ["user", "system"] else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content")}]})
            
        payload = {
            "contents": contents
        }
        
        api_key = settings.GEMINI_API_KEY
        
        async with httpx.AsyncClient() as client:
            # Using v1beta for gemini 1.5/2.5 compatibility via direct REST
            # This is a simplification.
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            usage = data.get("usageMetadata", {})
            tokens_in = usage.get("promptTokenCount", 0)
            tokens_out = usage.get("candidatesTokenCount", 0)
            
            text_response = ""
            if "candidates" in data and len(data["candidates"]) > 0:
                text_response = data["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            # Map back to OpenAI compatible format
            oai_response = {
                "id": "gemini-" + str(int(time.time())),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text_response
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": tokens_in,
                    "completion_tokens": tokens_out,
                    "total_tokens": tokens_in + tokens_out
                }
            }
            
            latency_ms = int((time.time() - start_time) * 1000)
            cost = self.calculate_cost(model, tokens_in, tokens_out)
            
            return CompletionResponse(
                provider=self.name,
                model=model,
                response=oai_response,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                latency_ms=latency_ms
            )
            
    async def health_check(self) -> bool:
        if not settings.GEMINI_API_KEY:
            return False
        return True