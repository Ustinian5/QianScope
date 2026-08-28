from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobKind = Literal["insight", "prediction", "world"]
JobStatus = Literal["queued", "running", "cancelling", "complete", "cancelled", "failed"]


class JobDecisionPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_index: int = Field(ge=1)
    total_rounds: int = Field(ge=1)
    agent_id: str
    name: str
    role: str
    question: str
    choice: str
    confidence: float = Field(ge=0, le=1)


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    kind: JobKind
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    processed_agents: int = Field(ge=0)
    total_agents: int = Field(ge=0)
    current_round: int = Field(default=0, ge=0)
    total_rounds: int = Field(default=0, ge=0)
    processed_decisions: int = Field(default=0, ge=0)
    total_decisions: int = Field(default=0, ge=0)
    decision_feed: list[JobDecisionPreview] = Field(default_factory=list, max_length=12)
    latest_trace: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cancellation_requested: bool = False
    result_available: bool = False
    error: str | None = None


__all__ = ["JobDecisionPreview", "JobKind", "JobRecord", "JobStatus"]
