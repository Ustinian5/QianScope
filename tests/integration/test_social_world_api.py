from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.serving.api import create_app
from echo_swm.world.constants import (
    GUIYANG_CONVENTION_CENTER_ID,
    GUIYANG_REPRESENTED_POPULATION,
)
from echo_swm.world.engine import MODEL_VERSION


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


def test_social_world_api_event_run_replay_search_and_drilldown(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    preset = client.get("/v1/social-world/preset")
    assert preset.status_code == 200
    assert preset.headers["X-Model-Version"] == MODEL_VERSION
    assert preset.json()["world"]["world_id"] == "guiyang_social_world"
    assert any(
        item["location_id"] == GUIYANG_CONVENTION_CENTER_ID
        for item in preset.json()["world"]["locations"]
    )
    convention_center = next(
        item
        for item in preset.json()["world"]["locations"]
        if item["location_id"] == GUIYANG_CONVENTION_CENTER_ID
    )
    assert convention_center["name"] == "贵阳国际会议展览中心"
    assert convention_center["parent_id"] == "guiyang"
    assert "数博会" in preset.json()["example_event"]["title"]
    assert "贵客松" in preset.json()["example_event"]["title"]
    body = {
        "project_id": "api_world",
        "events": [preset.json()["example_event"]],
        "horizon_ticks": 2,
        "paths": 1,
        "trace_agent_count": 2,
        "snapshot_interval": 1,
        "seed": 123,
    }
    response = client.post("/v1/social-world/simulations", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    run_id = payload["run_id"]
    assert payload["population"]["represented_population"] == GUIYANG_REPRESENTED_POPULATION
    assert client.get(f"/v1/social-world/simulations/{run_id}").status_code == 200
    replay = client.get(f"/v1/social-world/simulations/{run_id}/replay")
    assert replay.status_code == 200
    assert replay.json()["valid"] is True

    search = client.get(f"/v1/social-world/simulations/{run_id}/agents?limit=1")
    assert search.status_code == 200
    agent_id = search.json()["items"][0]["agent_id"]
    agent = client.get(f"/v1/social-world/simulations/{run_id}/agents/{agent_id}")
    assert agent.status_code == 200
    assert len(agent.json()["personality"]["big_five"]) == 5
    location = client.get(
        f"/v1/social-world/simulations/{run_id}/locations/{GUIYANG_CONVENTION_CENTER_ID}"
    )
    assert location.status_code == 200
    snapshot = client.get(f"/v1/social-world/simulations/{run_id}/snapshots/0/0")
    assert snapshot.status_code == 200
