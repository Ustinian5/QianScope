from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.demo import run_full_demo
from echo_swm.serving.api import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_api_health_prediction_models_and_calibration(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run_full_demo(5_000, 88, settings)
    client = TestClient(create_app(settings))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["statistical_runtime_ready"]
    assert health.headers["X-Model-Version"] == "echo-structured-logit-v1"

    person = {
        "person_id": "example",
        "age": 28,
        "education_level": 2,
        "income": 80000,
        "student": 0,
        "risk_preference": 0.4,
        "price_sensitivity": 0.6,
        "tech_acceptance": 0.8,
        "brand_trust_pre": 0.7,
        "peer_sensitivity": 0.5,
        "prior_purchase": 1,
        "purchase_intent_pre": 1,
        "survey_weight": 1,
    }
    prediction = client.post(
        "/v1/questionnaires/predict",
        json={"people": [person], "intervention": "price_up_30"},
    )
    assert prediction.status_code == 200
    assert 0 <= prediction.json()["population_predictions"]["purchase_post"] <= 1
    assert client.get("/v1/models").json()["models"]

    calibration = client.post(
        "/v1/calibration/run",
        json={"probabilities": [0.1] * 5 + [0.9] * 5, "outcomes": [0] * 5 + [1] * 5},
    )
    assert calibration.status_code == 200
    assert calibration.json()["promoted"] is False
    assert "echo_requests_total" in client.get("/metrics").text


def test_api_contract_validation_and_llm_not_configured(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    invalid = client.post(
        "/v1/data/validate",
        json={
            "kind": "person",
            "payload": {
                "person_id": "p",
                "source_id": "s",
                "survey_weight": -1,
                "observed_at": "2026-01-01T00:00:00Z",
                "available_at": "2026-01-01T00:00:00Z",
            },
        },
    )
    assert invalid.status_code == 422
    llm = client.post("/v1/llm/test")
    assert llm.status_code == 503
