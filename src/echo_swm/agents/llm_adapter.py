from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError

from echo_swm.core.config import Settings
from echo_swm.core.exceptions import ConfigurationError, LLMResponseError
from echo_swm.core.ids import stable_hash

OutputModel = TypeVar("OutputModel", bound=BaseModel)


@dataclass
class LLMCallBudget:
    max_calls: int
    max_input_tokens: int = 1_000_000
    max_output_tokens: int = 100_000
    calls: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0

    def reserve(self, input_text: str, max_output_tokens: int) -> None:
        estimated_input = max(1, len(input_text) // 4)
        if self.calls + 1 > self.max_calls:
            raise LLMResponseError("LLM call budget exhausted")
        if self.estimated_input_tokens + estimated_input > self.max_input_tokens:
            raise LLMResponseError("LLM input-token budget exhausted")
        if self.estimated_output_tokens + max_output_tokens > self.max_output_tokens:
            raise LLMResponseError("LLM output-token budget exhausted")
        self.calls += 1
        self.estimated_input_tokens += estimated_input
        self.estimated_output_tokens += max_output_tokens


class OpenAICompatibleLLM:
    def __init__(
        self,
        settings: Settings,
        budget: LLMCallBudget | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        if not settings.llm_configured:
            raise ConfigurationError(
                "set QIANSCOPE_LLM_API_KEY and QIANSCOPE_LLM_MODEL to enable the LLM adapter "
                "(legacy ECHO_* names are also accepted)"
            )
        self.settings = settings
        self.budget = budget or LLMCallBudget(max_calls=settings.llm_max_calls)
        self.cache_dir = cache_dir or settings.artifact_dir / "llm_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[OutputModel],
        *,
        max_output_tokens: int = 800,
    ) -> OutputModel:
        response_schema = response_model.model_json_schema()
        cache_key = stable_hash(
            {
                "model": self.settings.llm_model,
                "system": system_prompt,
                "user": user_prompt,
                "schema": response_schema,
            }
        )
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            return response_model.model_validate_json(cache_path.read_text(encoding="utf-8"))
        schema_json = json.dumps(response_schema, ensure_ascii=False, separators=(",", ":"))
        constrained_system_prompt = (
            f"{system_prompt}\n\n"
            "Return exactly one JSON object that validates against this JSON Schema. "
            "Include every required field and do not add fields that the schema forbids.\n"
            f"{schema_json}"
        )
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        provider_host = urlparse(self.settings.llm_base_url).hostname or ""
        is_deepseek = provider_host == "api.deepseek.com" or provider_host.endswith(".deepseek.com")
        remaining_calls = max(1, self.budget.max_calls - self.budget.calls)
        max_attempts = min(3, remaining_calls)
        parsed: OutputModel | None = None
        last_error: Exception | None = None
        for attempt in range(max_attempts):
            retry_note = (
                ""
                if attempt == 0
                else "\n\nThe previous provider response was empty or invalid. "
                f"Retry {attempt + 1}: return the JSON object only."
            )
            attempt_system_prompt = constrained_system_prompt + retry_note
            payload = {
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": attempt_system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": max_output_tokens,
                "response_format": {"type": "json_object"},
            }
            if is_deepseek:
                payload["thinking"] = {"type": "disabled"}
            self.budget.reserve(attempt_system_prompt + user_prompt, max_output_tokens)
            try:
                response = httpx.post(
                    f"{self.settings.llm_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.settings.llm_timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise LLMResponseError("provider response content is not text")
                parsed = response_model.model_validate_json(content)
                break
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                json.JSONDecodeError,
                ValidationError,
                LLMResponseError,
            ) as exc:
                last_error = exc
        if parsed is None:
            error_name = type(last_error).__name__ if last_error is not None else "UnknownError"
            raise LLMResponseError(f"invalid LLM provider response: {error_name}") from last_error
        cache_path.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
        return parsed

    def probe(self) -> dict[str, str | bool]:
        class Probe(BaseModel):
            ok: bool
            message: str

        result = self.complete_json(
            "Return JSON only. This is a connectivity check.",
            'Return {"ok": true, "message": "connected"}.',
            Probe,
            max_output_tokens=60,
        )
        return result.model_dump()
