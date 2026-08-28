from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

from echo_swm.city.anchors import SuzhouAnchors, load_suzhou_anchors
from echo_swm.city.network import MultiLayerCityGraph, build_multiplex_graph


@dataclass(frozen=True)
class CityWorld:
    anchors: SuzhouAnchors
    persons: pa.Table
    households: pa.Table
    institutions: pa.Table
    graph: MultiLayerCityGraph
    od_matrix: NDArray[np.float64]
    transport_capacity: NDArray[np.float64]
    health_capacity: NDArray[np.float64]
    world_version: str = "suzhou-synthetic-world-v1"

    @property
    def prototype_count(self) -> int:
        return self.persons.num_rows

    @property
    def represented_population(self) -> float:
        return float(np.asarray(self.persons["weight"].to_numpy(), dtype=float).sum())


def _allocate_counts(populations: NDArray[np.float64], total: int) -> NDArray[np.int64]:
    raw = populations / populations.sum() * total
    counts = np.floor(raw).astype(np.int64)
    counts[counts == 0] = 1
    remaining = total - int(counts.sum())
    order = np.argsort(-(raw - np.floor(raw)))
    if remaining > 0:
        counts[order[:remaining]] += 1
    elif remaining < 0:
        for index in order[::-1]:
            if remaining == 0:
                break
            if counts[index] > 1:
                counts[index] -= 1
                remaining += 1
    return counts


def _assign_households(
    district_index: NDArray[np.int16], rng: np.random.Generator
) -> tuple[NDArray[np.int64], pa.Table]:
    household_ids = np.empty(district_index.size, dtype=np.int64)
    household_rows: list[dict[str, Any]] = []
    next_household = 0
    for district in np.unique(district_index):
        members = np.flatnonzero(district_index == district)
        cursor = 0
        while cursor < members.size:
            size = int(rng.choice([1, 2, 3, 4, 5, 6], p=[0.16, 0.25, 0.28, 0.20, 0.08, 0.03]))
            chosen = members[cursor : min(cursor + size, members.size)]
            household_ids[chosen] = next_household
            household_rows.append(
                {
                    "household_id": int(next_household),
                    "district_index": int(district),
                    "prototype_members": int(chosen.size),
                    "housing_cost_index": float(np.clip(rng.lognormal(0, 0.25), 0.55, 1.9)),
                    "savings_buffer_months": float(np.clip(rng.gamma(2.2, 2.1), 0, 36)),
                }
            )
            next_household += 1
            cursor += chosen.size
    return household_ids, pa.Table.from_pylist(household_rows)


def _workplace_probabilities(
    anchors: SuzhouAnchors, home: int, employment_weight: NDArray[np.float64]
) -> NDArray[np.float64]:
    home_anchor = anchors.districts[home].anchor
    distances = np.asarray(
        [
            np.hypot(
                (item.anchor.centroid_lat - home_anchor.centroid_lat) * 111,
                (item.anchor.centroid_lon - home_anchor.centroid_lon) * 95,
            )
            for item in anchors.districts
        ],
        dtype=float,
    )
    gravity = employment_weight / np.square(distances + 12)
    gravity[home] *= 5.5
    return gravity / gravity.sum()


def _build_institutions(
    anchors: SuzhouAnchors,
    district_counts: NDArray[np.int64],
    rng: np.random.Generator,
) -> pa.Table:
    rows: list[dict[str, Any]] = []
    metrics = anchors.config.city_metrics
    institution_counts = {
        "district_government": len(anchors.districts),
        "hospital": int(metrics["hospitals"].value),
        "school": int(metrics["schools"].value),
        "firm_prototype": max(800, int(district_counts.sum() / 15)),
        "media": 60,
        "transport_hub": 120,
    }
    district_probability = district_counts / district_counts.sum()
    next_id = 0
    for institution_type, count in institution_counts.items():
        assigned = (
            np.arange(count) % len(anchors.districts)
            if institution_type == "district_government"
            else rng.choice(len(anchors.districts), count, p=district_probability)
        )
        for district in assigned:
            if institution_type == "firm_prototype":
                represented = metrics["registered_enterprises"].value / count
                capacity = float(rng.lognormal(4.0, 1.0))
            elif institution_type == "hospital":
                represented = 1.0
                capacity = metrics["health_workers"].value / count
            elif institution_type == "school":
                represented = 1.0
                capacity = float(rng.lognormal(7.3, 0.45))
            else:
                represented = 1.0
                capacity = float(rng.lognormal(3.5, 0.6))
            rows.append(
                {
                    "institution_id": f"inst_{next_id:06d}",
                    "institution_type": institution_type,
                    "district_index": int(district),
                    "represented_entities": float(represented),
                    "capacity": capacity,
                    "baseline_trust": float(np.clip(rng.normal(0.62, 0.12), 0.1, 0.95)),
                }
            )
            next_id += 1
    return pa.Table.from_pylist(rows)


