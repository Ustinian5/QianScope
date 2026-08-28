from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from echo_swm.core.config import Settings
from echo_swm.event_forecasting.contracts import EventForecastQuery, EventForecastResult
from echo_swm.event_forecasting.engine import run_event_forecast, verify_event_replay


def default_event_query_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scenarios" / "event_chain_forecast.json"


def load_event_query(path: Path | None = None) -> EventForecastQuery:
    raw = (path or default_event_query_path()).read_text(encoding="utf-8")
    return EventForecastQuery.model_validate_json(raw)


def event_artifact_root(settings: Settings | None = None) -> Path:
    return (settings or Settings.load()).artifact_dir / "event_forecasts"


def run_event_demo(
    query: EventForecastQuery | None = None,
    settings: Settings | None = None,
) -> tuple[EventForecastResult, dict[str, Any]]:
    root = event_artifact_root(settings)
    result = run_event_forecast(query or load_event_query(), root / "runs")
    replay = verify_event_replay(Path(result.artifact_dir))
    latest = root / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for name in (
        "forecast.json",
        "probability_curves.csv",
        "event_paths.npz",
        "replay.jsonl",
        "run_manifest.json",
    ):
        shutil.copy2(Path(result.artifact_dir) / name, latest / name)
    summary = {
        "run_id": result.run_id,
        "model_version": result.model_version,
        "domain": result.query.domain,
        "candidate_probabilities": {
            branch_id: {
                candidate.candidate_id: candidate.occurrence_probability
                for candidate in branch.candidates
            }
            for branch_id, branch in result.branches.items()
        },
        "counterfactual_probability_deltas": result.counterfactual_probability_deltas,
        "calibration_status": result.calibration_status,
        "replay": replay,
        "artifact_dir": result.artifact_dir,
    }
    (root / "latest_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result, summary
