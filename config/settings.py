"""
config/settings.py
Application configuration loaded from environment variables and .env file.
Validated using pydantic-settings.
"""
import os
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# Load .env from project root (one directory up from config/)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)


class Settings(BaseSettings):
    """
    Application configuration with support for Gemini API and models.
    Supports GEMINI_API_KEY and GEMINI_MODEL (with AI_MODEL / API_KEY fallbacks).
    """

    # AI provider selection
    ai_provider: Literal["gemini"] = Field(
        default="gemini",
        description="LLM provider to use. Currently supports: gemini",
    )

    # Gemini model identifier (preferred: GEMINI_MODEL, alias: AI_MODEL)
    gemini_model: str = Field(
        default="gemini-flash-latest",
        description="Gemini model identifier (e.g. gemini-flash-latest, gemini-3.8-flash, gemini-3.5-flash-lite)",
    )

    # Secondary alias for backwards compatibility
    ai_model: Optional[str] = Field(
        default=None,
        description="Generic model alias (used if GEMINI_MODEL is not set)",
    )

    # Gemini API key (preferred: GEMINI_API_KEY, alias: API_KEY)
    gemini_api_key: str = Field(
        default="",
        description="API key for Gemini. Set via GEMINI_API_KEY env var.",
    )

    api_key_fallback: Optional[str] = Field(
        default=None,
        alias="api_key",
        description="Generic API key fallback if GEMINI_API_KEY is not specified",
    )

    # File upload settings
    max_file_size_mb: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Maximum allowed upload file size in megabytes",
    )

    # Logging level
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Python logging level",
    )

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def extract_api_key(cls, v: Optional[str]) -> str:
        """Extract and clean the API key from environment."""
        if v is None:
            v = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY") or ""
        return str(v).strip().strip("\"'")

    @field_validator("gemini_model", mode="before")
    @classmethod
    def extract_model(cls, v: Optional[str]) -> str:
        """Extract and clean model name, prioritizing GEMINI_MODEL over AI_MODEL."""
        env_val = os.environ.get("GEMINI_MODEL") or os.environ.get("AI_MODEL") or v
        if not env_val or not str(env_val).strip():
            return "gemini-flash-latest"
        return str(env_val).strip().strip("\"'")

    @property
    def api_key(self) -> str:
        """Active API key for the configured provider."""
        key = self.gemini_api_key or self.api_key_fallback or os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY") or ""
        return key.strip().strip("\"'")

    @property
    def active_model(self) -> str:
        """Active model name for the configured provider."""
        return self.gemini_model or self.ai_model or "gemini-flash-latest"

    @property
    def max_file_size_bytes(self) -> int:
        """File size limit in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    def is_configured(self) -> bool:
        """Return True if a non-empty API key is configured."""
        return bool(self.api_key)


# Singleton instance used throughout the application
settings = Settings()
