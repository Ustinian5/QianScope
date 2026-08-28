from __future__ import annotations

from datetime import datetime

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResolvedEventForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_id: str
    candidate_id: str
    forecast_as_of: datetime
    horizon_end: datetime
    probability: float = Field(ge=0, le=1)
    outcome: int = Field(ge=0, le=1)
    outcome_available_at: datetime
    weight: float = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_resolution_timing(self) -> ResolvedEventForecast:
        if self.horizon_end <= self.forecast_as_of:
            raise ValueError("forecast horizon must end after the prediction cutoff")
        if self.outcome_available_at < self.horizon_end:
            raise ValueError("outcome resolution cannot be available before the horizon ends")
        return self


class CalibrationBin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_rate: float


class EventBacktestReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    weighted_base_rate: float
    brier_score: float
    brier_skill_score: float
    log_loss: float
    expected_calibration_error: float
    calibration_bins: list[CalibrationBin]


def score_resolved_forecasts(
    records: list[ResolvedEventForecast],
    *,
    bins: int = 10,
) -> EventBacktestReport:
    if not records:
        raise ValueError("at least one resolved forecast is required")
    if bins < 2:
        raise ValueError("at least two calibration bins are required")
    probabilities = np.asarray([record.probability for record in records], dtype=float)
    outcomes = np.asarray([record.outcome for record in records], dtype=float)
    weights = np.asarray([record.weight for record in records], dtype=float)
    base_rate = float(np.average(outcomes, weights=weights))
    brier = float(np.average(np.square(probabilities - outcomes), weights=weights))
    reference_brier = float(np.average(np.square(base_rate - outcomes), weights=weights))
    skill = 1 - brier / reference_brier if reference_brier > 0 else 0.0
    clipped = np.clip(probabilities, 1e-8, 1 - 1e-8)
    log_loss = float(
        np.average(
            -(outcomes * np.log(clipped) + (1 - outcomes) * np.log(1 - clipped)),
            weights=weights,
        )
    )
    edges = np.linspace(0, 1, bins + 1)
    calibration_bins: list[CalibrationBin] = []
    calibration_error = 0.0
    total_weight = float(weights.sum())
    for index in range(bins):
        selected = (probabilities >= edges[index]) & (
            probabilities <= edges[index + 1]
            if index == bins - 1
            else probabilities < edges[index + 1]
        )
        if not selected.any():
            continue
        bin_weight = float(weights[selected].sum())
        mean_probability = float(np.average(probabilities[selected], weights=weights[selected]))
        observed_rate = float(np.average(outcomes[selected], weights=weights[selected]))
        calibration_error += bin_weight / total_weight * abs(mean_probability - observed_rate)
        calibration_bins.append(
            CalibrationBin(
                lower=float(edges[index]),
                upper=float(edges[index + 1]),
                count=int(selected.sum()),
                mean_probability=mean_probability,
                observed_rate=observed_rate,
            )
        )
    return EventBacktestReport(
        count=len(records),
        weighted_base_rate=base_rate,
        brier_score=brier,
        brier_skill_score=skill,
        log_loss=log_loss,
        expected_calibration_error=calibration_error,
        calibration_bins=calibration_bins,
    )
