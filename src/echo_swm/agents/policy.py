from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echo_swm.contracts.person import DynamicAgentState


class AgentObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_ids: list[str]
    exposure_strength: float = Field(ge=0, le=1)
    neighbor_stance: float = Field(ge=-1, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class ActionDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_probabilities: dict[str, float]
    selected_action: str
    target_id: str | None = None
    content_stance: float | None = Field(default=None, ge=-1, le=1)
    emotion_delta: dict[str, float] = Field(default_factory=dict)
    belief_delta: dict[str, float] = Field(default_factory=dict)
    goal_delta: dict[str, float] = Field(default_factory=dict)
    trust_delta: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("action_probabilities")
    @classmethod
    def validate_probabilities(cls, value: dict[str, float]) -> dict[str, float]:
        if not value or any(probability < 0 or probability > 1 for probability in value.values()):
            raise ValueError("invalid action probability")
        if abs(sum(value.values()) - 1.0) > 1e-6:
            raise ValueError("action probabilities must sum to one")
        return value


class AgentPolicy(Protocol):
    def act(
        self,
        state: DynamicAgentState,
        observation: AgentObservation,
        action_space: list[str],
    ) -> ActionDistribution: ...
