from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from echo_swm import DISCLAIMER
from echo_swm.ai.contracts import AIExecutionMetadata
from echo_swm.city.contracts import (
    CityBranch,
    CityForecast,
    CityScopeQuery,
    CityTrajectoryPoint,
    QuantileBand,
)
from echo_swm.city.population import CityWorld
from echo_swm.core.ids import new_id, stable_hash
from echo_swm.core.random import derive_seed
from echo_swm.observability.run_manifest import append_jsonl

MODEL_VERSION = "suzhou-coupled-city-runtime-v1"
DATA_VERSION = "suzhou-official-anchors-2025+synthetic-micro-v1"


@dataclass
class CityMicroState:
    life_satisfaction: NDArray[np.float64]
    government_trust: NDArray[np.float64]
    economic_confidence: NDArray[np.float64]
    consumption_index: NDArray[np.float64]
    employment_probability: NDArray[np.float64]
    stress: NDArray[np.float64]
    rumor_belief: NDArray[np.float64]
    health_need: NDArray[np.float64]
    awareness: NDArray[np.float64]
    commute_minutes: NDArray[np.float64]
    organization_vitality: NDArray[np.float64]
    organization_reliability: NDArray[np.float64]
    organization_trust: NDArray[np.float64]

    def copy(self) -> CityMicroState:
        return CityMicroState(**{name: value.copy() for name, value in self.as_dict().items()})

    def as_dict(self) -> dict[str, NDArray[np.float64]]:
        return {
            "life_satisfaction": self.life_satisfaction,
            "government_trust": self.government_trust,
            "economic_confidence": self.economic_confidence,
            "consumption_index": self.consumption_index,
            "employment_probability": self.employment_probability,
            "stress": self.stress,
            "rumor_belief": self.rumor_belief,
            "health_need": self.health_need,
            "awareness": self.awareness,
            "commute_minutes": self.commute_minutes,
            "organization_vitality": self.organization_vitality,
            "organization_reliability": self.organization_reliability,
            "organization_trust": self.organization_trust,
        }


@dataclass(frozen=True)
class ActiveSignals:
    economic: NDArray[np.float64]
    mobility: NDArray[np.float64]
    health: NDArray[np.float64]
    information: NDArray[np.float64]
    credibility: NDArray[np.float64]
    transit_subsidy: NDArray[np.float64]
    voucher: NDArray[np.float64]
    sme_support: NDArray[np.float64]
    health_boost: NDArray[np.float64]
    public_information: NDArray[np.float64]
    budget_100m: float


def _person_arrays(world: CityWorld) -> dict[str, NDArray[Any]]:
    return {
        name: np.asarray(world.persons[name].to_numpy())
        for name in (
            "weight",
            "district_index",
            "age",
            "hukou_local",
            "education_level",
            "employment_status",
            "industry_sector",
            "income_annual",
            "commute_mode",
            "base_commute_minutes",
            "digital_affinity",
            "government_trust",
            "institutional_trust",
            "risk_aversion",
            "social_influence",
            "public_service_need",
            "life_satisfaction",
        )
    }


def _organization_arrays(world: CityWorld) -> dict[str, NDArray[Any]]:
    return {
        name: np.asarray(world.institutions[name].to_numpy())
        for name in (
            "institution_type",
            "district_index",
            "represented_entities",
            "capacity",
            "baseline_trust",
        )
    }


