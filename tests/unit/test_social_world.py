from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from echo_swm.core.config import Settings
from echo_swm.research.population import (
    BELIEF_DIMENSIONS,
    BIG_FIVE_DIMENSIONS,
    COGNITIVE_DIMENSIONS,
    GOAL_DIMENSIONS,
    MORAL_DIMENSIONS,
    RISK_DIMENSIONS,
    SCHWARTZ_DIMENSIONS,
)
from echo_swm.world.constants import (
    GUIYANG_CONVENTION_CENTER_ID,
    GUIYANG_REPRESENTED_POPULATION,
)
from echo_swm.world.contracts import WorldEvent, WorldSimulationRequest
from echo_swm.world.decisions import compile_questions, run_independent_decisions
from echo_swm.world.engine import (
    get_world_agent,
    get_world_location,
    run_world_simulation,
    search_world_agents,
    verify_world_replay,
)
from echo_swm.world.population import (
    RELATIONSHIP_TYPES,
    build_world_population,
    validate_world_population,
)
from echo_swm.world.runtime import ACTIONS, STATE_TRANSITION_ORDER, simulate_path


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "world-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def _request(*, paths: int = 2) -> WorldSimulationRequest:
    return WorldSimulationRequest(
        project_id="campus_launch_test",
        events=[
            WorldEvent(
                event_id="launch",
                title="新品发布与限时优惠",
                description="某科技品牌在校园发布新品并提供优惠。",
                start_tick=1,
                duration_ticks=4,
                source_location_id=GUIYANG_CONVENTION_CENTER_ID,
                target_location_ids=[GUIYANG_CONVENTION_CENTER_ID],
                channels=["social_media", "interpersonal", "onsite"],
                intensity=0.9,
                credibility=0.8,
                novelty=0.85,
                valence=0.5,
                belief_signals={"technology": 0.65, "brand_trust": 0.55},
                value_signals={"achievement": 0.4, "self_direction": 0.25},
                goal_signals={"growth": 0.5, "achievement": 0.45},
            )
        ],
        horizon_ticks=4,
        paths=paths,
        trace_agent_count=4,
        snapshot_interval=2,
        seed=91,
    )


def test_world_population_has_complete_structured_personality_and_graph() -> None:
    request = _request(paths=1)
    population = build_world_population(request.world, request.seed)
    columns = set(population.base.agents.column_names)
    expected = {
        *(f"big5_{name}" for name in BIG_FIVE_DIMENSIONS),
        *(f"schwartz_{name}" for name in SCHWARTZ_DIMENSIONS),
        *(f"moral_{name}" for name in MORAL_DIMENSIONS),
        *(f"risk_{name}" for name in RISK_DIMENSIONS),
        *(f"cognitive_{name}" for name in COGNITIVE_DIMENSIONS),
        *(f"goal_{name}" for name in GOAL_DIMENSIONS),
        *(f"belief_{name}" for name in BELIEF_DIMENSIONS),
    }
    assert expected <= columns
    assert population.size == 5_000
    assert population.represented_population == GUIYANG_REPRESENTED_POPULATION
    assert population.graph.edge_count == 30_000
    assert set(population.graph.relation_type.tolist()) == set(RELATIONSHIP_TYPES)
    assert len(population.locations) >= 9
    assert validate_world_population(population, request.world)["valid"] is True

    first = simulate_path(
        population,
        request,
        path_index=0,
        trace_indices=np.asarray([0, 1], dtype=np.int64),
    )
    second = simulate_path(
        population,
        request,
        path_index=0,
        trace_indices=np.asarray([0, 1], dtype=np.int64),
    )
    assert np.array_equal(first.event_awareness, second.event_awareness)
    assert first.event_awareness[0, 0] == 0
    assert first.event_awareness[-1, 0] > 0
    final_awareness = first.final_state.event_awareness[:, 0]
    assert set(np.unique(final_awareness).tolist()) <= {0.0, 1.0}
    assert set(np.unique(first.final_state.channel_awareness).tolist()) <= {0.0, 1.0}
    untouched = final_awareness == 0
    assert np.any(untouched)
    assert np.all(first.final_actions[untouched] == ACTIONS.index("ignore"))
    baseline_beliefs = np.column_stack(
        [
            np.asarray(population.base.agents[f"belief_{name}"], dtype=float) * 2 - 1
            for name in BELIEF_DIMENSIONS
        ]
    )
    assert np.array_equal(first.final_state.beliefs[untouched], baseline_beliefs[untouched])
    baseline_confidence = np.asarray(population.base.agents["belief_confidence"], dtype=float)
    assert np.allclose(
        first.final_state.belief_confidence[untouched], baseline_confidence[untouched, None]
    )
    baseline_stress = np.asarray(population.base.agents["baseline_stress"], dtype=float)
    assert np.allclose(first.final_state.stress, baseline_stress)
    baseline_trust = np.clip(
        0.5 * np.asarray(population.base.agents["social_trust"], dtype=float)
        + 0.5 * np.asarray(population.base.agents["institutional_trust"], dtype=float),
        0,
        1,
    )
    assert not np.allclose(first.final_state.trust, baseline_trust)

    negative_event = request.events[0].model_copy(
        update={
            "event_id": "incident",
            "title": "校园服务事故",
            "description": "服务中断引发安全担忧。",
            "valence": -0.9,
            "belief_signals": {"social_attitude": -0.8, "institutional_trust": -0.6},
            "value_signals": {"security": 0.8},
        }
    )
    negative_request = request.model_copy(update={"events": [negative_event], "seed": 92})
    negative = simulate_path(
        population,
        negative_request,
        path_index=0,
        trace_indices=np.asarray([], dtype=np.int64),
    )
    negative_reached = negative.final_state.event_awareness[:, 0] > 0.5
    assert np.any(negative_reached)
    assert (
        np.mean(negative.final_state.stress[negative_reached] - baseline_stress[negative_reached])
        > 0
    )
    assert np.mean(negative.final_state.anger[negative_reached]) > 0
    assert np.allclose(
        negative.final_state.stress[~negative_reached], baseline_stress[~negative_reached]
    )
    assert all(
        record["personality_signature"] == population.personality_signature
        for record in first.replay_records
    )
    assert first.replay_records[-1]["stage_order"] == list(STATE_TRANSITION_ORDER)


