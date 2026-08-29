from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from echo_swm.ai.contracts import AIExecutionMetadata


class PersonaSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    name: str
    role: str
    organization: str
    location_id: str
    location: str
    tier: str
    represented_weight: float = Field(gt=0)
    mood: str
    tags: list[str]
    bio: str


class PersonaSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    prototype_matches: int = Field(ge=0)
    represented_population: float = Field(ge=0)
    total_prototypes: int = Field(ge=5_000)
    total_represented_population: float = Field(ge=5_000)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    items: list[PersonaSearchItem]
    note: str


class PersonaMapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    tier: str
    represented_weight: float = Field(gt=0)
    route_location_ids: list[str] = Field(min_length=1)


class PersonaMapSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_prototypes: int = Field(ge=5_000)
    total_represented_population: float = Field(ge=5_000)
    items: list[PersonaMapItem]
    note: str


class PersonaTrait(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    score: float = Field(ge=0, le=1)


class PersonaDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    field: str
    label: str
    description: str
    score: float = Field(ge=-1, le=1)
    scale_min: float
    scale_max: float
    low_pole: str
    high_pole: str
    interpretation: str


class PersonaFramework(BaseModel):
    model_config = ConfigDict(extra="forbid")

    framework_id: str
    label: str
    reference: str
    description: str
    dimensions: list[PersonaDimension] = Field(min_length=1)


class PersonaState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mood: str
    stress: int = Field(ge=0, le=100)
    intention: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    current_action: str
    current_location: str


class PersonaRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    name: str
    role: str
    relation: str
    trust: float = Field(ge=0, le=1)
    strength: float = Field(ge=0, le=1)
    channel: str


class PersonaScheduleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: str
    activity: str
    location: str


class PersonaProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    name: str
    role: str
    organization: str
    age: int = Field(ge=18)
    age_group: str
    gender: str
    education_level: str
    region_type: str
    household_type: str
    tier: str
    represented_weight: float = Field(gt=0)
    bio: str
    traits: list[PersonaTrait]
    values: list[PersonaTrait]
    demographics: dict[str, str]
    frameworks: list[PersonaFramework] = Field(min_length=1)
    primary_goal: str
    primary_interest: str
    primary_channel: str
    state: PersonaState
    memories: list[str]
    schedule: list[PersonaScheduleItem]
    relationships: list[PersonaRelationship]
    mobility: dict[str, str]
    model_version: str
    data_version: str
    definition_version: str
    source_id: str
    field_origins: dict[str, str]
    profile_completeness: float = Field(ge=0, le=1)
    profile_hash: str
    profile_origin: Literal["synthetic"] = "synthetic"
    disclaimer: str


class PersonaInterviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=1_000)
    event_context: str = Field(default="", max_length=5_000)


class PersonaCrossCheckCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    name: str
    relation: str


class PersonaInterviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interview_id: str
    persona_id: str
    persona_name: str
    question: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    mode: Literal["deterministic_persona", "llm_persona"]
    cited_state: list[str]
    cross_check_candidates: list[PersonaCrossCheckCandidate]
    cognitive_boundary: str
    ai_execution: list[AIExecutionMetadata] = Field(default_factory=list)


__all__ = [
    "PersonaCrossCheckCandidate",
    "PersonaDimension",
    "PersonaFramework",
    "PersonaInterviewRequest",
    "PersonaInterviewResponse",
    "PersonaMapItem",
    "PersonaMapSnapshot",
    "PersonaProfile",
    "PersonaRelationship",
    "PersonaScheduleItem",
    "PersonaSearchItem",
    "PersonaSearchResult",
    "PersonaState",
    "PersonaTrait",
]
