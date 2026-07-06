"""
OmniModal Configuration
"""

import os
from dataclasses import dataclass, field

import yaml


@dataclass
class ProviderConfig:
    name: str
    api_key_env: str
    base_url: str | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    rate_limit_rps: float = 10.0
    enabled: bool = True
    regions: list[str] = field(default_factory=lambda: ["us-east"])
    cost_model: dict = field(default_factory=dict)

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
    jaeger_endpoint: str | None = None
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
class CoreConfig:
    enable_deduplication: bool = True
    dedup_exact_ttl_seconds: float = 30.0
    dedup_semantic_ttl_seconds: float = 5.0
    dedup_max_batch_size: int = 10

    enable_concurrency_limiting: bool = True
    concurrency_min_limit: int = 1
    concurrency_max_limit: int = 1000
    concurrency_default_limit: int = 10

    enable_experiments: bool = True
    experiment_min_samples: int = 100
    experiment_confidence_level: float = 0.95

    enable_schema_enforcement: bool = True
    schema_max_repair_attempts: int = 3

    prompt_storage_path: str = "./prompts"
    enable_prompt_registry: bool = True

    enable_carbon_tracking: bool = True
    carbon_default_region: str = "us-east"
    carbon_max_grams_per_day: float = 1000.0

    enable_watermarking: bool = False
    watermark_default_provider: str = "omnimodal"

@dataclass
class OmniModalConfig:
    app_name: str = "omnimodal"
    version: str = "1.0.0"
    debug: bool = False

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    cache: CacheConfig = field(default_factory=CacheConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    core: CoreConfig = field(default_factory=CoreConfig)

    fusion_max_stages: int = 10
    fusion_timeout_seconds: float = 300.0
    enable_streaming_fusion: bool = True

    @classmethod
    def from_env(cls) -> "OmniModalConfig":
        config = cls()

        # Providers
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
            "huggingface": ProviderConfig(
                name="huggingface",
                api_key_env="HF_TOKEN",
                rate_limit_rps=5.0,
                enabled=False
            ),
            "aws_bedrock": ProviderConfig(
                name="aws_bedrock",
                api_key_env="AWS_ACCESS_KEY_ID",
                rate_limit_rps=10.0,
                enabled=False
            ),
            "mistral": ProviderConfig(
                name="mistral",
                api_key_env="MISTRAL_API_KEY",
                rate_limit_rps=10.0,
                enabled=False
            ),
            "local": ProviderConfig(
                name="local",
                api_key_env="",
                base_url="http://localhost:11434",
                rate_limit_rps=100.0,
                enabled=True
            )
        }

        # Load custom weights
        weights_path = os.getenv("OMNI_WEIGHTS_FILE", "config/provider_weights.yaml")
        if os.path.exists(weights_path):
            with open(weights_path) as f:
                weights = yaml.safe_load(f)
                # Merge weights into provider configs (simplified)

        return config

settings = OmniModalConfig.from_env()
