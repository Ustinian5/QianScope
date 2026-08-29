from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from echo_swm.ai.contracts import AIExecutionMetadata


class MetricOrigin(StrEnum):
    OFFICIAL = "official"
    DERIVED = "derived"
    SYNTHETIC = "synthetic"
    ASSUMPTION = "assumption"


class MetricAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(ge=0)
    unit: str
    year: int = Field(ge=2000, le=2100)
    origin: MetricOrigin


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    url: str
    used_for: list[str]


class DistrictAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district_id: str
    name_zh: str
    population_2024: int = Field(gt=0)
    urbanization_2024: float = Field(ge=0, le=1)
    area_km2: float = Field(gt=0)
    gdp_2024_100m: float = Field(gt=0)
    primary_share: float = Field(ge=0, le=1)
    secondary_share: float = Field(ge=0, le=1)
    tertiary_share: float = Field(ge=0, le=1)
    centroid_lat: float = Field(ge=-90, le=90)
    centroid_lon: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def validate_industry_shares(self) -> DistrictAnchor:
        total = self.primary_share + self.secondary_share + self.tertiary_share
        if abs(total - 1.0) > 0.002:
            raise ValueError("district industry shares must sum to one within rounding tolerance")
        return self


class CityAnchorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city_id: str
    name_zh: str
    reference_date: date
    city_metrics: dict[str, MetricAnchor]
    districts: list[DistrictAnchor]
    sources: list[SourceReference]
    assumptions: list[str]

    @model_validator(mode="after")
    def validate_coverage(self) -> CityAnchorConfig:
        ids = [district.district_id for district in self.districts]
        if len(ids) != len(set(ids)):
            raise ValueError("district ids must be unique")
        required = {"resident_population", "urbanization_rate", "gdp"}
        if not required.issubset(self.city_metrics):
            raise ValueError("city configuration is missing core anchors")
        return self


class CityEventType(StrEnum):
    ECONOMIC_SHOCK = "economic_shock"
    EXTREME_WEATHER = "extreme_weather"
    PUBLIC_HEALTH = "public_health"
    TRANSIT_DISRUPTION = "transit_disruption"
    INDUSTRIAL_ACCIDENT = "industrial_accident"
    POLICY_ANNOUNCEMENT = "policy_announcement"
    REPUTATION_SHOCK = "reputation_shock"
    INFORMATION_SHOCK = "information_shock"
    TOURISM_SURGE = "tourism_surge"
    CUSTOM = "custom"


class CityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: CityEventType
    start_day: int = Field(ge=0)
    duration_days: int = Field(default=1, ge=1, le=365)
    intensity: float = Field(ge=0, le=1)
    affected_districts: list[str] = Field(default_factory=list)
    economic_direction: float = Field(default=0, ge=-1, le=1)
    mobility_direction: float = Field(default=0, ge=-1, le=1)
    health_direction: float = Field(default=0, ge=-1, le=1)
    information_valence: float = Field(default=0, ge=-1, le=1)
    credibility: float = Field(default=0.7, ge=0, le=1)
    source: str = "scenario_assumption"


class CityIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    start_day: int = Field(default=0, ge=0)
    duration_days: int = Field(default=30, ge=1, le=365)
    target_districts: list[str] = Field(default_factory=list)
    target_segments: list[str] = Field(default_factory=list)
    transit_subsidy: float = Field(default=0, ge=0, le=1)
    consumption_voucher_yuan: float = Field(default=0, ge=0, le=10000)
    sme_support: float = Field(default=0, ge=0, le=1)
    health_capacity_boost: float = Field(default=0, ge=0, le=1)
    public_information: float = Field(default=0, ge=0, le=1)
    estimated_budget_100m_cny: float = Field(default=0, ge=0)


class CityBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str
    name: str
    interventions: list[CityIntervention] = Field(default_factory=list)


class CityScopeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    city_id: str = "suzhou"
    districts: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)
    horizon_days: int = Field(default=30, ge=1, le=180)
    focal_metrics: list[str] = Field(
        default_factory=lambda: [
            "life_satisfaction",
            "government_trust",
            "economic_confidence",
            "consumption_index",
            "employment_rate",
            "congestion_index",
            "health_system_load",
            "rumor_belief",
            "organization_vitality",
            "public_service_reliability",
        ]
    )
    events: list[CityEvent] = Field(default_factory=list)
    branches: list[CityBranch]
    samples: int = Field(default=32, ge=1, le=256)
    random_seed: int = 2026
    save_micro_snapshots: bool = True

    @model_validator(mode="after")
    def validate_branches(self) -> CityScopeQuery:
        ids = [branch.branch_id for branch in self.branches]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("at least one uniquely named branch is required")
        return self


class QuantileBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    mean: float
    standard_deviation: float = Field(ge=0)


class CityTrajectoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=0)
    metrics: dict[str, QuantileBand]


class CityForecast(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    query_id: str
    city_id: str
    model_version: str
    data_version: str
    prototype_count: int
    represented_population: float
    represented_scope_population: float
    query: CityScopeQuery
    branch_trajectories: dict[str, list[CityTrajectoryPoint]]
    final_district_metrics: list[dict[str, object]]
    counterfactual_deltas: dict[str, dict[str, float]]
    assumptions: list[str]
    warnings: list[str]
    artifact_dir: str
    ai_execution: list[AIExecutionMetadata] = Field(default_factory=list)
    disclaimer: str
