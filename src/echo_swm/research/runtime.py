from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from echo_swm.core.ids import stable_hash
from echo_swm.research.contracts import AgentTier, EventScenario, ScenarioVariant
from echo_swm.research.population import ResearchPopulation
from echo_swm.research.semantics import VALUE_DIMENSIONS, EventInterpretation

ACTIONS = ("support", "oppose", "share", "discuss", "silence", "participate", "exit")
METRICS = (
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
)


@dataclass
class AgentState:
    awareness: NDArray[np.float64]
    belief: NDArray[np.float64]
    support: NDArray[np.float64]
    emotion: NDArray[np.float64]
    trust: NDArray[np.float64]
    risk: NDArray[np.float64]
    action_readiness: NDArray[np.float64]
    working_memory: NDArray[np.int64]
    event_memory: NDArray[np.int64]
    event_reached: NDArray[np.bool_]
    last_action: NDArray[np.int64]

    def copy(self) -> AgentState:
        return AgentState(**{name: value.copy() for name, value in vars(self).items()})


@dataclass(frozen=True)
class RuntimeScenario:
    scenario_id: str
    label: str
    intensity: float
    credibility: float
    valence: float
    value_signals: dict[str, float]


@dataclass
class ScenarioRun:
    scenario: RuntimeScenario
    timeline: NDArray[np.float64]
    final_action_shares: NDArray[np.float64]
    final_states: list[AgentState]
    final_actions: list[NDArray[np.int64]]
    replay_records: list[dict[str, Any]]


@dataclass
class RuntimeBundle:
    initial_state: AgentState
    scenarios: list[ScenarioRun]
    metric_names: tuple[str, ...]
    action_names: tuple[str, ...]
    interpretation: EventInterpretation
    evidence_refs: list[str]


def _column(population: ResearchPopulation, name: str) -> NDArray[np.float64]:
    return np.asarray(population.agents[name], dtype=float)


def initial_agent_state(population: ResearchPopulation) -> AgentState:
    size = population.agents.num_rows
    openness = _column(population, "openness")
    trust = 0.55 * _column(population, "social_trust") + 0.45 * _column(
        population, "institutional_trust"
    )
    support = np.clip(0.16 * (trust - 0.5) + 0.1 * (openness - 0.5), -1, 1)
    return AgentState(
        awareness=np.full(size, 0.025, dtype=float),
        belief=np.full(size, 0.05, dtype=float),
        support=support,
        emotion=np.zeros(size, dtype=float),
        trust=trust,
        risk=np.clip(1 - _column(population, "risk_preference"), 0, 1),
        action_readiness=_column(population, "action_tendency").copy(),
        working_memory=np.zeros(size, dtype=np.int64),
        event_memory=np.zeros(size, dtype=np.int64),
        event_reached=np.zeros(size, dtype=bool),
        last_action=np.full(size, ACTIONS.index("silence"), dtype=np.int64),
    )


def _scenario_definitions(
    event: EventScenario, interpretation: EventInterpretation
) -> list[RuntimeScenario]:
    base_signals = interpretation.value_signals
    scenarios = [
        RuntimeScenario(
            scenario_id="baseline_no_event",
            label="基线：事件未发生",
            intensity=0,
            credibility=event.credibility,
            valence=0,
            value_signals={key: 0 for key in VALUE_DIMENSIONS},
        ),
        RuntimeScenario(
            scenario_id="event_as_described",
            label="事件按描述发生",
            intensity=event.intensity,
            credibility=event.credibility,
            valence=interpretation.valence,
            value_signals=base_signals,
        ),
    ]
    for variant in event.alternatives:
        scenarios.append(_variant_scenario(event, interpretation, variant))
    return scenarios


def _variant_scenario(
    event: EventScenario,
    interpretation: EventInterpretation,
    variant: ScenarioVariant,
) -> RuntimeScenario:
    signals = {
        key: float(
            np.clip(
                interpretation.value_signals[key] + variant.value_signal_adjustments.get(key, 0),
                -1,
                1,
            )
        )
        for key in VALUE_DIMENSIONS
    }
    return RuntimeScenario(
        scenario_id=variant.variant_id,
        label=variant.label,
        intensity=float(np.clip(event.intensity * variant.intensity_multiplier, 0, 1)),
        credibility=float(np.clip(event.credibility + variant.credibility_shift, 0, 1)),
        valence=interpretation.valence,
        value_signals=signals,
    )


