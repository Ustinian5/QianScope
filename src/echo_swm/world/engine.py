from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from echo_swm import DISCLAIMER
from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.config import Settings
from echo_swm.core.ids import file_hash, new_id, stable_hash
from echo_swm.observability.run_manifest import RunManifest, append_jsonl
from echo_swm.research.population import (
    BELIEF_DIMENSIONS,
    BIG_FIVE_DIMENSIONS,
    COGNITIVE_DIMENSIONS,
    GOAL_DIMENSIONS,
    MORAL_DIMENSIONS,
    RISK_DIMENSIONS,
    SCHWARTZ_DIMENSIONS,
)
from echo_swm.world.contracts import (
    AgentTracePoint,
    BeliefDistributionPoint,
    DiffusionPoint,
    EmotionDistributionPoint,
    LocationActivityPoint,
    PopulationHeatCell,
    QuantileBand,
    SegmentDifference,
    WorldPopulationSummary,
    WorldSimulationArtifacts,
    WorldSimulationRequest,
    WorldSimulationResult,
)
from echo_swm.world.decisions import compile_questions, run_independent_decisions
from echo_swm.world.llm import compile_world_scenario
from echo_swm.world.population import WorldPopulation, build_world_population
from echo_swm.world.runtime import (
    ACTIONS,
    CHANNELS,
    EMOTION_DIMENSIONS,
    LOCATION_METRICS,
    STATE_TRANSITION_ORDER,
    PathOutput,
    SnapshotPayload,
    simulate_path,
)

MODEL_VERSION = "independent-agent-deliberation-v1"
DATA_VERSION = "weighted-synthetic-human-digital-twin-v3"

WorldProgressCallback = Callable[[dict[str, Any]], None]


def world_artifact_root(settings: Settings) -> Path:
    return settings.artifact_dir / "social_world"


def _band(values: NDArray[np.float64]) -> QuantileBand:
    return QuantileBand(
        p10=float(np.quantile(values, 0.1)),
        p50=float(np.quantile(values, 0.5)),
        p90=float(np.quantile(values, 0.9)),
        mean=float(np.mean(values)),
    )


def _weighted_mean(
    values: NDArray[np.float64] | NDArray[np.bool_],
    weights: NDArray[np.float64],
    mask: NDArray[np.bool_],
) -> float:
    selected_weights = weights[mask]
    if selected_weights.size == 0 or float(selected_weights.sum()) <= 0:
        return 0.0
    return float(np.average(values[mask], weights=selected_weights))


