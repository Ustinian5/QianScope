from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from echo_swm.event_forecasting.backtest import (
    ResolvedEventForecast,
    score_resolved_forecasts,
)
from echo_swm.event_forecasting.contracts import EventForecastBranch, EventForecastQuery
from echo_swm.event_forecasting.demo import load_event_query
from echo_swm.event_forecasting.engine import run_event_forecast, verify_event_replay


def _validated_query(**updates: object) -> EventForecastQuery:
    payload = load_event_query().model_dump(mode="json")
    payload.update(updates)
    return EventForecastQuery.model_validate(payload)


def test_event_query_rejects_future_signal_at_cutoff() -> None:
    payload = load_event_query().model_dump(mode="json")
    payload["signals"][0]["available_at"] = "2026-08-25T00:00:00+08:00"
    with pytest.raises(ValidationError, match="unavailable"):
        EventForecastQuery.model_validate(payload)


def test_event_chain_forecast_is_replayable_and_uses_common_random_numbers(
    tmp_path: Path,
) -> None:
    base = load_event_query()
    identical = EventForecastBranch(branch_id="identical", name="identical")
    query = _validated_query(
        samples=256,
        horizon_days=30,
        branches=[*base.branches, identical.model_dump(mode="json")],
    )
    result = run_event_forecast(query, tmp_path)
    control = result.branches["control"]
    same = result.branches["identical"]
    assert [item.occurrence_probability for item in control.candidates] == [
        item.occurrence_probability for item in same.candidates
    ]
    early = result.branches["early_response"]
    control_probability = {
        item.candidate_id: item.occurrence_probability for item in control.candidates
    }
    early_probability = {
        item.candidate_id: item.occurrence_probability for item in early.candidates
    }
    assert early_probability["production_adjustment"] < control_probability["production_adjustment"]
    assert early_probability["policy_support"] > control_probability["policy_support"]
    assert control.top_event_chains
    assert result.calibration_status == "prior_predictive_uncalibrated"
    assert verify_event_replay(Path(result.artifact_dir))["valid"] is True


def test_event_forecast_supports_queries_without_metrics(tmp_path: Path) -> None:
    payload = load_event_query().model_dump(mode="json")
    payload["initial_metrics"] = {}
    payload["samples"] = 32
    for candidate in payload["candidates"]:
        candidate["state_rules"] = []
        candidate["impacts"] = []
    for branch in payload["branches"]:
        for intervention in branch["interventions"]:
            intervention["metric_shifts"] = {}

    query = EventForecastQuery.model_validate(payload)
    result = run_event_forecast(query, tmp_path)

    assert all(not branch.final_metric_deltas for branch in result.branches.values())
    with np.load(Path(result.artifact_dir) / "event_paths.npz") as paths:
        assert paths["metric_names"].size == 0
        assert paths["final_metrics"].shape == (len(query.branches), query.samples, 0)
    assert verify_event_replay(Path(result.artifact_dir))["valid"] is True


def test_resolved_event_backtest_reports_calibration_metrics() -> None:
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    records = [
        ResolvedEventForecast(
            forecast_id=f"f{index}",
            candidate_id="event",
            forecast_as_of=cutoff + timedelta(days=index),
            horizon_end=cutoff + timedelta(days=index + 7),
            probability=0.85 if index % 2 else 0.15,
            outcome=index % 2,
            outcome_available_at=cutoff + timedelta(days=index + 8),
        )
        for index in range(20)
    ]
    report = score_resolved_forecasts(records, bins=5)
    assert report.count == 20
    assert report.weighted_base_rate == 0.5
    assert report.brier_score < 0.1
    assert report.brier_skill_score > 0
    assert len(report.calibration_bins) == 2