def _channel_match(population: ResearchPopulation, channels: list[str]) -> NDArray[np.float64]:
    mapping = {
        "online": "channel_social_media",
        "social_media": "channel_social_media",
        "news": "channel_news",
        "interpersonal": "channel_interpersonal",
        "community": "channel_community",
        "onsite": "channel_community",
        "search": "channel_search",
    }
    selected = [mapping[item] for item in channels if item in mapping]
    if not selected:
        selected = list(dict.fromkeys(mapping.values()))
    matrix = np.column_stack([_column(population, name) for name in selected])
    return np.clip(matrix.sum(axis=1), 0.05, 1)


def _value_alignment(
    population: ResearchPopulation,
    scenario: RuntimeScenario,
    personal_relevance: NDArray[np.float64],
) -> NDArray[np.float64]:
    matrix = np.column_stack(
        [_column(population, f"value_{dimension}") - 0.5 for dimension in VALUE_DIMENSIONS]
    )
    signal = np.asarray([scenario.value_signals[key] for key in VALUE_DIMENSIONS])
    denominator = max(1.0, float(np.abs(signal).sum()))
    alignment = np.sum(matrix * signal[None, :], axis=1) / denominator
    openness = _column(population, "openness")
    return np.clip(
        alignment
        + scenario.valence * (0.38 + 0.24 * openness)
        + scenario.intensity * personal_relevance,
        -1,
        1,
    )