def _initial_state(
    arrays: dict[str, NDArray[Any]],
    organizations: dict[str, NDArray[Any]],
    rng: np.random.Generator,
) -> CityMicroState:
    size = arrays["weight"].size
    employed = arrays["employment_status"] == 2
    employment_probability = np.where(employed, 0.97, 0.03).astype(float)
    employment_probability[arrays["employment_status"] == 3] = 0.20
    economic_confidence = np.clip(
        0.52
        + 0.10 * np.log1p(arrays["income_annual"] / 80_796)
        - 0.18 * (arrays["employment_status"] == 3)
        + rng.normal(0, 0.035, size),
        0,
        1,
    )
    stress = np.clip(
        0.30
        + arrays["base_commute_minutes"] / 300
        + 0.16 * (arrays["employment_status"] == 3)
        + rng.normal(0, 0.04, size),
        0,
        1,
    )
    return CityMicroState(
        life_satisfaction=arrays["life_satisfaction"].astype(float).copy(),
        government_trust=arrays["government_trust"].astype(float).copy(),
        economic_confidence=economic_confidence,
        consumption_index=np.clip(0.58 + 0.25 * economic_confidence - 0.15 * stress, 0, 1),
        employment_probability=employment_probability,
        stress=stress,
        rumor_belief=np.clip(rng.beta(1.3, 8.0, size), 0, 1),
        health_need=np.clip(arrays["public_service_need"] * 0.45, 0, 1),
        awareness=np.clip(rng.beta(1.5, 5.0, size), 0, 1),
        commute_minutes=arrays["base_commute_minutes"].astype(float).copy(),
        organization_vitality=np.clip(
            rng.normal(0.82, 0.035, organizations["district_index"].size), 0, 1
        ),
        organization_reliability=np.clip(
            rng.normal(0.84, 0.025, organizations["district_index"].size), 0, 1
        ),
        organization_trust=organizations["baseline_trust"].astype(float).copy(),
    )


def _segment_mask(arrays: dict[str, NDArray[Any]], segments: list[str]) -> NDArray[np.bool_]:
    mask = np.ones(arrays["weight"].size, dtype=bool)
    for segment in segments:
        if segment == "youth":
            mask &= (arrays["age"] >= 18) & (arrays["age"] <= 35)
        elif segment == "elderly":
            mask &= arrays["age"] >= 65
        elif segment == "migrant":
            mask &= arrays["hukou_local"] == 0
        elif segment == "manufacturing_worker":
            mask &= (arrays["industry_sector"] == 1) & (arrays["employment_status"] == 2)
        elif segment == "service_worker":
            mask &= (arrays["industry_sector"] == 2) & (arrays["employment_status"] == 2)
        elif segment == "student":
            mask &= arrays["employment_status"] == 1
        elif segment == "low_income":
            mask &= arrays["income_annual"] <= np.quantile(arrays["income_annual"], 0.30)
        else:
            raise ValueError(f"unsupported city segment: {segment}")
    return mask


def _scope_mask(
    world: CityWorld, arrays: dict[str, NDArray[Any]], query: CityScopeQuery
) -> NDArray[np.bool_]:
    mask = _segment_mask(arrays, query.segments)
    if query.districts:
        known = set(world.anchors.district_ids)
        unknown = set(query.districts) - known
        if unknown:
            raise ValueError(f"unknown districts in scope: {sorted(unknown)}")
        selected = np.asarray(
            [world.anchors.district_ids.index(district) for district in query.districts], dtype=int
        )
        mask &= np.isin(arrays["district_index"], selected)
    if not mask.any():
        raise ValueError("scope query selects no prototypes")
    return mask


def _target_mask(
    world: CityWorld,
    arrays: dict[str, NDArray[Any]],
    districts: list[str],
    segments: list[str],
) -> NDArray[np.bool_]:
    mask = _segment_mask(arrays, segments)
    if districts:
        indices = []
        for district in districts:
            if district not in world.anchors.district_ids:
                raise ValueError(f"unknown target district: {district}")
            indices.append(world.anchors.district_ids.index(district))
        mask &= np.isin(arrays["district_index"], np.asarray(indices))
    return mask


