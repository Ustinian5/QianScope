from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ValueOrigin(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    MISSING = "missing"
    SYNTHETIC = "synthetic"
    MODEL_GENERATED = "model_generated"


class MemoryKind(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class RelationshipKind(StrEnum):
    FRIEND = "friend"
    FAMILY = "family"
    COWORKER = "coworker"
    FOLLOWER = "follower"
    AUTHORITY = "authority"
    COMMUNITY = "community"


class BigFiveProfile(BaseModel):
    """Slow-moving personality traits. An event transition must never mutate these fields."""

    model_config = ConfigDict(extra="forbid")

    openness: float = Field(ge=0, le=1)
    conscientiousness: float = Field(ge=0, le=1)
    extraversion: float = Field(ge=0, le=1)
    agreeableness: float = Field(ge=0, le=1)
    neuroticism: float = Field(ge=0, le=1)


class SchwartzValueProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self_direction: float = Field(ge=0, le=1)
    stimulation: float = Field(ge=0, le=1)
    achievement: float = Field(ge=0, le=1)
    power: float = Field(ge=0, le=1)
    security: float = Field(ge=0, le=1)
    conformity: float = Field(ge=0, le=1)
    tradition: float = Field(ge=0, le=1)
    benevolence: float = Field(ge=0, le=1)
    universalism: float = Field(ge=0, le=1)
    hedonism: float = Field(ge=0, le=1)


class MoralFoundationProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    care: float = Field(ge=0, le=1)
    fairness: float = Field(ge=0, le=1)
    loyalty: float = Field(ge=0, le=1)
    authority: float = Field(ge=0, le=1)
    purity: float = Field(ge=0, le=1)
    liberty: float = Field(ge=0, le=1)


class RiskProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_risk: float = Field(ge=0, le=1)
    social_risk: float = Field(ge=0, le=1)
    technology_risk: float = Field(ge=0, le=1)
    health_risk: float = Field(ge=0, le=1)


class CognitiveStyleProfile(BaseModel):
    """Bipolar axes use -1 for the right label and +1 for the left label."""

    model_config = ConfigDict(extra="forbid")

    analytical_intuitive: float = Field(ge=-1, le=1)
    independent_social: float = Field(ge=-1, le=1)
    long_short_term: float = Field(ge=-1, le=1)
    evidence_experience: float = Field(ge=-1, le=1)


class PersonalityArchitecture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    big_five: BigFiveProfile
    schwartz_values: SchwartzValueProfile
    moral_foundations: MoralFoundationProfile
    risk_profile: RiskProfile
    cognitive_style: CognitiveStyleProfile
    uncertainty: dict[str, float] = Field(default_factory=dict)
    version: str = "human-digital-twin-personality-v2"

    @field_validator("uncertainty")
    @classmethod
    def bounded_uncertainty(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < 0 or item > 1 for item in value.values()):
            raise ValueError("personality uncertainty must be between zero and one")
        return value


class GoalProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    security: float = Field(ge=0, le=1)
    achievement: float = Field(ge=0, le=1)
    status: float = Field(ge=0, le=1)
    belonging: float = Field(ge=0, le=1)
    growth: float = Field(ge=0, le=1)
    meaning: float = Field(ge=0, le=1)
    survival: float = Field(ge=0, le=1)


class BeliefEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    updated_at: datetime
    evidence_refs: list[str] = Field(default_factory=list)


class EmotionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valence: float = Field(default=0, ge=-1, le=1)
    arousal: float = Field(default=0, ge=0, le=1)
    dominance: float = Field(default=0.5, ge=0, le=1)
    joy: float = Field(default=0, ge=0, le=1)
    anger: float = Field(default=0, ge=0, le=1)
    anxiety: float = Field(default=0, ge=0, le=1)


class MentalStateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emotion: EmotionProfile = Field(default_factory=EmotionProfile)
    attention: float = Field(default=0, ge=0, le=1)
    stress: float = Field(default=0, ge=0, le=1)
    trust: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    interest: float = Field(default=0, ge=0, le=1)
    intention: float = Field(default=0, ge=0, le=1)
    awareness: float = Field(default=0, ge=0, le=1)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    kind: MemoryKind
    content: str = Field(min_length=1, max_length=4_000)
    timestamp: datetime
    importance: float = Field(ge=0, le=1)
    emotion: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    decay_rate: float = Field(ge=0, le=1)
    source: str
    event_refs: list[str] = Field(default_factory=list)


class RelationshipProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    kind: RelationshipKind
    strength: float = Field(ge=0, le=1)
    trust: float = Field(ge=0, le=1)
    similarity: float = Field(ge=0, le=1)
    influence: float = Field(ge=0, le=1)
    frequency: float = Field(ge=0)


class HumanDigitalTwin(BaseModel):
    """Typed H_i(t) state used by policies instead of a free-form persona prompt."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    identity: dict[str, Any]
    personality: PersonalityArchitecture
    beliefs: dict[str, BeliefEntry]
    goals: GoalProfile
    memories: list[MemoryRecord] = Field(default_factory=list)
    relationships: list[RelationshipProfile] = Field(default_factory=list)
    current_state: MentalStateProfile = Field(default_factory=MentalStateProfile)
    profile_hash: str
    state_version: int = Field(default=0, ge=0)


class PersonProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: str
    source_id: str
    survey_weight: float = Field(default=1.0, ge=0)
    observed_at: datetime
    available_at: datetime
    demographics: dict[str, Any] = Field(default_factory=dict)
    socioeconomic: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    education: dict[str, Any] = Field(default_factory=dict)
    occupation: dict[str, Any] = Field(default_factory=dict)
    geography: dict[str, Any] = Field(default_factory=dict)
    stable_traits: dict[str, float] = Field(default_factory=dict)
    values: dict[str, float] = Field(default_factory=dict)
    preferences: dict[str, float] = Field(default_factory=dict)
    institutional_trust: dict[str, float] = Field(default_factory=dict)
    media_preferences: dict[str, float] = Field(default_factory=dict)
    historical_exposure: list[dict[str, Any]] = Field(default_factory=list)
    response_history: list[dict[str, Any]] = Field(default_factory=list)
    behavior_history: list[dict[str, Any]] = Field(default_factory=list)
    missingness_mask: dict[str, bool] = Field(default_factory=dict)
    value_origins: dict[str, ValueOrigin] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)
    personality: PersonalityArchitecture | None = None
    goals: GoalProfile | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> PersonProfile:
        if self.available_at < self.observed_at:
            raise ValueError("available_at must not precede observed_at")
        return self


class DynamicAgentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    snapshot_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    beliefs: dict[str, float] = Field(default_factory=dict)
    attitudes: dict[str, float] = Field(default_factory=dict)
    intentions: dict[str, float] = Field(default_factory=dict)
    emotions: dict[str, float] = Field(default_factory=dict)
    awareness: float = Field(default=0.0, ge=0, le=1)
    trust: dict[str, float] = Field(default_factory=dict)
    risk_perception: float = Field(default=0.0, ge=0, le=1)
    purchase_intent: float = Field(default=0.0, ge=0, le=1)
    expression_intent: float = Field(default=0.0, ge=0, le=1)
    action_readiness: float = Field(default=0.0, ge=0, le=1)
    working_memory: list[dict[str, Any]] = Field(default_factory=list)
    episodic_memory_refs: list[str] = Field(default_factory=list)
    semantic_memory_refs: list[str] = Field(default_factory=list)
    state_uncertainty: dict[str, float] = Field(default_factory=dict)
    last_updated_by: str
    goal_activation: dict[str, float] = Field(default_factory=dict)
    attention: float = Field(default=0.0, ge=0, le=1)
    stress: float = Field(default=0.0, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    interest: float = Field(default=0.0, ge=0, le=1)

    @field_validator("beliefs", "attitudes", "intentions", "emotions", "trust")
    @classmethod
    def bounded_maps(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < -1 or item > 1 for item in value.values()):
            raise ValueError("state-map values must be between -1 and 1")
        return value

    @field_validator("goal_activation")
    @classmethod
    def bounded_goals(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < 0 or item > 1 for item in value.values()):
            raise ValueError("goal activation must be between zero and one")
        return value
