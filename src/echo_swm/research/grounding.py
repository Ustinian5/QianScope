from __future__ import annotations

from collections.abc import Hashable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from echo_swm.core.config import Settings
from echo_swm.core.ids import stable_hash
from echo_swm.population.ipf import iterative_proportional_fitting
from echo_swm.population.weighting import effective_sample_size
from echo_swm.research.population import ResearchPopulation, save_population

SUPPORTED_MARGIN_FIELDS = {
    "age_group",
    "education_level",
    "gender",
    "primary_channel",
    "region_type",
    "social_role",
}


class MarginScale(StrEnum):
    PROPORTION = "proportion"
    COUNT = "count"


class PopulationMarginDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_000)
    scope: str = Field(default="target_population", max_length=500)
    observed_at: datetime
    available_at: datetime
    authorization_confirmed: bool
    deidentified_or_aggregate: bool
    scale: MarginScale = MarginScale.PROPORTION
    target_population: float | None = Field(default=None, gt=0)
    margins: dict[str, dict[str, float]] = Field(min_length=1)
    notes: str = Field(default="", max_length=5_000)

    @field_validator("observed_at", "available_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("population margin timestamps must include a timezone")
        return value

    @field_validator("margins")
    @classmethod
    def validate_margins(cls, value: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        unsupported = sorted(set(value) - SUPPORTED_MARGIN_FIELDS)
        if unsupported:
            raise ValueError(f"unsupported population margin fields: {unsupported}")
        for field, targets in value.items():
            if not targets:
                raise ValueError(f"population margin {field} cannot be empty")
            if any(not np.isfinite(item) or item < 0 for item in targets.values()):
                raise ValueError(f"population margin {field} must be finite and non-negative")
            if sum(targets.values()) <= 0:
                raise ValueError(f"population margin {field} must have a positive total")
        return value

    @model_validator(mode="after")
    def validate_source_and_totals(self) -> PopulationMarginDataset:
        if not self.authorization_confirmed:
            raise ValueError("authorization_confirmed must be true")
        if not self.deidentified_or_aggregate:
            raise ValueError("only deidentified or aggregate population anchors are accepted")
        if self.available_at < self.observed_at:
            raise ValueError("available_at must not precede observed_at")
        totals = [sum(targets.values()) for targets in self.margins.values()]
        if self.scale == MarginScale.PROPORTION:
            if any(not np.isclose(total, 1, atol=1e-6) for total in totals):
                raise ValueError("each proportion margin must sum to 1")
        else:
            if self.target_population is None:
                raise ValueError("count margins require target_population")
            if any(not np.isclose(total, self.target_population, rtol=1e-6) for total in totals):
                raise ValueError("each count margin must sum to target_population")
        return self


class PopulationGroundingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    source: str
    converged: bool
    iterations: int
    max_relative_error: float
    target_population: float
    weight_sum: float
    effective_sample_size: float
    design_effect: float
    minimum_weight: float
    median_weight: float
    maximum_weight: float
    maximum_to_median_ratio: float
    covered_fields: list[str]
    warnings: list[str]
    weighting_signature: str


def margin_dataset_root(settings: Settings) -> Path:
    return settings.artifact_dir / "research" / "grounding" / "population_margins"


def save_margin_dataset(dataset: PopulationMarginDataset, settings: Settings) -> Path:
    root = margin_dataset_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{dataset.dataset_id}.json"
    if path.exists():
        existing = PopulationMarginDataset.model_validate_json(path.read_text(encoding="utf-8"))
        if existing != dataset:
            raise ValueError(
                f"population margin dataset id already exists with different content: "
                f"{dataset.dataset_id}"
            )
        return path
    path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_margin_dataset(dataset_id: str, settings: Settings) -> PopulationMarginDataset:
    path = margin_dataset_root(settings) / f"{dataset_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"population margin dataset not found: {dataset_id}")
    return PopulationMarginDataset.model_validate_json(path.read_text(encoding="utf-8"))


def _target_margins(
    dataset: PopulationMarginDataset, agent_count: int
) -> tuple[dict[str, dict[Hashable, float]], float]:
    target_population = float(dataset.target_population or agent_count)
    if dataset.scale == MarginScale.COUNT:
        return (
            {
                field: {category: float(target) for category, target in targets.items()}
                for field, targets in dataset.margins.items()
            },
            target_population,
        )
    return (
        {
            field: {category: share * target_population for category, share in targets.items()}
            for field, targets in dataset.margins.items()
        },
        target_population,
    )


def apply_population_margins(
    population: ResearchPopulation,
    dataset: PopulationMarginDataset,
    settings: Settings | None = None,
    *,
    persist: bool = True,
) -> tuple[ResearchPopulation, PopulationGroundingReport]:
    records: list[dict[str, Hashable]] = [
        {field: population.agents[field][index].as_py() for field in dataset.margins}
        for index in range(population.agents.num_rows)
    ]
    margins, target_population = _target_margins(dataset, population.agents.num_rows)
    result = iterative_proportional_fitting(
        records,
        margins,
        initial_weights=np.asarray(population.agents["survey_weight"], dtype=float).tolist(),
        tolerance=1e-8,
        max_iterations=1_000,
    )
    weights = result.weights
    median = float(np.median(weights))
    ess = effective_sample_size(weights)
    ratio = float(weights.max() / max(median, 1e-12))
    design_effect = float(population.agents.num_rows / ess)
    warnings: list[str] = []
    if not result.converged:
        warnings.append("人口边际加权未在迭代上限内收敛")
    if ess < population.agents.num_rows * 0.35:
        warnings.append("有效样本量低于 Agent 数量的 35%，目标边际与原型池差异较大")
    if ratio > 20:
        warnings.append("最大权重超过中位权重 20 倍，部分小群体结果可能不稳定")
    weighting_signature = stable_hash(
        {
            "dataset": dataset.model_dump(mode="json"),
            "population_signature": population.manifest["profile_signature"],
            "weights": np.round(weights, 10).tolist(),
        }
    )
    report = PopulationGroundingReport(
        dataset_id=dataset.dataset_id,
        source=dataset.source,
        converged=result.converged,
        iterations=result.iterations,
        max_relative_error=result.max_relative_error,
        target_population=target_population,
        weight_sum=float(weights.sum()),
        effective_sample_size=ess,
        design_effect=design_effect,
        minimum_weight=float(weights.min()),
        median_weight=median,
        maximum_weight=float(weights.max()),
        maximum_to_median_ratio=ratio,
        covered_fields=sorted(dataset.margins),
        warnings=warnings,
        weighting_signature=weighting_signature,
    )
    weight_index = population.agents.schema.get_field_index("survey_weight")
    agents = population.agents.set_column(
        weight_index,
        "survey_weight",
        pa.array(weights, type=pa.float64()),
    )
    manifest: dict[str, Any] = {
        **population.manifest,
        "population_grounding": report.model_dump(mode="json"),
        "weighting_signature": weighting_signature,
    }
    grounded = ResearchPopulation(
        spec=population.spec,
        agents=agents,
        graph=population.graph,
        manifest=manifest,
    )
    if persist:
        save_population(grounded, settings or Settings.load())
    return grounded, report
