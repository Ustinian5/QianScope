from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.personas.catalog import MODEL_VERSION
from echo_swm.serving.api import create_app
from echo_swm.world.constants import (
    GUIYANG_REPRESENTED_POPULATION,
    GUIYANG_SCENE_IDS,
    GUIZHOU_UNIVERSITY_SCENE_ID,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "persona-api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_persona_search_profile_relationship_and_interview(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    search = client.get("/v1/personas?query=高校学生&limit=8")
    assert search.status_code == 200, search.text
    assert search.headers["X-Model-Version"] == MODEL_VERSION
    payload = search.json()
    assert payload["total_prototypes"] == 5_000
    assert payload["total_represented_population"] == GUIYANG_REPRESENTED_POPULATION
    assert payload["prototype_matches"] > 0
    assert len(payload["items"]) == 8
    assert len({item["name"] for item in payload["items"]}) == 8
    assert all("北京" not in item["bio"] for item in payload["items"])
    assert all("贵阳" in item["bio"] and "苏州" not in item["bio"] for item in payload["items"])
    assert all(item["location_id"] == GUIZHOU_UNIVERSITY_SCENE_ID for item in payload["items"])
    assert all(item["organization"] == "贵州大学" for item in payload["items"])

    campus_search = client.get("/v1/personas?query=贵州大学&limit=8")
    assert campus_search.status_code == 200
    campus_items = campus_search.json()["items"]
    assert campus_items
    assert any(item["location_id"] == GUIZHOU_UNIVERSITY_SCENE_ID for item in campus_items)

    map_snapshot = client.get("/v1/personas/map")
    assert map_snapshot.status_code == 200, map_snapshot.text
    map_body = map_snapshot.json()
    assert map_body["total_prototypes"] == 5_000
    assert map_body["total_represented_population"] == GUIYANG_REPRESENTED_POPULATION
    assert len(map_body["items"]) == 5_000
    assert len({item["persona_id"] for item in map_body["items"]}) == 5_000
    assert all(item["route_location_ids"] for item in map_body["items"])
    assert {
        location_id for item in map_body["items"] for location_id in item["route_location_ids"]
    } == set(GUIYANG_SCENE_IDS)
    for location_id in GUIYANG_SCENE_IDS:
        scene_search = client.get(f"/v1/personas?location_id={location_id}&limit=1")
        assert scene_search.status_code == 200
        assert scene_search.json()["prototype_matches"] > 0
    assert {item["tier"] for item in map_body["items"]} >= {"background", "representative"}
    assert map_snapshot.headers["etag"]
    assert "max-age=300" in map_snapshot.headers["cache-control"]
    not_modified = client.get(
        "/v1/personas/map",
        headers={"If-None-Match": map_snapshot.headers["etag"]},
    )
    assert not_modified.status_code == 304

    selected = payload["items"][0]
    exact = client.get(f"/v1/personas?query={selected['name']}")
    assert exact.status_code == 200
    assert exact.json()["items"][0]["persona_id"] == selected["persona_id"]

    profile = client.get(f"/v1/personas/{selected['persona_id']}")
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["name"] == selected["name"]
    assert len(body["traits"]) == 5
    assert len(body["values"]) == 10
    assert len(body["frameworks"]) == 9
    assert sum(len(item["dimensions"]) for item in body["frameworks"]) == 54
    assert body["definition_version"] == "echo-persona-definition-v3"
    assert body["profile_completeness"] == 1
    assert body["demographics"]["social_role"] == body["role"]
    assert body["field_origins"]["personality"] == "synthetic_correlated_vector"
    assert len(body["memories"]) == 3
    assert len(body["schedule"]) == 3
    assert body["relationships"]
    assert body["profile_origin"] == "synthetic"
    assert profile.headers["x-content-type-options"] == "nosniff"
    assert profile.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in profile.headers["content-security-policy"]

    interview = client.post(
        f"/v1/personas/{selected['persona_id']}/interview",
        json={
            "question": "你的朋友会怎么看这件事，为什么会影响你的选择？",
            "event_context": "数博会“贵客松”创新赛事开放报名",
        },
    )
    assert interview.status_code == 200, interview.text
    answer = interview.json()
    assert answer["mode"] == "deterministic_persona"
    assert answer["persona_id"] == selected["persona_id"]
    assert answer["answer"]
    assert len(answer["cited_state"]) == 4
    assert answer["cross_check_candidates"]
    assert client.get("/health").json()["persona_runtime_ready"] is True


def test_persona_api_rejects_unknown_id_and_empty_question(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    assert client.get("/v1/personas/agent_missing").status_code == 404
    response = client.post(
        "/v1/personas/agent_missing/interview",
        json={"question": "?"},
    )
    assert response.status_code == 422
