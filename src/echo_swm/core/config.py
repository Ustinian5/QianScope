from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from echo_swm.core.exceptions import ConfigurationError


def _env(primary: str, legacy: str) -> str | None:
    value = os.getenv(primary)
    return value if value is not None else os.getenv(legacy)


def _int_env(name: str, legacy_name: str, default: int) -> int:
    raw = _env(name, legacy_name)
    try:
        return int(raw) if raw is not None else default
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc


def _float_env(name: str, legacy_name: str, default: float) -> float:
    raw = _env(name, legacy_name)
    try:
        return float(raw) if raw is not None else default
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc


def _bool_env(name: str, legacy_name: str, default: bool) -> bool:
    raw = _env(name, legacy_name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


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
    llm_required: bool = False

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        load_dotenv(env_file or ".env", override=False)
        return cls(
            artifact_dir=Path(_env("QIANSCOPE_ARTIFACT_DIR", "ECHO_ARTIFACT_DIR") or "artifacts"),
            min_segment_size=_int_env("QIANSCOPE_MIN_SEGMENT_SIZE", "ECHO_MIN_SEGMENT_SIZE", 30),
            log_level=_env("QIANSCOPE_LOG_LEVEL", "ECHO_LOG_LEVEL") or "INFO",
            llm_api_key=_env("QIANSCOPE_LLM_API_KEY", "ECHO_LLM_API_KEY") or None,
            llm_base_url=(
                _env("QIANSCOPE_LLM_BASE_URL", "ECHO_LLM_BASE_URL") or "https://api.openai.com/v1"
            ).rstrip("/"),
            llm_model=_env("QIANSCOPE_LLM_MODEL", "ECHO_LLM_MODEL") or None,
            llm_timeout_seconds=_float_env(
                "QIANSCOPE_LLM_TIMEOUT_SECONDS", "ECHO_LLM_TIMEOUT_SECONDS", 45.0
            ),
            llm_max_calls=_int_env("QIANSCOPE_LLM_MAX_CALLS", "ECHO_LLM_MAX_CALLS", 100),
            llm_required=_bool_env("QIANSCOPE_LLM_REQUIRED", "ECHO_LLM_REQUIRED", False),
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)
