from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from echo_swm.contracts.event import EventType
from echo_swm.contracts.question import QuestionSpec


class InterventionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    event_type: EventType
    intensity: float = Field(ge=0, le=1)
    channel: str
    target_segments: list[str] = Field(default_factory=list)
    attributes: dict[str, float | str | bool] = Field(default_factory=dict)


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    name: str
    description: str
    as_of_time: datetime
    population_id: str
    population_size: int = Field(ge=1, le=1_000_000)
    sampling_strategy: str = "weighted_prototype"
    initial_state: dict[str, float] = Field(default_factory=dict)
    interventions: list[InterventionSpec]
    control_condition: str
    network_config: dict[str, float | str | int] = Field(default_factory=dict)
    environment_config: dict[str, float | str | int] = Field(default_factory=dict)
    allowed_actions: list[str]
    social_constraints: dict[str, float] = Field(default_factory=dict)
    start_time: datetime
    end_time: datetime
    tick_size: timedelta = timedelta(days=1)
    horizons: list[int] = Field(default_factory=lambda: [1, 7, 14])
    questions: list[QuestionSpec]
    target_metrics: list[str]
    uncertainty_config: dict[str, float | int | str] = Field(default_factory=dict)
    llm_budget: int = Field(default=0, ge=0)
    random_seed: int = 2026

    @model_validator(mode="after")
    def validate_timeline(self) -> ScenarioSpec:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must follow start_time")
        if self.as_of_time > self.start_time:
            raise ValueError("as_of_time cannot be after scenario start")
        if self.tick_size.total_seconds() <= 0:
            raise ValueError("tick_size must be positive")
        return self
