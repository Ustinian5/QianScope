from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echo_swm import DISCLAIMER


class ProbabilityPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_probabilities: dict[str, float]
    expected_value: float | None = None
    predicted_state_delta: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str] = Field(default_factory=list)
    used_fields: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    out_of_distribution: bool = False

    @field_validator("option_probabilities")
    @classmethod
    def probability_simplex(cls, value: dict[str, float]) -> dict[str, float]:
        if not value or any(prob < 0 or prob > 1 for prob in value.values()):
            raise ValueError("option probabilities must be within [0, 1]")
        if abs(sum(value.values()) - 1.0) > 1e-6:
            raise ValueError("option probabilities must sum to one")
        return value


class ForecastOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    model_version: str
    data_version: str
    scenario_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    individual_predictions: list[dict[str, Any]] = Field(default_factory=list)
    segment_predictions: list[dict[str, Any]] = Field(default_factory=list)
    population_predictions: dict[str, float] = Field(default_factory=dict)
    trajectory_predictions: list[dict[str, Any]] = Field(default_factory=list)
    outcome_probabilities: dict[str, float] = Field(default_factory=dict)
    time_to_event: dict[str, float] = Field(default_factory=dict)
    counterfactual_deltas: dict[str, float] = Field(default_factory=dict)
    confidence_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    calibration_status: str = "uncalibrated"
    explanation_factors: list[str] = Field(default_factory=list)
    applicability_boundary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
