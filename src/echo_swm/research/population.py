from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from echo_swm.core.config import Settings
from echo_swm.core.ids import file_hash, stable_hash
from echo_swm.personas.definitions import organization_type_for
from echo_swm.research.contracts import AgentTier, PopulationSpec

POPULATION_VERSION = "human-digital-twin-population-v3"
GRAPH_VERSION = "multiplex-social-graph-v1"
RELATIONSHIP_TYPES = ("family", "acquaintance", "coworker", "community", "online")
SUPPORTED_FILTERS = {
    "age_group",
    "education_level",
    "primary_channel",
    "region_type",
    "social_role",
}

BIG_FIVE_DIMENSIONS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)
SCHWARTZ_DIMENSIONS = (
    "self_direction",
    "stimulation",
    "achievement",
    "power",
    "security",
    "conformity",
    "tradition",
    "benevolence",
    "universalism",
    "hedonism",
)
MORAL_DIMENSIONS = ("care", "fairness", "loyalty", "authority", "purity", "liberty")
RISK_DIMENSIONS = ("financial", "social", "technology", "health")
COGNITIVE_DIMENSIONS = (
    "analytical_intuitive",
    "independent_social",
    "long_short_term",
    "evidence_experience",
)
GOAL_DIMENSIONS = (
    "security",
    "achievement",
    "status",
    "belonging",
    "growth",
    "meaning",
    "survival",
)
BELIEF_DIMENSIONS = (
    "technology",
    "economic_outlook",
    "brand_trust",
    "institutional_trust",
    "social_attitude",
)


@dataclass(frozen=True)
class SocialGraph:
    source: NDArray[np.int64]
    target: NDArray[np.int64]
    strength: NDArray[np.float64]
    trust: NDArray[np.float64]
    relationship_type: NDArray[np.object_]

    @property
    def edge_count(self) -> int:
        return int(self.source.size)

    def aggregate_from_sources(
        self,
        values: NDArray[np.float64],
        node_count: int,
        *,
        trust: NDArray[np.float64] | None = None,
    ) -> NDArray[np.float64]:
        active_trust = self.trust if trust is None else trust
        weights = self.strength * active_trust
        numerator = np.zeros(node_count, dtype=float)
        denominator = np.zeros(node_count, dtype=float)
        np.add.at(numerator, self.target, weights * values[self.source])
        np.add.at(denominator, self.target, weights)
        return np.divide(
            numerator,
            denominator,
            out=np.zeros(node_count, dtype=float),
            where=denominator > 0,
        )


@dataclass(frozen=True)
class ResearchPopulation:
    spec: PopulationSpec
    agents: pa.Table
    graph: SocialGraph
    manifest: dict[str, Any]


def population_root(settings: Settings) -> Path:
    return settings.artifact_dir / "research" / "populations"


def _sigmoid(value: NDArray[np.float64]) -> NDArray[np.float64]:
    return 1 / (1 + np.exp(-value))


def _stable_agent_id(spec: PopulationSpec, index: int) -> str:
    digest = hashlib.sha256(
        f"{POPULATION_VERSION}:{spec.population_id}:{spec.seed}:{index}".encode()
    ).hexdigest()
    return f"agent_{digest[:16]}"


def _filtered_choice(
    rng: np.random.Generator,
    spec: PopulationSpec,
    field: str,
    values: list[str],
    probabilities: list[float],
    size: int,
) -> NDArray[np.object_]:
    requested = spec.filters.get(field)
    selected_values = values
    selected_probabilities = np.asarray(probabilities, dtype=float)
    if requested is not None:
        unknown = sorted(set(requested) - set(values))
        if unknown:
            raise ValueError(f"unsupported {field} filter values: {unknown}")
        indices = [values.index(item) for item in requested]
        selected_values = [values[index] for index in indices]
        selected_probabilities = selected_probabilities[indices]
    selected_probabilities /= selected_probabilities.sum()
    return np.asarray(
        rng.choice(selected_values, size=size, p=selected_probabilities),
        dtype=object,
    )


def _household_ids(rng: np.random.Generator, size: int) -> NDArray[np.object_]:
    order = rng.permutation(size)
    result = np.empty(size, dtype=object)
    cursor = 0
    household_index = 0
    while cursor < size:
        household_size = int(rng.choice([1, 2, 3, 4, 5], p=[0.17, 0.3, 0.27, 0.18, 0.08]))
        members = order[cursor : min(size, cursor + household_size)]
        result[members] = f"household_{household_index:06d}"
        cursor += household_size
        household_index += 1
    return result


