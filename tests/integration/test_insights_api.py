from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from echo_swm.core.config import Settings
from echo_swm.insights.engine import MODEL_VERSION
from echo_swm.serving.api import create_app
from echo_swm.world.constants import GUIYANG_REPRESENTED_POPULATION


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "insight-api-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_all_agent_insight_tools_run_and_persist(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    fields_by_tool = {
        "marketing": {"event": "夜间公共学习空间发布体验招募", "horizon": "1周"},
        "trend": {"term": "夜间学习空间", "horizon": "1周"},
        "brand": {"brand": "ECHO 预见"},
        "product": {"features": "可解释报告, 情景对比, 数据导出"},
        "pricing": {
            "product": "事件预测服务",
            "prices": "49, 99, 199, 399",
            "audience": "研究者与产品团队",
        },
        "competitive": {
            "brand": "我方产品",
            "competitor": "主要竞品",
            "action": "竞品降价并上线更快的推演功能",
        },
        "funnel": {"product": "首次事件推演", "channel": "内容社区 + 搜索"},
        "churn": {"change": "价格上调并减少免费次数", "horizon": "1月"},
        "creator": {"brief": "向研究者解释事件预测平台", "platform": "专业社群"},
    }

    first_signature: tuple[str, list[dict[str, object]]] | None = None
    for tool, fields in fields_by_tool.items():
        response = client.post(
            "/v1/insights",
            json={"tool": tool, "fields": fields},
        )
        assert response.status_code == 200, response.text
        assert response.headers["X-Model-Version"] == MODEL_VERSION
        body = response.json()
        assert body["tool"] == tool
        assert body["status"] == "complete"
        assert body["population"]["agent_count"] == 5_000
        assert body["population"]["represented_population"] == GUIYANG_REPRESENTED_POPULATION
        assert body["population"]["population_origin"] == "synthetic"
        assert body["provenance"]["calibrated"] is False
        assert body["provenance"]["grounding_status"] == "synthetic_unanchored"
        assert body["bars"]
        assert len(body["quotes"]) == 3
        assert all(0 <= bar["value"] <= 100 for bar in body["bars"])
        run_id = body["run_id"]
        assert client.get(f"/v1/insights/{run_id}").json() == body
        if tool == "marketing":
            assert sum(bar["value"] for bar in body["bars"]) == 100
            first_signature = (body["metric_value"], body["bars"])

    repeated = client.post(
        "/v1/insights",
        json={"tool": "marketing", "fields": fields_by_tool["marketing"]},
    )
    assert repeated.status_code == 200
    assert first_signature == (repeated.json()["metric_value"], repeated.json()["bars"])
    assert client.get("/health").json()["insight_runtime_ready"] is True


def test_insight_contract_rejects_incomplete_tool_input(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    missing_feature = client.post(
        "/v1/insights",
        json={"tool": "product", "fields": {"features": "只有一个功能"}},
    )
    missing_price = client.post(
        "/v1/insights",
        json={
            "tool": "pricing",
            "fields": {"product": "服务", "prices": "99", "audience": "研究者"},
        },
    )
    assert missing_feature.status_code == 422
    assert missing_price.status_code == 422
    assert client.get("/v1/insights/insight_missing").status_code == 404
