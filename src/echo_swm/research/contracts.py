from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentTier(StrEnum):
    KEY = "key"
    REPRESENTATIVE = "representative"
    BACKGROUND = "background"


class QuestionKind(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    SCALE = "scale"
    RANKING = "ranking"
    NUMERIC = "numeric"
    OPEN_TEXT = "open_text"


class MetricDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"


DECISION_METRICS = {
    "awareness",
    "support",
    "opposition",
    "sharing",
    "discussion",
    "silence",
    "participation",
    "exit",
    "polarization",
    "trust",
}


class EvaluationMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str = Field(min_length=1, max_length=80)
    direction: MetricDirection = MetricDirection.INCREASE
    weight: float = Field(default=1, gt=0, le=10)

    @field_validator("metric_id")
    @classmethod
    def supported_metric(cls, value: str) -> str:
        if value not in DECISION_METRICS:
            raise ValueError(f"unsupported decision metric: {value}")
        return value


class EvaluationProtocol(BaseModel):
    """Decision criteria locked before a constrained-L2 simulation starts."""

    model_config = ConfigDict(extra="forbid")

    baseline_scenario_id: Literal["baseline_no_event"] = "baseline_no_event"
    primary_metric: EvaluationMetric = Field(
        default_factory=lambda: EvaluationMetric(
            metric_id="support",
            label="支持",
            direction=MetricDirection.INCREASE,
            weight=1,
        )
    )
    auxiliary_metrics: list[EvaluationMetric] = Field(
        default_factory=lambda: [
            EvaluationMetric(
                metric_id="awareness",
                label="知晓",
                direction=MetricDirection.INCREASE,
                weight=0.5,
            ),
            EvaluationMetric(
                metric_id="polarization",
                label="分化",
                direction=MetricDirection.DECREASE,
                weight=0.5,
            ),
        ],
        max_length=4,
    )
    minimum_effect: float = Field(default=0.02, gt=0, le=0.5)
    forecast_as_of: datetime | None = None
    future_information_policy: Literal["exclude"] = "exclude"

    @field_validator("forecast_as_of")
    @classmethod
    def require_aware_forecast_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("forecast_as_of must include a timezone")
        return value

    @model_validator(mode="after")
    def unique_metrics(self) -> EvaluationProtocol:
        auxiliary_ids = [item.metric_id for item in self.auxiliary_metrics]
        if len(auxiliary_ids) != len(set(auxiliary_ids)):
            raise ValueError("auxiliary evaluation metrics must be unique")
        if self.primary_metric.metric_id in auxiliary_ids:
            if "auxiliary_metrics" not in self.model_fields_set:
                self.auxiliary_metrics = [
                    item
                    for item in self.auxiliary_metrics
                    if item.metric_id != self.primary_metric.metric_id
                ]
                return self
            raise ValueError("primary metric cannot also be an auxiliary metric")
        return self


class QuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str
    label: str = Field(min_length=1, max_length=200)
    position: float | None = Field(default=None, ge=-1, le=1)


class ResearchQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    question_id: str
    text: str = Field(min_length=2, max_length=1_000)
    kind: QuestionKind
    options: list[QuestionOption] = Field(default_factory=list, max_length=20)
    latent_construct: str = Field(
        default="support",
        alias="construct",
        min_length=1,
        max_length=80,
    )
    direction: int = Field(default=1, ge=-1, le=1)
    scale_min: float | None = None
    scale_max: float | None = None
    required: bool = True

    @model_validator(mode="after")
    def validate_response_space(self) -> ResearchQuestion:
        option_kinds = {
            QuestionKind.SINGLE_CHOICE,
            QuestionKind.MULTIPLE_CHOICE,
            QuestionKind.RANKING,
        }
        if self.kind in option_kinds and len(self.options) < 2:
            raise ValueError(f"{self.kind} questions require at least two options")
        if self.kind == QuestionKind.SCALE:
            low = 1 if self.scale_min is None else self.scale_min
            high = 5 if self.scale_max is None else self.scale_max
            if high <= low or high - low > 10:
                raise ValueError("scale questions require an increasing range of at most 10")
        if self.kind == QuestionKind.NUMERIC:
            if self.scale_min is None or self.scale_max is None:
                raise ValueError("numeric questions require scale_min and scale_max")
            if self.scale_max <= self.scale_min:
                raise ValueError("numeric questions require an increasing range")
        option_ids = [item.option_id for item in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("question option ids must be unique")
        return self


class Questionnaire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questionnaire_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    questions: list[ResearchQuestion] = Field(min_length=1, max_length=30)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def unique_question_ids(self) -> Questionnaire:
        ids = [item.question_id for item in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question ids must be unique")
        return self


class PopulationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    population_id: str = "general_population_5000"
    name: str = "通用研究人群"
    size: int = Field(default=5_000, ge=5_000, le=20_000)
    seed: int = 2026
    filters: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("filters")
    @classmethod
    def non_empty_filters(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if any(not choices for choices in value.values()):
            raise ValueError("population filters cannot contain an empty choice list")
        return value


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    summary: str = Field(min_length=1, max_length=2_000)
    source: str = "user_supplied"
    credibility: float = Field(default=0.7, ge=0, le=1)
    available_at: datetime | None = None

    @field_validator("available_at")
    @classmethod
    def require_aware_availability(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("available_at must include a timezone")
        return value


class ScenarioVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: str
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2_000)
    intensity_multiplier: float = Field(default=1, ge=0, le=2)
    credibility_shift: float = Field(default=0, ge=-1, le=1)
    value_signal_adjustments: dict[str, float] = Field(default_factory=dict)

    @field_validator("value_signal_adjustments")
    @classmethod
    def bounded_adjustments(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < -1 or item > 1 for item in value.values()):
            raise ValueError("value-signal adjustments must be within [-1, 1]")
        return value


class EventScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=3, max_length=10_000)
    actors: list[str] = Field(default_factory=list, max_length=30)
    audience: str = Field(default="目标人群", max_length=500)
    channels: list[str] = Field(default_factory=lambda: ["online", "interpersonal"])
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=50)
    intensity: float = Field(default=0.65, ge=0, le=1)
    credibility: float = Field(default=0.7, ge=0, le=1)
    valence: float = Field(default=0, ge=-1, le=1)
    value_signals: dict[str, float] = Field(default_factory=dict)
    expected_outcomes: list[str] = Field(default_factory=list, max_length=20)
    alternatives: list[ScenarioVariant] = Field(default_factory=list, max_length=5)

    @field_validator("value_signals")
    @classmethod
    def bounded_signals(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < -1 or item > 1 for item in value.values()):
            raise ValueError("value signals must be within [-1, 1]")
        return value


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str = Field(min_length=1, max_length=200)
    population_id: str | None = None
    population: PopulationSpec | None = None
    population_margin_id: str | None = None
    questionnaire_id: str | None = None
    questionnaire: Questionnaire | None = None
    calibration_id: str | None = None
    event: EventScenario
    horizon_ticks: int = Field(default=30, ge=30, le=180)
    paths: int = Field(default=8, ge=3, le=64)
    seed: int = 2026
    evaluation_protocol: EvaluationProtocol = Field(default_factory=EvaluationProtocol)
    group_fields: list[str] = Field(
        default_factory=lambda: [
            "age_group",
            "gender",
            "social_role",
            "organization_type",
            "education_level",
            "primary_channel",
        ],
        min_length=3,
        max_length=6,
    )

    @model_validator(mode="after")
    def require_population_and_questionnaire(self) -> PredictionRequest:
        if (self.population_id is None) == (self.population is None):
            raise ValueError("provide exactly one of population_id or population")
        if (self.questionnaire_id is None) == (self.questionnaire is None):
            raise ValueError("provide exactly one of questionnaire_id or questionnaire")
        return self


class ProbabilityBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float


class OptionEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str
    label: str
    probability: ProbabilityBand
    predicted_rank: int | None = None


class OpenTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str
    share: ProbabilityBand
    representative_answer: str


class QuestionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: str
    options: list[OptionEstimate] = Field(default_factory=list)
    numeric_value: ProbabilityBand | None = None
    themes: list[OpenTheme] = Field(default_factory=list)


class GroupDifference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_field: str
    group_label: str = ""
    group_value: str
    group_value_label: str = ""
    agent_count: int
    represented_population: float = Field(default=0, ge=0)
    leading_answer: str
    probability: float
    delta_vs_overall: float


class CrossTabRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_value: str
    group_value_label: str
    agent_count: int = Field(ge=0)
    represented_population: float = Field(ge=0)
    weighted_share: float = Field(ge=0, le=1)
    response_distribution: dict[str, float]
    leading_answer: str

    @field_validator("response_distribution")
    @classmethod
    def bounded_response_distribution(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(item) for item in value.values()):
            raise ValueError("cross-tab response values must be finite")
        return value


class QuestionCrossTab(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_field: str
    group_label: str
    response_type: Literal["distribution", "numeric_mean"]
    rows: list[CrossTabRow]


class RepresentativeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str
    persona_label: str
    role: str
    organization_type: str
    segment: str
    predicted_answer: str
    answer: str
    confidence: float = Field(ge=0, le=1)
    represented_weight: float = Field(gt=0)
    basis: list[str]
    synthetic: Literal[True] = True


class QuestionForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question_text: str
    kind: QuestionKind
    baseline: QuestionSnapshot
    post_event: QuestionSnapshot
    change_summary: str
    group_differences: list[GroupDifference]
    cross_tabs: list[QuestionCrossTab] = Field(default_factory=list)
    representative_responses: list[RepresentativeResponse] = Field(default_factory=list)
    key_drivers: list[str]
    missingness: float = Field(ge=0, le=1)
    out_of_distribution: bool


class TimelinePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int
    metrics: dict[str, ProbabilityBand]


class DownstreamOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_id: str
    label: str
    probability: ProbabilityBand
    likely_tick: ProbabilityBand | None = None


class ScenarioForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    label: str
    timeline: list[TimelinePoint]
    final_actions: dict[str, ProbabilityBand]
    downstream_outcomes: list[DownstreamOutcome]


class ProtocolLock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_as_of: datetime
    horizon_ticks: int
    scenario_ids: list[str]
    metric_ids: list[str]
    baseline_scenario_id: str
    future_information_forbidden: bool = True
    excluded_evidence_ids: list[str] = Field(default_factory=list)
    untimestamped_evidence_ids: list[str] = Field(default_factory=list)
    input_signature: str


class CounterfactualEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_label: str
    metric_id: str
    metric_label: str
    direction: MetricDirection
    weight: float
    baseline_value: ProbabilityBand
    scenario_value: ProbabilityBand
    paired_delta: ProbabilityBand
    direction_consistency: float = Field(ge=0, le=1)
    cod_score: float = Field(ge=0, le=1)
    effect_detected: bool


class ScenarioRanking(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    label: str
    rank: int = Field(ge=1)
    decision_score: float = Field(ge=0, le=1)
    primary_metric_value: ProbabilityBand
    primary_metric_delta: ProbabilityBand


class ConstrainedL2Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_level: Literal["constrained_l2"] = "constrained_l2"
    baseline_scenario_id: str
    common_random_numbers: bool = True
    protocol_lock: ProtocolLock
    scenario_ranking: list[ScenarioRanking]
    effects: list[CounterfactualEffect]
    cod_score: float = Field(ge=0, le=1)
    cod_interpretation: str
    warnings: list[str] = Field(default_factory=list)


class ParticipantReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    tier: AgentTier
    segment: str
    final_action: str
    response_summary: str
    top_drivers: list[str]
    evidence_refs: list[str]
    profile_origin: str


class PopulationRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    population_id: str
    agent_count: int
    tier_counts: dict[str, int]
    relationship_count: int
    agents_observed: int
    agents_decided: int
    agents_acted: int
    agents_remembered: int
    stable_profiles: bool
    represented_population: float | None = None
    effective_sample_size: float | None = None


class GroundingRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "synthetic_unanchored"
    population_margin_id: str | None = None
    source: str | None = None
    covered_fields: list[str] = Field(default_factory=list)
    converged: bool | None = None
    design_effect: float | None = None
    warnings: list[str] = Field(default_factory=list)


class CalibrationRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "uncalibrated_prior"
    calibration_id: str | None = None
    dataset_id: str | None = None
    training_records: int = 0
    holdout_records: int = 0
    holdout_brier_before: float | None = None
    holdout_brier_after: float | None = None
    applied: bool = False
    warnings: list[str] = Field(default_factory=list)


class PredictionArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_json: str
    questionnaire_csv: str
    individual_predictions: str
    replay_log: str
    run_manifest: str


class ReportRunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str
    data_version: str
    seed: int
    paths: int = Field(ge=1)
    horizon_ticks: int = Field(ge=1)
    scenario_count: int = Field(ge=1)
    requested_agents: int = Field(ge=1)
    successful_agents: int = Field(ge=0)
    failed_agents: int = Field(ge=0)
    represented_population: float = Field(gt=0)
    effective_sample_size: float = Field(gt=0)
    population_source: str
    weighting_method: str
    interval_definition: str
    calibration_status: str
    profile_signature: str


class ReportQualityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    label: str
    status: Literal["pass", "warning", "fail"]
    observed: str
    expected: str
    detail: str


class ReportQualitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "warning", "fail"]
    passed: int = Field(ge=0)
    warnings: int = Field(ge=0)
    failures: int = Field(ge=0)
    checks: list[ReportQualityCheck]


class PredictionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    title: str
    status: str = "completed"
    created_at: datetime
    conclusion: str
    population: PopulationRunSummary
    grounding: GroundingRunSummary = Field(default_factory=GroundingRunSummary)
    calibration: CalibrationRunSummary = Field(default_factory=CalibrationRunSummary)
    report_metadata: ReportRunMetadata | None = None
    report_quality: ReportQualitySummary | None = None
    questionnaire_forecast: list[QuestionForecast]
    group_insights: list[str]
    scenarios: list[ScenarioForecast]
    l2_evaluation: ConstrainedL2Evaluation | None = None
    key_drivers: list[str]
    uncertainty: list[str]
    limitations: list[str]
    participant_receipts: list[ParticipantReceipt]
    semantic_interpretation: dict[str, Any]
    artifacts: PredictionArtifacts
    deterministic_signature: str
    disclaimer: str


class OutcomeSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sample_size: int = Field(default=0, ge=0)
    questionnaire_results: dict[str, dict[str, float] | float | str] = Field(default_factory=dict)
    event_outcomes: dict[str, bool | float | str] = Field(default_factory=dict)
    scenario_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=5_000)

    @field_validator("observed_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @field_validator("scenario_metrics")
    @classmethod
    def bounded_scenario_metrics(
        cls, value: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        for scenario_id, metrics in value.items():
            if not scenario_id or not metrics:
                raise ValueError("scenario_metrics requires named scenarios and metrics")
            for metric_id, observed in metrics.items():
                if metric_id not in DECISION_METRICS:
                    raise ValueError(f"unsupported scenario metric: {metric_id}")
                if not 0 <= observed <= 1:
                    raise ValueError("scenario metric observations must be within [0, 1]")
        return value
