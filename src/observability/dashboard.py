import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from typing import Dict, Any

router = APIRouter()

# Global state for dashboard, usually backed by Redis/PG
dashboard_state: Dict[str, Any] = {
    "total_savings": 0.0,
    "cache_hits": 0,
    "total_requests": 0,
    "providers": {
        "openai": {"status": "healthy", "latency": 500, "error_rate": 0.0},
        "deepseek": {"status": "healthy", "latency": 600, "error_rate": 0.0}
    }
}

def get_dashboard_data():
    return dashboard_state

@router.get("/dashboard/data")
async def get_data():
    return get_dashboard_data()
    
@router.get("/savings")
async def get_savings():
    return {"savings": dashboard_state.get("total_savings", 0.0)}

async def event_generator(request: Request):
    while True:
        if await request.is_disconnected():
            break
            
        yield {
            "event": "update",
            "data": json.dumps(get_dashboard_data())
        }
        await asyncio.sleep(5.0) # Update every 5s

@router.get("/dashboard/stream")
async def dashboard_stream(request: Request):
    return EventSourceResponse(event_generator(request))
