from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from echo_swm.core.ids import stable_hash
from echo_swm.research.population import (
    BELIEF_DIMENSIONS,
    BIG_FIVE_DIMENSIONS,
    COGNITIVE_DIMENSIONS,
    GOAL_DIMENSIONS,
    MORAL_DIMENSIONS,
    RISK_DIMENSIONS,
    SCHWARTZ_DIMENSIONS,
)
from echo_swm.world.contracts import ChannelType, WorldEvent, WorldSimulationRequest
from echo_swm.world.population import WorldPopulation

ACTIONS = ("ignore", "consume", "discuss", "share", "support", "oppose", "participate", "exit")
EMOTION_DIMENSIONS = ("valence", "arousal", "stress", "joy", "anger", "anxiety")
LOCATION_METRICS = (
    "present_population",
    "aware_fraction",
    "active_expression_fraction",
    "emotion_valence",
    "support",
)
STATE_TRANSITION_ORDER = (
    "mobility_and_context",
    "event_and_individual_exposure",
    "belief_update",
    "emotion_appraisal",
    "goal_activation",
    "intention_and_action",
    "memory_consolidation",
    "private_state_update",
)
CHANNELS = tuple(item.value for item in ChannelType)


@dataclass(frozen=True)
class PersonalityMatrix:
    big_five: NDArray[np.float64]
    schwartz: NDArray[np.float64]
    moral: NDArray[np.float64]
    risk: NDArray[np.float64]
    cognitive: NDArray[np.float64]
    base_goals: NDArray[np.float64]
    signature: str


@dataclass
class WorldState:
    event_awareness: NDArray[np.float64]
    channel_awareness: NDArray[np.float64]
    attention: NDArray[np.float64]
    beliefs: NDArray[np.float64]
    belief_confidence: NDArray[np.float64]
    emotion_valence: NDArray[np.float64]
    emotion_arousal: NDArray[np.float64]
    stress: NDArray[np.float64]
    joy: NDArray[np.float64]
    anger: NDArray[np.float64]
    anxiety: NDArray[np.float64]
    trust: NDArray[np.float64]
    confidence: NDArray[np.float64]
    interest: NDArray[np.float64]
    intention: NDArray[np.float64]
    goals: NDArray[np.float64]
    actions: NDArray[np.int64]
    working_memory_salience: NDArray[np.float64]
    episodic_memory_count: NDArray[np.int64]
    semantic_memory_strength: NDArray[np.float64]


@dataclass(frozen=True)
class EventRuntime:
    event: WorldEvent
    belief_signal: NDArray[np.float64]
    goal_signal: NDArray[np.float64]
    value_alignment: NDArray[np.float64]
    audience_relevance: NDArray[np.float64]
    channel_mask: NDArray[np.bool_]
    effective_valence: float


@dataclass(frozen=True)
class SnapshotPayload:
    tick: int
    location: NDArray[np.int64]
    event_awareness: NDArray[np.float64]
    beliefs: NDArray[np.float64]
    emotion: NDArray[np.float64]
    goals: NDArray[np.float64]
    actions: NDArray[np.int64]
    working_memory_salience: NDArray[np.float64]
    episodic_memory_count: NDArray[np.int64]
    semantic_memory_strength: NDArray[np.float64]
    relationship_trust: NDArray[np.float64]
    state_hash: str


@dataclass
class PathOutput:
    event_awareness: NDArray[np.float64]
    event_new_reach: NDArray[np.float64]
    channel_reach: NDArray[np.float64]
    emotions: NDArray[np.float64]
    beliefs: NDArray[np.float64]
    action_shares: NDArray[np.float64]
    location_metrics: NDArray[np.float64]
    location_action_shares: NDArray[np.float64]
    final_state: WorldState
    final_actions: NDArray[np.int64]
    final_locations: NDArray[np.int64]
    trace_records: list[dict[str, Any]]
    replay_records: list[dict[str, Any]]
    snapshots: list[SnapshotPayload]


def _column(population: WorldPopulation, name: str) -> NDArray[np.float64]:
    return np.asarray(population.base.agents[name], dtype=float)


def _object_column(population: WorldPopulation, name: str) -> NDArray[np.object_]:
    return np.asarray(population.base.agents[name].to_pylist(), dtype=object)


def personality_matrix(population: WorldPopulation) -> PersonalityMatrix:
    def matrix(prefix: str, dimensions: tuple[str, ...]) -> NDArray[np.float64]:
        return np.column_stack([_column(population, f"{prefix}{name}") for name in dimensions])

    return PersonalityMatrix(
        big_five=matrix("big5_", BIG_FIVE_DIMENSIONS),
        schwartz=matrix("schwartz_", SCHWARTZ_DIMENSIONS),
        moral=matrix("moral_", MORAL_DIMENSIONS),
        risk=matrix("risk_", RISK_DIMENSIONS),
        cognitive=matrix("cognitive_", COGNITIVE_DIMENSIONS),
        base_goals=matrix("goal_", GOAL_DIMENSIONS),
        signature=population.personality_signature,
    )


