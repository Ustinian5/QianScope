from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.serving.api import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "city-api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_city_api_build_simulate_results_and_replay(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    city = client.get("/v1/cities/suzhou")
    assert city.status_code == 200
    assert city.headers["X-Model-Version"] == "suzhou-coupled-city-runtime-v1"
    assert city.json()["anchor_validation"]["population_matches"] is True
    assert city.json()["microdata_status"] == "synthetic_only"

    built = client.post(
        "/v1/cities/suzhou/build",
        json={"prototype_count": 5_000, "seed": 31},
    )
    assert built.status_code == 200
    assert built.json()["validation"]["graph_edges"] == 40_000
    assert client.get("/health").json()["city_runtime_ready"] is True

    query = {
        "query_id": "api_smoke",
        "city_id": "suzhou",
        "districts": [],
        "segments": [],
        "horizon_days": 1,
        "focal_metrics": ["life_satisfaction", "employment_rate"],
        "events": [],
        "branches": [
            {"branch_id": "control", "name": "control", "interventions": []},
            {"branch_id": "same", "name": "same", "interventions": []},
        ],
        "samples": 1,
        "random_seed": 31,
        "save_micro_snapshots": False,
    }
    simulated = client.post(
        "/v1/cities/suzhou/simulate",
        json={"prototype_count": 5_000, "samples": 1, "seed": 31, "query": query},
    )
    assert simulated.status_code == 200
    body = simulated.json()
    run_id = body["summary"]["run_id"]
    assert body["forecast"]["counterfactual_deltas"]["same"] == {
        "life_satisfaction": 0.0,
        "employment_rate": 0.0,
    }
    assert client.get(f"/v1/city-simulations/{run_id}/results").status_code == 200
    replay = client.get(f"/v1/city-simulations/{run_id}/replay")
    assert replay.json()["valid"] is True
    assert replay.json()["snapshots_valid"] is True
    report = client.get(f"/v1/city-simulations/{run_id}/report")
    assert report.status_code == 200
    assert "模拟苏州" in report.text

    llm_compile = client.post(
        "/v1/cities/suzhou/compile",
        json={"prompt": "模拟高温天气"},
    )
    assert llm_compile.status_code == 503
