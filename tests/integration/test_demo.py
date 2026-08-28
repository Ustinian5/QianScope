from __future__ import annotations

import json
from pathlib import Path

from echo_swm.core.config import Settings
from echo_swm.demo import run_full_demo
from echo_swm.simulation.snapshot import SnapshotStore


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_end_to_end_demo_produces_real_artifacts_and_replay(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    summary = run_full_demo(5_000, 77, settings)
    root = settings.artifact_dir / "demo"
    required = {
        "population_report.html",
        "model_evaluation.html",
        "calibration_report.html",
        "counterfactual_report.html",
        "trajectory.csv",
        "individual_predictions.parquet",
        "segment_predictions.parquet",
        "run_manifest.json",
        "replay.jsonl",
    }
    assert required.issubset({path.name for path in root.iterdir()})
    assert summary["holdout_mean_metrics"]["brier"] < 0.25
    run_dir = root / "runs" / summary["run_id"]
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["root_seed"] == 2026
    final = SnapshotStore(run_dir / "snapshots").load("price_up_30", 14)
    assert final.tick == 14
    assert final.awareness.mean() > 0.5