def _initial_state(
    population: WorldPopulation, personality: PersonalityMatrix, event_count: int
) -> WorldState:
    size = population.size
    belief_values = np.column_stack(
        [_column(population, f"belief_{name}") * 2 - 1 for name in BELIEF_DIMENSIONS]
    )
    confidence = _column(population, "belief_confidence")
    return WorldState(
        event_awareness=np.zeros((size, event_count), dtype=float),
        channel_awareness=np.zeros((size, event_count, len(CHANNELS)), dtype=float),
        attention=np.zeros(size, dtype=float),
        beliefs=belief_values,
        belief_confidence=np.repeat(confidence[:, None], len(BELIEF_DIMENSIONS), axis=1),
        emotion_valence=_column(population, "baseline_emotion_valence"),
        emotion_arousal=_column(population, "baseline_emotion_arousal"),
        stress=_column(population, "baseline_stress"),
        joy=np.zeros(size, dtype=float),
        anger=np.zeros(size, dtype=float),
        anxiety=np.zeros(size, dtype=float),
        trust=np.clip(
            0.5 * _column(population, "social_trust")
            + 0.5 * _column(population, "institutional_trust"),
            0,
            1,
        ),
        confidence=confidence.copy(),
        interest=_column(population, "baseline_interest"),
        intention=_column(population, "baseline_intention"),
        goals=personality.base_goals.copy(),
        actions=np.full(size, ACTIONS.index("ignore"), dtype=np.int64),
        working_memory_salience=np.zeros(size, dtype=float),
        episodic_memory_count=np.zeros(size, dtype=np.int64),
        semantic_memory_strength=np.zeros(size, dtype=float),
    )


def _semantic_polarity(event: WorldEvent) -> float:
    if abs(event.valence) > 1e-12:
        return event.valence
    text = f"{event.title} {event.description}".lower()
    positive = ("优惠", "改善", "开放", "增长", "成功", "新品", "支持", "benefit", "improve")
    negative = ("事故", "危机", "涨价", "污染", "丑闻", "中断", "风险", "crisis", "failure")
    score = sum(token in text for token in positive) - sum(token in text for token in negative)
    return float(np.clip(score * 0.22, -0.75, 0.75))


def _belief_signal(event: WorldEvent, effective_valence: float) -> NDArray[np.float64]:
    signal = np.full(len(BELIEF_DIMENSIONS), effective_valence * 0.35, dtype=float)
    for name, value in event.belief_signals.items():
        if name in BELIEF_DIMENSIONS:
            signal[BELIEF_DIMENSIONS.index(name)] = value
    text = f"{event.title} {event.description}".lower()
    keyword_mapping = {
        "technology": ("科技", "技术", "ai", "软件", "平台", "product"),
        "economic_outlook": ("经济", "就业", "价格", "消费", "市场", "price"),
        "brand_trust": ("品牌", "新品", "广告", "产品", "brand"),
        "institutional_trust": ("政策", "政府", "学校", "机构", "policy"),
        "social_attitude": ("社区", "社会", "公共", "群体", "community"),
    }
    direction = effective_valence if abs(effective_valence) > 0.05 else 0.24
    for dimension, tokens in keyword_mapping.items():
        if any(token in text for token in tokens) and dimension not in event.belief_signals:
            index = BELIEF_DIMENSIONS.index(dimension)
            signal[index] = float(np.clip(signal[index] + direction * 0.65, -1, 1))
    return np.clip(signal, -1, 1)


def _goal_signal(event: WorldEvent, effective_valence: float) -> NDArray[np.float64]:
    signal = np.zeros(len(GOAL_DIMENSIONS), dtype=float)
    for name, value in event.goal_signals.items():
        if name in GOAL_DIMENSIONS:
            signal[GOAL_DIMENSIONS.index(name)] = value
    if event.goal_signals:
        return signal
    if effective_valence >= 0:
        for name, value in {"achievement": 0.55, "growth": 0.62, "belonging": 0.3}.items():
            signal[GOAL_DIMENSIONS.index(name)] = value * max(effective_valence, 0.25)
    else:
        for name, value in {"security": 0.58, "survival": 0.72, "status": -0.2}.items():
            signal[GOAL_DIMENSIONS.index(name)] = value * abs(effective_valence)
    return signal