def build_suzhou_world(
    prototype_count: int = 30_000,
    seed: int = 2026,
    anchors: SuzhouAnchors | None = None,
) -> CityWorld:
    if not 5_000 <= prototype_count <= 250_000:
        raise ValueError("prototype_count must be between 5,000 and 250,000")
    city = anchors or load_suzhou_anchors()
    rng = np.random.default_rng(seed)
    district_populations = np.asarray(
        [district.population_2025 for district in city.districts], dtype=float
    )
    district_counts = _allocate_counts(district_populations, prototype_count)
    district_index = np.repeat(np.arange(len(city.districts), dtype=np.int16), district_counts)
    weights = np.concatenate(
        [
            np.full(count, population / count, dtype=float)
            for count, population in zip(district_counts, district_populations, strict=True)
        ]
    )
    urban_rates = np.asarray(
        [district.anchor.urbanization_2024 for district in city.districts], dtype=float
    )
    urban = np.zeros(prototype_count, dtype=np.int8)
    for district, urban_rate in enumerate(urban_rates):
        members = np.flatnonzero(district_index == district)
        urban_count = round(float(urban_rate) * members.size)
        urban[rng.permutation(members)[:urban_count]] = 1

    age_band = rng.choice(5, prototype_count, p=[0.15, 0.13, 0.34, 0.23, 0.15])
    age_ranges = ((0, 14), (15, 24), (25, 44), (45, 64), (65, 90))
    age = np.asarray(
        [rng.integers(age_ranges[band][0], age_ranges[band][1] + 1) for band in age_band],
        dtype=np.int16,
    )
    sex = rng.binomial(1, 0.493, prototype_count).astype(np.int8)
    hukou_local = rng.binomial(
        1, np.clip(0.54 + 0.09 * (age >= 45) - 0.10 * (district_index == 8), 0.25, 0.85)
    ).astype(np.int8)
    education = np.where(
        age < 16,
        0,
        rng.choice(4, prototype_count, p=[0.18, 0.35, 0.37, 0.10]),
    ).astype(np.int8)
    employment_status = np.full(prototype_count, 2, dtype=np.int8)
    employment_status[age < 16] = 0
    employment_status[(age >= 16) & (age <= 24) & (rng.random(prototype_count) < 0.55)] = 1
    employment_status[age >= 65] = 4
    working_age = (age >= 18) & (age < 65) & (employment_status != 1)
    unemployment_probability = np.clip(0.045 + 0.025 * (education == 0), 0.02, 0.12)
    employment_status[working_age & (rng.random(prototype_count) < unemployment_probability)] = 3
    employed = employment_status == 2

    primary = np.asarray(
        [district.anchor.primary_share for district in city.districts], dtype=float
    )
    secondary = np.asarray(
        [district.anchor.secondary_share for district in city.districts], dtype=float
    )
    sector_draw = rng.random(prototype_count)
    sector = np.where(
        sector_draw < primary[district_index],
        0,
        np.where(sector_draw < primary[district_index] + secondary[district_index], 1, 2),
    ).astype(np.int8)
    sector[~employed] = 3

    gdp_weights = np.asarray([district.gdp_2025_100m for district in city.districts])
    workplace_district = district_index.copy()
    for home in range(len(city.districts)):
        candidates = np.flatnonzero((district_index == home) & employed)
        if candidates.size:
            probability = _workplace_probabilities(city, home, gdp_weights)
            workplace_district[candidates] = rng.choice(
                len(city.districts), candidates.size, p=probability
            )

    district_income_factor = np.asarray(
        [district.gdp_2025_100m / district.population_2025 for district in city.districts]
    )
    district_income_factor /= np.average(district_income_factor, weights=district_populations)
    raw_income = rng.lognormal(10.8, 0.55, prototype_count)
    raw_income *= district_income_factor[district_index]
    raw_income *= np.choose(education, [0.65, 0.82, 1.12, 1.48])
    raw_income *= np.where(employed, 1.0, np.where(employment_status == 4, 0.58, 0.35))
    target_income = city.config.city_metrics["disposable_income_per_capita"].value
    raw_income *= target_income / np.average(raw_income, weights=weights)

    car_probability = np.clip(0.30 + 0.22 * urban + 0.15 * (raw_income > target_income), 0.08, 0.78)
    car_owner = rng.binomial(1, car_probability).astype(np.int8)
    mode_draw = rng.random(prototype_count)
    commute_mode = np.select(
        [
            ~employed,
            mode_draw < 0.38 * car_owner,
            mode_draw < 0.62,
            mode_draw < 0.79,
            mode_draw < 0.93,
        ],
        [0, 1, 2, 3, 4],
        default=5,
    ).astype(np.int8)
    cross_district = workplace_district != district_index
    commute_minutes = np.select(
        [
            commute_mode == 0,
            commute_mode == 1,
            commute_mode == 2,
            commute_mode == 3,
            commute_mode == 4,
        ],
        [0, 31, 38, 45, 24],
        default=18,
    ).astype(float)
    commute_minutes += cross_district * rng.uniform(12, 35, prototype_count)
    commute_minutes = np.clip(commute_minutes + rng.normal(0, 7, prototype_count), 0, 120)

    digital_affinity = np.clip(
        rng.beta(3.2, 1.8, prototype_count) - 0.006 * np.maximum(age - 45, 0), 0, 1
    )
    government_trust = np.clip(rng.beta(4.0, 2.0, prototype_count), 0, 1)
    institutional_trust = np.clip(
        0.55 * government_trust + 0.45 * rng.beta(3.0, 2.2, prototype_count), 0, 1
    )
    risk_aversion = np.clip(rng.beta(2.8, 2.2, prototype_count), 0, 1)
    social_influence = np.clip(rng.beta(2.2, 2.5, prototype_count), 0, 1)
    service_need = np.clip(
        0.15 + 0.45 * (age >= 65) + 0.18 * (age < 10) + rng.normal(0, 0.12, prototype_count),
        0,
        1,
    )
    life_satisfaction = np.clip(
        0.50
        + 0.08 * np.log1p(raw_income / target_income)
        - 0.0015 * commute_minutes
        - 0.10 * (employment_status == 3)
        + rng.normal(0, 0.10, prototype_count),
        0.05,
        0.95,
    )
    household_ids, households = _assign_households(district_index, rng)

    persons = pa.table(
        {
            "person_id": [f"szp_{index:07d}" for index in range(prototype_count)],
            "weight": weights,
            "district_index": district_index,
            "district_id": [city.districts[index].anchor.district_id for index in district_index],
            "household_id": household_ids,
            "urban": urban,
            "age": age,
            "sex": sex,
            "hukou_local": hukou_local,
            "education_level": education,
            "employment_status": employment_status,
            "industry_sector": sector,
            "workplace_district": workplace_district,
            "income_annual": raw_income,
            "car_owner": car_owner,
            "commute_mode": commute_mode,
            "base_commute_minutes": commute_minutes,
            "digital_affinity": digital_affinity,
            "government_trust": government_trust,
            "institutional_trust": institutional_trust,
            "risk_aversion": risk_aversion,
            "social_influence": social_influence,
            "public_service_need": service_need,
            "life_satisfaction": life_satisfaction,
            "data_origin": ["synthetic_prototype"] * prototype_count,
        }
    )
    graph = build_multiplex_graph(
        household_ids,
        district_index.astype(np.int64),
        workplace_district.astype(np.int64),
        sector,
        digital_affinity,
        seed=seed + 101,
    )
    od_matrix = np.zeros((len(city.districts), len(city.districts)), dtype=float)
    np.add.at(
        od_matrix,
        (district_index[employed], workplace_district[employed]),
        weights[employed],
    )
    motorized = np.isin(commute_mode, [1, 2, 3]).astype(float)
    baseline_mobility = np.bincount(
        district_index,
        weights=weights * employed * motorized,
        minlength=len(city.districts),
    )
    transport_capacity = np.maximum(baseline_mobility / 0.78, city.population * 0.01)
    district_health_need = np.bincount(
        district_index,
        weights=weights * service_need * 0.45,
        minlength=len(city.districts),
    )
    health_capacity = np.asarray(district_health_need / 0.68, dtype=np.float64)
    institutions = _build_institutions(city, district_counts, rng)
    return CityWorld(
        anchors=city,
        persons=persons,
        households=households,
        institutions=institutions,
        graph=graph,
        od_matrix=od_matrix,
        transport_capacity=transport_capacity,
        health_capacity=health_capacity,
    )