def test_world_run_persists_replays_and_supports_drilldown(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    result = run_world_simulation(_request(), settings)
    assert result.population.prototype_count == 5_000
    assert result.population.relationship_types == sorted(RELATIONSHIP_TYPES)
    assert result.diffusion_curve[0].reached_fraction.mean == 0
    assert result.diffusion_curve[-1].reached_fraction.mean > 0
    assert (
        result.diffusion_curve[-1].reached_fraction.p90
        > result.diffusion_curve[-1].reached_fraction.p10
    )
    assert all(item.aware_event_ids or item.action == "ignore" for item in result.agent_trace)
    assert all(
        set(item.received_event_ids) <= set(item.aware_event_ids) for item in result.agent_trace
    )
    assert result.state_transition_order == list(STATE_TRANSITION_ORDER)
    assert set(result.final_action_distribution) == {
        "ignore",
        "consume",
        "discuss",
        "share",
        "support",
        "oppose",
        "participate",
        "exit",
    }
    replay = verify_world_replay(result.run_id, settings)
    assert replay["valid"] is True
    assert replay["checks"]["personality_immutable"] is True

    search = search_world_agents(result.run_id, settings, limit=3)
    assert search["prototype_matches"] == 5_000
    assert len(search["items"]) == 3
    agent_id = search["items"][0]["agent_id"]
    agent = get_world_agent(result.run_id, agent_id, settings)
    assert set(agent["personality"]) == {
        "big_five",
        "schwartz_values",
        "moral_foundations",
        "risk_profile",
        "cognitive_style",
        "immutable_profile_hash",
    }
    assert agent["relationships"]
    location = get_world_location(result.run_id, GUIYANG_CONVENTION_CENTER_ID, settings)
    assert location["location"]["location_type"] == "workplace"
    assert location["assigned_population"]["primary"] > 0


def test_independent_agents_make_real_variable_multi_round_decisions() -> None:
    request = _request(paths=1).model_copy(update={"decision_rounds": 4})
    population = build_world_population(request.world, request.seed)
    updates: list[dict[str, object]] = []
    first = run_independent_decisions(
        request,
        population,
        progress_callback=updates.append,
        batch_size=250,
    )
    second = run_independent_decisions(request, population, batch_size=500)

    assert first.report.total_decisions == 5_000 * 4
    assert first.report.completed_decisions == first.report.total_decisions
    assert first.individual_decisions.num_rows == first.report.total_decisions
    assert [len(item.options) for item in first.report.rounds] == [5, 5, 5, 4]
    assert all(item.agent_count == 5_000 for item in first.report.rounds)
    assert all(
        abs(sum(option.share for option in item.options) - 1) < 1e-9 for item in first.report.rounds
    )
    assert first.report.deterministic_signature == second.report.deterministic_signature
    assert updates[-1]["processed_decisions"] == first.report.total_decisions
    assert updates[-1]["preview"]

    rows = first.individual_decisions.to_pylist()
    lookup = {(str(row["agent_id"]), int(row["round_index"])): str(row["choice"]) for row in rows}
    for round_result in first.report.rounds:
        assert len(round_result.representatives) == min(5, len(round_result.options))
        for representative in round_result.representatives:
            assert (
                lookup[(representative.agent_id, round_result.round_index)] == representative.choice
            )


def test_decision_report_does_not_read_relationship_graph() -> None:
    request = _request(paths=1).model_copy(update={"decision_rounds": 2})
    population = build_world_population(request.world, request.seed)
    disconnected_graph = replace(
        population.graph,
        trust=np.zeros_like(population.graph.trust),
        strength=np.zeros_like(population.graph.strength),
        influence=np.zeros_like(population.graph.influence),
    )
    disconnected_population = replace(population, graph=disconnected_graph)
    connected = run_independent_decisions(request, population, batch_size=500)
    disconnected = run_independent_decisions(request, disconnected_population, batch_size=500)
    assert connected.report.deterministic_signature == disconnected.report.deterministic_signature
    assert connected.individual_decisions.equals(disconnected.individual_decisions)


def test_event_semantics_generate_different_questions_and_response_spaces() -> None:
    product = _request(paths=1).model_copy(update={"decision_rounds": 3})
    risk_event = product.events[0].model_copy(
        update={
            "event_id": "risk",
            "title": "公共空间发生设备安全事故",
            "description": "设备故障导致服务中断，现已启动检测和风险处置。",
            "valence": -0.8,
        }
    )
    risk = product.model_copy(update={"events": [risk_event]})
    product_category, product_questions = compile_questions(product)
    risk_category, risk_questions = compile_questions(risk)
    assert product_category == "technology"
    assert risk_category == "risk"
    assert product_questions[0].prompt != risk_questions[0].prompt
    assert [item.label for item in product_questions[0].options] != [
        item.label for item in risk_questions[0].options
    ]