def _event_alignment(
    population: WorldPopulation, personality: PersonalityMatrix, event: WorldEvent
) -> NDArray[np.float64]:
    vector = np.zeros(len(SCHWARTZ_DIMENSIONS), dtype=float)
    aliases = {
        "autonomy": "self_direction",
        "community": "benevolence",
        "care": "benevolence",
        "fairness": "universalism",
    }
    for name, value in event.value_signals.items():
        normalized = aliases.get(name, name)
        if normalized in SCHWARTZ_DIMENSIONS:
            vector[SCHWARTZ_DIMENSIONS.index(normalized)] += value
    if not np.any(vector):
        effective_valence = _semantic_polarity(event)
        vector[SCHWARTZ_DIMENSIONS.index("self_direction")] = 0.2 * effective_valence
        vector[SCHWARTZ_DIMENSIONS.index("security")] = -0.18 * effective_valence
        vector[SCHWARTZ_DIMENSIONS.index("benevolence")] = 0.24 * effective_valence
    denominator = max(1.0, float(np.abs(vector).sum()))
    centered = personality.schwartz - 0.5
    moral_care = personality.moral[:, MORAL_DIMENSIONS.index("care")] - 0.5
    alignment = np.sum(centered * vector, axis=1) / denominator + 0.08 * moral_care
    return np.clip(alignment, -1, 1)


def _audience_relevance(population: WorldPopulation, event: WorldEvent) -> NDArray[np.float64]:
    relevance = np.ones(population.size, dtype=float)
    for field, allowed in event.audience_filters.items():
        if field not in population.base.agents.column_names:
            raise ValueError(f"unsupported event audience field: {field}")
        values = _object_column(population, field)
        relevance *= np.where(np.isin(values, np.asarray(allowed, dtype=object)), 1.0, 0.08)
    return relevance


def _event_runtimes(
    population: WorldPopulation,
    personality: PersonalityMatrix,
    events: list[WorldEvent],
) -> list[EventRuntime]:
    result = []
    for event in events:
        effective_valence = _semantic_polarity(event)
        channel_mask = np.asarray(
            [channel in {item.value for item in event.channels} for channel in CHANNELS],
            dtype=bool,
        )
        result.append(
            EventRuntime(
                event=event,
                belief_signal=_belief_signal(event, effective_valence),
                goal_signal=_goal_signal(event, effective_valence),
                value_alignment=_event_alignment(population, personality, event),
                audience_relevance=_audience_relevance(population, event),
                channel_mask=channel_mask,
                effective_valence=effective_valence,
            )
        )
    return result


def _channel_preferences(population: WorldPopulation) -> NDArray[np.float64]:
    columns: dict[str, NDArray[np.float64]] = {
        "social_media": _column(population, "channel_social_media"),
        "news": _column(population, "channel_news"),
        "interpersonal": _column(population, "channel_interpersonal"),
        "community": _column(population, "channel_community"),
        "search": _column(population, "channel_search"),
        "onsite": np.full(population.size, 0.28, dtype=float),
    }
    return np.column_stack([columns[name] for name in CHANNELS])


def _ancestors(population: WorldPopulation, location_id: str) -> set[str]:
    parents = {item.location_id: item.parent_id for item in population.locations}
    result = {location_id}
    cursor = parents[location_id]
    while cursor is not None:
        result.add(cursor)
        cursor = parents[cursor]
    return result


def _spatial_relevance(
    population: WorldPopulation,
    current_locations: NDArray[np.int64],
    event: WorldEvent,
) -> NDArray[np.float64]:
    if not event.target_location_ids and event.source_location_id is None:
        return np.ones(population.size, dtype=float)
    targets = set(event.target_location_ids)
    if not targets and event.source_location_id is not None:
        targets.add(event.source_location_id)
    target_ancestors = {target: _ancestors(population, target) for target in targets}
    affinities = np.full(len(population.locations), 0.12, dtype=float)
    for index, location in enumerate(population.locations):
        location_ancestors = _ancestors(population, location.location_id)
        for target, ancestors in target_ancestors.items():
            if location.location_id == target:
                affinities[index] = max(affinities[index], 1.0)
            elif target in location_ancestors:
                affinities[index] = max(affinities[index], 0.88)
            elif location.location_id in ancestors:
                affinities[index] = max(affinities[index], 0.68)
            elif location_ancestors & ancestors:
                affinities[index] = max(affinities[index], 0.42)
    return affinities[current_locations]


def _event_kernel(event: WorldEvent, tick: int) -> float:
    age = tick - event.start_tick
    if age < 0:
        return 0.0
    if age < event.duration_ticks:
        return float(0.55 + 0.45 * np.exp(-age / max(4.0, event.duration_ticks / 3)))
    tail_age = age - event.duration_ticks
    return float(0.32 * np.exp(-tail_age / max(6.0, event.duration_ticks / 2)))


def _state_support(state: WorldState) -> NDArray[np.float64]:
    return np.clip(np.mean(state.beliefs, axis=1), -1, 1)


