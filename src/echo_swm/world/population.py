from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from echo_swm.core.ids import stable_hash
from echo_swm.research.contracts import AgentTier, PopulationSpec
from echo_swm.research.population import (
    BELIEF_DIMENSIONS,
    BIG_FIVE_DIMENSIONS,
    COGNITIVE_DIMENSIONS,
    GOAL_DIMENSIONS,
    MORAL_DIMENSIONS,
    RISK_DIMENSIONS,
    SCHWARTZ_DIMENSIONS,
    ResearchPopulation,
    generate_population,
)
from echo_swm.world.contracts import LocationSpec, LocationType, WorldSpec

RELATIONSHIP_TYPES = ("family", "friend", "coworker", "follower", "authority", "community")


@dataclass(frozen=True)
class WorldGraph:
    source: NDArray[np.int64]
    target: NDArray[np.int64]
    relation_type: NDArray[np.object_]
    strength: NDArray[np.float64]
    trust: NDArray[np.float64]
    similarity: NDArray[np.float64]
    influence: NDArray[np.float64]
    frequency: NDArray[np.float64]
    channel: NDArray[np.object_]
    graph_version: str = "human-relational-multiplex-v2"

    @property
    def edge_count(self) -> int:
        return int(self.source.size)

    @property
    def content_hash(self) -> str:
        return stable_hash(
            {
                "source": self.source.tolist(),
                "target": self.target.tolist(),
                "relation_type": self.relation_type.tolist(),
                "strength": np.round(self.strength, 8).tolist(),
                "trust": np.round(self.trust, 8).tolist(),
                "similarity": np.round(self.similarity, 8).tolist(),
                "influence": np.round(self.influence, 8).tolist(),
                "frequency": np.round(self.frequency, 8).tolist(),
                "channel": self.channel.tolist(),
            }
        )

    def aggregate_from_sources(
        self,
        values: NDArray[np.float64],
        node_count: int,
        *,
        trust: NDArray[np.float64] | None = None,
        source_activity: NDArray[np.float64] | None = None,
        edge_mask: NDArray[np.bool_] | None = None,
        normalize_active_sources: bool = True,
        fallback: float = 0.0,
    ) -> NDArray[np.float64]:
        if values.shape != (node_count,):
            raise ValueError("value vector does not match world graph node count")
        active_trust = self.trust if trust is None else trust
        if active_trust.shape != self.trust.shape:
            raise ValueError("dynamic trust vector does not match world graph")
        activity = np.ones(node_count, dtype=float) if source_activity is None else source_activity
        if activity.shape != (node_count,):
            raise ValueError("source activity vector does not match world graph node count")
        selected: NDArray[np.float64] = np.ones(self.edge_count, dtype=float)
        if edge_mask is not None:
            if edge_mask.shape != (self.edge_count,):
                raise ValueError("edge mask does not match world graph")
            selected = np.asarray(edge_mask, dtype=float).reshape(self.edge_count)
        frequency_weight = np.log1p(self.frequency) / np.log(31.0)
        base_edge_weight = (
            self.strength
            * active_trust
            * (0.35 + 0.65 * self.similarity)
            * (0.35 + 0.65 * self.influence)
            * frequency_weight
            * selected
        )
        signal_weight = base_edge_weight * activity[self.source]
        numerator = np.zeros(node_count, dtype=float)
        denominator = np.zeros(node_count, dtype=float)
        np.add.at(numerator, self.target, signal_weight * values[self.source])
        denominator_weight = signal_weight if normalize_active_sources else base_edge_weight
        np.add.at(denominator, self.target, denominator_weight)
        return np.divide(
            numerator,
            denominator,
            out=np.full(node_count, fallback, dtype=float),
            where=denominator > 0,
        )


