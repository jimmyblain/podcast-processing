"""Configuration management using pydantic-settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


WhisperModel = Literal["tiny", "base", "small", "medium", "large-v3"]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic API
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude",
    )

    # Whisper settings
    whisper_model: WhisperModel = Field(
        default="medium",
        description="Whisper model to use for transcription",
    )

    # Claude model
    claude_model: str = Field(
        default="claude-sonnet-4-5",
        description="Claude model to use for content generation",
    )

    # Output settings
    default_output_dir: Path = Field(
        default=Path("output"),
        description="Default output directory",
    )

    # Chapter settings
    default_chapter_count: int = Field(
        default=10,
        ge=3,
        le=30,
        description="Default number of chapters to generate",
    )


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
