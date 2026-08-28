from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from echo_swm.core.exceptions import ConfigurationError


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc


@dataclass(frozen=True)
class Settings:
    artifact_dir: Path
    min_segment_size: int
    log_level: str
    llm_api_key: str | None
    llm_base_url: str
    llm_model: str | None
    llm_timeout_seconds: float
    llm_max_calls: int

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        load_dotenv(env_file or ".env", override=False)
        return cls(
            artifact_dir=Path(os.getenv("ECHO_ARTIFACT_DIR", "artifacts")),
            min_segment_size=_int_env("ECHO_MIN_SEGMENT_SIZE", 30),
            log_level=os.getenv("ECHO_LOG_LEVEL", "INFO"),
            llm_api_key=os.getenv("ECHO_LLM_API_KEY") or None,
            llm_base_url=os.getenv("ECHO_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_model=os.getenv("ECHO_LLM_MODEL") or None,
            llm_timeout_seconds=_float_env("ECHO_LLM_TIMEOUT_SECONDS", 45.0),
            llm_max_calls=_int_env("ECHO_LLM_MAX_CALLS", 100),
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)
