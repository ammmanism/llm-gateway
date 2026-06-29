import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # App config
    APP_NAME: str = "Neurocache"
    ENV: str = "development"
    PORT: int = 8000
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # PostgreSQL
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/neurocache"
    
    # Cache
    DEFAULT_CACHE_TTL_HOURS: int = 24
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.92
    
    # Providers (set via environment variables in production)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    
    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
