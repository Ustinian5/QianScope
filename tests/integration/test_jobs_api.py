from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.jobs.manager import MODEL_VERSION
from echo_swm.serving.api import create_app


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "jobs-api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_insight_background_job_progress_and_result_recovery(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        created = client.post(
            "/v1/jobs/insight",
            json={
                "tool": "trend",
                "fields": {"term": "夜间学习空间", "horizon": "1周"},
            },
        )
        assert created.status_code == 200, created.text
        assert created.headers["X-Model-Version"] == MODEL_VERSION
        job_id = created.json()["job_id"]
        assert created.json()["status"] in {"queued", "running"}

        # Coverage instrumentation makes the cold 5,000-persona build slower on CI.
        deadline = time.monotonic() + 30
        record = created.json()
        while record["status"] not in {"complete", "failed", "cancelled"}:
            assert time.monotonic() < deadline
            record = client.get(f"/v1/jobs/{job_id}").json()
            time.sleep(0.02)
        assert record["status"] == "complete", record
        assert record["progress"] == 100
        assert record["processed_agents"] == 5_000
        assert record["result_available"] is True

        result = client.get(f"/v1/jobs/{job_id}/result")
        assert result.status_code == 200, result.text
        assert result.json()["tool"] == "trend"
        assert result.json()["population"]["agent_count"] == 5_000
        assert client.get("/health").json()["job_runtime_ready"] is True
        assert client.get("/v1/jobs/job_missing").status_code == 404


def test_job_cancel_endpoint_is_idempotent(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        created = client.post(
            "/v1/jobs/insight",
            json={"tool": "brand", "fields": {"brand": "ECHO"}},
        )
        assert created.status_code == 200
        job_id = created.json()["job_id"]
        cancelled = client.post(f"/v1/jobs/{job_id}/cancel")
        repeated = client.post(f"/v1/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200
        assert repeated.status_code == 200
        assert repeated.json()["status"] in {"cancelling", "cancelled", "complete"}


def test_world_job_reports_actual_rounds_decisions_and_live_agent_feed(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        preset = client.get("/v1/social-world/preset").json()
        created = client.post(
            "/v1/jobs/world",
            json={
                "project_id": "independent_world_job",
                "events": [preset["example_event"]],
                "horizon_ticks": 1,
                "paths": 1,
                "trace_agent_count": 1,
                "snapshot_interval": 1,
                "decision_rounds": 3,
                "seed": 2026,
            },
        )
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        deadline = time.monotonic() + 30
        record = created.json()
        while record["status"] not in {"complete", "failed", "cancelled"}:
            assert time.monotonic() < deadline
            record = client.get(f"/v1/jobs/{job_id}").json()
            time.sleep(0.02)

        assert record["status"] == "complete", record
        assert record["current_round"] == record["total_rounds"] == 3
        assert record["processed_decisions"] == record["total_decisions"] == 15_000
        assert len(record["decision_feed"]) == 10
        assert all(item["choice"] for item in record["decision_feed"])
        result = client.get(f"/v1/jobs/{job_id}/result").json()
        assert result["decision_report"]["completed_decisions"] == 15_000
        assert result["decision_report"]["interaction_mode"] == "independent"
