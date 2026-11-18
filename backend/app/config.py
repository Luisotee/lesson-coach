"""The one config: model, reasoning effort, token limits, deadlines and limits.

Values come from the environment, or from the repo's `.env` when it exists (local dev).
On Container Apps they come from secrets and env vars.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

ReasoningEffort = Literal["minimal", "low", "medium", "high"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Azure OpenAI. Without a key the API still works, and every AI part abstains.
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_api_version: str = "2025-04-01-preview"
    model_live: str = "gpt-5.5-live"

    # Per task: the mistake explainer and the transcription of photos and drawings.
    mistake_reasoning_effort: ReasoningEffort = "low"
    mistake_max_completion_tokens: int = 4000
    mistake_deadline_s: float = 30.0
    transcribe_reasoning_effort: ReasoningEffort = "low"
    transcribe_max_completion_tokens: int = 4000
    transcribe_deadline_s: float = 45.0
    llm_attempt_timeout_s: float = 25.0

    # sympy runs in worker processes with a wall-clock limit per request.
    math_workers: int = 2
    math_timeout_s: float = 3.0

    content_dir: Path = REPO_ROOT / "content" / "generated"

    # Requests per minute per client IP. With trust_proxy, the client IP is the right-most
    # X-Forwarded-For entry (the one the Container Apps ingress adds).
    rate_mistake_per_min: int = 20
    rate_transcribe_per_min: int = 10
    rate_check_working_per_min: int = 60
    trust_proxy: bool = False

    @property
    def llm_configured(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
