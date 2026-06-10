"""Application settings via pydantic-settings.

All configuration is driven by environment variables.
Never read os.environ directly — use this module.
"""

from __future__ import annotations

import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Runtime
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mcpforge"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "change-me-min-32-characters-long"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://mcpforge-monorepo-web-8nay-c7a96u1b9.vercel.app",
        "https://mcpforge-monorepo.vercel.app",
    ]

    # Encryption (Fernet master key for credentials at rest)
    ENCRYPTION_KEY: str = ""

    # CSRF
    CSRF_SECRET: str = ""

    # Rate limiting
    RATE_LIMIT_PER_IP_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_IP_PER_MINUTE: int = 5

    # Account lockout
    LOCKOUT_MAX_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # HIBP
    HIBP_ENABLED: bool = True
    HIBP_API_URL: str = "https://api.pwnedpasswords.com/range"

    # GitHub OAuth (optional, Phase 2)
    GITHUB_OAUTH_CLIENT_ID: str = ""
    GITHUB_OAUTH_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = ""

    # LLM provider (OpenAI-compatible, primary = DeepSeek)
    LLM_PROVIDER: str = "opencode-go"
    LLM_BASE_URL: str = "https://opencode.ai/zen/go/v1"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_KEY: str = ""
    LLM_MAX_TOKENS: int = 2000
    LLM_TEMPERATURE: float = 0.0
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_RETRY_ATTEMPTS: int = 3
    LLM_PROMPT_CACHING_ENABLED: bool = True
    LLM_JSON_MODE: bool = True

    # Application URL (used in email links, redirects)
    APP_URL: str = "http://localhost:3000"

    # Email (Resend, Phase 1.1)
    EMAIL_PROVIDER_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "noreply@mcpforge.io"

    # Stripe billing (Phase 1.1)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_LITIGATED_MODE: bool = False
    STRIPE_PRICE_PRO_MONTHLY: str = ""
    STRIPE_PRICE_PRO_YEARLY: str = ""
    STRIPE_PRICE_TEAM_SEAT_MONTHLY: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    # AWS S3 (object storage for OpenAPI specs and other files)
    AWS_S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_ENDPOINT_URL: str = ""  # Optional: for S3-compatible services

    # Sentry
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # API keys (F7)
    MAX_API_KEYS_PER_USER: int = 5

    # Cost guardrails
    MAX_AI_CREDITS_PER_USER_PER_DAY: int = 100
    MAX_SPEC_SIZE_BYTES: int = 5_242_880  # 5MB
    MAX_SPEC_FETCH_TIMEOUT_SECONDS: int = 10

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins that arrive as JSON strings from env vars.

        pydantic-settings passes the raw env var value as a string. When
        `list[str]` is the annotated type, it attempts JSON parsing but
        may fall back to comma-splitting. This validator ensures the value
        is correctly parsed regardless.
        """
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # Fallback: comma-separated
            return [item.strip().strip('"').strip("'") for item in v.split(",") if item.strip()]
        raise TypeError(f"Unexpected CORS_ORIGINS type: {type(v).__name__}")

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT_SECRET is at least 32 characters in production."""
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters long. "
                "Generate one with: openssl rand -hex 32"
            )
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "production", "testing"}
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def sentry_sample_rate(self) -> float:
        """100% in dev, 10% in prod unless overridden."""
        if self.SENTRY_TRACES_SAMPLE_RATE:
            return self.SENTRY_TRACES_SAMPLE_RATE
        return 1.0 if self.is_development else 0.1


settings = Settings()
