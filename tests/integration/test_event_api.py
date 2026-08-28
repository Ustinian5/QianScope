from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.serving.api import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "event-api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_event_forecast_api_default_run_results_replay_and_backtest(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    response = client.post("/v1/event-forecasts", json={})
    assert response.status_code == 200
    assert response.headers["X-Model-Version"] == "echo-event-hazard-chain-v1"
    body = response.json()
    run_id = body["summary"]["run_id"]
    assert body["forecast"]["calibration_status"] == "prior_predictive_uncalibrated"
    assert client.get(f"/v1/event-forecasts/{run_id}/results").status_code == 200
    replay = client.get(f"/v1/event-forecasts/{run_id}/replay")
    assert replay.json()["valid"] is True

    records = [
        {
            "forecast_id": "f0",
            "candidate_id": "event",
            "forecast_as_of": "2026-01-01T00:00:00Z",
            "horizon_end": "2026-01-08T00:00:00Z",
            "probability": 0.2,
            "outcome": 0,
            "outcome_available_at": "2026-01-09T00:00:00Z",
            "weight": 1,
        },
        {
            "forecast_id": "f1",
            "candidate_id": "event",
            "forecast_as_of": "2026-01-02T00:00:00Z",
            "horizon_end": "2026-01-09T00:00:00Z",
            "probability": 0.8,
            "outcome": 1,
            "outcome_available_at": "2026-01-10T00:00:00Z",
            "weight": 1,
        },
    ]
    backtest = client.post(
        "/v1/event-forecasts/backtest",
        json={"records": records, "bins": 5},
    )
    assert backtest.status_code == 200
    assert backtest.json()["brier_score"] < 0.1

    compile_response = client.post(
        "/v1/event-forecasts/compile",
        json={"prompt": "预测未来一个月可能出现的供应链中断事件"},
    )
    assert compile_response.status_code == 503
