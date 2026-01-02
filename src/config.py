"""Configuration management for the multi-agent system."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Anthropic API Configuration
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use",
    )

    # Database Configuration
    database_url: str = Field(..., description="PostgreSQL connection URL")

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    # API Configuration
    api_port: int = Field(default=8000, description="API server port")
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_workers: int = Field(default=4, description="Number of API workers")

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: Literal["json", "text"] = Field(default="json", description="Log format")

    # Security
    secret_key: str = Field(..., description="Secret key for JWT signing")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration in minutes"
    )

    # Agent Configuration
    max_retries: int = Field(default=3, description="Max retries for LLM calls")
    retry_delay: float = Field(default=1.0, description="Initial retry delay in seconds")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    max_tokens: int = Field(default=4096, description="Max tokens for LLM responses")

    # Conversation Settings
    conversation_ttl: int = Field(default=1800, description="Conversation TTL in seconds")
    max_conversation_length: int = Field(
        default=100, description="Max messages in conversation"
    )

    # Inventory Settings
    low_stock_threshold: int = Field(default=10, description="Low stock alert threshold")
    reservation_ttl: int = Field(
        default=300, description="Inventory reservation TTL in seconds"
    )

    # Kitchen Settings
    peak_hours_start: int = Field(default=11, description="Morning peak start hour")
    peak_hours_end: int = Field(default=13, description="Morning peak end hour")
    evening_peak_start: int = Field(default=18, description="Evening peak start hour")
    evening_peak_end: int = Field(default=20, description="Evening peak end hour")

    # Delivery Settings
    max_delivery_distance_km: float = Field(
        default=10.0, description="Max delivery distance in km"
    )
    driver_pool_size: int = Field(default=5, description="Number of drivers in pool")

    # Support Settings
    auto_refund_threshold: float = Field(
        default=100.0, description="Auto-approve refunds below this amount"
    )
    escalation_threshold: int = Field(
        default=3, description="Failed attempts before escalation"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