def _softmax_actions(
    rng: np.random.Generator,
    population: WorldPopulation,
    personality: PersonalityMatrix,
    state: WorldState,
    neighbor_stance: NDArray[np.float64],
) -> NDArray[np.int64]:
    support = _state_support(state)
    awareness = np.max(state.event_awareness, axis=1)
    positive = np.clip(support, 0, 1)
    negative = np.clip(-support, 0, 1)
    uncertainty = 1 - np.mean(state.belief_confidence, axis=1)
    analytical = (
        personality.cognitive[:, COGNITIVE_DIMENSIONS.index("analytical_intuitive")] + 1
    ) / 2
    social_risk = personality.risk[:, RISK_DIMENSIONS.index("social")]
    action_tendency = _column(population, "action_tendency")
    expression = _column(population, "expression_tendency")
    norm_agreement = 1 - np.abs(support - neighbor_stance) / 2
    logits = np.column_stack(
        [
            1.25 * (1 - awareness) + 0.55 * (1 - state.interest),
            0.45 + 0.9 * awareness + 0.25 * uncertainty,
            -0.05 + 0.9 * analytical + 0.75 * uncertainty + 0.42 * awareness,
            -0.48
            + 1.0 * expression
            + 0.72 * state.emotion_arousal
            + 0.35 * awareness
            + 0.12 * state.trust,
            -0.18
            + 1.45 * positive
            + 0.38 * norm_agreement
            + 0.35 * state.intention
            + 0.18 * state.trust,
            -0.2
            + 1.45 * negative
            + 0.4 * (1 - norm_agreement)
            + 0.38 * state.anger
            + 0.18 * (1 - state.trust),
            -0.62 + 1.1 * action_tendency + 0.72 * state.intention + 0.45 * np.abs(support),
            -1.15 + 0.78 * state.stress + 0.52 * state.anxiety + 0.35 * (1 - social_risk),
        ]
    )
    tiers = _object_column(population, "tier")
    noise = np.full(population.size, 0.82, dtype=float)
    noise[tiers == "key"] = 0.38
    noise[tiers == "representative"] = 0.58
    uniforms = np.clip(rng.random(logits.shape), 1e-12, 1 - 1e-12)
    gumbel = -np.log(-np.log(uniforms))
    actions = np.argmax(logits + gumbel * noise[:, None], axis=1).astype(np.int64)
    actions[awareness < 0.5] = ACTIONS.index("ignore")
    return actions


def _weighted_mean(
    values: NDArray[np.float64] | NDArray[np.bool_],
    weights: NDArray[np.float64],
    mask: NDArray[np.bool_] | None = None,
) -> float:
    active_weights = weights if mask is None else weights[mask]
    active_values = values if mask is None else values[mask]
    if active_weights.size == 0 or float(active_weights.sum()) <= 0:
        return 0.0
    return float(np.average(active_values, weights=active_weights))


def _state_hash(
    state: WorldState,
    locations: NDArray[np.int64],
    relationship_trust: NDArray[np.float64],
) -> str:
    digest = hashlib.sha256()
    arrays = (
        state.event_awareness,
        state.channel_awareness,
        state.attention,
        state.beliefs,
        state.belief_confidence,
        state.emotion_valence,
        state.emotion_arousal,
        state.stress,
        state.joy,
        state.anger,
        state.anxiety,
        state.trust,
        state.confidence,
        state.interest,
        state.intention,
        state.goals,
        state.working_memory_salience,
        state.semantic_memory_strength,
        relationship_trust,
    )
    for array in arrays:
        digest.update(np.round(array, 8).tobytes())
    digest.update(state.actions.tobytes())
    digest.update(state.episodic_memory_count.tobytes())
    digest.update(locations.tobytes())
    return digest.hexdigest()


def _snapshot(
    tick: int,
    state: WorldState,
    locations: NDArray[np.int64],
    relationship_trust: NDArray[np.float64],
    state_hash: str,
) -> SnapshotPayload:
    emotion = np.column_stack(
        [
            state.emotion_valence,
            state.emotion_arousal,
            state.stress,
            state.joy,
            state.anger,
            state.anxiety,
        ]
    )
    return SnapshotPayload(
        tick=tick,
        location=locations.copy(),
        event_awareness=state.event_awareness.copy(),
        beliefs=state.beliefs.copy(),
        emotion=emotion,
        goals=state.goals.copy(),
        actions=state.actions.copy(),
        working_memory_salience=state.working_memory_salience.copy(),
        episodic_memory_count=state.episodic_memory_count.copy(),
        semantic_memory_strength=state.semantic_memory_strength.copy(),
        relationship_trust=relationship_trust.copy(),
        state_hash=state_hash,
    )


