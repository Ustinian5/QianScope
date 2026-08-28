from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.research.examples import (
    example_calibration_dataset,
    example_population_margins,
    example_prediction_request,
)
from echo_swm.serving.api import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "research-api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_questionnaire_driven_prediction_api_round_trip(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    request = example_prediction_request(paths=3)
    assert request.population is not None
    assert request.questionnaire is not None

    population = client.post(
        "/v1/populations/generate",
        json=request.population.model_dump(mode="json"),
        headers={"Idempotency-Key": "population-demo"},
    )
    assert population.status_code == 200
    assert population.json()["validation"]["tier_counts"]["background"] == 4_500
    repeated_population = client.post(
        "/v1/populations/generate",
        json=request.population.model_dump(mode="json"),
        headers={"Idempotency-Key": "population-demo"},
    )
    assert repeated_population.json() == population.json()
    assert client.get("/v1/populations/general_population_5000").status_code == 200

    questionnaire = client.post(
        "/v1/questionnaires",
        json=request.questionnaire.model_dump(mode="json"),
    )
    assert questionnaire.status_code == 200
    assert questionnaire.json()["question_count"] == 10
    assert client.get("/v1/questionnaires/general_event_reaction_10q").status_code == 200

    assert client.get("/v1/examples/population-margin").status_code == 200
    assert client.get("/v1/examples/calibration-dataset").status_code == 200
    margin_dataset = example_population_margins()
    margin = client.post(
        "/v1/population-margins",
        json=margin_dataset.model_dump(mode="json"),
    )
    assert margin.status_code == 200, margin.text
    assert (
        client.post(
            "/v1/population-margins",
            json=margin_dataset.model_dump(mode="json"),
        ).status_code
        == 200
    )
    conflicting_margin = margin_dataset.model_dump(mode="json")
    conflicting_margin["name"] = "different content"
    assert client.post("/v1/population-margins", json=conflicting_margin).status_code == 409
    assert client.get(f"/v1/population-margins/{margin_dataset.dataset_id}").status_code == 200

    calibration_dataset = example_calibration_dataset()
    calibration_data = client.post(
        "/v1/calibration-datasets",
        json=calibration_dataset.model_dump(mode="json"),
    )
    assert calibration_data.status_code == 200, calibration_data.text
    calibration = client.post(
        "/v1/calibrations",
        json={"dataset_id": calibration_dataset.dataset_id},
    )
    assert calibration.status_code == 200, calibration.text
    calibration_profile = calibration.json()
    assert calibration_profile["status"] == "validated"
    assert (
        client.get(f"/v1/calibrations/{calibration_profile['calibration_id']}").status_code == 200
    )

    payload = request.model_copy(
        update={
            "population": None,
            "population_id": "general_population_5000",
            "questionnaire": None,
            "questionnaire_id": "general_event_reaction_10q",
            "population_margin_id": margin_dataset.dataset_id,
            "calibration_id": calibration_profile["calibration_id"],
        }
    ).model_dump(mode="json")
    prediction = client.post("/v1/predictions", json=payload)
    assert prediction.status_code == 200, prediction.text
    assert prediction.headers["X-Model-Version"] == "questionnaire-event-swm-v3"
    body = prediction.json()
    run_id = body["run_id"]
    assert body["population"]["agents_acted"] == 5_000
    assert body["grounding"]["status"] == "synthetic_anchored_to_authorized_aggregates"
    assert body["population"]["represented_population"] == 100_000
    assert body["calibration"]["applied"] is True
    assert len(body["questionnaire_forecast"]) == 10
    assert body["l2_evaluation"]["capability_level"] == "constrained_l2"
    assert body["l2_evaluation"]["common_random_numbers"] is True
    assert len(body["l2_evaluation"]["scenario_ranking"]) == 3
    assert body["l2_evaluation"]["protocol_lock"]["future_information_forbidden"] is True
    assert body["report_metadata"]["model_version"] == "questionnaire-event-swm-v3"
    assert body["report_metadata"]["successful_agents"] == 5_000
    assert body["report_metadata"]["failed_agents"] == 0
    assert body["report_quality"]["failures"] == 0
    assert body["report_quality"]["passed"] >= 7
    assert len(body["questionnaire_forecast"][0]["cross_tabs"]) == 6
    assert len(body["questionnaire_forecast"][0]["representative_responses"]) == 3
    assert body["questionnaire_forecast"][0]["cross_tabs"][0]["group_label"] == "年龄"
    assert client.get(f"/v1/predictions/{run_id}").status_code == 200
    assert client.get("/v1/predictions").json()["items"][0]["run_id"] == run_id
    assert client.get(f"/v1/predictions/{run_id}/replay").json()["valid"] is True

    outcome = client.post(
        f"/v1/predictions/{run_id}/outcomes",
        json={
            "sample_size": 100,
            "questionnaire_results": {"q03_stance": {"support": 0.5}},
            "event_outcomes": {"broad_awareness": True},
        },
    )
    assert outcome.status_code == 200
    assert outcome.json()["evaluation"]["matched_values"] == 2
    assert outcome.json()["calibration_observations_appended"] == 2
    exported_json = client.get(f"/v1/predictions/{run_id}/export?format=json")
    exported_csv = client.get(f"/v1/predictions/{run_id}/export?format=csv")
    assert exported_json.status_code == 200
    assert exported_csv.status_code == 200
    assert "question_id" in exported_csv.text
    health = client.get("/health").json()
    assert health["generic_prediction_runtime_ready"] is True
    assert health["personality_population_ready"] is True