def _active_signals(
    world: CityWorld,
    arrays: dict[str, NDArray[Any]],
    query: CityScopeQuery,
    branch: CityBranch,
    day: int,
    rng: np.random.Generator,
) -> ActiveSignals:
    size = arrays["weight"].size
    economic = np.zeros(size)
    mobility = np.zeros(size)
    health = np.zeros(size)
    information = np.zeros(size)
    credibility_numerator = np.zeros(size)
    credibility_denominator = np.zeros(size)
    for event in query.events:
        if not event.start_day <= day < event.start_day + event.duration_days:
            continue
        target = _target_mask(world, arrays, event.affected_districts, [])
        path_scale = float(np.clip(rng.normal(1.0, 0.09), 0.70, 1.30))
        intensity = event.intensity * path_scale
        economic[target] += event.economic_direction * intensity
        mobility[target] += event.mobility_direction * intensity
        health[target] += event.health_direction * intensity
        information[target] += event.information_valence * intensity
        credibility_numerator[target] += event.credibility * intensity
        credibility_denominator[target] += intensity
    credibility = np.divide(
        credibility_numerator,
        credibility_denominator,
        out=np.full(size, 0.5),
        where=credibility_denominator > 0,
    )
    transit = np.zeros(size)
    voucher = np.zeros(size)
    sme = np.zeros(size)
    health_boost = np.zeros(size)
    public_information = np.zeros(size)
    budget = 0.0
    for intervention in branch.interventions:
        if not intervention.start_day <= day < intervention.start_day + intervention.duration_days:
            continue
        target = _target_mask(
            world, arrays, intervention.target_districts, intervention.target_segments
        )
        transit[target] = np.maximum(transit[target], intervention.transit_subsidy)
        voucher[target] += intervention.consumption_voucher_yuan
        sme[target] = np.maximum(sme[target], intervention.sme_support)
        health_boost[target] = np.maximum(health_boost[target], intervention.health_capacity_boost)
        public_information[target] = np.maximum(
            public_information[target], intervention.public_information
        )
        budget += intervention.estimated_budget_100m_cny / intervention.duration_days
    return ActiveSignals(
        economic=economic,
        mobility=mobility,
        health=health,
        information=information,
        credibility=credibility,
        transit_subsidy=transit,
        voucher=voucher,
        sme_support=sme,
        health_boost=health_boost,
        public_information=public_information,
        budget_100m=budget,
    )


def _district_load(
    district_index: NDArray[np.int64],
    weights: NDArray[np.float64],
    demand: NDArray[np.float64],
    capacity: NDArray[np.float64],
) -> NDArray[np.float64]:
    total = np.bincount(district_index, weights=weights * demand, minlength=capacity.size)
    return np.clip(total / np.maximum(capacity, 1), 0, 3)


def _district_mean(
    district_index: NDArray[np.int64],
    weights: NDArray[np.float64],
    values: NDArray[np.float64],
    district_count: int,
    *,
    fallback: float = 0.0,
) -> NDArray[np.float64]:
    numerator = np.bincount(
        district_index,
        weights=weights * values,
        minlength=district_count,
    )
    denominator = np.bincount(district_index, weights=weights, minlength=district_count)
    return np.divide(
        numerator,
        denominator,
        out=np.full(district_count, fallback, dtype=float),
        where=denominator > 0,
    )


def _district_max(
    district_index: NDArray[np.int64],
    values: NDArray[np.float64],
    district_count: int,
) -> NDArray[np.float64]:
    result = np.zeros(district_count, dtype=float)
    np.maximum.at(result, district_index, values)
    return result


