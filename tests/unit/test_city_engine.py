from __future__ import annotations

import json
from pathlib import Path

import pytest

from echo_swm.city.contracts import CityBranch, CityEvent, CityEventType, CityScopeQuery
from echo_swm.city.engine import run_city_scope_query, verify_city_replay
from echo_swm.city.population import build_suzhou_world


def _query() -> CityScopeQuery:
    return CityScopeQuery(
        query_id="common_random_numbers",
        districts=["kunshan"],
        horizon_days=2,
        focal_metrics=["life_satisfaction", "rumor_belief", "employment_rate"],
        events=[
            CityEvent(
                event_id="information_test",
                event_type=CityEventType.INFORMATION_SHOCK,
                start_day=0,
                duration_days=2,
                intensity=0.5,
                affected_districts=["kunshan"],
                information_valence=-0.6,
            )
        ],
        branches=[
            CityBranch(branch_id="control", name="control"),
            CityBranch(branch_id="identical", name="identical"),
        ],
        samples=2,
        random_seed=19,
        save_micro_snapshots=True,
    )


def test_city_engine_uses_common_random_numbers_and_verifiable_snapshots(
    tmp_path: Path,
) -> None:
    world = build_suzhou_world(5_000, seed=19)
    forecast = run_city_scope_query(world, _query(), tmp_path)
    assert forecast.represented_scope_population < forecast.represented_population
    assert forecast.query.samples == 2
    assert set(forecast.branch_trajectories) == {"control", "identical"}
    assert all(value == 0 for value in forecast.counterfactual_deltas["identical"].values())
    for point in forecast.branch_trajectories["control"]:
        for band in point.metrics.values():
            assert band.p10 <= band.p50 <= band.p90

    run_dir = Path(forecast.artifact_dir)
    replay = verify_city_replay(run_dir)
    assert replay["valid"] is True
    assert replay["snapshots_valid"] is True
    assert replay["snapshot_count"] == 4
    persisted = json.loads((run_dir / "forecast.json").read_text(encoding="utf-8"))
    assert persisted["query"]["districts"] == ["kunshan"]
    assert (run_dir / "district_final.parquet").exists()


def test_city_scope_rejects_unknown_district_and_metric(tmp_path: Path) -> None:
    world = build_suzhou_world(5_000, seed=20)
    unknown_district = _query().model_copy(update={"districts": ["not-a-district"]})
    with pytest.raises(ValueError, match="unknown districts"):
        run_city_scope_query(world, unknown_district, tmp_path)
    unknown_metric = _query().model_copy(update={"focal_metrics": ["magic"]})
    with pytest.raises(ValueError, match="unsupported focal metrics"):
        run_city_scope_query(world, unknown_metric, tmp_path)
