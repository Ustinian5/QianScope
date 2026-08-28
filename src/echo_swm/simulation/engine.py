from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from echo_swm import DISCLAIMER
from echo_swm.agents.selector import ActiveAgentSelector, AgentTiers
from echo_swm.core.ids import new_id, stable_hash
from echo_swm.data.synthetic import BRANCHES, TARGETS
from echo_swm.graph.generation import GeneratedGraph, generate_homophilic_graph
from echo_swm.models.echo import EchoModelBundle
from echo_swm.observability.run_manifest import RunManifest, append_jsonl
from echo_swm.population.weighting import effective_sample_size, weighted_mean
from echo_swm.simulation.snapshot import Snapshot, SnapshotStore


@dataclass(frozen=True)
class SimulationResult:
    run_id: str
    trajectory: list[dict[str, Any]]
    branch_results: dict[str, dict[str, float]]
    counterfactual_deltas: dict[str, dict[str, float]]
    tiers: AgentTiers
    output_dir: Path
    manifest: RunManifest


def _weighted_confidence_interval(
    values: NDArray[np.float64], weights: NDArray[np.float64]
) -> tuple[float, float]:
    mean = weighted_mean(values, weights)
    normalized = weights / weights.sum()
    variance = float(np.sum(normalized * np.square(values - mean)))
    standard_error = np.sqrt(variance / effective_sample_size(weights))
    return max(0.0, mean - 1.96 * standard_error), min(1.0, mean + 1.96 * standard_error)


def _select_tiers(
    table: pa.Table,
    graph: GeneratedGraph,
    probabilities: dict[str, NDArray[np.float64]],
) -> AgentTiers:
    count = table.num_rows
    centrality = graph.weighted_in_degree(count)
    influence = np.asarray(table["peer_sensitivity"].to_numpy(), dtype=float) * (centrality + 1)
    purchase = probabilities["purchase_post"]
    uncertainty = 1 - np.abs(purchase - 0.5) * 2
    exposure = np.asarray(table["tech_acceptance"].to_numpy(), dtype=float)
    segments = np.asarray(table["segment"].to_pylist(), dtype=object)
    _, frequencies = np.unique(segments, return_counts=True)
    frequency_map = dict(zip(np.unique(segments), frequencies, strict=True))
    diversity = np.asarray([1 / frequency_map[item] for item in segments], dtype=float)
    return ActiveAgentSelector().select(
        centrality,
        influence,
        uncertainty,
        exposure,
        diversity,
        key_count=max(1, int(count * 0.01)),
        representative_count=max(1, int(count * 0.10)),
    )


def _simulate_branch(
    table: pa.Table,
    bundle: EchoModelBundle,
    graph: GeneratedGraph,
    branch: str,
    days: int,
    snapshot_store: SnapshotStore,
    replay_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, NDArray[np.float64]]]:
    weights = np.asarray(table["survey_weight"].to_numpy(), dtype=float)
    peer_sensitivity = np.asarray(table["peer_sensitivity"].to_numpy(), dtype=float)
    predictions = bundle.predict(table, intervention=branch)
    awareness = np.full(table.num_rows, 0.08 if branch == "control" else 0.28, dtype=float)
    negative = predictions["complain_post"].copy()
    purchase = predictions["purchase_post"].copy()
    trust = predictions["trust_high_post"].copy()
    broadcast = 0.015 if branch == "control" else 0.085
    recommendation_strength = 0.35
    trajectory: list[dict[str, Any]] = []

    for tick in range(days + 1):
        expressed_negative = awareness * negative
        snapshot = Snapshot(
            branch, tick, awareness.copy(), expressed_negative.copy(), purchase.copy(), trust.copy()
        )
        snapshot_path = snapshot_store.save(snapshot)
        record = {
            "branch": branch,
            "day": tick,
            "awareness": weighted_mean(awareness, weights),
            "purchase_probability": weighted_mean(purchase, weights),
            "brand_trust_probability": weighted_mean(trust, weights),
            "complaint_probability": weighted_mean(expressed_negative, weights),
            "churn_probability": weighted_mean(predictions["churn_post"] * awareness, weights),
            "recommend_probability": weighted_mean(predictions["recommend_post"], weights),
            "snapshot_hash": snapshot.content_hash,
        }
        trajectory.append(record)
        append_jsonl(
            replay_path,
            {
                "type": "snapshot",
                "branch": branch,
                "tick": tick,
                "snapshot_path": str(snapshot_path),
                "snapshot_hash": snapshot.content_hash,
                "macro_hash": stable_hash(record),
            },
        )
        if tick == days:
            break
        neighbor_negative = graph.aggregate_from_sources(expressed_negative, table.num_rows)
        exposure_pressure = np.clip(broadcast + recommendation_strength * neighbor_negative, 0, 0.5)
        awareness = np.clip(awareness + (1 - awareness) * exposure_pressure, 0, 1)
        social_delta = np.clip(
            peer_sensitivity * (neighbor_negative - expressed_negative) * 0.18,
            -0.08,
            0.08,
        )
        negative = np.clip(negative + social_delta, 0, 1)
        purchase = np.clip(purchase - np.maximum(social_delta, 0) * 0.30, 0, 1)
        trust = np.clip(trust - np.maximum(social_delta, 0) * 0.20, 0, 1)
    return trajectory, {
        **predictions,
        "awareness": awareness,
        "negative_expression": awareness * negative,
    }


