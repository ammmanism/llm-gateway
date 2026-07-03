"""
OmniModal Configuration
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import yaml
import json

@dataclass
class ProviderConfig:
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
    semantic_cache_url: str = "redis://localhost:6379/0"
    vector_cache_url: str = "redis://localhost:6379/1"
    semantic_ttl_seconds: int = 3600
    vector_ttl_seconds: int = 86400
    similarity_threshold: float = 0.95
    max_entries: int = 100000

@dataclass
class RoutingConfig:
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
    enable_opentelemetry: bool = True
    jaeger_endpoint: Optional[str] = None
    prometheus_port: int = 9090
    log_level: str = "INFO"
    enable_cost_tracking: bool = True
    enable_latency_histograms: bool = True

@dataclass
class SecurityConfig:
    pii_redaction_enabled: bool = True
    rbac_enabled: bool = True
    rbac_policy_file: str = "config/rbac_policies.json"
    audit_log_enabled: bool = True
    audit_log_backend: str = "console"  # console, elasticsearch, cloudtrail

@dataclass
class OmniModalConfig:
    app_name: str = "omnimodal"
    version: str = "1.0.0"
    debug: bool = False

    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    cache: CacheConfig = field(default_factory=CacheConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    fusion_max_stages: int = 10
    fusion_timeout_seconds: float = 300.0
    enable_streaming_fusion: bool = True