def _select_trace_agents(population: WorldPopulation, count: int, seed: int) -> NDArray[np.int64]:
    if count == 0:
        return np.asarray([], dtype=np.int64)
    tiers = np.asarray(population.base.agents["tier"].to_pylist(), dtype=object)
    influence = np.asarray(population.base.agents["influence"], dtype=float)
    selected: list[int] = []
    for tier in ("key", "representative", "background"):
        candidates = np.flatnonzero(tiers == tier)
        if candidates.size:
            ranked = candidates[np.argsort(-influence[candidates], kind="stable")]
            selected.extend(ranked[: max(1, count // 4)].tolist())
    campus_types = {"campus", "school", "library", "canteen"}
    campus_locations = {
        index
        for index, location in enumerate(population.locations)
        if location.location_type.value in campus_types
    }
    campus_agents = np.flatnonzero(
        np.isin(population.primary_location, np.asarray(sorted(campus_locations), dtype=np.int64))
    )
    if campus_agents.size:
        selected.extend(campus_agents[: min(3, campus_agents.size)].tolist())
    rng = np.random.default_rng(seed + 8_111)
    remaining = np.setdiff1d(np.arange(population.size, dtype=np.int64), np.asarray(selected))
    if len(selected) < count and remaining.size:
        selected.extend(rng.permutation(remaining)[: count - len(selected)].tolist())
    return np.asarray(list(dict.fromkeys(selected))[:count], dtype=np.int64)


def _diffusion(
    request: WorldSimulationRequest,
    population: WorldPopulation,
    paths: list[PathOutput],
) -> list[DiffusionPoint]:
    awareness = np.stack([item.event_awareness for item in paths])
    new_reach = np.stack([item.event_new_reach for item in paths])
    channel = np.stack([item.channel_reach for item in paths])
    result: list[DiffusionPoint] = []
    for event_index, event in enumerate(request.events):
        for tick in range(request.horizon_ticks + 1):
            reached = awareness[:, tick, event_index]
            result.append(
                DiffusionPoint(
                    event_id=event.event_id,
                    tick=tick,
                    reached_fraction=_band(reached),
                    reached_population=_band(reached * population.represented_population),
                    newly_reached_fraction=_band(new_reach[:, tick, event_index]),
                    channel_reach={
                        name: _band(channel[:, tick, event_index, channel_index])
                        for channel_index, name in enumerate(CHANNELS)
                    },
                )
            )
    return result


def _heatmap(
    request: WorldSimulationRequest,
    population: WorldPopulation,
    paths: list[PathOutput],
) -> list[PopulationHeatCell]:
    stacked = np.stack([item.location_metrics for item in paths])
    result: list[PopulationHeatCell] = []
    for tick in range(request.horizon_ticks + 1):
        for location_index, location in enumerate(population.locations):
            if float(np.mean(stacked[:, tick, location_index, 0])) <= 0:
                continue
            result.append(
                PopulationHeatCell(
                    tick=tick,
                    location_id=location.location_id,
                    metrics={
                        name: _band(stacked[:, tick, location_index, metric_index])
                        for metric_index, name in enumerate(LOCATION_METRICS)
                    },
                )
            )
    return result


def _emotion_distribution(
    request: WorldSimulationRequest, paths: list[PathOutput]
) -> list[EmotionDistributionPoint]:
    stacked = np.stack([item.emotions for item in paths])
    return [
        EmotionDistributionPoint(
            tick=tick,
            metrics={
                name: _band(stacked[:, tick, index])
                for index, name in enumerate(EMOTION_DIMENSIONS)
            },
        )
        for tick in range(request.horizon_ticks + 1)
    ]


def _belief_distribution(
    request: WorldSimulationRequest, paths: list[PathOutput]
) -> list[BeliefDistributionPoint]:
    stacked = np.stack([item.beliefs for item in paths])
    return [
        BeliefDistributionPoint(
            tick=tick,
            beliefs={
                name: _band(stacked[:, tick, index]) for index, name in enumerate(BELIEF_DIMENSIONS)
            },
        )
        for tick in range(request.horizon_ticks + 1)
    ]


def _segment_differences(
    population: WorldPopulation, paths: list[PathOutput]
) -> list[SegmentDifference]:
    result: list[SegmentDifference] = []
    for field in ("age_group", "social_role", "primary_channel"):
        values = np.asarray(population.base.agents[field].to_pylist(), dtype=object)
        for value in np.unique(values):
            mask = values == value
            reached_values: list[float] = []
            support_values: list[float] = []
            action_values: list[NDArray[np.float64]] = []
            for path in paths:
                reached = np.max(path.final_state.event_awareness, axis=1)
                support = np.mean(path.final_state.beliefs, axis=1)
                reached_values.append(_weighted_mean(reached, population.weights, mask))
                support_values.append(_weighted_mean(support, population.weights, mask))
                action_values.append(
                    np.asarray(
                        [
                            _weighted_mean(path.final_actions == index, population.weights, mask)
                            for index in range(len(ACTIONS))
                        ]
                    )
                )
            action_matrix = np.stack(action_values)
            leading_index = int(np.argmax(action_matrix.mean(axis=0)))
            result.append(
                SegmentDifference(
                    segment_field=field,
                    segment_value=str(value),
                    prototype_count=int(np.sum(mask)),
                    represented_population=float(population.weights[mask].sum()),
                    reached_fraction=_band(np.asarray(reached_values)),
                    support=_band(np.asarray(support_values)),
                    leading_action=ACTIONS[leading_index],
                    leading_action_share=_band(action_matrix[:, leading_index]),
                )
            )
    return result


def _location_activity(
    request: WorldSimulationRequest,
    population: WorldPopulation,
    paths: list[PathOutput],
) -> list[LocationActivityPoint]:
    metrics = np.stack([item.location_metrics for item in paths])
    actions = np.stack([item.location_action_shares for item in paths])
    result: list[LocationActivityPoint] = []
    for tick in range(request.horizon_ticks + 1):
        for location_index, location in enumerate(population.locations):
            present = float(np.mean(metrics[:, tick, location_index, 0]))
            if present <= 0:
                continue
            dominant = int(np.argmax(actions[:, tick, location_index].mean(axis=0)))
            result.append(
                LocationActivityPoint(
                    tick=tick,
                    location_id=location.location_id,
                    present_population=present,
                    awareness=_band(metrics[:, tick, location_index, 1]),
                    active_expression=_band(metrics[:, tick, location_index, 2]),
                    dominant_action=ACTIONS[dominant],
                )
            )
    return result


def _save_snapshot(path: Path, snapshot: SnapshotPayload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        location=snapshot.location,
        event_awareness=snapshot.event_awareness,
        beliefs=snapshot.beliefs,
        emotion=snapshot.emotion,
        goals=snapshot.goals,
        actions=snapshot.actions,
        working_memory_salience=snapshot.working_memory_salience,
        episodic_memory_count=snapshot.episodic_memory_count,
        semantic_memory_strength=snapshot.semantic_memory_strength,
        relationship_trust=snapshot.relationship_trust,
        state_hash=np.asarray(snapshot.state_hash),
    )


def _write_trajectory(path: Path, request: WorldSimulationRequest, paths: list[PathOutput]) -> None:
    awareness = np.stack([item.event_awareness for item in paths])
    emotions = np.stack([item.emotions for item in paths])
    beliefs = np.stack([item.beliefs for item in paths])
    actions = np.stack([item.action_shares for item in paths])
    rows: list[dict[str, Any]] = []
    for path_index in range(len(paths)):
        for tick in range(request.horizon_ticks + 1):
            row: dict[str, Any] = {"path": path_index, "tick": tick}
            row.update(
                {
                    f"awareness_{event.event_id}": awareness[path_index, tick, event_index]
                    for event_index, event in enumerate(request.events)
                }
            )
            row.update(
                {
                    f"emotion_{name}": emotions[path_index, tick, index]
                    for index, name in enumerate(EMOTION_DIMENSIONS)
                }
            )
            row.update(
                {
                    f"belief_{name}": beliefs[path_index, tick, index]
                    for index, name in enumerate(BELIEF_DIMENSIONS)
                }
            )
            row.update(
                {
                    f"action_{name}": actions[path_index, tick, index]
                    for index, name in enumerate(ACTIONS)
                }
            )
            rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _trace_table(records: list[AgentTracePoint]) -> pa.Table:
    rows = []
    for record in records:
        row = record.model_dump()
        for name in (
            "received_event_ids",
            "aware_event_ids",
            "received_channels",
            "beliefs",
            "emotion",
            "goals",
            "reason_codes",
        ):
            row[name] = json.dumps(row[name], ensure_ascii=False, sort_keys=True)
        rows.append(row)
    if rows:
        return pa.Table.from_pylist(rows)
    return pa.table(
        {
            "agent_id": pa.array([], type=pa.string()),
            "path": pa.array([], type=pa.int64()),
            "tick": pa.array([], type=pa.int64()),
        }
    )


def _artifact_hashes(run_dir: Path, snapshot_paths: list[Path]) -> dict[str, str]:
    named = {
        "result.json": run_dir / "result.json",
        "trajectory.csv": run_dir / "trajectory.csv",
        "agent_traces.parquet": run_dir / "agent_traces.parquet",
        "replay.jsonl": run_dir / "replay.jsonl",
        "population.parquet": run_dir / "population.parquet",
        "relationships.parquet": run_dir / "relationships.parquet",
        "locations.json": run_dir / "locations.json",
        "agent_decisions.parquet": run_dir / "agent_decisions.parquet",
    }
    hashes = {name: file_hash(path) for name, path in named.items()}
    hashes.update(
        {
            str(path.relative_to(run_dir)).replace("\\", "/"): file_hash(path)
            for path in snapshot_paths
        }
    )
    return hashes


def run_world_simulation(
    request: WorldSimulationRequest,
    settings: Settings | None = None,
    *,
    progress_callback: WorldProgressCallback | None = None,
) -> WorldSimulationResult:
    runtime_settings = settings or Settings.load()
    ai_execution = []
    if runtime_settings.llm_configured:
        _, base_questions = compile_questions(request)
        llm = OpenAICompatibleLLM(runtime_settings)
        request = compile_world_scenario(request, base_questions, llm)
        if llm.last_execution is not None:
            ai_execution.append(llm.last_execution)
    population = build_world_population(request.world, request.seed)
    total_decisions = population.size * request.decision_rounds
    if progress_callback is not None:
        progress_callback(
            {
                "phase": "population",
                "processed_decisions": 0,
                "total_decisions": total_decisions,
                "processed_agents": 0,
                "total_agents": population.size,
                "current_round": 0,
                "total_rounds": request.decision_rounds,
            }
        )
    decision_run = run_independent_decisions(
        request,
        population,
        progress_callback=progress_callback,
    )
    trace_indices = _select_trace_agents(population, request.trace_agent_count, request.seed)
    outputs: list[PathOutput] = []
    for path_index in range(request.paths):
        outputs.append(
            simulate_path(
                population,
                request,
                path_index=path_index,
                trace_indices=trace_indices,
            )
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "world_state",
                    "processed_decisions": total_decisions,
                    "total_decisions": total_decisions,
                    "processed_agents": population.size,
                    "total_agents": population.size,
                    "current_round": request.decision_rounds,
                    "total_rounds": request.decision_rounds,
                    "completed_paths": path_index + 1,
                    "total_paths": request.paths,
                }
            )
    run_id = new_id("worldrun")
    run_dir = world_artifact_root(runtime_settings) / "runs" / run_id
    snapshot_dir = run_dir / "snapshots"
    run_dir.mkdir(parents=True, exist_ok=True)
    profile_table = population.base.agents.append_column(
        "represented_weight", pa.array(population.weights)
    )
    profile_table = profile_table.append_column(
        "home_location_id",
        pa.array([population.location_ids[index] for index in population.home_location]),
    )
    profile_table = profile_table.append_column(
        "primary_location_id",
        pa.array([population.location_ids[index] for index in population.primary_location]),
    )
    profile_table = profile_table.append_column(
        "social_location_id",
        pa.array([population.location_ids[index] for index in population.social_location]),
    )
    pq.write_table(profile_table, run_dir / "population.parquet", compression="zstd")
    pq.write_table(
        pa.table(
            {
                "source": population.graph.source,
                "target": population.graph.target,
                "relationship_type": population.graph.relation_type.tolist(),
                "strength": population.graph.strength,
                "trust": population.graph.trust,
                "similarity": population.graph.similarity,
                "influence": population.graph.influence,
                "frequency": population.graph.frequency,
                "channel": population.graph.channel.tolist(),
            }
        ),
        run_dir / "relationships.parquet",
        compression="zstd",
    )
    (run_dir / "locations.json").write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in population.locations],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    snapshot_paths: list[Path] = []
    replay_path = run_dir / "replay.jsonl"
    for path_index, output in enumerate(outputs):
        for record in output.replay_records:
            append_jsonl(replay_path, record)
        for snapshot in output.snapshots:
            path = snapshot_dir / f"path_{path_index:03d}" / f"tick_{snapshot.tick:04d}.npz"
            _save_snapshot(path, snapshot)
            snapshot_paths.append(path)

    _write_trajectory(run_dir / "trajectory.csv", request, outputs)
    trace_records = [
        AgentTracePoint.model_validate(record)
        for output in outputs
        for record in output.trace_records
    ]
    pq.write_table(
        _trace_table(trace_records), run_dir / "agent_traces.parquet", compression="zstd"
    )
    pq.write_table(
        decision_run.individual_decisions,
        run_dir / "agent_decisions.parquet",
        compression="zstd",
    )
    action_stack = np.stack([item.action_shares[-1] for item in outputs])
    diffusion = _diffusion(request, population, outputs)
    heatmap = _heatmap(request, population, outputs)
    emotion_distribution = _emotion_distribution(request, outputs)
    belief_distribution = _belief_distribution(request, outputs)
    segment_difference = _segment_differences(population, outputs)
    location_activity = _location_activity(request, population, outputs)
    deterministic_payload = {
        "request": request.model_dump(mode="json"),
        "population_manifest": population.manifest,
        "diffusion": [item.model_dump(mode="json") for item in diffusion],
        "emotions": [item.model_dump(mode="json") for item in emotion_distribution],
        "beliefs": [item.model_dump(mode="json") for item in belief_distribution],
        "actions": np.round(action_stack, 10).tolist(),
        "independent_decisions": decision_run.report.model_dump(mode="json"),
    }
    deterministic_signature = stable_hash(deterministic_payload)
    artifacts = WorldSimulationArtifacts(
        result_json=str((run_dir / "result.json").resolve()),
        trajectory_csv=str((run_dir / "trajectory.csv").resolve()),
        agent_traces=str((run_dir / "agent_traces.parquet").resolve()),
        replay_log=str(replay_path.resolve()),
        run_manifest=str((run_dir / "run_manifest.json").resolve()),
        snapshot_directory=str(snapshot_dir.resolve()),
        population_profiles=str((run_dir / "population.parquet").resolve()),
        relationships=str((run_dir / "relationships.parquet").resolve()),
        locations=str((run_dir / "locations.json").resolve()),
        agent_decisions=str((run_dir / "agent_decisions.parquet").resolve()),
    )
    result = WorldSimulationResult(
        run_id=run_id,
        project_id=request.project_id,
        world_id=request.world.world_id,
        model_version=MODEL_VERSION,
        data_version=DATA_VERSION,
        population=WorldPopulationSummary(
            prototype_count=population.size,
            represented_population=population.represented_population,
            tier_counts=population.manifest["tier_counts"],
            relationship_count=population.graph.edge_count,
            relationship_types=population.manifest["relationship_types"],
            location_count=len(population.locations),
            immutable_personality_signature=population.personality_signature,
        ),
        diffusion_curve=diffusion,
        population_heatmap=heatmap,
        emotion_distribution=emotion_distribution,
        belief_distribution=belief_distribution,
        segment_difference=segment_difference,
        location_activity=location_activity,
        agent_trace=trace_records,
        decision_report=decision_run.report,
        final_action_distribution={
            name: _band(action_stack[:, index]) for index, name in enumerate(ACTIONS)
        },
        state_transition_order=list(STATE_TRANSITION_ORDER),
        ai_execution=ai_execution,
        deterministic_signature=deterministic_signature,
        artifacts=artifacts,
        limitations=[
            "The people are weighted synthetic prototypes, not records of identifiable residents.",
            (
                "Uncalibrated synthetic mechanisms must be fitted and externally validated "
                "before real-world claims."
            ),
            (
                "Location ids are semantic backend entities and do not imply AMap or any "
                "other UI integration."
            ),
            (
                "Agent traces and answers are simulated receipts and must not be "
                "presented as quotes "
                "from real people."
            ),
        ],
        disclaimer=DISCLAIMER,
    )
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    artifact_hashes = _artifact_hashes(run_dir, snapshot_paths)
    manifest = RunManifest(
        run_id=run_id,
        scenario_id=request.project_id,
        root_seed=request.seed,
        model_version=MODEL_VERSION,
        data_version=DATA_VERSION,
        graph_version=population.graph.graph_version,
        prompt_version="human-digital-twin-social-world-v2",
        config_hash=stable_hash(
            {
                "horizon_ticks": request.horizon_ticks,
                "paths": request.paths,
                "snapshot_interval": request.snapshot_interval,
            }
        ),
        input_hash=stable_hash(request.model_dump(mode="json")),
        output_hash=deterministic_signature,
        warnings=result.limitations,
        metadata={
            "personality_signature": population.personality_signature,
            "prototype_count": population.size,
            "represented_population": population.represented_population,
            "relationship_count": population.graph.edge_count,
            "location_count": len(population.locations),
            "path_count": request.paths,
            "horizon_ticks": request.horizon_ticks,
            "artifact_hashes": artifact_hashes,
            "interaction_mode": request.interaction_mode,
            "decision_rounds": request.decision_rounds,
            "total_decisions": decision_run.report.total_decisions,
            "ai_execution": [item.model_dump(mode="json") for item in ai_execution],
            "replay_records": sum(len(item.replay_records) for item in outputs),
        },
    )
    manifest.write(run_dir / "run_manifest.json")
    return result


def _run_dir(run_id: str, settings: Settings) -> Path:
    runs_root = (world_artifact_root(settings) / "runs").resolve()
    path = (runs_root / run_id).resolve()
    if not path.is_relative_to(runs_root) or not path.is_dir():
        raise FileNotFoundError(f"social-world simulation not found: {run_id}")
    return path


def load_world_simulation(run_id: str, settings: Settings | None = None) -> WorldSimulationResult:
    runtime_settings = settings or Settings.load()
    path = _run_dir(run_id, runtime_settings) / "result.json"
    return WorldSimulationResult.model_validate_json(path.read_text(encoding="utf-8"))


def search_world_agents(
    run_id: str,
    settings: Settings | None = None,
    *,
    query: str = "",
    tier: str | None = None,
    location_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    runtime_settings = settings or Settings.load()
    run_dir = _run_dir(run_id, runtime_settings)
    rows = pq.read_table(run_dir / "population.parquet").to_pylist()
    normalized_query = query.strip().casefold()

    def matches(row: dict[str, Any]) -> bool:
        if tier is not None and row["tier"] != tier:
            return False
        if location_id is not None and location_id not in {
            row["home_location_id"],
            row["primary_location_id"],
            row["social_location_id"],
        }:
            return False
        if not normalized_query:
            return True
        searchable = (
            row["agent_id"],
            row["segment"],
            row["social_role"],
            row["age_group"],
            row["primary_goal"],
            row["primary_interest"],
            row["primary_channel"],
        )
        return any(normalized_query in str(value).casefold() for value in searchable)

    matched = [row for row in rows if matches(row)]
    selected = matched[: max(1, min(limit, 100))]
    fields = (
        "agent_id",
        "tier",
        "represented_weight",
        "segment",
        "age_group",
        "social_role",
        "primary_goal",
        "primary_interest",
        "primary_channel",
        "home_location_id",
        "primary_location_id",
        "social_location_id",
        "profile_hash",
    )
    return {
        "run_id": run_id,
        "prototype_matches": len(matched),
        "represented_population": float(sum(float(row["represented_weight"]) for row in matched)),
        "items": [{field: row[field] for field in fields} for row in selected],
        "note": "Search results are weighted synthetic prototypes, not identifiable residents.",
    }


def get_world_agent(run_id: str, agent_id: str, settings: Settings | None = None) -> dict[str, Any]:
    runtime_settings = settings or Settings.load()
    run_dir = _run_dir(run_id, runtime_settings)
    table = pq.read_table(run_dir / "population.parquet")
    ids = table["agent_id"].to_pylist()
    try:
        row_index = ids.index(agent_id)
    except ValueError as exc:
        raise FileNotFoundError(f"agent not found: {agent_id}") from exc
    row = table.slice(row_index, 1).to_pylist()[0]

    def vector(prefix: str, dimensions: tuple[str, ...]) -> dict[str, float]:
        return {name: float(row[f"{prefix}{name}"]) for name in dimensions}

    relationships = pq.read_table(run_dir / "relationships.parquet")
    source = np.asarray(relationships["source"], dtype=np.int64)
    target = np.asarray(relationships["target"], dtype=np.int64)
    connected = np.flatnonzero((source == row_index) | (target == row_index))[:50]
    relationship_rows = relationships.take(pa.array(connected)).to_pylist()
    for relation in relationship_rows:
        peer_index = (
            int(relation["target"])
            if int(relation["source"]) == row_index
            else int(relation["source"])
        )
        relation["peer_agent_id"] = str(ids[peer_index])
    result = load_world_simulation(run_id, runtime_settings)
    traces = [
        item.model_dump(mode="json") for item in result.agent_trace if item.agent_id == agent_id
    ]
    return {
        "agent_id": agent_id,
        "identity": {
            name: row[name]
            for name in (
                "age",
                "age_group",
                "gender",
                "education_level",
                "social_role",
                "region_type",
                "household_type",
                "segment",
            )
        },
        "personality": {
            "big_five": vector("big5_", BIG_FIVE_DIMENSIONS),
            "schwartz_values": vector("schwartz_", SCHWARTZ_DIMENSIONS),
            "moral_foundations": vector("moral_", MORAL_DIMENSIONS),
            "risk_profile": vector("risk_", RISK_DIMENSIONS),
            "cognitive_style": vector("cognitive_", COGNITIVE_DIMENSIONS),
            "immutable_profile_hash": row["profile_hash"],
        },
        "baseline_beliefs": vector("belief_", BELIEF_DIMENSIONS),
        "baseline_goals": vector("goal_", GOAL_DIMENSIONS),
        "habits": {
            "primary_goal": row["primary_goal"],
            "primary_interest": row["primary_interest"],
            "primary_channel": row["primary_channel"],
        },
        "mobility": {
            "home_location_id": row["home_location_id"],
            "primary_location_id": row["primary_location_id"],
            "social_location_id": row["social_location_id"],
        },
        "tier": row["tier"],
        "represented_weight": row["represented_weight"],
        "relationships": relationship_rows,
        "simulation_trace": traces,
        "profile_origin": row["profile_origin"],
        "disclaimer": DISCLAIMER,
    }


def get_world_location(
    run_id: str, location_id: str, settings: Settings | None = None
) -> dict[str, Any]:
    runtime_settings = settings or Settings.load()
    run_dir = _run_dir(run_id, runtime_settings)
    locations = json.loads((run_dir / "locations.json").read_text(encoding="utf-8"))
    try:
        location = next(item for item in locations if item["location_id"] == location_id)
    except StopIteration as exc:
        raise FileNotFoundError(f"location not found: {location_id}") from exc
    profiles = pq.read_table(run_dir / "population.parquet")
    weights = np.asarray(profiles["represented_weight"], dtype=float)
    home = np.asarray(profiles["home_location_id"].to_pylist(), dtype=object)
    primary = np.asarray(profiles["primary_location_id"].to_pylist(), dtype=object)
    social = np.asarray(profiles["social_location_id"].to_pylist(), dtype=object)
    result = load_world_simulation(run_id, runtime_settings)
    return {
        "run_id": run_id,
        "location": location,
        "assigned_population": {
            "home": float(weights[home == location_id].sum()),
            "primary": float(weights[primary == location_id].sum()),
            "social": float(weights[social == location_id].sum()),
        },
        "population_heatmap": [
            item.model_dump(mode="json")
            for item in result.population_heatmap
            if item.location_id == location_id
        ],
        "activity": [
            item.model_dump(mode="json")
            for item in result.location_activity
            if item.location_id == location_id
        ],
    }


def verify_world_replay(run_id: str, settings: Settings | None = None) -> dict[str, Any]:
    runtime_settings = settings or Settings.load()
    run_dir = _run_dir(run_id, runtime_settings)
    manifest = RunManifest.read(run_dir / "run_manifest.json")
    lines = [
        json.loads(line)
        for line in (run_dir / "replay.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    previous_by_path: dict[int, str] = {}
    chain_valid = True
    personality_immutable = True
    snapshots_valid = True
    ticks_by_path: dict[int, list[int]] = {}
    resolved_run_dir = run_dir.resolve()
    for record in lines:
        path_index = int(record["path"])
        previous = previous_by_path.get(path_index, "0" * 64)
        record_hash = str(record["record_hash"])
        core = {key: value for key, value in record.items() if key != "record_hash"}
        if record["previous_hash"] != previous or stable_hash(core) != record_hash:
            chain_valid = False
        previous_by_path[path_index] = record_hash
        ticks_by_path.setdefault(path_index, []).append(int(record["tick"]))
        if record["personality_signature"] != manifest.metadata["personality_signature"]:
            personality_immutable = False
        snapshot_name = record.get("snapshot")
        if snapshot_name:
            snapshot_path = (run_dir / "snapshots" / str(snapshot_name)).resolve()
            if not snapshot_path.is_relative_to(resolved_run_dir) or not snapshot_path.exists():
                snapshots_valid = False
            else:
                with np.load(snapshot_path) as payload:
                    if str(payload["state_hash"].item()) != record["state_hash"]:
                        snapshots_valid = False
    expected_records = int(manifest.metadata["replay_records"])
    expected_paths = int(manifest.metadata.get("path_count", len(ticks_by_path)))
    expected_horizon = int(
        manifest.metadata.get(
            "horizon_ticks",
            max((max(ticks) for ticks in ticks_by_path.values() if ticks), default=-1),
        )
    )
    path_count_valid = sorted(ticks_by_path) == list(range(expected_paths))
    tick_sequences_valid = path_count_valid and all(
        ticks_by_path[path_index] == list(range(expected_horizon + 1))
        for path_index in range(expected_paths)
    )
    stored_hashes = dict(manifest.metadata["artifact_hashes"])
    artifact_hashes_valid = True
    for name, expected_hash in stored_hashes.items():
        artifact_path = (run_dir / name).resolve()
        if (
            not artifact_path.is_relative_to(resolved_run_dir)
            or not artifact_path.exists()
            or file_hash(artifact_path) != expected_hash
        ):
            artifact_hashes_valid = False
            break
    checks = {
        "record_count": len(lines) == expected_records,
        "hash_chain": chain_valid,
        "path_count": path_count_valid,
        "tick_sequences": tick_sequences_valid,
        "personality_immutable": personality_immutable,
        "snapshots": snapshots_valid,
        "artifact_hashes": artifact_hashes_valid,
    }
    return {
        "run_id": run_id,
        "valid": all(checks.values()),
        "checks": checks,
        "records": len(lines),
        "paths": len(ticks_by_path),
        "personality_signature": manifest.metadata["personality_signature"],
    }
