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
    Application configuration with support for Gemini API, MongoDB persistence, and models.
    Supports GEMINI_API_KEY, GEMINI_MODEL, and MONGODB_URI.
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

    # ── MongoDB Settings ────────────────────────────────────────────────────────
    mongodb_uri: str = Field(
        default="",
        description="MongoDB Atlas connection URI. Set via MONGODB_URI env var.",
    )

    mongodb_database: str = Field(
        default="ai_coding_assistant",
        description="MongoDB Database name.",
    )

    mongodb_users_collection: str = Field(
        default="users",
        description="MongoDB collection for user accounts.",
    )

    mongodb_history_collection: str = Field(
        default="coding_history",
        description="MongoDB collection for coding history records.",
    )

    mongodb_activity_collection: str = Field(
        default="activity_logs",
        description="MongoDB collection for user activity logs.",
    )

    # ── Environment & App Base URL ──────────────────────────────────────────────
    environment: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Deployment environment (development, production, testing)",
    )

    app_base_url: str = Field(
        default="http://localhost:8501",
        description="Base URL for password reset links and callbacks",
    )

    # ── Password Reset Settings ────────────────────────────────────────────────
    password_reset_token_expiry_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Password reset token expiration time in minutes",
    )

    # ── SMTP Email Settings ────────────────────────────────────────────────────
    smtp_host: str = Field(
        default="",
        description="SMTP server host (e.g. smtp.gmail.com)",
    )

    smtp_port: int = Field(
        default=587,
        description="SMTP server port (e.g. 587 for STARTTLS, 465 for SSL)",
    )

    smtp_username: str = Field(
        default="",
        description="SMTP username or email address",
    )

    smtp_password: str = Field(
        default="",
        description="SMTP password or app password",
    )

    smtp_from_email: str = Field(
        default="",
        description="Sender email address for notifications",
    )

    smtp_use_tls: bool = Field(
        default=True,
        description="Enable STARTTLS for SMTP connections",
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

    @field_validator("mongodb_uri", mode="before")
    @classmethod
    def extract_mongo_uri(cls, v: Optional[str]) -> str:
        """Extract and clean the MongoDB URI."""
        if v is None:
            v = os.environ.get("MONGODB_URI") or ""
        return str(v).strip().strip("\"'")

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

    def is_mongo_configured(self) -> bool:
        """Return True if a non-empty MongoDB URI is configured."""
        return bool(self.mongodb_uri)

    @property
    def is_smtp_configured(self) -> bool:
        """Return True if SMTP host and port are configured."""
        return bool(self.smtp_host and self.smtp_host.strip())

    @property
    def is_development(self) -> bool:
        """Return True if running in development mode."""
        return self.environment.lower() == "development"


# Singleton instance used throughout the application
settings = Settings()
