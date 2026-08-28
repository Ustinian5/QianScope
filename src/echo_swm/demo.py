from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from echo_swm.core.config import Settings
from echo_swm.data.synthetic import BRANCHES, TARGETS, write_synthetic_demo
from echo_swm.data.validation.leakage import scan_table_for_leakage
from echo_swm.evaluation.evaluate import evaluate_bundle, write_evaluation
from echo_swm.models.echo import (
    NUMERIC_FEATURES,
    EchoModelBundle,
    respondent_split,
    train_echo_model,
)
from echo_swm.population.weighting import effective_sample_size
from echo_swm.simulation.engine import SimulationResult, run_counterfactual_simulation


def demo_dir(settings: Settings | None = None) -> Path:
    return (settings or Settings.load()).artifact_dir / "demo"


def generate_demo(size: int = 10_000, seed: int = 2026, settings: Settings | None = None) -> Path:
    root = demo_dir(settings)
    path = write_synthetic_demo(root, size=size, seed=seed)
    table = pq.read_table(path)
    weights = np.asarray(table["survey_weight"].to_numpy(), dtype=float)
    segments = table.group_by("segment").aggregate(
        [("survey_weight", "sum"), ("person_id", "count")]
    )
    rows = "".join(
        f"<tr><td>{segment}</td><td>{count}</td><td>{weight:.1f}</td></tr>"
        for segment, weight, count in zip(
            segments["segment"].to_pylist(),
            segments["survey_weight_sum"].to_pylist(),
            segments["person_id_count"].to_pylist(),
            strict=True,
        )
    )
    html = (
        "<!doctype html><meta charset='utf-8'><title>Synthetic population</title>"
        "<style>body{font:15px system-ui;max-width:900px;margin:40px auto}"
        "table{border-collapse:collapse}"
        "td,th{border:1px solid #bbb;padding:8px}</style>"
        "<h1>Synthetic population report</h1><p>SYNTHETIC DATA — NOT REAL HUMAN DATA</p>"
        f"<p>Rows: {table.num_rows}; weighted population: {weights.sum():.1f}; "
        f"effective sample size: {effective_sample_size(weights):.1f}</p>"
        "<table><tr><th>Segment</th><th>Records</th><th>Weight</th></tr>" + rows + "</table>"
    )
    (root / "population_report.html").write_text(html, encoding="utf-8")
    return path


def train_demo(settings: Settings | None = None) -> Path:
    root = demo_dir(settings)
    data_path = root / "population.parquet"
    if not data_path.exists():
        raise FileNotFoundError("generate demo data before training")
    table = pq.read_table(data_path)
    findings = scan_table_for_leakage(
        table, NUMERIC_FEATURES + ("treatment",), datetime(2026, 1, 1, tzinfo=UTC)
    )
    if findings:
        raise ValueError(f"leakage scanner rejected training data: {findings}")
    train_indices, calibration_indices, test_indices = respondent_split(table.num_rows)
    bundle = train_echo_model(table, train_indices, calibration_indices)
    model_path = root / "models" / "echo.joblib"
    bundle.save(model_path)
    np.savez_compressed(
        root / "split_indices.npz",
        train=train_indices,
        calibration=calibration_indices,
        test=test_indices,
    )
    card = {
        "model_version": bundle.model_version,
        "data_version": bundle.data_version,
        "training_rows": int(train_indices.size),
        "calibration_rows": int(calibration_indices.size),
        "test_rows": int(test_indices.size),
        "features": [*NUMERIC_FEATURES, "treatment"],
        "targets": list(TARGETS),
        "intended_use": "synthetic/offline conditional probability experiments",
        "limitations": [
            "not trained on real people",
            "not valid for high-risk individual decisions",
            "event vocabulary is limited to demo branches",
        ],
    }
    (root / "model_card.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return model_path


def evaluate_demo(settings: Settings | None = None) -> dict[str, Any]:
    root = demo_dir(settings)
    bundle = EchoModelBundle.load(root / "models" / "echo.joblib")
    table = pq.read_table(root / "population.parquet")
    with np.load(root / "split_indices.npz") as splits:
        test_indices = splits["test"]
    report = evaluate_bundle(bundle, table, test_indices)
    write_evaluation(report, root)
    calibration_rows = []
    for target, variants in report["targets"].items():
        calibration_rows.append(
            {
                "target": target,
                "uncalibrated_ece": variants["echo_uncalibrated"]["ece"],
                "calibrated_ece": variants["echo_calibrated"]["ece"],
                "temperature": variants["temperature"],
            }
        )
    (root / "calibration_report.html").write_text(
        "<!doctype html><meta charset='utf-8'><h1>Calibration report</h1><pre>"
        + json.dumps(calibration_rows, ensure_ascii=False, indent=2)
        + "</pre><p>Holdout calibration metrics; synthetic data only.</p>",
        encoding="utf-8",
    )
    return report


def _write_segment_predictions(
    table: pa.Table, result: SimulationResult, destination: Path
) -> None:
    weights = np.asarray(table["survey_weight"].to_numpy(), dtype=float)
    segments = np.asarray(table["segment"].to_pylist(), dtype=object)
    bundle = EchoModelBundle.load(destination.parent / "models" / "echo.joblib")
    rows: list[dict[str, Any]] = []
    for branch in BRANCHES:
        predictions = bundle.predict(table, branch)
        for segment in np.unique(segments):
            mask = segments == segment
            row: dict[str, Any] = {
                "run_id": result.run_id,
                "branch": branch,
                "segment": str(segment),
                "sample_size": int(mask.sum()),
                "weight": float(weights[mask].sum()),
            }
            for target in TARGETS:
                row[target] = float(np.average(predictions[target][mask], weights=weights[mask]))
            rows.append(row)
    pq.write_table(pa.Table.from_pylist(rows), destination)


def simulate_demo(settings: Settings | None = None) -> SimulationResult:
    root = demo_dir(settings)
    table = pq.read_table(root / "population.parquet")
    bundle = EchoModelBundle.load(root / "models" / "echo.joblib")
    result = run_counterfactual_simulation(table, bundle, root / "runs")
    for name in [
        "counterfactual_report.html",
        "trajectory.csv",
        "individual_predictions.parquet",
        "run_manifest.json",
        "replay.jsonl",
    ]:
        shutil.copy2(result.output_dir / name, root / name)
    _write_segment_predictions(table, result, root / "segment_predictions.parquet")
    summary = {
        "run_id": result.run_id,
        "completed_at": datetime.now(UTC).isoformat(),
        "branch_results": result.branch_results,
        "counterfactual_deltas": result.counterfactual_deltas,
        "artifacts": sorted(path.name for path in root.iterdir() if path.is_file()),
    }
    (root.parent / "latest_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def run_full_demo(
    size: int = 10_000, seed: int = 2026, settings: Settings | None = None
) -> dict[str, Any]:
    generate_demo(size=size, seed=seed, settings=settings)
    train_demo(settings=settings)
    evaluation = evaluate_demo(settings=settings)
    simulation = simulate_demo(settings=settings)
    mean_metrics = {
        metric: float(
            np.mean(
                [evaluation["targets"][target]["echo_calibrated"][metric] for target in TARGETS]
            )
        )
        for metric in ("log_loss", "brier", "ece")
    }
    summary = {
        "run_id": simulation.run_id,
        "rows": size,
        "holdout_mean_metrics": mean_metrics,
        "branch_results": simulation.branch_results,
        "artifact_dir": str(demo_dir(settings).resolve()),
    }
    (demo_dir(settings).parent / "latest_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
