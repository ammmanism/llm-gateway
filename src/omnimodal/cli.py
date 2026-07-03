"""
OmniModal CLI - Command-line interface for the unified gateway.
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Optional

import click
import structlog

# We can import from omnimodal dynamically to avoid circular references
# but since settings is at config, that's safe
from omnimodal.config import settings

logger = structlog.get_logger()


class MockResult:
    def __init__(self, content, cost_usd=0.01, latency_ms=500, providers=None):
        self.content = content
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.providers = providers or ["openai"]


class MockOmniClient:
    def __init__(self, api_key=None):
        self.api_key = api_key

    async def generate(self, prompt, modality, quality, max_cost_usd=None):
        return MockResult(
            content=f"Generated {modality} for prompt: {prompt}",
            cost_usd=0.002,
            latency_ms=250
        )

    async def transcribe(self, audio_data, language=None):
        return MockResult(
            content="Transcribed text from mock audio data",
            cost_usd=0.006,
            latency_ms=300
        )

    async def fuse(self, inputs, output, operation="fuse", duration_seconds=None):
        return MockResult(
            content=f"Fused multimodal output as {output}",
            cost_usd=0.045,
            latency_ms=1200,
            providers=["openai", "replicate"]
        )

    async def health(self):
        return {
            "status": "healthy",
            "version": "1.0.0",
            "providers": {
                "openai": {"enabled": True, "regions": ["us-east"]},
                "anthropic": {"enabled": True, "regions": ["us-west"]},
                "google": {"enabled": True, "regions": ["us-central"]}
            }
        }

    async def get_cost_report(self, days=30):
        return {
            "total_optimizations": 42,
            "cache_hits": 24,
            "model_downgrades": 18,
            "total_saved_usd": 1.24,
            "cache_hit_rate": 0.57
        }