def _record_aggregates(
    population: WorldPopulation,
    state: WorldState,
    locations: NDArray[np.int64],
    event_new: NDArray[np.float64],
    tick: int,
    event_awareness: NDArray[np.float64],
    event_new_reach: NDArray[np.float64],
    channel_reach: NDArray[np.float64],
    emotions: NDArray[np.float64],
    beliefs: NDArray[np.float64],
    action_shares: NDArray[np.float64],
    location_metrics: NDArray[np.float64],
    location_action_shares: NDArray[np.float64],
) -> None:
    weights = population.weights
    overall_awareness = np.max(state.event_awareness, axis=1)
    support = _state_support(state)
    active_actions = np.isin(
        state.actions,
        [ACTIONS.index("discuss"), ACTIONS.index("share"), ACTIONS.index("participate")],
    )
    for event_index in range(state.event_awareness.shape[1]):
        event_awareness[tick, event_index] = _weighted_mean(
            state.event_awareness[:, event_index], weights
        )
        event_new_reach[tick, event_index] = _weighted_mean(event_new[:, event_index], weights)
        for channel_index in range(len(CHANNELS)):
            channel_reach[tick, event_index, channel_index] = _weighted_mean(
                state.channel_awareness[:, event_index, channel_index], weights
            )
    emotion_arrays = (
        state.emotion_valence,
        state.emotion_arousal,
        state.stress,
        state.joy,
        state.anger,
        state.anxiety,
    )
    for index, values in enumerate(emotion_arrays):
        emotions[tick, index] = _weighted_mean(values, weights)
    for index in range(len(BELIEF_DIMENSIONS)):
        beliefs[tick, index] = _weighted_mean(state.beliefs[:, index], weights)
    for index in range(len(ACTIONS)):
        action_shares[tick, index] = _weighted_mean(state.actions == index, weights)
    for location_index in range(len(population.locations)):
        mask = locations == location_index
        present = float(weights[mask].sum())
        location_metrics[tick, location_index] = np.asarray(
            [
                present,
                _weighted_mean(overall_awareness, weights, mask),
                _weighted_mean(active_actions, weights, mask),
                _weighted_mean(state.emotion_valence, weights, mask),
                _weighted_mean(support, weights, mask),
            ]
        )
        for action_index in range(len(ACTIONS)):
            location_action_shares[tick, location_index, action_index] = _weighted_mean(
                state.actions == action_index, weights, mask
            )


def _trace_records(
    population: WorldPopulation,
    events: list[WorldEvent],
    state: WorldState,
    locations: NDArray[np.int64],
    event_new: NDArray[np.float64],
    channel_new: NDArray[np.float64],
    tick: int,
    path_index: int,
    trace_indices: NDArray[np.int64],
) -> list[dict[str, Any]]:
    if trace_indices.size == 0:
        return []
    agent_ids = population.base.agents["agent_id"].to_pylist()
    tiers = population.base.agents["tier"].to_pylist()
    result: list[dict[str, Any]] = []
    for agent_index in trace_indices:
        index = int(agent_index)
        received_events = [
            event.event_id
            for event_position, event in enumerate(events)
            if event_new[index, event_position] > 1e-5
        ]
        aware_events = [
            event.event_id
            for event_position, event in enumerate(events)
            if state.event_awareness[index, event_position] > 0.5
        ]
        received_channels = [
            CHANNELS[channel_index]
            for channel_index in range(len(CHANNELS))
            if np.max(channel_new[index, :, channel_index]) > 1e-5
        ]
        action = ACTIONS[int(state.actions[index])]
        support = float(np.mean(state.beliefs[index]))
        reason_codes = ["STRUCTURED_HUMAN_STATE", "LOCATION_CONTEXT"]
        if received_events:
            reason_codes.append("EVENT_EXPOSURE")
        if action in {"share", "discuss", "participate"}:
            reason_codes.append("SOCIAL_EXPRESSION")
        if support > 0.2:
            reason_codes.append("BELIEF_GOAL_CONGRUENCE")
        elif support < -0.2:
            reason_codes.append("BELIEF_GOAL_CONFLICT")
        result.append(
            {
                "agent_id": str(agent_ids[index]),
                "tier": str(tiers[index]),
                "path": path_index,
                "tick": tick,
                "location_id": population.location_ids[int(locations[index])],
                "received_event_ids": received_events,
                "aware_event_ids": aware_events,
                "received_channels": received_channels,
                "beliefs": {
                    name: float(state.beliefs[index, position])
                    for position, name in enumerate(BELIEF_DIMENSIONS)
                },
                "emotion": {
                    "valence": float(state.emotion_valence[index]),
                    "arousal": float(state.emotion_arousal[index]),
                    "stress": float(state.stress[index]),
                    "joy": float(state.joy[index]),
                    "anger": float(state.anger[index]),
                    "anxiety": float(state.anxiety[index]),
                },
                "goals": {
                    name: float(state.goals[index, position])
                    for position, name in enumerate(GOAL_DIMENSIONS)
                },
                "action": action,
                "working_memory_salience": float(state.working_memory_salience[index]),
                "episodic_memory_count": int(state.episodic_memory_count[index]),
                "semantic_memory_strength": float(state.semantic_memory_strength[index]),
                "reason_codes": reason_codes,
            }
        )
    return result


