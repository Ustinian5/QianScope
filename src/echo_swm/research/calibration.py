from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from echo_swm.core.config import Settings
from echo_swm.core.ids import stable_hash


class CalibrationStatus(StrEnum):
    VALIDATED = "validated"
    CANDIDATE_NOT_IMPROVED = "candidate_not_improved"


class CalibrationTargetType(StrEnum):
    QUESTION_OPTION = "question_option"
    EVENT_OUTCOME = "event_outcome"


class CalibrationObservation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    observation_id: str
    target_type: CalibrationTargetType = CalibrationTargetType.QUESTION_OPTION
    question_id: str | None = None
    option_id: str | None = None
    outcome_id: str | None = None
    construct_name: str = Field(default="unknown", alias="construct")
    forecast_as_of: datetime
    outcome_available_at: datetime
    predicted_probability: float = Field(ge=0, le=1)
    observed_share: float = Field(ge=0, le=1)
    sample_size: int = Field(ge=1)
    horizon_ticks: int = Field(default=30, ge=1)
    group_field: str | None = None
    group_value: str | None = None
    source: str = Field(min_length=1, max_length=500)
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("forecast_as_of", "outcome_available_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("calibration timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def prevent_future_leakage(self) -> CalibrationObservation:
        if self.outcome_available_at < self.forecast_as_of:
            raise ValueError("outcome_available_at must not precede forecast_as_of")
        if self.target_type == CalibrationTargetType.QUESTION_OPTION:
            if not self.question_id or not self.option_id:
                raise ValueError("question-option observations require question_id and option_id")
            if self.outcome_id is not None:
                raise ValueError("question-option observations cannot include outcome_id")
        else:
            if not self.outcome_id:
                raise ValueError("event-outcome observations require outcome_id")
            if self.question_id is not None or self.option_id is not None:
                raise ValueError(
                    "event-outcome observations cannot include question_id or option_id"
                )
        return self


class CalibrationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    authorization_confirmed: bool
    deidentified_or_aggregate: bool
    observations: list[CalibrationObservation] = Field(min_length=10, max_length=200_000)
    notes: str = Field(default="", max_length=5_000)

    @model_validator(mode="after")
    def validate_use(self) -> CalibrationDataset:
        if not self.authorization_confirmed:
            raise ValueError("authorization_confirmed must be true")
        if not self.deidentified_or_aggregate:
            raise ValueError("only deidentified or aggregate calibration data are accepted")
        ids = [item.observation_id for item in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("calibration observation ids must be unique")
        return self


class CalibrationParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(gt=0)
    bias: float
    training_records: int
    training_weight: float


class CalibrationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brier_score: float
    log_loss: float
    mean_calibration_error: float


class CalibrationProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_id: str
    dataset_id: str
    created_at: datetime
    status: CalibrationStatus
    temporal_cutoff: datetime
    training_records: int
    holdout_records: int
    minimum_records_per_key: int
    overall: CalibrationParameters
    target_types: dict[str, CalibrationParameters]
    constructs: dict[str, CalibrationParameters]
    question_options: dict[str, CalibrationParameters]
    event_outcomes: dict[str, CalibrationParameters]
    before: CalibrationMetrics
    after: CalibrationMetrics
    improvement: dict[str, float]
    covered_question_options: list[str]
    profile_signature: str
    warnings: list[str]


class CalibrationFitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    holdout_fraction: float = Field(default=0.2, ge=0.1, le=0.5)
    minimum_records_per_key: int = Field(default=8, ge=5, le=1_000)


def calibration_dataset_root(settings: Settings) -> Path:
    return settings.artifact_dir / "research" / "calibration" / "datasets"


def calibration_profile_root(settings: Settings) -> Path:
    return settings.artifact_dir / "research" / "calibration" / "profiles"


def save_calibration_dataset(dataset: CalibrationDataset, settings: Settings) -> Path:
    root = calibration_dataset_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{dataset.dataset_id}.json"
    if path.exists():
        existing = CalibrationDataset.model_validate_json(path.read_text(encoding="utf-8"))
        if existing != dataset:
            raise ValueError(
                "calibration dataset id already exists with different content: "
                f"{dataset.dataset_id}"
            )
        return path
    path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_calibration_dataset(dataset_id: str, settings: Settings) -> CalibrationDataset:
    path = calibration_dataset_root(settings) / f"{dataset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"calibration dataset not found: {dataset_id}")
    return CalibrationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def save_calibration_profile(profile: CalibrationProfile, settings: Settings) -> Path:
    root = calibration_profile_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{profile.calibration_id}.json"
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_calibration_profile(calibration_id: str, settings: Settings) -> CalibrationProfile:
    path = calibration_profile_root(settings) / f"{calibration_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"calibration profile not found: {calibration_id}")
    return CalibrationProfile.model_validate_json(path.read_text(encoding="utf-8"))


def _logit(probabilities: NDArray[np.float64]) -> NDArray[np.float64]:
    clipped = np.clip(probabilities, 1e-7, 1 - 1e-7)
    return np.log(clipped / (1 - clipped))


def _apply_parameters(
    probabilities: NDArray[np.float64], parameters: CalibrationParameters
) -> NDArray[np.float64]:
    return 1 / (1 + np.exp(-(_logit(probabilities) / parameters.temperature + parameters.bias)))


def _fit_parameters(observations: list[CalibrationObservation]) -> CalibrationParameters:
    probabilities = np.asarray([item.predicted_probability for item in observations], dtype=float)
    outcomes = np.asarray([item.observed_share for item in observations], dtype=float)
    weights = np.asarray([item.sample_size for item in observations], dtype=float)
    logits = _logit(probabilities)
    temperatures = np.geomspace(0.4, 3.5, 50)
    biases = np.linspace(-2.0, 2.0, 81)
    best_loss = float("inf")
    best_temperature = 1.0
    best_bias = 0.0
    for temperature in temperatures:
        calibrated = 1 / (1 + np.exp(-(logits[None, :] / float(temperature) + biases[:, None])))
        clipped = np.clip(calibrated, 1e-9, 1 - 1e-9)
        losses = -np.average(
            outcomes[None, :] * np.log(clipped) + (1 - outcomes[None, :]) * np.log(1 - clipped),
            weights=weights,
            axis=1,
        )
        bias_index = int(np.argmin(losses))
        loss = float(losses[bias_index])
        if loss < best_loss:
            best_loss = loss
            best_temperature = float(temperature)
            best_bias = float(biases[bias_index])
    return CalibrationParameters(
        temperature=best_temperature,
        bias=best_bias,
        training_records=len(observations),
        training_weight=float(weights.sum()),
    )


def _metrics(
    observations: list[CalibrationObservation],
    probabilities: NDArray[np.float64],
) -> CalibrationMetrics:
    outcomes = np.asarray([item.observed_share for item in observations], dtype=float)
    weights = np.asarray([item.sample_size for item in observations], dtype=float)
    clipped = np.clip(probabilities, 1e-9, 1 - 1e-9)
    return CalibrationMetrics(
        brier_score=float(np.average((probabilities - outcomes) ** 2, weights=weights)),
        log_loss=float(
            -np.average(
                outcomes * np.log(clipped) + (1 - outcomes) * np.log(1 - clipped),
                weights=weights,
            )
        ),
        mean_calibration_error=float(
            abs(np.average(probabilities, weights=weights) - np.average(outcomes, weights=weights))
        ),
    )


def _observation_key(observation: CalibrationObservation) -> str:
    if observation.target_type == CalibrationTargetType.EVENT_OUTCOME:
        return f"event::{observation.outcome_id}"
    return f"question::{observation.question_id}::{observation.option_id}"


def _target_type_key(observation: CalibrationObservation) -> str:
    return observation.target_type.value


def _construct_key(observation: CalibrationObservation) -> str | None:
    if observation.target_type != CalibrationTargetType.QUESTION_OPTION:
        return None
    if observation.construct_name in {"", "unknown"}:
        return None
    return observation.construct_name


def fit_calibration_profile(
    dataset: CalibrationDataset,
    *,
    holdout_fraction: float = 0.2,
    minimum_records_per_key: int = 8,
) -> CalibrationProfile:
    if not 0.1 <= holdout_fraction <= 0.5:
        raise ValueError("holdout_fraction must be within [0.1, 0.5]")
    ordered = sorted(dataset.observations, key=lambda item: item.forecast_as_of)
    split_index = max(5, min(len(ordered) - 2, int(len(ordered) * (1 - holdout_fraction))))
    temporal_cutoff = ordered[split_index].forecast_as_of
    training = [
        item for item in ordered[:split_index] if item.outcome_available_at <= temporal_cutoff
    ]
    holdout = ordered[split_index:]
    if len(training) < 5 or len(holdout) < 2:
        raise ValueError("not enough leakage-safe training and temporal holdout observations")
    overall = _fit_parameters(training)
    grouped: dict[str, list[CalibrationObservation]] = {}
    grouped_target_types: dict[str, list[CalibrationObservation]] = {}
    grouped_constructs: dict[str, list[CalibrationObservation]] = {}
    for observation in training:
        grouped.setdefault(_observation_key(observation), []).append(observation)
        grouped_target_types.setdefault(_target_type_key(observation), []).append(observation)
        construct_key = _construct_key(observation)
        if construct_key is not None:
            grouped_constructs.setdefault(construct_key, []).append(observation)
    per_key = {
        key: _fit_parameters(observations)
        for key, observations in grouped.items()
        if len(observations) >= minimum_records_per_key
    }
    per_target_type = {
        key: _fit_parameters(observations)
        for key, observations in grouped_target_types.items()
        if len(observations) >= minimum_records_per_key
    }
    per_construct = {
        key: _fit_parameters(observations)
        for key, observations in grouped_constructs.items()
        if len(observations) >= minimum_records_per_key
    }

    def parameters_for(observation: CalibrationObservation) -> CalibrationParameters:
        exact = per_key.get(_observation_key(observation))
        if exact is not None:
            return exact
        construct_key = _construct_key(observation)
        if construct_key is not None and construct_key in per_construct:
            return per_construct[construct_key]
        return per_target_type.get(_target_type_key(observation), overall)

    raw_probabilities = np.asarray([item.predicted_probability for item in holdout], dtype=float)
    calibrated_probabilities = np.asarray(
        [
            _apply_parameters(
                np.asarray([item.predicted_probability], dtype=float),
                parameters_for(item),
            )[0]
            for item in holdout
        ],
        dtype=float,
    )
    before = _metrics(holdout, raw_probabilities)
    after = _metrics(holdout, calibrated_probabilities)
    status = (
        CalibrationStatus.VALIDATED
        if after.brier_score <= before.brier_score and after.log_loss <= before.log_loss + 1e-6
        else CalibrationStatus.CANDIDATE_NOT_IMPROVED
    )
    warnings = []
    if not per_key:
        warnings.append("单题选项或事件结果记录不足，当前使用类型或构念级校准参数")
    if status != CalibrationStatus.VALIDATED:
        warnings.append("时间留出集未改善，不会自动应用此校准版本")
    profile_payload = {
        "dataset_id": dataset.dataset_id,
        "temporal_cutoff": temporal_cutoff.isoformat(),
        "overall": overall.model_dump(),
        "target_types": {key: value.model_dump() for key, value in sorted(per_target_type.items())},
        "constructs": {key: value.model_dump() for key, value in sorted(per_construct.items())},
        "question_options": {key: value.model_dump() for key, value in sorted(per_key.items())},
        "minimum_records_per_key": minimum_records_per_key,
    }
    profile_signature = stable_hash(profile_payload)
    return CalibrationProfile(
        calibration_id=f"calibration_{profile_signature[:16]}",
        dataset_id=dataset.dataset_id,
        created_at=datetime.now(UTC),
        status=status,
        temporal_cutoff=temporal_cutoff,
        training_records=len(training),
        holdout_records=len(holdout),
        minimum_records_per_key=minimum_records_per_key,
        overall=overall,
        target_types=per_target_type,
        constructs=per_construct,
        question_options={
            key.removeprefix("question::"): value
            for key, value in per_key.items()
            if key.startswith("question::")
        },
        event_outcomes={
            key.removeprefix("event::"): value
            for key, value in per_key.items()
            if key.startswith("event::")
        },
        before=before,
        after=after,
        improvement={
            "brier_score": before.brier_score - after.brier_score,
            "log_loss": before.log_loss - after.log_loss,
            "mean_calibration_error": (
                before.mean_calibration_error - after.mean_calibration_error
            ),
        },
        covered_question_options=sorted(
            key.removeprefix("question::") for key in per_key if key.startswith("question::")
        ),
        profile_signature=profile_signature,
        warnings=warnings,
    )


def fit_and_save_calibration(
    request: CalibrationFitRequest, settings: Settings
) -> CalibrationProfile:
    dataset = load_calibration_dataset(request.dataset_id, settings)
    profile = fit_calibration_profile(
        dataset,
        holdout_fraction=request.holdout_fraction,
        minimum_records_per_key=request.minimum_records_per_key,
    )
    existing_path = calibration_profile_root(settings) / f"{profile.calibration_id}.json"
    if existing_path.exists():
        return load_calibration_profile(profile.calibration_id, settings)
    save_calibration_profile(profile, settings)
    return profile


def calibrate_probability_matrix(
    probabilities: NDArray[np.float64],
    *,
    question_id: str,
    construct_name: str,
    option_ids: list[str],
    profile: CalibrationProfile | None,
    normalize: bool,
) -> NDArray[np.float64]:
    if profile is None or profile.status != CalibrationStatus.VALIDATED:
        return probabilities
    calibrated = probabilities.copy()
    for option_index, option_id in enumerate(option_ids):
        parameters = profile.question_options.get(f"{question_id}::{option_id}")
        if parameters is None:
            parameters = profile.constructs.get(construct_name)
        if parameters is None:
            parameters = profile.target_types.get(
                CalibrationTargetType.QUESTION_OPTION.value,
                profile.overall,
            )
        calibrated[:, option_index] = _apply_parameters(calibrated[:, option_index], parameters)
    if normalize:
        row_sums = calibrated.sum(axis=1, keepdims=True)
        calibrated = np.divide(
            calibrated,
            row_sums,
            out=np.full_like(calibrated, 1 / calibrated.shape[1]),
            where=row_sums > 0,
        )
    return calibrated


def calibrate_event_probabilities(
    probabilities: NDArray[np.float64],
    *,
    outcome_id: str,
    profile: CalibrationProfile | None,
) -> NDArray[np.float64]:
    if profile is None or profile.status != CalibrationStatus.VALIDATED:
        return probabilities
    parameters = profile.event_outcomes.get(outcome_id)
    if parameters is None:
        parameters = profile.target_types.get(
            CalibrationTargetType.EVENT_OUTCOME.value,
            profile.overall,
        )
    return _apply_parameters(probabilities, parameters)


def backfill_observation_path(settings: Settings) -> Path:
    return settings.artifact_dir / "research" / "calibration" / "backfill_observations.jsonl"


def append_backfill_observations(
    observations: list[CalibrationObservation], settings: Settings
) -> Path:
    path = backfill_observation_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for observation in observations:
            handle.write(observation.model_dump_json() + "\n")
    return path
