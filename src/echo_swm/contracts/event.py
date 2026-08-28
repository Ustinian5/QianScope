from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventType(StrEnum):
    PRODUCT_LAUNCH = "product_launch"
    PRICE_CHANGE = "price_change"
    POLICY_CHANGE = "policy_change"
    PUBLIC_STATEMENT = "public_statement"
    PLATFORM_RULE_CHANGE = "platform_rule_change"
    COMPETITOR_ACTION = "competitor_action"
    REPUTATION_SHOCK = "reputation_shock"
    ECONOMIC_SIGNAL = "economic_signal"
    SOCIAL_INCIDENT = "social_incident"
    INFORMATION_CAMPAIGN = "information_campaign"
    ORGANIZATIONAL_CHANGE = "organizational_change"
    CUSTOM = "custom"


class EventSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: EventType
    actors: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    occurred_at: datetime
    became_available_at: datetime
    end_at: datetime | None = None
    geographic_scope: list[str] = Field(default_factory=list)
    population_scope: list[str] = Field(default_factory=list)
    channel: str | None = None
    intensity: float = Field(default=0.0, ge=0, le=1)
    valence: float = Field(default=0.0, ge=-1, le=1)
    credibility: float = Field(default=0.5, ge=0, le=1)
    novelty: float = Field(default=0.5, ge=0, le=1)
    reversibility: float = Field(default=0.5, ge=0, le=1)
    duration: timedelta | None = None
    raw_text: str = ""
    normalized_summary: str = ""
    structured_attributes: dict[str, Any] = Field(default_factory=dict)
    evidence_spans: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    normalization_confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_times(self) -> EventSpec:
        if self.became_available_at < self.occurred_at:
            raise ValueError("became_available_at must not precede occurred_at")
        if self.end_at and self.end_at < self.occurred_at:
            raise ValueError("end_at must not precede occurred_at")
        return self
