from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BaselineOrigin(StrEnum):
    HISTORICAL = "historical"
    EXPERT_PRIOR = "expert_prior"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


class ComparisonOperator(StrEnum):
    LESS_THAN = "lt"
    LESS_OR_EQUAL = "le"
    GREATER_THAN = "gt"
    GREATER_OR_EQUAL = "ge"


class ObservedSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    name: str
    observed_at: datetime
    available_at: datetime
    standardized_value: float = Field(ge=-8, le=8)
    reliability: float = Field(default=0.7, ge=0, le=1)
    tags: list[str] = Field(min_length=1)
    actors: list[str] = Field(default_factory=list)
    geographic_scope: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    data_origin: Literal["observed", "derived", "assumption"] = "observed"

    @field_validator("observed_at", "available_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("signal timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_availability(self) -> ObservedSignal:
        if self.available_at < self.observed_at:
            raise ValueError("signal available_at must not precede observed_at")
        return self


class SignalEvidenceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_tag: str
    log_odds_per_standard_deviation: float = Field(ge=-5, le=5)
    half_life_days: float = Field(default=14, gt=0, le=3650)
    minimum_lag_days: int = Field(default=0, ge=0, le=365)


class StateConditionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    operator: ComparisonOperator
    threshold: float
    log_odds_shift: float = Field(ge=-8, le=8)


class ParentEventRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_candidate_id: str
    log_odds_shift: float = Field(ge=-8, le=8)
    minimum_lag_days: int = Field(default=1, ge=0, le=365)
    maximum_lag_days: int = Field(default=60, ge=0, le=365)
    half_life_days: float = Field(default=14, gt=0, le=3650)

    @model_validator(mode="after")
    def validate_lag(self) -> ParentEventRule:
        if self.maximum_lag_days < self.minimum_lag_days:
            raise ValueError("maximum parent lag must not be below minimum lag")
        return self


class MetricImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    mean_delta: float
    standard_deviation: float = Field(default=0.0, ge=0)
    half_life_days: float = Field(default=30, gt=0, le=3650)
    lower_bound: float | None = None
    upper_bound: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> MetricImpact:
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.upper_bound < self.lower_bound
        ):
            raise ValueError("impact upper bound must not be below lower bound")
        return self


class EventHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    event_type: str
    label: str
    description: str = ""
    actors: list[str] = Field(default_factory=list)
    geographic_scope: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    baseline_daily_hazard: float = Field(gt=0, lt=1)
    baseline_origin: BaselineOrigin = BaselineOrigin.UNKNOWN
    baseline_sample_size: int = Field(default=0, ge=0)
    earliest_day: int = Field(default=1, ge=1, le=365)
    latest_day: int | None = Field(default=None, ge=1, le=365)
    signal_rules: list[SignalEvidenceRule] = Field(default_factory=list)
    state_rules: list[StateConditionRule] = Field(default_factory=list)
    parent_rules: list[ParentEventRule] = Field(default_factory=list)
    impacts: list[MetricImpact] = Field(default_factory=list)
    severity_mean: float = Field(default=0.5, ge=0, le=1)
    severity_standard_deviation: float = Field(default=0.12, ge=0, le=1)

    @model_validator(mode="after")
    def validate_window_and_impacts(self) -> EventHypothesis:
        if self.latest_day is not None and self.latest_day < self.earliest_day:
            raise ValueError("latest event day must not be below earliest day")
        impact_metrics = [impact.metric for impact in self.impacts]
        if len(impact_metrics) != len(set(impact_metrics)):
            raise ValueError("an event may define at most one impact per metric")
        return self


class ForecastIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    start_day: int = Field(default=1, ge=1, le=365)
    duration_days: int = Field(default=30, ge=1, le=365)
    target_candidate_ids: list[str] = Field(default_factory=list)
    target_event_types: list[str] = Field(default_factory=list)
    target_tags: list[str] = Field(default_factory=list)
    hazard_log_odds_shift: float = Field(default=0, ge=-8, le=8)
    metric_shifts: dict[str, float] = Field(default_factory=dict)
    estimated_cost: float = Field(default=0, ge=0)


class EventForecastBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str
    name: str
    interventions: list[ForecastIntervention] = Field(default_factory=list)


class EventForecastQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    domain: str
    as_of: datetime
    horizon_days: int = Field(default=30, ge=1, le=365)
    initial_metrics: dict[str, float] = Field(default_factory=dict)
    signals: list[ObservedSignal] = Field(default_factory=list)
    candidates: list[EventHypothesis] = Field(min_length=1, max_length=200)
    branches: list[EventForecastBranch] = Field(min_length=1, max_length=20)
    samples: int = Field(default=1_024, ge=32, le=100_000)
    random_seed: int = 2026

    @field_validator("as_of")
    @classmethod
    def require_aware_cutoff(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_references_and_cutoff(self) -> EventForecastQuery:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate ids must be unique")
        branch_ids = [branch.branch_id for branch in self.branches]
        if len(branch_ids) != len(set(branch_ids)):
            raise ValueError("branch ids must be unique")
        known = set(candidate_ids)
        for candidate in self.candidates:
            parents = {rule.parent_candidate_id for rule in candidate.parent_rules}
            if candidate.candidate_id in parents:
                raise ValueError("an event cannot be its own parent")
            if unknown := parents - known:
                raise ValueError(f"unknown parent candidates: {sorted(unknown)}")
        for signal in self.signals:
            if signal.available_at > self.as_of:
                raise ValueError(
                    f"signal {signal.signal_id} was unavailable at the prediction cutoff"
                )
        for branch in self.branches:
            for intervention in branch.interventions:
                unknown = set(intervention.target_candidate_ids) - known
                if unknown:
                    raise ValueError(f"unknown intervention candidates: {sorted(unknown)}")
        return self


class DistributionBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    mean: float
    standard_deviation: float = Field(ge=0)


class DailyEventProbability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1)
    first_occurrence_probability: float = Field(ge=0, le=1)
    cumulative_probability: float = Field(ge=0, le=1)


class CandidateEventForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    event_type: str
    label: str
    occurrence_probability: float = Field(ge=0, le=1)
    probability_curve: list[DailyEventProbability]
    conditional_time_to_event_days: DistributionBand | None
    severity_if_occurred: DistributionBand | None
    leading_evidence: list[dict[str, float | str]]
    baseline_origin: BaselineOrigin
    out_of_distribution: bool


class EventChainForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_sequence: list[str]
    probability: float = Field(ge=0, le=1)


class BranchEventForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str
    candidates: list[CandidateEventForecast]
    final_metric_deltas: dict[str, DistributionBand]
    top_event_chains: list[EventChainForecast]
    expected_intervention_cost: float = Field(ge=0)


class EventForecastResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    model_version: str
    query: EventForecastQuery
    branches: dict[str, BranchEventForecast]
    counterfactual_probability_deltas: dict[str, dict[str, float]]
    calibration_status: str
    artifact_dir: str
    assumptions: list[str]
    warnings: list[str]
    disclaimer: str