@dataclass(frozen=True)
class WorldPopulation:
    base: ResearchPopulation
    weights: NDArray[np.float64]
    graph: WorldGraph
    locations: tuple[LocationSpec, ...]
    home_location: NDArray[np.int64]
    primary_location: NDArray[np.int64]
    social_location: NDArray[np.int64]
    transit_location: int
    online_location: int
    personality_signature: str
    manifest: dict[str, Any]

    @property
    def size(self) -> int:
        return self.base.agents.num_rows

    @property
    def represented_population(self) -> float:
        return float(round(float(self.weights.sum()), 6))

    @property
    def location_ids(self) -> tuple[str, ...]:
        return tuple(item.location_id for item in self.locations)

    def locations_at_tick(self, tick: int, world: WorldSpec) -> NDArray[np.int64]:
        elapsed_minutes = tick * world.tick_minutes
        hour = int((world.start_hour + elapsed_minutes // 60) % 24)
        day = int(elapsed_minutes // (24 * 60))
        weekend = day % 7 in {5, 6}
        if 7 <= hour < 9 or 17 <= hour < 18:
            return np.full(self.size, self.transit_location, dtype=np.int64)
        if 9 <= hour < 17 and not weekend:
            return self.primary_location.copy()
        if 10 <= hour < 21:
            return self.social_location.copy()
        return self.home_location.copy()


def _as_object(population: ResearchPopulation, name: str) -> NDArray[np.object_]:
    return np.asarray(population.agents[name].to_pylist(), dtype=object)


def _as_float(population: ResearchPopulation, name: str) -> NDArray[np.float64]:
    return np.asarray(population.agents[name], dtype=float)


def _build_world_graph(population: ResearchPopulation, seed: int) -> WorldGraph:
    base = population.graph
    size = population.agents.num_rows
    rng = np.random.default_rng(seed + 93_101)
    relation_mapping = {
        "family": "family",
        "acquaintance": "friend",
        "coworker": "coworker",
        "community": "community",
        "online": "follower",
    }
    base_relations = np.asarray(
        [relation_mapping[str(item)] for item in base.relationship_type], dtype=object
    )
    roles = _as_object(population, "social_role")
    age_groups = _as_object(population, "age_group")
    channels = _as_object(population, "primary_channel")
    openness = _as_float(population, "openness")
    source = base.source.copy()
    target = base.target.copy()
    similarity = np.clip(
        0.12
        + 0.32 * (roles[source] == roles[target])
        + 0.24 * (age_groups[source] == age_groups[target])
        + 0.18 * (channels[source] == channels[target])
        + 0.14 * (1 - np.abs(openness[source] - openness[target])),
        0,
        1,
    )
    influence_by_agent = _as_float(population, "influence")
    influence = influence_by_agent[source]
    frequency_centers = {
        "family": 24.0,
        "friend": 11.0,
        "coworker": 16.0,
        "follower": 7.0,
        "community": 8.0,
    }
    frequency = np.asarray(
        [max(0.1, rng.normal(frequency_centers[str(item)], 2.2)) for item in base_relations],
        dtype=float,
    )
    relation_channels = {
        "family": "interpersonal",
        "friend": "interpersonal",
        "coworker": "community",
        "follower": "social_media",
        "community": "community",
    }
    graph_channel = np.asarray(
        [relation_channels[str(item)] for item in base_relations], dtype=object
    )

    tiers = _as_object(population, "tier")
    authorities = np.flatnonzero(tiers == AgentTier.KEY.value).astype(np.int64)
    if authorities.size == 0:
        authorities = np.arange(min(50, size), dtype=np.int64)
    authority_target = np.arange(size, dtype=np.int64)
    authority_source = authorities[np.arange(size) % authorities.size]
    collisions = authority_source == authority_target
    if collisions.any():
        authority_source[collisions] = authorities[
            (np.arange(size)[collisions] + 1) % authorities.size
        ]
    authority_similarity = np.clip(
        0.25 + 0.35 * (roles[authority_source] == roles[authority_target]), 0, 1
    )
    authority_influence = np.clip(influence_by_agent[authority_source] + 0.2, 0, 1)

    return WorldGraph(
        source=np.concatenate([source, authority_source]),
        target=np.concatenate([target, authority_target]),
        relation_type=np.concatenate([base_relations, np.full(size, "authority", dtype=object)]),
        strength=np.concatenate(
            [base.strength.copy(), np.clip(rng.normal(0.62, 0.1, size), 0.1, 1)]
        ),
        trust=np.concatenate([base.trust.copy(), np.clip(rng.normal(0.58, 0.14, size), 0.05, 1)]),
        similarity=np.concatenate([similarity, authority_similarity]),
        influence=np.concatenate([influence, authority_influence]),
        frequency=np.concatenate([frequency, np.clip(rng.normal(5.0, 1.2, size), 0.1, 30)]),
        channel=np.concatenate([graph_channel, np.full(size, "news", dtype=object)]),
    )


def _indices_of_type(locations: tuple[LocationSpec, ...], kind: LocationType) -> list[int]:
    return [index for index, item in enumerate(locations) if item.location_type == kind]


def _first_or_root(locations: tuple[LocationSpec, ...], kind: LocationType, root: int) -> int:
    candidates = _indices_of_type(locations, kind)
    return candidates[0] if candidates else root


def _capacity_weighted_assignment(
    locations: tuple[LocationSpec, ...],
    candidates: list[int],
    weights: NDArray[np.float64],
    rng: np.random.Generator,
    fallback: int,
) -> NDArray[np.int64]:
    result = np.full(weights.size, fallback, dtype=np.int64)
    if not candidates:
        return result
    total_weight = float(weights.sum())
    capacities = np.asarray([locations[index].capacity for index in candidates], dtype=float)
    if float(capacities.sum()) >= total_weight:
        proportions = capacities / capacities.sum()
        raw_counts = proportions * weights.size
        counts = np.floor(raw_counts).astype(np.int64)
        counts[np.argsort(-(raw_counts - counts))[: weights.size - int(counts.sum())]] += 1
    else:
        average_weight = total_weight / weights.size
        counts = np.floor(capacities / average_weight).astype(np.int64)
    order = rng.permutation(weights.size)
    cursor = 0
    for location_index, count in zip(candidates, counts, strict=True):
        members = order[cursor : min(weights.size, cursor + int(count))]
        result[members] = location_index
        cursor += int(count)
    return result


def _enforce_direct_capacity(
    assignment: NDArray[np.int64],
    locations: tuple[LocationSpec, ...],
    weights: NDArray[np.float64],
    rng: np.random.Generator,
    fallback: int,
) -> NDArray[np.int64]:
    result = assignment.copy()
    for location_index, location in enumerate(locations):
        if location_index == fallback:
            continue
        members = np.flatnonzero(result == location_index).astype(np.int64)
        if members.size == 0 or float(weights[members].sum()) <= location.capacity:
            continue
        ordered = rng.permutation(members)
        cumulative = np.cumsum(weights[ordered])
        overflow = ordered[cumulative > location.capacity]
        result[overflow] = fallback
    return result


def _assign_subset_by_capacity(
    assignment: NDArray[np.int64],
    members: NDArray[np.int64],
    locations: tuple[LocationSpec, ...],
    candidates: list[int],
    weights: NDArray[np.float64],
    rng: np.random.Generator,
    fallback: int,
) -> None:
    """Assign one population subset without collapsing a location type to its first item."""

    if members.size == 0:
        return
    assignment[members] = _capacity_weighted_assignment(
        locations,
        candidates,
        weights[members],
        rng,
        fallback,
    )


def _assign_locations(
    population: ResearchPopulation,
    world: WorldSpec,
    weights: NDArray[np.float64],
    seed: int,
) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.int64], int, int]:
    locations = tuple(world.locations)
    size = population.agents.num_rows
    rng = np.random.default_rng(seed + 20_269)
    roots = [index for index, item in enumerate(locations) if item.parent_id is None]
    root = roots[0]
    residential = _indices_of_type(locations, LocationType.RESIDENTIAL) or [root]
    home = _capacity_weighted_assignment(locations, residential, weights, rng, root)
    workplaces = _indices_of_type(locations, LocationType.WORKPLACE) or [root]
    education = [
        *_indices_of_type(locations, LocationType.SCHOOL),
        *_indices_of_type(locations, LocationType.CAMPUS),
    ] or workplaces
    communities = _indices_of_type(locations, LocationType.COMMUNITY) or [root]
    retail = _indices_of_type(locations, LocationType.RETAIL) or communities
    libraries = _indices_of_type(locations, LocationType.LIBRARY) or education
    canteens = _indices_of_type(locations, LocationType.CANTEEN) or residential
    transit = _first_or_root(locations, LocationType.TRANSIT, root)
    online = _first_or_root(locations, LocationType.ONLINE, root)

    roles = _as_object(population, "social_role")
    interests = _as_object(population, "primary_interest")
    primary = np.full(size, root, dtype=np.int64)
    role_assignments = (
        (["professional", "skilled_worker"], workplaces, root),
        (["student"], education, communities[0]),
        (["caregiver", "retired", "job_seeker"], communities, root),
        (["service_worker", "self_employed"], retail, communities[0]),
    )
    for role_values, candidates, fallback in role_assignments:
        members = np.flatnonzero(np.isin(roles, role_values)).astype(np.int64)
        _assign_subset_by_capacity(
            primary,
            members,
            locations,
            candidates,
            weights,
            rng,
            fallback,
        )

    social = np.full(size, communities[0], dtype=np.int64)
    interest_assignments = (
        (["learning"], libraries, communities[0]),
        (["technology"], workplaces, retail[0]),
        (["culture"], retail, communities[0]),
        (["daily_life"], canteens, communities[0]),
    )
    for interest_values, candidates, fallback in interest_assignments:
        members = np.flatnonzero(np.isin(interests, interest_values)).astype(np.int64)
        _assign_subset_by_capacity(
            social,
            members,
            locations,
            candidates,
            weights,
            rng,
            fallback,
        )
    primary = _enforce_direct_capacity(primary, locations, weights, rng, root)
    social = _enforce_direct_capacity(social, locations, weights, rng, root)
    return home, primary, social, transit, online


def validate_world_population(population: WorldPopulation, world: WorldSpec) -> dict[str, Any]:
    graph = population.graph
    personality_columns = [
        *(f"big5_{name}" for name in BIG_FIVE_DIMENSIONS),
        *(f"schwartz_{name}" for name in SCHWARTZ_DIMENSIONS),
        *(f"moral_{name}" for name in MORAL_DIMENSIONS),
        *(f"risk_{name}" for name in RISK_DIMENSIONS),
        *(f"cognitive_{name}" for name in COGNITIVE_DIMENSIONS),
        *(f"goal_{name}" for name in GOAL_DIMENSIONS),
        *(f"belief_{name}" for name in BELIEF_DIMENSIONS),
    ]
    table = population.base.agents
    personality_finite = all(
        np.isfinite(np.asarray(table[name], dtype=float)).all() for name in personality_columns
    )
    capacity_violations: dict[str, dict[str, float]] = {}
    for label, assignment in (
        ("home", population.home_location),
        ("primary", population.primary_location),
        ("social", population.social_location),
    ):
        for index, location in enumerate(population.locations):
            if location.parent_id is None:
                continue
            assigned = float(population.weights[assignment == index].sum())
            if assigned > location.capacity + float(population.weights.max()):
                capacity_violations[f"{label}:{location.location_id}"] = {
                    "assigned": assigned,
                    "capacity": location.capacity,
                }
    checks = {
        "prototype_count": population.size == world.prototype_count,
        "positive_weights": bool(np.all(population.weights > 0)),
        "represented_population": bool(
            np.isclose(population.represented_population, world.represented_population)
        ),
        "complete_relationship_types": set(graph.relation_type.tolist()) == set(RELATIONSHIP_TYPES),
        "no_self_loops": bool(np.all(graph.source != graph.target)),
        "graph_attributes_bounded": bool(
            np.all((graph.strength >= 0) & (graph.strength <= 1))
            and np.all((graph.trust >= 0) & (graph.trust <= 1))
            and np.all((graph.similarity >= 0) & (graph.similarity <= 1))
            and np.all((graph.influence >= 0) & (graph.influence <= 1))
            and np.all(graph.frequency >= 0)
        ),
        "personality_complete_and_finite": personality_finite,
        "direct_location_capacity": not capacity_violations,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "capacity_violations": capacity_violations,
    }


def build_world_population(world: WorldSpec, seed: int) -> WorldPopulation:
    population_spec = PopulationSpec(
        population_id=f"{world.world_id}_prototypes",
        name=f"{world.name}加权人格样本",
        size=world.prototype_count,
        seed=seed,
        filters=world.population_filters,
    )
    base = generate_population(population_spec, persist=False)
    base_weights = _as_float(base, "survey_weight")
    weights = base_weights * (world.represented_population / float(base_weights.sum()))
    graph = _build_world_graph(base, seed)
    locations = tuple(world.locations)
    home, primary, social, transit, online = _assign_locations(base, world, weights, seed)
    personality_signature = str(base.manifest["profile_signature"])
    tier_values = _as_object(base, "tier")
    provisional = WorldPopulation(
        base=base,
        weights=weights,
        graph=graph,
        locations=locations,
        home_location=home,
        primary_location=primary,
        social_location=social,
        transit_location=transit,
        online_location=online,
        personality_signature=personality_signature,
        manifest={},
    )
    validation = validate_world_population(provisional, world)
    if not validation["valid"]:
        raise ValueError(f"generated social world failed validation: {validation}")
    manifest = {
        "world_id": world.world_id,
        "population_version": base.manifest["population_version"],
        "graph_version": graph.graph_version,
        "prototype_count": base.agents.num_rows,
        "represented_population": provisional.represented_population,
        "personality_signature": personality_signature,
        "graph_hash": graph.content_hash,
        "tier_counts": {tier.value: int(np.sum(tier_values == tier.value)) for tier in AgentTier},
        "relationship_types": sorted(set(graph.relation_type.tolist())),
        "location_ids": [item.location_id for item in locations],
        "origin": "weighted_synthetic_prototypes",
        "validation": validation,
    }
    return WorldPopulation(
        base=base,
        weights=weights,
        graph=graph,
        locations=locations,
        home_location=home,
        primary_location=primary,
        social_location=social,
        transit_location=transit,
        online_location=online,
        personality_signature=personality_signature,
        manifest=manifest,
    )