def _advance(
    world: CityWorld,
    arrays: dict[str, NDArray[Any]],
    organizations: dict[str, NDArray[Any]],
    state: CityMicroState,
    signals: ActiveSignals,
    rng: np.random.Generator,
) -> tuple[CityMicroState, NDArray[np.float64], NDArray[np.float64]]:
    district = arrays["district_index"].astype(np.int64)
    weights = arrays["weight"].astype(float)
    district_count = len(world.anchors.districts)
    organization_district = organizations["district_index"].astype(np.int64)
    organization_weight = organizations["represented_entities"].astype(float)
    organization_type = organizations["institution_type"]
    economic_by_district = _district_mean(district, weights, signals.economic, district_count)
    mobility_by_district = _district_mean(district, weights, signals.mobility, district_count)
    health_by_district = _district_mean(district, weights, signals.health, district_count)
    sme_by_district = _district_max(district, signals.sme_support, district_count)
    information_by_district = _district_mean(
        district, weights, signals.public_information, district_count
    )
    firm = organization_type == "firm_prototype"
    hospital = organization_type == "hospital"
    transport_hub = organization_type == "transport_hub"
    organization_economic = economic_by_district[organization_district]
    organization_mobility = mobility_by_district[organization_district]
    organization_health = health_by_district[organization_district]
    organization_sme = sme_by_district[organization_district]
    organization_information = information_by_district[organization_district]
    state.organization_vitality = np.clip(
        0.94 * state.organization_vitality
        + 0.049
        + 0.040 * organization_economic * firm
        + 0.030 * organization_sme * firm
        - 0.025 * np.maximum(organization_mobility, 0) * transport_hub
        - 0.030 * np.maximum(organization_health, 0) * hospital,
        0,
        1,
    )
    state.organization_reliability = np.clip(
        0.94 * state.organization_reliability
        + 0.030 * state.organization_vitality
        + 0.025
        - 0.025 * np.maximum(organization_mobility, 0) * transport_hub
        - 0.035 * np.maximum(organization_health, 0) * hospital,
        0,
        1,
    )
    state.organization_trust = np.clip(
        0.96 * state.organization_trust
        + 0.020 * state.organization_reliability
        + 0.010
        + 0.025 * organization_information,
        0,
        1,
    )
    firm_vitality = _district_mean(
        organization_district[firm],
        organization_weight[firm],
        state.organization_vitality[firm],
        district_count,
        fallback=0.82,
    )
    sector = arrays["industry_sector"]
    employed_status = arrays["employment_status"] == 2
    economic_exposure = np.where(sector == 1, 1.0, np.where(sector == 2, 0.72, 0.35))
    employment_delta = (
        0.018 * signals.economic * economic_exposure
        + 0.012 * signals.sme_support * employed_status
        + 0.006 * (firm_vitality[district] - 0.82) * employed_status
        + rng.normal(0, 0.0015, weights.size)
    )
    state.employment_probability = np.clip(
        state.employment_probability + employment_delta, 0.01, 0.995
    )
    social_economy = world.graph.aggregate(state.economic_confidence, weights.size)
    state.economic_confidence = np.clip(
        0.91 * state.economic_confidence
        + 0.035 * social_economy
        + 0.055 * (0.5 + 0.5 * signals.economic)
        + 0.025 * signals.sme_support
        - 0.035 * (1 - state.employment_probability),
        0,
        1,
    )

    motorized = np.isin(arrays["commute_mode"], [1, 2, 3]).astype(float)
    car_load = (arrays["commute_mode"] == 1).astype(float)
    transit_shift = 1 - 0.24 * signals.transit_subsidy * car_load
    mobility_demand = (
        state.employment_probability
        * motorized
        * transit_shift
        * (1 + 0.35 * np.maximum(signals.mobility, 0))
    )
    transport_reliability = _district_mean(
        organization_district[transport_hub],
        organization_weight[transport_hub],
        state.organization_reliability[transport_hub],
        district_count,
        fallback=0.84,
    )
    effective_transport_capacity = world.transport_capacity * np.clip(
        transport_reliability / 0.84, 0.65, 1.20
    )
    congestion = _district_load(
        district,
        weights,
        mobility_demand,
        effective_transport_capacity,
    )
    commute_multiplier = np.clip(
        0.82 + 0.30 * congestion[district] + 0.22 * signals.mobility, 0.55, 2.2
    )
    state.commute_minutes = np.clip(arrays["base_commute_minutes"] * commute_multiplier, 0, 180)

    heat_sensitive = 0.45 + 0.45 * arrays["public_service_need"]
    state.health_need = np.clip(
        0.88 * state.health_need
        + 0.12 * arrays["public_service_need"] * 0.45
        + 0.10 * np.maximum(signals.health, 0) * heat_sensitive,
        0,
        1,
    )
    district_boost = _district_max(
        district,
        signals.health_boost,
        world.health_capacity.size,
    )
    hospital_reliability = _district_mean(
        organization_district[hospital],
        organization_weight[hospital],
        state.organization_reliability[hospital],
        district_count,
        fallback=0.84,
    )
    health_capacity = (
        world.health_capacity
        * np.clip(hospital_reliability / 0.84, 0.65, 1.20)
        * (1 + district_boost)
    )
    health_load = _district_load(district, weights, state.health_need, health_capacity)

    neighbor_rumor = world.graph.aggregate(state.rumor_belief, weights.size)
    information_pressure = np.maximum(-signals.information, 0) * (
        0.35 + 0.65 * arrays["digital_affinity"]
    )
    correction = (
        signals.public_information * state.government_trust * (0.45 + 0.55 * signals.credibility)
    )
    state.awareness = np.clip(
        state.awareness
        + (1 - state.awareness) * (0.08 * np.abs(signals.information) + 0.05 * neighbor_rumor),
        0,
        1,
    )
    state.rumor_belief = np.clip(
        0.70 * state.rumor_belief
        + 0.20 * neighbor_rumor * arrays["social_influence"]
        + 0.18 * information_pressure * (1 - arrays["institutional_trust"])
        - 0.16 * correction,
        0,
        1,
    )

    voucher_relief = np.clip(signals.voucher / np.maximum(arrays["income_annual"] / 12, 1), 0, 0.8)
    state.stress = np.clip(
        0.88 * state.stress
        + 0.10 * (state.commute_minutes / 90)
        + 0.08 * (1 - state.employment_probability)
        + 0.07 * np.maximum(signals.health, 0)
        + 0.05 * state.rumor_belief
        - 0.06 * voucher_relief
        - 0.04 * signals.transit_subsidy,
        0,
        1,
    )
    state.consumption_index = np.clip(
        0.84 * state.consumption_index
        + 0.11 * state.economic_confidence
        + 0.10 * voucher_relief
        - 0.06 * state.stress,
        0,
        1,
    )
    service_quality = np.clip(1.15 - health_load[district], -1, 1)
    institution_trust = _district_mean(
        organization_district,
        organization_weight,
        state.organization_trust,
        district_count,
        fallback=0.62,
    )
    state.government_trust = np.clip(
        0.94 * state.government_trust
        + 0.025 * service_quality
        + 0.035 * correction
        + 0.012 * state.economic_confidence
        + 0.015 * (institution_trust[district] - 0.62)
        - 0.025 * state.rumor_belief,
        0,
        1,
    )
    state.life_satisfaction = np.clip(
        0.88 * state.life_satisfaction
        + 0.035 * state.government_trust
        + 0.035 * state.economic_confidence
        + 0.025 * state.consumption_index
        - 0.045 * state.stress
        - 0.012 * health_load[district],
        0,
        1,
    )
    return state, congestion, health_load