def _tier_parameters(
    population: ResearchPopulation,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    tiers = np.asarray(population.agents["tier"].to_pylist(), dtype=object)
    deliberation = np.full(tiers.size, 0.28)
    decision_noise = np.full(tiers.size, 0.86)
    amplification = np.ones(tiers.size)
    key = tiers == AgentTier.KEY.value
    representative = tiers == AgentTier.REPRESENTATIVE.value
    deliberation[key] = 0.15
    deliberation[representative] = 0.21
    decision_noise[key] = 0.42
    decision_noise[representative] = 0.63
    amplification[key] = 1.8
    amplification[representative] = 1.25
    return deliberation, decision_noise, amplification


def _choose_actions(
    rng: np.random.Generator,
    population: ResearchPopulation,
    state: AgentState,
    decision_noise: NDArray[np.float64],
) -> NDArray[np.int64]:
    expression = _column(population, "expression_tendency")
    positive = np.clip(state.support, 0, 1)
    negative = np.clip(-state.support, 0, 1)
    uncertainty = 1 - np.abs(state.support)
    logits = np.column_stack(
        [
            -0.05 + 1.65 * positive + 0.4 * state.awareness,
            -0.05 + 1.65 * negative + 0.4 * state.awareness,
            -0.38 + 0.95 * expression + 0.65 * np.abs(state.support) + 0.45 * state.awareness,
            -0.12 + 0.72 * expression + 0.78 * uncertainty + 0.28 * state.awareness,
            0.34 + 0.9 * (1 - expression) + 0.72 * (1 - state.awareness),
            -0.62
            + 1.15 * state.action_readiness
            + 0.72 * np.abs(state.support)
            + 0.3 * state.awareness,
            -1.05 + 0.65 * state.risk + 0.62 * np.clip(-state.emotion, 0, 1) + 0.35 * negative,
        ]
    )
    uniforms = np.clip(rng.random(logits.shape), 1e-12, 1 - 1e-12)
    gumbel = -np.log(-np.log(uniforms))
    return np.argmax(logits + gumbel * decision_noise[:, None], axis=1).astype(np.int64)


def _state_metrics(
    population: ResearchPopulation,
    state: AgentState,
    actions: NDArray[np.int64],
) -> NDArray[np.float64]:
    weights = _column(population, "survey_weight")
    weights = weights / weights.sum()

    def weighted(value: NDArray[np.float64] | NDArray[np.bool_]) -> float:
        return float(np.sum(weights * value))

    support = weighted(np.clip(state.support, 0, 1) * state.awareness)
    opposition = weighted(np.clip(-state.support, 0, 1) * state.awareness)
    polarization = float(np.sqrt(np.sum(weights * (state.support - weighted(state.support)) ** 2)))
    return np.asarray(
        [
            weighted(state.awareness),
            support,
            opposition,
            weighted(actions == ACTIONS.index("share")),
            weighted(actions == ACTIONS.index("discuss")),
            weighted(actions == ACTIONS.index("silence")),
            weighted(actions == ACTIONS.index("participate")),
            weighted(actions == ACTIONS.index("exit")),
            polarization,
            weighted(state.trust),
        ],
        dtype=float,
    )


def _state_hash(state: AgentState, actions: NDArray[np.int64]) -> str:
    digest = hashlib.sha256()
    for name in ("awareness", "belief", "support", "emotion", "trust", "risk"):
        digest.update(np.round(getattr(state, name), 8).tobytes())
    digest.update(state.working_memory.tobytes())
    digest.update(state.event_memory.tobytes())
    digest.update(state.event_reached.tobytes())
    digest.update(actions.tobytes())
    return digest.hexdigest()


def _simulate_one_path(
    population: ResearchPopulation,
    event: EventScenario,
    scenario: RuntimeScenario,
    initial_state: AgentState,
    horizon_ticks: int,
    path_index: int,
    seed: int,
) -> tuple[
    NDArray[np.float64],
    AgentState,
    NDArray[np.int64],
    list[dict[str, Any]],
]:
    size = population.agents.num_rows
    rng = np.random.default_rng(seed + path_index * 1_000_003)
    state = initial_state.copy()
    relationship_trust = population.graph.trust.copy()
    channel_match = _channel_match(population, event.channels)
    deliberation, decision_noise, amplification = _tier_parameters(population)
    path_environment = float(np.clip(np.exp(rng.normal(0, 0.14)), 0.65, 1.45))
    personal_relevance = rng.normal(0, 0.075, size)
    alignment = _value_alignment(population, scenario, personal_relevance)
    skepticism = _column(population, "information_skepticism")
    sensitivity = _column(population, "emotional_sensitivity")
    actions = state.last_action.copy()
    timeline = np.empty((horizon_ticks + 1, len(METRICS)), dtype=float)
    timeline[0] = _state_metrics(population, state, actions)
    replay: list[dict[str, Any]] = []
    previous_hash = "0" * 64
    for tick in range(1, horizon_ticks + 1):
        schedule = 0.36 + 0.64 * np.exp(-(tick - 1) / max(5, horizon_ticks / 3))
        active_action = (
            np.isin(
                actions,
                [ACTIONS.index("share"), ACTIONS.index("discuss"), ACTIONS.index("participate")],
            ).astype(float)
            * state.event_reached
        )
        transmitted = active_action * state.awareness * amplification
        neighbor_exposure = population.graph.aggregate_from_sources(
            transmitted, size, trust=relationship_trust
        )
        direct_hazard = np.clip(
            scenario.intensity
            * schedule
            * scenario.credibility
            * (0.035 + 0.2 * channel_match)
            * path_environment,
            0,
            0.95,
        )
        direct_visible = rng.random(size) < direct_hazard
        social_visible = neighbor_exposure > 1e-10
        previously_reached = state.event_reached.copy()
        state.event_reached |= direct_visible | social_visible
        direct_exposure = direct_visible * (0.28 + 0.52 * scenario.credibility)
        exposure = np.clip(direct_exposure + 0.2 * neighbor_exposure, 0, 1)
        awareness_gain = (1 - state.awareness) * exposure
        state.awareness = np.clip(state.awareness + awareness_gain, 0, 1)

        neighbor_stance = population.graph.aggregate_from_sources(
            state.support * active_action, size, trust=relationship_trust
        )
        visible = state.event_reached.astype(float)
        perceived = visible * (
            alignment * (0.42 + 0.58 * scenario.credibility)
            + 0.27 * neighbor_stance
            - 0.12 * skepticism * np.sign(alignment)
            + rng.normal(0, 0.035, size)
        )
        target_support = np.tanh(1.55 * perceived)
        learning_rate = deliberation * (0.22 + 0.78 * state.awareness) * visible
        state.support = np.clip(
            state.support + learning_rate * (target_support - state.support), -1, 1
        )
        updated_belief = np.clip(
            0.86 * state.belief
            + 0.14 * state.awareness * (scenario.credibility * (1 - skepticism)),
            0,
            1,
        )
        state.belief = np.where(state.event_reached, updated_belief, state.belief)
        emotional_target = (
            np.sign(state.support) * sensitivity * (0.25 + 0.75 * np.abs(state.support))
        )
        updated_emotion = np.clip(0.84 * state.emotion + 0.16 * emotional_target, -1, 1)
        state.emotion = np.where(state.event_reached, updated_emotion, state.emotion)
        consistency = 1 - np.abs(target_support - neighbor_stance) / 2
        updated_trust = np.clip(state.trust + 0.012 * state.awareness * (consistency - 0.5), 0, 1)
        state.trust = np.where(state.event_reached, updated_trust, state.trust)
        updated_risk = np.clip(0.9 * state.risk + 0.1 * (sensitivity * np.abs(state.emotion)), 0, 1)
        state.risk = np.where(state.event_reached, updated_risk, state.risk)

        actions = _choose_actions(rng, population, state, decision_noise)
        observed = direct_visible | social_visible
        interacted = state.event_reached & np.isin(
            actions,
            [
                ACTIONS.index("support"),
                ACTIONS.index("oppose"),
                ACTIONS.index("share"),
                ACTIONS.index("discuss"),
                ACTIONS.index("participate"),
            ],
        )
        state.working_memory = np.minimum(
            7,
            np.floor(0.82 * state.working_memory + observed + interacted).astype(np.int64),
        )
        state.event_memory += (observed | interacted).astype(np.int64)
        state.last_action = actions.copy()
        source_active = interacted[population.graph.source]
        stance_distance = np.abs(
            state.support[population.graph.source] - state.support[population.graph.target]
        )
        relationship_trust = np.clip(
            relationship_trust + source_active * 0.006 * (0.5 - stance_distance / 2),
            0.05,
            1,
        )
        timeline[tick] = _state_metrics(population, state, actions)
        state_hash = _state_hash(state, actions)
        record_core = {
            "scenario_id": scenario.scenario_id,
            "path": path_index,
            "tick": tick,
            "previous_hash": previous_hash,
            "state_hash": state_hash,
            "stage_counts": {
                "observed": size,
                "decided": size,
                "acted": size,
                "remembered": size,
            },
            "visibility_counts": {
                "directly_exposed": int(np.sum(direct_visible)),
                "socially_exposed": int(np.sum(social_visible & ~direct_visible)),
                "newly_exposed": int(np.sum(state.event_reached & ~previously_reached)),
                "cumulative_exposed": int(np.sum(state.event_reached)),
                "unexposed": int(np.sum(~state.event_reached)),
            },
            "tier_counts": {
                AgentTier.KEY.value: 50,
                AgentTier.REPRESENTATIVE.value: min(450, size - 50),
                AgentTier.BACKGROUND.value: max(0, size - 500),
            },
        }
        record_hash = stable_hash(record_core)
        replay.append({**record_core, "record_hash": record_hash})
        previous_hash = record_hash
    return timeline, state, actions, replay


def simulate_population(
    population: ResearchPopulation,
    event: EventScenario,
    interpretation: EventInterpretation,
    *,
    horizon_ticks: int,
    paths: int,
    seed: int,
) -> RuntimeBundle:
    initial = initial_agent_state(population)
    scenario_runs: list[ScenarioRun] = []
    for scenario in _scenario_definitions(event, interpretation):
        timelines: list[NDArray[np.float64]] = []
        action_shares: list[NDArray[np.float64]] = []
        final_states: list[AgentState] = []
        final_actions: list[NDArray[np.int64]] = []
        replay_records: list[dict[str, Any]] = []
        for path_index in range(paths):
            timeline, state, actions, replay = _simulate_one_path(
                population,
                event,
                scenario,
                initial,
                horizon_ticks,
                path_index,
                seed,
            )
            timelines.append(timeline)
            final_states.append(state)
            final_actions.append(actions)
            weights = _column(population, "survey_weight")
            weights = weights / weights.sum()
            action_shares.append(
                np.asarray([np.sum(weights * (actions == index)) for index in range(len(ACTIONS))])
            )
            replay_records.extend(replay)
        scenario_runs.append(
            ScenarioRun(
                scenario=scenario,
                timeline=np.stack(timelines),
                final_action_shares=np.stack(action_shares),
                final_states=final_states,
                final_actions=final_actions,
                replay_records=replay_records,
            )
        )
    return RuntimeBundle(
        initial_state=initial,
        scenarios=scenario_runs,
        metric_names=METRICS,
        action_names=ACTIONS,
        interpretation=interpretation,
        evidence_refs=[item.evidence_id for item in event.evidence] or ["event_description"],
    )