def validate_city_world(world: CityWorld) -> dict[str, Any]:
    persons = world.persons
    weights = np.asarray(persons["weight"].to_numpy(), dtype=float)
    district_index = np.asarray(persons["district_index"].to_numpy(), dtype=int)
    urban = np.asarray(persons["urban"].to_numpy(), dtype=float)
    income = np.asarray(persons["income_annual"].to_numpy(), dtype=float)
    district_errors: dict[str, float] = {}
    urban_errors: dict[str, float] = {}
    for index, district in enumerate(world.anchors.districts):
        mask = district_index == index
        represented = float(weights[mask].sum())
        district_errors[district.anchor.district_id] = (
            abs(represented - district.population_2025) / district.population_2025
        )
        urban_errors[district.anchor.district_id] = abs(
            float(np.average(urban[mask], weights=weights[mask]))
            - district.anchor.urbanization_2024
        )
    return {
        "prototype_count": persons.num_rows,
        "represented_population": float(weights.sum()),
        "population_relative_error": abs(weights.sum() - world.anchors.population)
        / world.anchors.population,
        "income_relative_error": abs(
            float(np.average(income, weights=weights))
            - world.anchors.config.city_metrics["disposable_income_per_capita"].value
        )
        / world.anchors.config.city_metrics["disposable_income_per_capita"].value,
        "max_district_population_error": max(district_errors.values()),
        "max_district_urbanization_error": max(urban_errors.values()),
        "negative_weight_count": int(np.sum(weights < 0)),
        "household_count": world.households.num_rows,
        "institution_count": world.institutions.num_rows,
        "graph_edges": world.graph.edge_count,
        "od_total_commuters": float(world.od_matrix.sum()),
        "district_population_errors": district_errors,
        "district_urbanization_errors": urban_errors,
    }
