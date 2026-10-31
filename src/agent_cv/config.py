from functools import cached_property
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    public_host: str = "agent-cv.fernandoperalta.xyz"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_url: str = "http://127.0.0.1:11435"
    profile_path: Path = Path("data/profile.json")
    state_path: Path = Path("data/state/responses.sqlite3")
    api_key_file: Path = Path(".secrets/api_key")
    allow_draft_profile: bool = False
    requests_per_minute: int = Field(default=20, ge=1)
    model_timeout_seconds: float = Field(default=45, ge=1, le=120)
    response_ttl_seconds: int = Field(default=86400, ge=60)
    max_stored_responses: int = Field(default=2000, ge=1)
    max_body_bytes: int = Field(default=32768, ge=1024)
    max_context_chars: int = Field(default=16000, ge=1000)
    max_question_chars: int = Field(default=2000, ge=100)
    model_context: int = Field(default=4096, ge=2048, le=8192)
    model_threads: int = Field(default=3, ge=1, le=6)
    public_model: str = "cv-fernando"
    allowed_origins: list[str] = []

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, origins):
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS origins must be exact HTTPS origins without credentials or paths"
                )
        return origins

    @cached_property
    def api_key(self) -> str:
        key = self.api_key_file.read_text().strip()
        if len(key) < 32 or any(c.isspace() for c in key):
            raise ValueError("API key must contain at least 32 characters without whitespace")
        return key
