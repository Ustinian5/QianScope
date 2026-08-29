from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class AIExecutionMetadata(BaseModel):
    """Safe, persistable receipt proving that a provider call backed an operation."""

    model_config = ConfigDict(extra="forbid")

    operation: str
    provider: str
    model: str
    provider_call_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cache_hit: bool = False
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    variation_id: str | None = None


__all__ = ["AIExecutionMetadata"]
