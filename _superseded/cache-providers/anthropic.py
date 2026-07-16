import httpx
import time
from typing import Dict, Any, AsyncGenerator
from src.providers.base import BaseProvider, CompletionResponse
from src.config import settings

class AnthropicProvider(BaseProvider):
    
    @property
    def name(self) -> str:
        return "anthropic"
        
    @property
    def supported_models(self) -> list[str]:
        return ["claude-sonnet-4", "claude-haiku-3.5", "claude-3-5-sonnet-latest"]
        
    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        prices = {
            "claude-sonnet-4": {"in": 0.003 / 1000, "out": 0.015 / 1000},
            "claude-3-5-sonnet-latest": {"in": 0.003 / 1000, "out": 0.015 / 1000},
            "claude-haiku-3.5": {"in": 0.001 / 1000, "out": 0.005 / 1000}
        }
        # default to haiku if unknown
        p = prices.get(model, prices["claude-haiku-3.5"])
        return tokens_in * p["in"] + tokens_out * p["out"]

    async def stream(self, model: str, messages: list[Dict[str, Any]], params: Dict[str, Any]) -> AsyncGenerator[str, None]:
        import uuid
        import json
        
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        system_prompt = ""
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt += msg.get("content", "") + "\n"
            else:
                filtered_messages.append(msg)
                
        payload = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": params.get("max_tokens", 1000),
            "stream": True,
            **{k:v for k,v in params.items() if k not in ["max_tokens", "presence_penalty", "frequency_penalty", "stream"]}
        }
        
        if system_prompt:
            payload["system"] = system_prompt.strip()
            
        msg_id = f"msg_{uuid.uuid4().hex}"
        created_time = int(time.time())
        done_yielded = False
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60.0) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_str = line[len("data:"):].strip()
                        try:
                            data = json.loads(data_str)
                            data_type = data.get("type")
                            if data_type == "message_start":
                                msg_id = data.get("message", {}).get("id", msg_id)
                                model = data.get("message", {}).get("model", model)
                            elif data_type == "content_block_delta":
                                text = data.get("delta", {}).get("text", "")
                                if text:
                                    oai_chunk = {
                                        "id": msg_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_time,
                                        "model": model,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {"content": text},
                                            "finish_reason": None
                                        }]
                                    }
                                    yield f"data: {json.dumps(oai_chunk)}\n\n"
                            elif data_type == "message_delta":
                                stop_reason = data.get("delta", {}).get("stop_reason")
                                if stop_reason == "end_turn":
                                    stop_reason = "stop"
                                oai_chunk = {
                                    "id": msg_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": stop_reason or "stop"
                                    }]
                                }
                                yield f"data: {json.dumps(oai_chunk)}\n\n"
                                yield "data: [DONE]\n\n"
                                done_yielded = True
                        except json.JSONDecodeError:
                            pass
                
                if not done_yielded:
                    yield "data: [DONE]\n\n"

    async def complete(self, model: str, messages: list[Dict[str, Any]], params: Dict[str, Any]) -> CompletionResponse:
        start_time = time.time()
        
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Anthropic messages API requires top-level system parameter if role="system"
        system_prompt = ""
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt += msg.get("content", "") + "\n"
            else:
                filtered_messages.append(msg)
                
        payload = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": params.get("max_tokens", 1000),
            **{k:v for k,v in params.items() if k not in ["max_tokens", "presence_penalty", "frequency_penalty"]} # exclude some openai specific params
        }
        
        if system_prompt:
            payload["system"] = system_prompt.strip()
        
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            usage = data.get("usage", {})
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            
            # Map back to OpenAI compatible format for internal response
            oai_response = {
                "id": data.get("id"),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": data.get("model"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": data.get("content", [{}])[0].get("text", "")
                    },
                    "finish_reason": data.get("stop_reason")
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
        if not settings.ANTHROPIC_API_KEY:
            return False
        # Anthropic doesn't have a /models endpoint without auth, we might just assume true or do a dummy request
        return True