def _assign_tiers(influence: NDArray[np.float64]) -> NDArray[np.object_]:
    size = influence.size
    order = np.argsort(-influence, kind="stable")
    tiers = np.full(size, AgentTier.BACKGROUND.value, dtype=object)
    tiers[order[:50]] = AgentTier.KEY.value
    representative_end = min(size, 500)
    tiers[order[50:representative_end]] = AgentTier.REPRESENTATIVE.value
    return tiers


def _make_agents(spec: PopulationSpec) -> pa.Table:
    unsupported = sorted(set(spec.filters) - SUPPORTED_FILTERS)
    if unsupported:
        raise ValueError(f"unsupported population filters: {unsupported}")
    rng = np.random.default_rng(spec.seed)
    size = spec.size
    age_group = _filtered_choice(
        rng,
        spec,
        "age_group",
        ["18-24", "25-34", "35-44", "45-59", "60+"],
        [0.14, 0.23, 0.22, 0.25, 0.16],
        size,
    )
    age_ranges = {
        "18-24": (18, 25),
        "25-34": (25, 35),
        "35-44": (35, 45),
        "45-59": (45, 60),
        "60+": (60, 79),
    }
    ages = np.asarray(
        [rng.integers(*age_ranges[str(group)]) for group in age_group],
        dtype=np.int64,
    )
    gender = np.asarray(
        rng.choice(
            ["female", "male", "non_binary", "undisclosed"],
            size=size,
            p=[0.493, 0.493, 0.006, 0.008],
        ),
        dtype=object,
    )
    education = _filtered_choice(
        rng,
        spec,
        "education_level",
        ["secondary_or_below", "vocational", "undergraduate", "postgraduate"],
        [0.25, 0.24, 0.42, 0.09],
        size,
    )
    social_role = _filtered_choice(
        rng,
        spec,
        "social_role",
        [
            "student",
            "professional",
            "service_worker",
            "skilled_worker",
            "caregiver",
            "self_employed",
            "retired",
            "job_seeker",
        ],
        [0.1, 0.23, 0.18, 0.15, 0.08, 0.12, 0.09, 0.05],
        size,
    )
    region_type = _filtered_choice(
        rng,
        spec,
        "region_type",
        ["urban_core", "suburban", "town", "rural"],
        [0.34, 0.29, 0.22, 0.15],
        size,
    )
    household_type = np.asarray(
        rng.choice(
            ["single", "couple", "with_children", "multigenerational", "shared"],
            size=size,
            p=[0.18, 0.21, 0.34, 0.19, 0.08],
        ),
        dtype=object,
    )
    household_id = _household_ids(rng, size)

    common = rng.normal(0, 1, size=(size, 1))
    independent = rng.normal(0, 1, size=(size, 5))
    traits = _sigmoid(0.35 * common + 0.9 * independent)
    openness, conscientiousness, extraversion, agreeableness, emotional_sensitivity = (
        traits[:, index] for index in range(5)
    )
    neuroticism = emotional_sensitivity
    value_noise = rng.normal(0, 0.7, size=(size, 6))
    care = _sigmoid(0.8 * (agreeableness - 0.5) + value_noise[:, 0])
    fairness = _sigmoid(0.6 * (agreeableness - 0.5) + value_noise[:, 1])
    security = _sigmoid(0.7 * (conscientiousness - 0.5) + value_noise[:, 2])
    tradition = _sigmoid(-0.65 * (openness - 0.5) + value_noise[:, 3])
    autonomy = _sigmoid(0.75 * (openness - 0.5) + value_noise[:, 4])
    community = _sigmoid(0.5 * (agreeableness + extraversion - 1) + value_noise[:, 5])

    schwartz_noise = rng.normal(0, 0.45, size=(size, len(SCHWARTZ_DIMENSIONS)))
    schwartz_self_direction = _sigmoid(
        1.35 * (openness - 0.5) + 0.55 * (autonomy - 0.5) + schwartz_noise[:, 0]
    )
    schwartz_stimulation = _sigmoid(
        1.0 * (openness - 0.5) + 0.75 * (extraversion - 0.5) + schwartz_noise[:, 1]
    )
    schwartz_achievement = _sigmoid(
        1.2 * (conscientiousness - 0.5) + 0.4 * (extraversion - 0.5) + schwartz_noise[:, 2]
    )
    schwartz_power = _sigmoid(
        0.75 * (extraversion - 0.5) - 0.45 * (agreeableness - 0.5) + schwartz_noise[:, 3]
    )
    schwartz_security = np.clip(0.6 * security + 0.4 * _sigmoid(schwartz_noise[:, 4]), 0, 1)
    schwartz_conformity = _sigmoid(
        0.7 * (conscientiousness - 0.5)
        + 0.45 * (agreeableness - 0.5)
        - 0.35 * (openness - 0.5)
        + schwartz_noise[:, 5]
    )
    schwartz_tradition = np.clip(0.68 * tradition + 0.32 * _sigmoid(schwartz_noise[:, 6]), 0, 1)
    schwartz_benevolence = np.clip(
        0.48 * care + 0.32 * community + 0.2 * _sigmoid(schwartz_noise[:, 7]), 0, 1
    )
    schwartz_universalism = np.clip(
        0.45 * fairness
        + 0.3 * care
        + 0.25 * _sigmoid(0.5 * (openness - 0.5) + schwartz_noise[:, 8]),
        0,
        1,
    )
    schwartz_hedonism = _sigmoid(
        0.55 * (extraversion - 0.5) + 0.4 * (openness - 0.5) + schwartz_noise[:, 9]
    )

    moral_noise = rng.normal(0, 0.32, size=(size, len(MORAL_DIMENSIONS)))
    moral_care = np.clip(0.82 * care + 0.18 * _sigmoid(moral_noise[:, 0]), 0, 1)
    moral_fairness = np.clip(0.82 * fairness + 0.18 * _sigmoid(moral_noise[:, 1]), 0, 1)
    moral_loyalty = np.clip(
        0.48 * community + 0.34 * tradition + 0.18 * _sigmoid(moral_noise[:, 2]), 0, 1
    )
    moral_authority = np.clip(
        0.42 * security + 0.36 * tradition + 0.22 * _sigmoid(moral_noise[:, 3]),
        0,
        1,
    )
    moral_purity = np.clip(
        0.42 * conscientiousness + 0.34 * tradition + 0.24 * _sigmoid(moral_noise[:, 4]),
        0,
        1,
    )
    moral_liberty = np.clip(
        0.56 * autonomy + 0.26 * openness + 0.18 * _sigmoid(moral_noise[:, 5]),
        0,
        1,
    )

    risk_preference = np.clip(
        0.2 + 0.58 * openness - 0.2 * emotional_sensitivity + rng.normal(0, 0.12, size),
        0,
        1,
    )
    social_trust = np.clip(0.18 + 0.54 * agreeableness + rng.normal(0, 0.14, size), 0, 1)
    institutional_trust = np.clip(
        0.2 + 0.36 * conscientiousness + 0.18 * security + rng.normal(0, 0.16, size),
        0,
        1,
    )
    expression_tendency = np.clip(
        0.08 + 0.7 * extraversion + 0.15 * openness + rng.normal(0, 0.12, size),
        0,
        1,
    )
    action_tendency = np.clip(
        0.08 + 0.48 * conscientiousness + 0.25 * extraversion + rng.normal(0, 0.13, size),
        0,
        1,
    )
    information_skepticism = np.clip(
        0.58 - 0.28 * social_trust + 0.18 * openness + rng.normal(0, 0.12, size),
        0,
        1,
    )

    risk_financial = np.clip(
        risk_preference + 0.12 * (schwartz_achievement - 0.5) + rng.normal(0, 0.08, size),
        0,
        1,
    )
    risk_social = np.clip(
        0.58 * risk_preference
        + 0.3 * extraversion
        - 0.18 * neuroticism
        + rng.normal(0, 0.08, size),
        0,
        1,
    )
    risk_technology = np.clip(
        0.5 * risk_preference
        + 0.42 * openness
        - 0.12 * information_skepticism
        + rng.normal(0, 0.08, size),
        0,
        1,
    )
    risk_health = np.clip(
        0.42 * risk_preference
        + 0.25 * conscientiousness
        - 0.28 * neuroticism
        + rng.normal(0, 0.08, size),
        0,
        1,
    )
    cognitive_analytical_intuitive = np.clip(
        1.25 * (conscientiousness - 0.5) + 0.75 * (openness - 0.5) + rng.normal(0, 0.28, size),
        -1,
        1,
    )
    cognitive_independent_social = np.clip(
        1.2 * (autonomy - 0.5) - 0.55 * (agreeableness - 0.5) + rng.normal(0, 0.28, size),
        -1,
        1,
    )
    cognitive_long_short_term = np.clip(
        1.35 * (conscientiousness - 0.5) + 0.45 * (security - 0.5) + rng.normal(0, 0.28, size),
        -1,
        1,
    )
    cognitive_evidence_experience = np.clip(
        1.0 * (openness - 0.5)
        + 0.7 * (conscientiousness - 0.5)
        + 0.35 * (information_skepticism - 0.5)
        + rng.normal(0, 0.28, size),
        -1,
        1,
    )

    goal_security = np.clip(0.52 * schwartz_security + 0.26 * neuroticism + 0.22 * security, 0, 1)
    goal_achievement = np.clip(
        0.58 * schwartz_achievement + 0.26 * conscientiousness + 0.16 * autonomy, 0, 1
    )
    goal_status = np.clip(
        0.64 * schwartz_power + 0.22 * extraversion + 0.14 * schwartz_achievement, 0, 1
    )
    goal_belonging = np.clip(
        0.48 * community + 0.32 * agreeableness + 0.2 * schwartz_benevolence, 0, 1
    )
    goal_growth = np.clip(
        0.48 * openness + 0.34 * schwartz_self_direction + 0.18 * schwartz_stimulation, 0, 1
    )
    goal_meaning = np.clip(
        0.4 * schwartz_universalism + 0.32 * moral_care + 0.28 * schwartz_benevolence, 0, 1
    )
    goal_survival = np.clip(
        0.5 * neuroticism + 0.32 * schwartz_security + 0.18 * (1 - risk_health), 0, 1
    )
    goal_matrix = np.column_stack(
        [
            goal_security,
            goal_achievement,
            goal_status,
            goal_belonging,
            goal_growth,
            goal_meaning,
            goal_survival,
        ]
    )

    belief_technology = np.clip(
        0.46 * openness + 0.34 * risk_technology + 0.2 * (1 - information_skepticism), 0, 1
    )
    belief_economic_outlook = np.clip(
        0.38 * institutional_trust
        + 0.26 * risk_financial
        + 0.2 * conscientiousness
        + rng.normal(0.08, 0.1, size),
        0,
        1,
    )
    belief_brand_trust = np.clip(
        0.42 * social_trust
        + 0.28 * agreeableness
        + 0.18 * (1 - information_skepticism)
        + rng.normal(0, 0.1, size),
        0,
        1,
    )
    belief_institutional_trust = institutional_trust.copy()
    belief_social_attitude = np.clip(
        0.4 * agreeableness + 0.34 * community + 0.26 * schwartz_universalism, 0, 1
    )
    belief_confidence = np.clip(
        0.42
        + 0.28 * np.abs(cognitive_evidence_experience)
        + 0.18 * conscientiousness
        - 0.16 * neuroticism,
        0.1,
        0.95,
    )

    channel_matrix = rng.dirichlet([2.2, 1.8, 1.5, 1.4, 1.1], size=size)
    channel_names = ["social_media", "news", "interpersonal", "community", "search"]
    primary_channel = np.asarray(
        [channel_names[index] for index in np.argmax(channel_matrix, axis=1)], dtype=object
    )
    requested_channels = spec.filters.get("primary_channel")
    if requested_channels is not None:
        unknown_channels = sorted(set(requested_channels) - set(channel_names))
        if unknown_channels:
            raise ValueError(f"unsupported primary_channel filter values: {unknown_channels}")
        primary_channel = np.asarray(rng.choice(requested_channels, size=size), dtype=object)
        for index, channel in enumerate(primary_channel):
            channel_matrix[index, channel_names.index(str(channel))] += 1.4
        channel_matrix /= channel_matrix.sum(axis=1, keepdims=True)

    interest_names = ["daily_life", "technology", "culture", "health", "community", "learning"]
    primary_goal = np.asarray(
        [GOAL_DIMENSIONS[index] for index in np.argmax(goal_matrix, axis=1)], dtype=object
    )
    primary_interest = np.asarray(rng.choice(interest_names, size=size), dtype=object)
    influence = np.clip(
        0.34 * expression_tendency
        + 0.25 * action_tendency
        + 0.18 * extraversion
        + 0.13 * social_trust
        + 0.1 * (1 - information_skepticism),
        0,
        1,
    )
    tier = _assign_tiers(influence)
    origin_payload = json.dumps(
        {
            "demographics": "synthetic",
            "social_role": "synthetic",
            "organization_type": "synthetic",
            "personality": "synthetic_correlated_vector",
            "values": "synthetic_correlated_vector",
            "moral_foundations": "synthetic_correlated_vector",
            "risk_and_cognition": "synthetic_correlated_vector",
            "goals_and_interests": "synthetic_correlated_vector",
            "media_habits": "synthetic",
            "dynamic_state": "synthetic",
            "memory": "synthetic",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    agent_ids = [_stable_agent_id(spec, index) for index in range(size)]
    organization_type = np.asarray(
        [organization_type_for(str(role), index) for index, role in enumerate(social_role)],
        dtype=object,
    )
    profile_hashes = [
        stable_hash(
            {
                "agent_id": agent_ids[index],
                "age": int(ages[index]),
                "role": str(social_role[index]),
                "organization_type": str(organization_type[index]),
                "traits": [round(float(value), 8) for value in traits[index]],
                "values": [
                    round(float(array[index]), 8)
                    for array in (care, fairness, security, tradition, autonomy, community)
                ],
                "schwartz_values": [
                    round(float(array[index]), 8)
                    for array in (
                        schwartz_self_direction,
                        schwartz_stimulation,
                        schwartz_achievement,
                        schwartz_power,
                        schwartz_security,
                        schwartz_conformity,
                        schwartz_tradition,
                        schwartz_benevolence,
                        schwartz_universalism,
                        schwartz_hedonism,
                    )
                ],
                "moral_foundations": [
                    round(float(array[index]), 8)
                    for array in (
                        moral_care,
                        moral_fairness,
                        moral_loyalty,
                        moral_authority,
                        moral_purity,
                        moral_liberty,
                    )
                ],
                "goals": [round(float(value), 8) for value in goal_matrix[index]],
                "risk": [
                    round(float(array[index]), 8)
                    for array in (
                        risk_preference,
                        risk_financial,
                        risk_social,
                        risk_technology,
                        risk_health,
                    )
                ],
                "cognitive": [
                    round(float(array[index]), 8)
                    for array in (
                        cognitive_analytical_intuitive,
                        cognitive_independent_social,
                        cognitive_long_short_term,
                        cognitive_evidence_experience,
                    )
                ],
                "beliefs": [
                    round(float(array[index]), 8)
                    for array in (
                        belief_technology,
                        belief_economic_outlook,
                        belief_brand_trust,
                        belief_institutional_trust,
                        belief_social_attitude,
                        belief_confidence,
                    )
                ],
                "information_behavior": [
                    round(float(array[index]), 8)
                    for array in (
                        social_trust,
                        institutional_trust,
                        information_skepticism,
                        expression_tendency,
                        action_tendency,
                        influence,
                    )
                ],
                "channels": [round(float(value), 8) for value in channel_matrix[index]],
            }
        )
        for index in range(size)
    ]
    rows: dict[str, Any] = {
        "agent_index": np.arange(size, dtype=np.int64),
        "agent_id": agent_ids,
        "source_id": [f"synthetic:{spec.population_id}"] * size,
        "profile_origin": ["synthetic"] * size,
        "field_origins": [origin_payload] * size,
        "profile_hash": profile_hashes,
        "survey_weight": np.ones(size, dtype=float),
        "tier": tier.tolist(),
        "age": ages,
        "age_group": age_group.tolist(),
        "gender": gender.tolist(),
        "education_level": education.tolist(),
        "social_role": social_role.tolist(),
        "organization_type": organization_type.tolist(),
        "region_type": region_type.tolist(),
        "household_type": household_type.tolist(),
        "household_id": household_id.tolist(),
        "segment": [f"{age_group[index]} · {region_type[index]}" for index in range(size)],
        "openness": openness,
        "conscientiousness": conscientiousness,
        "extraversion": extraversion,
        "agreeableness": agreeableness,
        "emotional_sensitivity": emotional_sensitivity,
        "neuroticism": neuroticism,
        "big5_openness": openness,
        "big5_conscientiousness": conscientiousness,
        "big5_extraversion": extraversion,
        "big5_agreeableness": agreeableness,
        "big5_neuroticism": neuroticism,
        "value_care": care,
        "value_fairness": fairness,
        "value_security": security,
        "value_tradition": tradition,
        "value_autonomy": autonomy,
        "value_community": community,
        "schwartz_self_direction": schwartz_self_direction,
        "schwartz_stimulation": schwartz_stimulation,
        "schwartz_achievement": schwartz_achievement,
        "schwartz_power": schwartz_power,
        "schwartz_security": schwartz_security,
        "schwartz_conformity": schwartz_conformity,
        "schwartz_tradition": schwartz_tradition,
        "schwartz_benevolence": schwartz_benevolence,
        "schwartz_universalism": schwartz_universalism,
        "schwartz_hedonism": schwartz_hedonism,
        "moral_care": moral_care,
        "moral_fairness": moral_fairness,
        "moral_loyalty": moral_loyalty,
        "moral_authority": moral_authority,
        "moral_purity": moral_purity,
        "moral_liberty": moral_liberty,
        "primary_goal": primary_goal.tolist(),
        "goal_security": goal_security,
        "goal_achievement": goal_achievement,
        "goal_status": goal_status,
        "goal_belonging": goal_belonging,
        "goal_growth": goal_growth,
        "goal_meaning": goal_meaning,
        "goal_survival": goal_survival,
        "primary_interest": primary_interest.tolist(),
        "risk_preference": risk_preference,
        "risk_financial": risk_financial,
        "risk_social": risk_social,
        "risk_technology": risk_technology,
        "risk_health": risk_health,
        "cognitive_analytical_intuitive": cognitive_analytical_intuitive,
        "cognitive_independent_social": cognitive_independent_social,
        "cognitive_long_short_term": cognitive_long_short_term,
        "cognitive_evidence_experience": cognitive_evidence_experience,
        "social_trust": social_trust,
        "institutional_trust": institutional_trust,
        "expression_tendency": expression_tendency,
        "action_tendency": action_tendency,
        "information_skepticism": information_skepticism,
        "belief_technology": belief_technology,
        "belief_economic_outlook": belief_economic_outlook,
        "belief_brand_trust": belief_brand_trust,
        "belief_institutional_trust": belief_institutional_trust,
        "belief_social_attitude": belief_social_attitude,
        "belief_confidence": belief_confidence,
        "channel_social_media": channel_matrix[:, 0],
        "channel_news": channel_matrix[:, 1],
        "channel_interpersonal": channel_matrix[:, 2],
        "channel_community": channel_matrix[:, 3],
        "channel_search": channel_matrix[:, 4],
        "primary_channel": primary_channel.tolist(),
        "influence": influence,
        "baseline_emotion_valence": np.zeros(size, dtype=float),
        "baseline_emotion_arousal": np.full(size, 0.08, dtype=float),
        "baseline_stress": np.clip(0.22 + 0.38 * neuroticism, 0, 1),
        "baseline_confidence": belief_confidence,
        "baseline_interest": np.clip(0.25 + 0.38 * openness, 0, 1),
        "baseline_intention": np.clip(0.18 + 0.45 * action_tendency, 0, 1),
        "baseline_awareness": np.full(size, 0.025, dtype=float),
        "working_memory_count": np.zeros(size, dtype=np.int64),
        "event_memory_count": np.zeros(size, dtype=np.int64),
        "long_term_memory_ref": [f"memory://{agent_id}/long-term" for agent_id in agent_ids],
    }
    return pa.table(rows)


def _group_indices(values: NDArray[np.object_]) -> dict[str, NDArray[np.int64]]:
    return {
        str(value): np.flatnonzero(values == value).astype(np.int64) for value in np.unique(values)
    }


def _select_target(
    rng: np.random.Generator,
    source: int,
    pool: NDArray[np.int64],
    size: int,
) -> int:
    if pool.size > 1:
        target = int(rng.choice(pool))
        if target != source:
            return target
        alternatives = pool[pool != source]
        if alternatives.size:
            return int(rng.choice(alternatives))
    offset = int(rng.integers(1, size))
    return (source + offset) % size


def _make_graph(agents: pa.Table, seed: int) -> SocialGraph:
    rng = np.random.default_rng(seed + 17_711)
    size = agents.num_rows
    household = np.asarray(agents["household_id"].to_pylist(), dtype=object)
    role = np.asarray(agents["social_role"].to_pylist(), dtype=object)
    region = np.asarray(agents["region_type"].to_pylist(), dtype=object)
    age_group = np.asarray(agents["age_group"].to_pylist(), dtype=object)
    channel = np.asarray(agents["primary_channel"].to_pylist(), dtype=object)
    pools = {
        "family": _group_indices(household),
        "coworker": _group_indices(role),
        "community": _group_indices(region),
        "acquaintance": _group_indices(age_group),
        "online": _group_indices(channel),
    }
    values_by_type = {
        "family": household,
        "coworker": role,
        "community": region,
        "acquaintance": age_group,
        "online": channel,
    }
    source = np.repeat(np.arange(size, dtype=np.int64), len(RELATIONSHIP_TYPES))
    target = np.empty(source.size, dtype=np.int64)
    strength = np.empty(source.size, dtype=float)
    trust = np.empty(source.size, dtype=float)
    relationship_type = np.empty(source.size, dtype=object)
    beta_parameters = {
        "family": ((5.0, 1.7), (5.5, 1.5)),
        "acquaintance": ((2.4, 3.1), (2.6, 2.8)),
        "coworker": ((3.1, 2.5), (3.2, 2.4)),
        "community": ((2.8, 2.7), (2.9, 2.6)),
        "online": ((2.0, 3.4), (2.1, 3.2)),
    }
    for source_index in range(size):
        for type_index, edge_type in enumerate(RELATIONSHIP_TYPES):
            edge_index = source_index * len(RELATIONSHIP_TYPES) + type_index
            group_value = str(values_by_type[edge_type][source_index])
            pool = pools[edge_type][group_value]
            target[edge_index] = _select_target(rng, source_index, pool, size)
            strength_beta, trust_beta = beta_parameters[edge_type]
            strength[edge_index] = float(rng.beta(*strength_beta))
            trust[edge_index] = float(rng.beta(*trust_beta))
            relationship_type[edge_index] = edge_type
    return SocialGraph(source, target, strength, trust, relationship_type)


def validate_population(population: ResearchPopulation) -> dict[str, Any]:
    agents = population.agents
    graph = population.graph
    agent_ids = agents["agent_id"].to_pylist()
    tiers = np.asarray(agents["tier"].to_pylist(), dtype=object)
    outgoing = np.bincount(graph.source, minlength=agents.num_rows)
    tier_counts = {tier.value: int(np.sum(tiers == tier.value)) for tier in AgentTier}
    expected_representative = min(450, agents.num_rows - 50)
    checks = {
        "minimum_agent_count": agents.num_rows >= 5_000,
        "unique_stable_ids": len(agent_ids) == len(set(agent_ids)),
        "profile_hashes_present": agents["profile_hash"].null_count == 0,
        "memory_references_present": agents["long_term_memory_ref"].null_count == 0,
        "all_agents_have_relationships": bool(np.all(outgoing >= len(RELATIONSHIP_TYPES))),
        "all_relationship_types_present": set(graph.relationship_type.tolist())
        == set(RELATIONSHIP_TYPES),
        "key_tier_exact": tier_counts[AgentTier.KEY.value] == 50,
        "representative_tier_exact": tier_counts[AgentTier.REPRESENTATIVE.value]
        == expected_representative,
        "background_tier_exact": tier_counts[AgentTier.BACKGROUND.value]
        == agents.num_rows - 50 - expected_representative,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "agent_count": agents.num_rows,
        "relationship_count": graph.edge_count,
        "tier_counts": tier_counts,
    }


def save_population(population: ResearchPopulation, settings: Settings) -> Path:
    directory = population_root(settings) / population.spec.population_id
    directory.mkdir(parents=True, exist_ok=True)
    agents_path = directory / "agents.parquet"
    relationships_path = directory / "relationships.parquet"
    pq.write_table(population.agents, agents_path, compression="zstd")
    relationship_table = pa.table(
        {
            "source": population.graph.source,
            "target": population.graph.target,
            "strength": population.graph.strength,
            "trust": population.graph.trust,
            "relationship_type": population.graph.relationship_type.tolist(),
        }
    )
    pq.write_table(relationship_table, relationships_path, compression="zstd")
    manifest = {
        **population.manifest,
        "artifacts": {
            "agents.parquet": file_hash(agents_path),
            "relationships.parquet": file_hash(relationships_path),
        },
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return directory


def generate_population(
    spec: PopulationSpec,
    settings: Settings | None = None,
    *,
    persist: bool = True,
) -> ResearchPopulation:
    agents = _make_agents(spec)
    graph = _make_graph(agents, spec.seed)
    provisional = ResearchPopulation(spec=spec, agents=agents, graph=graph, manifest={})
    validation = validate_population(provisional)
    if not validation["valid"]:
        raise ValueError(f"generated population failed validation: {validation['checks']}")
    technical_fields = {
        "agent_id",
        "profile_hash",
        "long_term_memory_ref",
        "working_memory_count",
        "event_memory_count",
    }
    demographic_fields = {
        "age",
        "age_group",
        "gender",
        "education_level",
        "social_role",
        "region_type",
        "household_type",
        "household_id",
        "primary_channel",
    }
    field_provenance = {
        field: {
            "source_dataset": "stable_synthetic_population_prior_v2",
            "source_type": "generated",
            "measurement_year": None,
            "sample_weight_field": "survey_weight",
            "confidence_level": (
                1.0 if field in technical_fields else 0.45 if field in demographic_fields else 0.35
            ),
            "update_rule": "seeded_structural_generation",
            "missing_flag": False,
        }
        for field in agents.column_names
    }
    edge_provenance = {
        relationship_type: {
            "source_dataset": "multiplex_social_graph_prior_v1",
            "source_type": "generated",
            "confidence_level": 0.3,
            "update_rule": "seeded_homophily_and_relationship_prior",
            "observed_edge": False,
        }
        for relationship_type in RELATIONSHIP_TYPES
    }
    manifest = {
        "population_id": spec.population_id,
        "population_version": POPULATION_VERSION,
        "graph_version": GRAPH_VERSION,
        "spec": spec.model_dump(mode="json"),
        "profile_signature": stable_hash(agents["profile_hash"].to_pylist()),
        "validation": validation,
        "data_origin": "synthetic",
        "field_provenance": field_provenance,
        "edge_provenance": edge_provenance,
        "missingness_policy": "preserve_missing_and_never_autofill_with_llm",
        "limitations": [
            "This population is synthetic and is not a copy of identifiable real people.",
            (
                "Population filters define the simulated target group; "
                "they do not prove representativeness."
            ),
        ],
    }
    population = ResearchPopulation(spec=spec, agents=agents, graph=graph, manifest=manifest)
    if persist:
        save_population(population, settings or Settings.load())
    return population


def load_population(population_id: str, settings: Settings) -> ResearchPopulation:
    directory = population_root(settings) / population_id
    manifest_path = directory / "manifest.json"
    agents_path = directory / "agents.parquet"
    relationships_path = directory / "relationships.parquet"
    if not manifest_path.exists() or not agents_path.exists() or not relationships_path.exists():
        raise FileNotFoundError(f"population not found: {population_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if file_hash(agents_path) != manifest["artifacts"]["agents.parquet"]:
        raise ValueError("population agent artifact hash mismatch")
    if file_hash(relationships_path) != manifest["artifacts"]["relationships.parquet"]:
        raise ValueError("population relationship artifact hash mismatch")
    agents = pq.read_table(agents_path)
    relationships = pq.read_table(relationships_path)
    graph = SocialGraph(
        source=np.asarray(relationships["source"], dtype=np.int64),
        target=np.asarray(relationships["target"], dtype=np.int64),
        strength=np.asarray(relationships["strength"], dtype=float),
        trust=np.asarray(relationships["trust"], dtype=float),
        relationship_type=np.asarray(relationships["relationship_type"].to_pylist(), dtype=object),
    )
    population = ResearchPopulation(
        spec=PopulationSpec.model_validate(manifest["spec"]),
        agents=agents,
        graph=graph,
        manifest=manifest,
    )
    validation = validate_population(population)
    if not validation["valid"]:
        raise ValueError(f"stored population failed validation: {validation['checks']}")
    return population