def run_counterfactual_simulation(
    table: pa.Table,
    bundle: EchoModelBundle,
    output_dir: Path,
    *,
    days: int = 14,
    seed: int = 2026,
) -> SimulationResult:
    if days < 1 or days > 365:
        raise ValueError("simulation horizon must be between 1 and 365 days")
    run_id = new_id("run")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    graph = generate_homophilic_graph(table, seed=seed)
    snapshot_store = SnapshotStore(run_dir / "snapshots")
    replay_path = run_dir / "replay.jsonl"
    all_trajectory: list[dict[str, Any]] = []
    branch_arrays: dict[str, dict[str, NDArray[np.float64]]] = {}
    for branch in BRANCHES:
        trajectory, arrays = _simulate_branch(
            table, bundle, graph, branch, days, snapshot_store, replay_path
        )
        all_trajectory.extend(trajectory)
        branch_arrays[branch] = arrays

    weights = np.asarray(table["survey_weight"].to_numpy(), dtype=float)
    branch_results: dict[str, dict[str, float]] = {}
    confidence_intervals: dict[str, dict[str, tuple[float, float]]] = {}
    for branch, arrays in branch_arrays.items():
        result = {target: weighted_mean(arrays[target], weights) for target in TARGETS}
        confidence_intervals[branch] = {
            target: _weighted_confidence_interval(arrays[target], weights) for target in TARGETS
        }
        result["awareness"] = weighted_mean(arrays["awareness"], weights)
        result["negative_expression"] = weighted_mean(arrays["negative_expression"], weights)
        result["ground_truth_purchase"] = weighted_mean(
            np.asarray(table[f"gt_purchase_post_{branch}"].to_numpy(), dtype=float), weights
        )
        branch_results[branch] = result
    control = branch_results["control"]
    deltas = {
        branch: {key: value - control.get(key, 0.0) for key, value in result.items()}
        for branch, result in branch_results.items()
        if branch != "control"
    }
    base_predictions = bundle.predict(table, intervention="control")
    tiers = _select_tiers(table, graph, base_predictions)

    trajectory_path = run_dir / "trajectory.csv"
    with trajectory_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_trajectory[0]))
        writer.writeheader()
        writer.writerows(all_trajectory)
    individual = pa.table(
        {
            "person_id": table["person_id"],
            "survey_weight": table["survey_weight"],
            **{
                f"{branch}_{target}": pa.array(branch_arrays[branch][target])
                for branch in BRANCHES
                for target in TARGETS
            },
        }
    )
    pq.write_table(individual, run_dir / "individual_predictions.parquet", compression="zstd")
    output_payload = {
        "run_id": run_id,
        "branch_results": branch_results,
        "counterfactual_deltas": deltas,
        "confidence_intervals_95": confidence_intervals,
        "effective_sample_size": effective_sample_size(weights),
        "tier_counts": {
            "key": tiers.key_agents.size,
            "representative": tiers.representative_agents.size,
            "background": tiers.background_agents.size,
        },
        "disclaimer": DISCLAIMER,
    }
    (run_dir / "results.json").write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = RunManifest(
        run_id=run_id,
        scenario_id="price_change_demo",
        root_seed=seed,
        model_version=bundle.model_version,
        data_version=bundle.data_version,
        graph_version=graph.graph_version,
        config_hash=stable_hash({"days": days, "seed": seed, "branches": BRANCHES}),
        input_hash=stable_hash(
            {
                "rows": table.num_rows,
                "schema": str(table.schema),
                "person_ids": table["person_id"].to_pylist(),
            }
        ),
        output_hash=stable_hash({"trajectory": all_trajectory, "results": output_payload}),
        metadata={"edge_count": graph.edge_count, "weighted_population": float(weights.sum())},
    )
    manifest.write(run_dir / "run_manifest.json")
    _write_counterfactual_report(run_dir, output_payload)
    return SimulationResult(
        run_id, all_trajectory, branch_results, deltas, tiers, run_dir, manifest
    )


def _write_counterfactual_report(run_dir: Path, payload: dict[str, Any]) -> None:
    rows = []
    for branch, values in payload["branch_results"].items():
        rows.append(
            "<tr>"
            f"<td>{branch}</td><td>{values['purchase_post']:.3f}</td>"
            f"<td>{values['ground_truth_purchase']:.3f}</td>"
            f"<td>{values['trust_high_post']:.3f}</td><td>{values['churn_post']:.3f}</td>"
            f"<td>{values['awareness']:.3f}</td></tr>"
        )
    html = (
        "<!doctype html><meta charset='utf-8'><title>ECHO-SWM counterfactual</title>"
        "<style>body{font:15px system-ui;max-width:1000px;margin:40px auto}"
        "table{border-collapse:collapse}"
        "th,td{padding:9px;border:1px solid #ccd1d1}th{background:#e8f6f3}</style>"
        "<h1>Counterfactual price experiment</h1><p>SYNTHETIC DATA — NOT REAL HUMAN DATA</p>"
        "<table><tr><th>Branch</th><th>Predicted purchase</th><th>Ground truth purchase</th>"
        "<th>Trust</th><th>Churn</th><th>Day-14 awareness</th></tr>"
        + "".join(rows)
        + "</table><h2>Runtime tiers</h2><pre>"
        + json.dumps(payload["tier_counts"], ensure_ascii=False, indent=2)
        + "</pre><p>本结果为概率模拟与条件预测，不构成对现实结果的保证。</p>"
    )
    (run_dir / "counterfactual_report.html").write_text(html, encoding="utf-8")
