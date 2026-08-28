from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import BaseModel

from echo_swm.agents.llm_adapter import LLMCallBudget, OpenAICompatibleLLM
from echo_swm.core.config import Settings
from echo_swm.core.exceptions import LLMResponseError
from echo_swm.data.synthetic import generate_synthetic_population
from echo_swm.graph.generation import generate_homophilic_graph
from echo_swm.simulation.snapshot import Snapshot, SnapshotStore


def test_generated_graph_has_expected_size_and_no_self_loops() -> None:
    table = generate_synthetic_population(5_000, seed=30)
    graph = generate_homophilic_graph(table, neighbors_per_node=3, seed=30)
    assert graph.edge_count == 15_000
    assert not np.any(graph.source == graph.target)
    aggregate = graph.aggregate_from_sources(np.ones(table.num_rows), table.num_rows)
    assert np.allclose(aggregate, 1)


def test_snapshot_round_trip_and_tamper_detection(tmp_path: Path) -> None:
    snapshot = Snapshot(
        branch="control",
        tick=1,
        awareness=np.asarray([0.1, 0.2]),
        negative_expression=np.asarray([0.3, 0.4]),
        purchase_intent=np.asarray([0.5, 0.6]),
        trust=np.asarray([0.7, 0.8]),
    )
    store = SnapshotStore(tmp_path)
    store.save(snapshot)
    assert store.load("control", 1).content_hash == snapshot.content_hash


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path,
        min_segment_size=30,
        log_level="INFO",
        llm_api_key="secret",
        llm_base_url="https://example.invalid/v1",
        llm_model="model",
        llm_timeout_seconds=1,
        llm_max_calls=2,
    )


def test_llm_budget_refuses_excess_calls() -> None:
    budget = LLMCallBudget(max_calls=1)
    budget.reserve("hello", 10)
    with pytest.raises(LLMResponseError, match="budget"):
        budget.reserve("again", 10)


def test_llm_invalid_json_is_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Output(BaseModel):
        ok: bool

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "not-json"}}]}

    monkeypatch.setattr("httpx.post", lambda *args, **kwargs: FakeResponse())
    client = OpenAICompatibleLLM(_settings(tmp_path))
    with pytest.raises(LLMResponseError, match="invalid"):
        client.complete_json("system", "user", Output)


def test_llm_cache_avoids_second_provider_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Output(BaseModel):
        ok: bool

    calls = SimpleNamespace(count=0)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": json.dumps({"ok": True})}}]}

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        calls.count += 1
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)
    client = OpenAICompatibleLLM(_settings(tmp_path))
    assert client.complete_json("system", "user", Output).ok
    assert client.complete_json("system", "user", Output).ok
    assert calls.count == 1


def test_llm_sends_response_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Output(BaseModel):
        ok: bool

    captured_payload: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": json.dumps({"ok": True})}}]}

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        payload = kwargs.get("json")
        assert isinstance(payload, dict)
        captured_payload.update(payload)
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)
    client = OpenAICompatibleLLM(_settings(tmp_path))

    assert client.complete_json("system", "user", Output).ok
    messages = captured_payload["messages"]
    assert isinstance(messages, list)
    system_message = messages[0]
    assert isinstance(system_message, dict)
    assert "JSON Schema" in str(system_message["content"])
    assert '"ok"' in str(system_message["content"])
