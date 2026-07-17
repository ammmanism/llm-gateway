import os
from typing import Optional


class Settings:
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")
    CACHE_REDACTION_ENABLED: bool = os.environ.get("CACHE_REDACTION_ENABLED", "true").lower() == "true"
    CACHE_DRIFT_INVALIDATION_ENABLED: bool = os.environ.get("CACHE_DRIFT_INVALIDATION_ENABLED", "true").lower() == "true"
    DEFAULT_CACHE_TTL_HOURS: int = int(os.environ.get("DEFAULT_CACHE_TTL_HOURS", "24"))


settings = Settings()