def _weighted_mean(values: NDArray[np.float64], weights: NDArray[np.float64]) -> float:
    return float(np.average(values, weights=weights))


def _macro_metrics(
    state: CityMicroState,
    organizations: dict[str, NDArray[Any]],
    congestion: NDArray[np.float64],
    health_load: NDArray[np.float64],
    district: NDArray[np.int64],
    weights: NDArray[np.float64],
    mask: NDArray[np.bool_],
    labor_force_mask: NDArray[np.bool_],
    cumulative_budget: float,
) -> dict[str, float]:
    selected_weights = weights[mask]
    employment_mask = mask & labor_force_mask
    if not employment_mask.any():
        employment_mask = mask
    organization_district = organizations["district_index"].astype(np.int64)
    organization_scope = np.isin(organization_district, np.unique(district[mask]))
    organization_type = organizations["institution_type"]
    firms = organization_scope & (organization_type == "firm_prototype")
    public_services = organization_scope & (organization_type != "firm_prototype")
    organization_weight = organizations["represented_entities"].astype(float)
    service_weight = organizations["capacity"].astype(float)
    return {
        "life_satisfaction": _weighted_mean(state.life_satisfaction[mask], selected_weights),
        "government_trust": _weighted_mean(state.government_trust[mask], selected_weights),
        "economic_confidence": _weighted_mean(state.economic_confidence[mask], selected_weights),
        "consumption_index": _weighted_mean(state.consumption_index[mask], selected_weights),
        "employment_rate": _weighted_mean(
            state.employment_probability[employment_mask], weights[employment_mask]
        ),
        "congestion_index": _weighted_mean(congestion[district[mask]], selected_weights),
        "health_system_load": _weighted_mean(health_load[district[mask]], selected_weights),
        "rumor_belief": _weighted_mean(state.rumor_belief[mask], selected_weights),
        "stress": _weighted_mean(state.stress[mask], selected_weights),
        "commute_minutes": _weighted_mean(state.commute_minutes[mask], selected_weights),
        "organization_vitality": _weighted_mean(
            state.organization_vitality[firms], organization_weight[firms]
        ),
        "public_service_reliability": _weighted_mean(
            state.organization_reliability[public_services], service_weight[public_services]
        ),
        "policy_cost_100m_cny": cumulative_budget,
    }


