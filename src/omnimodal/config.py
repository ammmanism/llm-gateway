"""
OmniModal Configuration
Production-grade settings with environment-based overrides.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os


@dataclass
class ProviderConfig:
    """Configuration for a single AI provider."""
    name: str
    api_key_env: str
    base_url: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    rate_limit_rps: float = 10.0
    enabled: bool = True
    regions: List[str] = field(default_factory=lambda: ["us-east"])
    cost_model: Dict = field(default_factory=dict)
    
    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "")


@dataclass
class CacheConfig:
    """Two-tier caching configuration."""
    semantic_cache_url: str = "redis://localhost:6379/0"
    vector_cache_url: str = "redis://localhost:6379/1"
    semantic_ttl_seconds: int = 3600
    vector_ttl_seconds: int = 86400
    similarity_threshold: float = 0.95
    max_entries: int = 100000


@dataclass
class RoutingConfig:
    """Routing and optimization settings."""
    default_quality_threshold: float = 0.7
    default_latency_budget_ms: int = 5000
    enable_cost_optimization: bool = True
    enable_semantic_caching: bool = True
    fallback_enabled: bool = True
    fallback_max_attempts: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 30
    enable_bulkhead: bool = True


@dataclass
class ObservabilityConfig:
    """Metrics and tracing configuration."""
    enable_opentelemetry: bool = True
    jaeger_endpoint: Optional[str] = None
    prometheus_port: int = 9090
    log_level: str = "INFO"
    enable_cost_tracking: bool = True
    enable_latency_histograms: bool = True


@dataclass
class OmniModalConfig:
    """Master configuration."""
    app_name: str = "omnimodal"
    version: str = "1.0.0"
    debug: bool = False
    
    # Sub-configs
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    cache: CacheConfig = field(default_factory=CacheConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    
    # Fusion
    fusion_max_stages: int = 10
    fusion_timeout_seconds: float = 300.0
    enable_streaming_fusion: bool = True
    
    @classmethod
    def from_env(cls) -> "OmniModalConfig":
        """Load configuration from environment variables."""
        config = cls()
        
        # Provider configs
        config.providers = {
            "openai": ProviderConfig(
                name="openai",
                api_key_env="OPENAI_API_KEY",
                rate_limit_rps=50.0,
                cost_model={"gpt-4o": {"input": 0.005, "output": 0.015}}
            ),
            "anthropic": ProviderConfig(
                name="anthropic",
                api_key_env="ANTHROPIC_API_KEY",
                rate_limit_rps=20.0,
                cost_model={"claude-3-opus": {"input": 0.015, "output": 0.075}}
            ),
            "google": ProviderConfig(
                name="google",
                api_key_env="GOOGLE_API_KEY",
                rate_limit_rps=30.0
            ),
            "stability": ProviderConfig(
                name="stability",
                api_key_env="STABILITY_API_KEY",
                rate_limit_rps=10.0
            ),
            "replicate": ProviderConfig(
                name="replicate",
                api_key_env="REPLICATE_API_TOKEN",
                rate_limit_rps=5.0
            ),
            "local": ProviderConfig(
                name="local",
                api_key_env="",
                base_url="http://localhost:11434",  # Ollama
                rate_limit_rps=100.0,
                enabled=False  # Opt-in
            )
        }
        
        return config


# Global config instance
settings = OmniModalConfig.from_env()
