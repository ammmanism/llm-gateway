from fastapi import Header, HTTPException, status

from src.config import settings


def require_admin_api_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    if not settings.ADMIN_API_KEY:
        return
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


def validate_startup_security() -> None:
    if settings.ENV.lower() not in {"production", "prod"}:
        return

    if "*" in settings.CORS_ORIGINS:
        raise RuntimeError("CORS_ORIGINS must not contain '*' in production")
    if not settings.ADMIN_API_KEY:
        raise RuntimeError("ADMIN_API_KEY is required in production")

    if settings.REQUIRE_PROVIDER_KEYS_IN_PROD:
        provider_keys = [
            settings.OPENAI_API_KEY,
            settings.ANTHROPIC_API_KEY,
            settings.DEEPSEEK_API_KEY,
            settings.GROQ_API_KEY,
            settings.GEMINI_API_KEY,
        ]
        if not any(provider_keys):
            raise RuntimeError("At least one provider API key is required in production")