def simulate_path(
    population: WorldPopulation,
    request: WorldSimulationRequest,
    *,
    path_index: int,
    trace_indices: NDArray[np.int64],
) -> PathOutput:
    personality = personality_matrix(population)
    state = _initial_state(population, personality, len(request.events))
    events = _event_runtimes(population, personality, request.events)
    rng = np.random.default_rng(request.seed + path_index * 1_000_003)
    relationship_trust = population.graph.trust.copy()
    channel_preferences = _channel_preferences(population)
    skepticism = _column(population, "information_skepticism")
    action_tendency = _column(population, "action_tendency")
    neuroticism = personality.big_five[:, BIG_FIVE_DIMENSIONS.index("neuroticism")]
    openness = personality.big_five[:, BIG_FIVE_DIMENSIONS.index("openness")]
    analytical = (
        personality.cognitive[:, COGNITIVE_DIMENSIONS.index("analytical_intuitive")] + 1
    ) / 2
    baseline_valence = _column(population, "baseline_emotion_valence")
    baseline_arousal = _column(population, "baseline_emotion_arousal")
    baseline_stress = _column(population, "baseline_stress")
    baseline_confidence = _column(population, "belief_confidence")
    ticks = request.horizon_ticks + 1
    event_count = len(events)
    event_regime_multiplier = np.clip(rng.lognormal(0, 0.18, event_count), 0.55, 1.65)
    location_count = len(population.locations)
    event_awareness = np.zeros((ticks, event_count), dtype=float)
    event_new_reach = np.zeros((ticks, event_count), dtype=float)
    channel_reach = np.zeros((ticks, event_count, len(CHANNELS)), dtype=float)
    emotions = np.zeros((ticks, len(EMOTION_DIMENSIONS)), dtype=float)
    beliefs = np.zeros((ticks, len(BELIEF_DIMENSIONS)), dtype=float)
    action_shares = np.zeros((ticks, len(ACTIONS)), dtype=float)
    location_metrics = np.zeros((ticks, location_count, len(LOCATION_METRICS)), dtype=float)
    location_action_shares = np.zeros((ticks, location_count, len(ACTIONS)), dtype=float)
    trace_records: list[dict[str, Any]] = []
    replay_records: list[dict[str, Any]] = []
    snapshots: list[SnapshotPayload] = []
    previous_hash = "0" * 64
    current_locations = population.locations_at_tick(0, request.world)
    zero_event_new = np.zeros_like(state.event_awareness)
    zero_channel_new = np.zeros_like(state.channel_awareness)

    for tick in range(ticks):
        current_locations = population.locations_at_tick(tick, request.world)
        event_new = zero_event_new.copy()
        channel_new = zero_channel_new.copy()
        updated_agents = np.zeros(population.size, dtype=bool)
        if tick > 0:
            combined_belief_evidence = np.zeros_like(state.beliefs)
            combined_goal_signal = np.zeros_like(state.goals)
            appraisal_numerator = np.zeros(population.size, dtype=float)
            appraisal_denominator = np.zeros(population.size, dtype=float)
            credibility_numerator = np.zeros(population.size, dtype=float)
            credibility_denominator = np.zeros(population.size, dtype=float)
            attention_signal = np.zeros(population.size, dtype=float)
            for event_index, runtime in enumerate(events):
                kernel = _event_kernel(runtime.event, tick)
                if kernel <= 0:
                    continue
                spatial = _spatial_relevance(population, current_locations, runtime.event)
                path_multiplier = float(
                    event_regime_multiplier[event_index]
                    * np.clip(rng.lognormal(0, 0.035), 0.85, 1.18)
                )
                individual_multiplier = np.clip(rng.lognormal(0, 0.12, population.size), 0.55, 1.7)
                channel_hazards = np.zeros((population.size, len(CHANNELS)), dtype=float)
                for channel_index, channel_name in enumerate(CHANNELS):
                    if not runtime.channel_mask[channel_index]:
                        continue
                    onsite = 1.55 if channel_name == ChannelType.ONSITE.value else 1.0
                    channel_hazards[:, channel_index] = (
                        runtime.event.intensity
                        * runtime.event.credibility
                        * kernel
                        * path_multiplier
                        * individual_multiplier
                        * runtime.audience_relevance
                        * spatial
                        * onsite
                        * (0.004 + 0.052 * channel_preferences[:, channel_index])
                    )
                total_hazard = np.sum(channel_hazards, axis=1)
                any_new_channel = np.zeros(population.size, dtype=bool)
                for channel_index in range(len(CHANNELS)):
                    hazard = channel_hazards[:, channel_index]
                    channel_probability = 1 - np.exp(-np.clip(hazard, 0, 6))
                    prior_channel = state.channel_awareness[:, event_index, channel_index] > 0.5
                    new_channel = (~prior_channel) & (
                        rng.random(population.size) < channel_probability
                    )
                    state.channel_awareness[new_channel, event_index, channel_index] = 1.0
                    channel_new[:, event_index, channel_index] = new_channel.astype(float)
                    any_new_channel |= new_channel

                prior_reached = state.event_awareness[:, event_index] > 0.5
                new_touch = (~prior_reached) & any_new_channel
                reinforcement_probability = 1 - np.exp(-0.2 * np.clip(total_hazard, 0, 6))
                reinforced = prior_reached & (
                    rng.random(population.size) < reinforcement_probability
                )
                learning_exposure = new_touch.astype(float) + 0.15 * reinforced.astype(float)
                state.event_awareness[new_touch, event_index] = 1.0
                event_new[:, event_index] = new_touch.astype(float)
                attention_signal = np.maximum(attention_signal, learning_exposure)
                updated_agents |= learning_exposure > 0
                credibility_numerator += learning_exposure * runtime.event.credibility
                credibility_denominator += learning_exposure
                credibility_learning = runtime.event.credibility * (1 - 0.62 * skepticism)
                deliberation = (
                    0.08 + 0.12 * analytical + 0.08 * state.belief_confidence.mean(axis=1)
                )
                learning = learning_exposure * credibility_learning * deliberation
                target_belief = np.tanh(
                    runtime.belief_signal[None, :] + 0.38 * runtime.value_alignment[:, None]
                )
                combined_belief_evidence += learning[:, None] * (target_belief - state.beliefs)
                combined_goal_signal += learning_exposure[:, None] * runtime.goal_signal[None, :]
                appraisal = np.clip(
                    runtime.effective_valence + 0.48 * runtime.value_alignment, -1, 1
                )
                appraisal_numerator += learning_exposure * appraisal
                appraisal_denominator += learning_exposure

            state.attention = np.clip(
                0.82 * state.attention + attention_signal * (0.42 + 0.38 * openness),
                0,
                1,
            )
            state.beliefs = np.clip(state.beliefs + combined_belief_evidence, -1, 1)
            evidence_strength = attention_signal
            state.belief_confidence = np.clip(
                state.belief_confidence
                + evidence_strength[:, None] * (0.06 + 0.08 * analytical[:, None])
                + 0.018 * (baseline_confidence[:, None] - state.belief_confidence),
                0.05,
                0.99,
            )

            appraisal = np.divide(
                appraisal_numerator,
                appraisal_denominator,
                out=np.zeros(population.size, dtype=float),
                where=appraisal_denominator > 1e-12,
            )
            support = _state_support(state)
            emotion_target = np.clip(evidence_strength * (0.62 * appraisal + 0.38 * support), -1, 1)
            state.emotion_valence = np.clip(
                0.84 * state.emotion_valence
                + 0.16 * np.clip(baseline_valence + emotion_target, -1, 1),
                -1,
                1,
            )
            arousal_target = np.clip(
                baseline_arousal + evidence_strength + np.abs(emotion_target) * neuroticism,
                0,
                1,
            )
            state.emotion_arousal = np.clip(
                0.8 * state.emotion_arousal + 0.2 * arousal_target,
                0,
                1,
            )
            stress_target = np.clip(
                baseline_stress + np.clip(-emotion_target, 0, 1) * (0.45 + 0.55 * neuroticism),
                0,
                1,
            )
            state.stress = np.clip(
                0.88 * state.stress + 0.12 * stress_target,
                0,
                1,
            )
            state.joy = np.clip(0.82 * state.joy + 0.18 * np.clip(emotion_target, 0, 1), 0, 1)
            state.anger = np.clip(
                0.84 * state.anger
                + 0.16 * np.clip(-emotion_target, 0, 1) * (0.55 + 0.45 * state.intention),
                0,
                1,
            )
            state.anxiety = np.clip(
                0.86 * state.anxiety
                + 0.14 * np.clip(state.stress - baseline_stress, 0, 1) * (0.5 + 0.5 * neuroticism),
                0,
                1,
            )

            state.goals = np.clip(
                state.goals
                + 0.16 * combined_goal_signal
                + 0.025 * (personality.base_goals - state.goals),
                0,
                1,
            )
            goal_congruence = np.mean(state.goals * (support[:, None] + 1) / 2, axis=1)
            state.interest = np.clip(
                0.86 * state.interest + 0.14 * (state.attention + goal_congruence) / 2, 0, 1
            )
            state.confidence = np.clip(
                0.78 * state.confidence
                + 0.22 * np.mean(state.belief_confidence, axis=1)
                - 0.08 * state.anxiety,
                0,
                1,
            )
            state.intention = np.clip(
                0.76 * state.intention
                + 0.24
                * (
                    0.34 * np.abs(support)
                    + 0.28 * goal_congruence
                    + 0.22 * action_tendency
                    + 0.16 * state.emotion_arousal
                ),
                0,
                1,
            )

            previous_support = _state_support(state)
            # Core decisions are independent: an Agent can only compare with its own stance.
            neighbor_stance = previous_support.copy()
            perceived_credibility = np.divide(
                credibility_numerator,
                credibility_denominator,
                out=np.full(population.size, 0.5, dtype=float),
                where=credibility_denominator > 1e-12,
            )
            state.trust = np.clip(
                state.trust + evidence_strength * 0.02 * (perceived_credibility - 0.5),
                0,
                1,
            )
            state.actions = _softmax_actions(rng, population, personality, state, neighbor_stance)
            interacted = np.isin(
                state.actions,
                [
                    ACTIONS.index("discuss"),
                    ACTIONS.index("share"),
                    ACTIONS.index("support"),
                    ACTIONS.index("oppose"),
                    ACTIONS.index("participate"),
                ],
            )
            memory_importance = np.clip(
                0.46 * evidence_strength
                + 0.28 * state.emotion_arousal
                + 0.26 * interacted.astype(float),
                0,
                1,
            )
            state.working_memory_salience = np.clip(
                state.working_memory_salience * np.exp(-0.16) + memory_importance, 0, 3
            )
            episode = memory_importance > (0.48 - 0.14 * openness)
            state.episodic_memory_count += episode.astype(np.int64)
            consolidation = episode & (state.episodic_memory_count % 3 == 0)
            state.semantic_memory_strength = np.clip(
                0.992 * state.semantic_memory_strength
                + consolidation.astype(float) * (0.04 + 0.08 * np.abs(support)),
                0,
                1,
            )
        _record_aggregates(
            population,
            state,
            current_locations,
            event_new,
            tick,
            event_awareness,
            event_new_reach,
            channel_reach,
            emotions,
            beliefs,
            action_shares,
            location_metrics,
            location_action_shares,
        )
        if path_index == 0:
            trace_records.extend(
                _trace_records(
                    population,
                    request.events,
                    state,
                    current_locations,
                    event_new,
                    channel_new,
                    tick,
                    path_index,
                    trace_indices,
                )
            )
        state_hash = _state_hash(state, current_locations, relationship_trust)
        should_snapshot = tick % request.snapshot_interval == 0 or tick == request.horizon_ticks
        snapshot_name = f"path_{path_index:03d}/tick_{tick:04d}.npz" if should_snapshot else None
        record_core = {
            "path": path_index,
            "tick": tick,
            "previous_hash": previous_hash,
            "state_hash": state_hash,
            "personality_signature": personality.signature,
            "stage_order": list(STATE_TRANSITION_ORDER),
            "stage_counts": {
                "mobility_and_context": population.size,
                "event_and_individual_exposure": int(np.sum(updated_agents)),
                "belief_update": int(np.sum(updated_agents)),
                "emotion_appraisal": int(np.sum(updated_agents)),
                "goal_activation": int(np.sum(updated_agents)),
                "intention_and_action": population.size,
                "memory_consolidation": int(np.sum(state.episodic_memory_count > 0)),
                "private_state_update": population.size,
            },
            "event_touch_counts": {
                runtime.event.event_id: int(np.sum(state.event_awareness[:, index] > 0.01))
                for index, runtime in enumerate(events)
            },
            "snapshot": snapshot_name,
        }
        record_hash = stable_hash(record_core)
        replay_records.append({**record_core, "record_hash": record_hash})
        previous_hash = record_hash
        if should_snapshot:
            snapshots.append(
                _snapshot(tick, state, current_locations, relationship_trust, state_hash)
            )

    return PathOutput(
        event_awareness=event_awareness,
        event_new_reach=event_new_reach,
        channel_reach=channel_reach,
        emotions=emotions,
        beliefs=beliefs,
        action_shares=action_shares,
        location_metrics=location_metrics,
        location_action_shares=location_action_shares,
        final_state=state,
        final_actions=state.actions.copy(),
        final_locations=current_locations,
        trace_records=trace_records,
        replay_records=replay_records,
        snapshots=snapshots,
    )