def _state_hash(state: CityMicroState) -> str:
    digest = hashlib.sha256()
    for name, values in state.as_dict().items():
        array = np.ascontiguousarray(values)
        digest.update(name.encode("utf-8"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes())
    return digest.hexdigest()


def _save_checkpoint(path: Path, state: CityMicroState, branch: str, day: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "branch": np.asarray(branch),
        "day": np.asarray(day),
        "state_hash": np.asarray(_state_hash(state)),
        **state.as_dict(),
    }
    np.savez_compressed(path, **payload)


def _simulate_path(
    world: CityWorld,
    arrays: dict[str, NDArray[Any]],
    organizations: dict[str, NDArray[Any]],
    query: CityScopeQuery,
    branch: CityBranch,
    sample: int,
    scope_mask: NDArray[np.bool_],
    run_dir: Path,
) -> tuple[list[dict[str, float]], CityMicroState, NDArray[np.float64], NDArray[np.float64]]:
    # Common random numbers isolate policy effects from Monte Carlo path noise.
    seed = derive_seed(query.random_seed, f"{query.query_id}:{sample}")
    rng = np.random.default_rng(seed)
    state = _initial_state(arrays, organizations, rng)
    district = arrays["district_index"].astype(np.int64)
    weights = arrays["weight"].astype(float)
    labor_force_mask = (
        (arrays["age"] >= 18) & (arrays["age"] < 65) & (arrays["employment_status"] != 1)
    )
    congestion = np.ones(len(world.anchors.districts), dtype=float) * 0.8
    health_load = np.ones(len(world.anchors.districts), dtype=float) * 0.65
    trajectory: list[dict[str, float]] = []
    cumulative_budget = 0.0
    checkpoint_days = {0, query.horizon_days, *[event.start_day for event in query.events]}
    replay_path = run_dir / "replay.jsonl"
    for day in range(query.horizon_days + 1):
        if day > 0:
            signals = _active_signals(world, arrays, query, branch, day - 1, rng)
            cumulative_budget += signals.budget_100m
            state, congestion, health_load = _advance(
                world,
                arrays,
                organizations,
                state,
                signals,
                rng,
            )
        metrics = _macro_metrics(
            state,
            organizations,
            congestion,
            health_load,
            district,
            weights,
            scope_mask,
            labor_force_mask,
            cumulative_budget,
        )
        metrics["day"] = float(day)
        trajectory.append(metrics)
        state_hash = _state_hash(state)
        append_jsonl(
            replay_path,
            {
                "type": "city_tick",
                "branch": branch.branch_id,
                "sample": sample,
                "day": day,
                "seed": seed,
                "state_hash": state_hash,
                "macro_hash": stable_hash(metrics),
            },
        )
        if query.save_micro_snapshots and sample == 0 and day in checkpoint_days:
            _save_checkpoint(
                run_dir / "snapshots" / branch.branch_id / f"day_{day:03d}.npz",
                state,
                branch.branch_id,
                day,
            )
    return trajectory, state, congestion, health_load


def _quantile_band(values: NDArray[np.float64]) -> QuantileBand:
    return QuantileBand(
        p10=float(np.quantile(values, 0.10)),
        p50=float(np.quantile(values, 0.50)),
        p90=float(np.quantile(values, 0.90)),
        mean=float(np.mean(values)),
        standard_deviation=float(np.std(values)),
    )


def _district_metrics(
    world: CityWorld,
    arrays: dict[str, NDArray[Any]],
    organizations: dict[str, NDArray[Any]],
    final_states: list[CityMicroState],
    final_congestion: list[NDArray[np.float64]],
    final_health: list[NDArray[np.float64]],
    branch_id: str,
) -> list[dict[str, object]]:
    district = arrays["district_index"].astype(np.int64)
    weights = arrays["weight"].astype(float)
    labor_force = (arrays["age"] >= 18) & (arrays["age"] < 65) & (arrays["employment_status"] != 1)
    organization_district = organizations["district_index"].astype(np.int64)
    organization_type = organizations["institution_type"]
    organization_weight = organizations["represented_entities"].astype(float)
    service_weight = organizations["capacity"].astype(float)
    results: list[dict[str, object]] = []
    for index, anchor in enumerate(world.anchors.districts):
        mask = district == index
        metrics: dict[str, QuantileBand] = {}
        for name in (
            "life_satisfaction",
            "government_trust",
            "economic_confidence",
            "consumption_index",
            "rumor_belief",
        ):
            samples = np.asarray(
                [
                    _weighted_mean(getattr(state, name)[mask], weights[mask])
                    for state in final_states
                ]
            )
            metrics[name] = _quantile_band(samples)
        employment_mask = mask & labor_force
        metrics["employment_probability"] = _quantile_band(
            np.asarray(
                [
                    _weighted_mean(
                        state.employment_probability[employment_mask],
                        weights[employment_mask],
                    )
                    for state in final_states
                ]
            )
        )
        metrics["congestion_index"] = _quantile_band(
            np.asarray([values[index] for values in final_congestion])
        )
        metrics["health_system_load"] = _quantile_band(
            np.asarray([values[index] for values in final_health])
        )
        firm_mask = (organization_district == index) & (organization_type == "firm_prototype")
        service_mask = (organization_district == index) & (organization_type != "firm_prototype")
        metrics["organization_vitality"] = _quantile_band(
            np.asarray(
                [
                    _weighted_mean(
                        state.organization_vitality[firm_mask],
                        organization_weight[firm_mask],
                    )
                    for state in final_states
                ]
            )
        )
        metrics["public_service_reliability"] = _quantile_band(
            np.asarray(
                [
                    _weighted_mean(
                        state.organization_reliability[service_mask],
                        service_weight[service_mask],
                    )
                    for state in final_states
                ]
            )
        )
        results.append(
            {
                "branch_id": branch_id,
                "district_id": anchor.anchor.district_id,
                "district_name": anchor.anchor.name_zh,
                "represented_population": anchor.population_2025,
                "metrics": {name: band.model_dump() for name, band in metrics.items()},
            }
        )
    return results


def run_city_scope_query(
    world: CityWorld,
    query: CityScopeQuery,
    artifact_root: Path,
    ai_execution: list[AIExecutionMetadata] | None = None,
) -> CityForecast:
    if query.city_id != world.anchors.config.city_id:
        raise ValueError("scope query city does not match loaded world")
    known_metrics = {
        "life_satisfaction",
        "government_trust",
        "economic_confidence",
        "consumption_index",
        "employment_rate",
        "congestion_index",
        "health_system_load",
        "rumor_belief",
        "stress",
        "commute_minutes",
        "organization_vitality",
        "public_service_reliability",
        "policy_cost_100m_cny",
    }
    unknown_metrics = set(query.focal_metrics) - known_metrics
    if unknown_metrics:
        raise ValueError(f"unsupported focal metrics: {sorted(unknown_metrics)}")
    run_id = new_id("cityrun")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    arrays = _person_arrays(world)
    organizations = _organization_arrays(world)
    scope_mask = _scope_mask(world, arrays, query)
    branch_trajectories: dict[str, list[CityTrajectoryPoint]] = {}
    district_results: list[dict[str, object]] = []
    final_values: dict[str, dict[str, float]] = {}
    trajectory_rows: list[dict[str, Any]] = []

    for branch in query.branches:
        paths: list[list[dict[str, float]]] = []
        final_states: list[CityMicroState] = []
        final_congestion: list[NDArray[np.float64]] = []
        final_health: list[NDArray[np.float64]] = []
        for sample in range(query.samples):
            trajectory, state, congestion, health = _simulate_path(
                world,
                arrays,
                organizations,
                query,
                branch,
                sample,
                scope_mask,
                run_dir,
            )
            paths.append(trajectory)
            final_states.append(state)
            final_congestion.append(congestion)
            final_health.append(health)
        points: list[CityTrajectoryPoint] = []
        for day in range(query.horizon_days + 1):
            metric_bands: dict[str, QuantileBand] = {}
            for metric in query.focal_metrics:
                values = np.asarray([path[day][metric] for path in paths], dtype=float)
                metric_bands[metric] = _quantile_band(values)
                trajectory_rows.append(
                    {
                        "branch_id": branch.branch_id,
                        "day": day,
                        "metric": metric,
                        **metric_bands[metric].model_dump(),
                    }
                )
            points.append(CityTrajectoryPoint(day=day, metrics=metric_bands))
        branch_trajectories[branch.branch_id] = points
        final_values[branch.branch_id] = {
            metric: points[-1].metrics[metric].p50 for metric in query.focal_metrics
        }
        district_results.extend(
            _district_metrics(
                world,
                arrays,
                organizations,
                final_states,
                final_congestion,
                final_health,
                branch.branch_id,
            )
        )

    control_id = query.branches[0].branch_id
    counterfactual = {
        branch_id: {
            metric: values[metric] - final_values[control_id][metric]
            for metric in query.focal_metrics
        }
        for branch_id, values in final_values.items()
        if branch_id != control_id
    }
    warnings = [
        "City totals and district constraints use official aggregate statistics; "
        "micro records are synthetic.",
        "District 2025 values are share-scaled from official 2024 district tables.",
        "Mechanism parameters are explicit scenario assumptions, not fitted causal effects.",
        "K-path bands represent modeled scenario uncertainty, not guaranteed frequentist coverage.",
    ]
    forecast = CityForecast(
        run_id=run_id,
        query_id=query.query_id,
        city_id=query.city_id,
        model_version=MODEL_VERSION,
        data_version=DATA_VERSION,
        prototype_count=world.prototype_count,
        represented_population=world.represented_population,
        represented_scope_population=float(arrays["weight"][scope_mask].sum()),
        query=query,
        branch_trajectories=branch_trajectories,
        final_district_metrics=district_results,
        counterfactual_deltas=counterfactual,
        assumptions=world.anchors.config.assumptions,
        warnings=warnings,
        artifact_dir=str(run_dir.resolve()),
        ai_execution=ai_execution or [],
        disclaimer=DISCLAIMER,
    )
    (run_dir / "forecast.json").write_text(forecast.model_dump_json(indent=2), encoding="utf-8")
    with (run_dir / "trajectory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trajectory_rows[0]))
        writer.writeheader()
        writer.writerows(trajectory_rows)
    pq.write_table(pa.Table.from_pylist(district_results), run_dir / "district_final.parquet")
    manifest = {
        "run_id": run_id,
        "query_hash": stable_hash(query.model_dump(mode="json")),
        "world_version": world.world_version,
        "model_version": MODEL_VERSION,
        "data_version": DATA_VERSION,
        "prototype_count": world.prototype_count,
        "represented_population": world.represented_population,
        "graph_edges": world.graph.edge_count,
        "institution_count": world.institutions.num_rows,
        "samples": query.samples,
        "root_seed": query.random_seed,
        "ai_execution": [item.model_dump(mode="json") for item in (ai_execution or [])],
        "output_hash": stable_hash(
            {
                "counterfactual": counterfactual,
                "final_values": final_values,
                "trajectory_rows": trajectory_rows,
            }
        ),
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return forecast


def verify_city_replay(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (run_dir / "replay.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    unique_ticks = {(record["branch"], record["sample"], record["day"]) for record in records}
    expected = (
        manifest["samples"]
        * len({record["branch"] for record in records})
        * (max(record["day"] for record in records) + 1)
    )
    record_index = {
        (record["branch"], record["sample"], record["day"]): record for record in records
    }
    snapshot_files = sorted((run_dir / "snapshots").rglob("*.npz"))
    verified_snapshots = 0
    for snapshot_path in snapshot_files:
        with np.load(snapshot_path, allow_pickle=False) as snapshot:
            state = CityMicroState(
                **{
                    name: np.asarray(snapshot[name], dtype=float)
                    for name in CityMicroState.__dataclass_fields__
                }
            )
            branch = str(snapshot["branch"].item())
            day = int(snapshot["day"].item())
            stored_hash = str(snapshot["state_hash"].item())
        record = record_index.get((branch, 0, day))
        if (
            stored_hash == _state_hash(state)
            and record is not None
            and record["state_hash"] == stored_hash
        ):
            verified_snapshots += 1
    return {
        "run_id": manifest["run_id"],
        "record_count": len(records),
        "unique_tick_count": len(unique_ticks),
        "expected_tick_count": expected,
        "snapshot_count": len(snapshot_files),
        "verified_snapshot_count": verified_snapshots,
        "valid": len(records) == len(unique_ticks) == expected
        and all(record.get("state_hash") and record.get("macro_hash") for record in records),
        "snapshots_valid": verified_snapshots == len(snapshot_files),
    }
