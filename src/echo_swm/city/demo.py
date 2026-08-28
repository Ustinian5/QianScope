from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from echo_swm.city.anchors import load_suzhou_anchors, validate_anchor_totals
from echo_swm.city.contracts import CityForecast, CityScopeQuery
from echo_swm.city.engine import run_city_scope_query, verify_city_replay
from echo_swm.city.population import CityWorld, build_suzhou_world, validate_city_world
from echo_swm.city.report import write_city_report
from echo_swm.core.config import Settings


def default_query_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scenarios" / "suzhou_city_resilience.json"


def load_default_city_query(path: Path | None = None) -> CityScopeQuery:
    raw = (path or default_query_path()).read_text(encoding="utf-8")
    return CityScopeQuery.model_validate_json(raw)


def city_artifact_root(settings: Settings | None = None) -> Path:
    return (settings or Settings.load()).artifact_dir / "suzhou"


def persist_city_world(world: CityWorld, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(world.persons, output_dir / "persons.parquet", compression="zstd")
    pq.write_table(world.households, output_dir / "households.parquet", compression="zstd")
    pq.write_table(world.institutions, output_dir / "institutions.parquet", compression="zstd")
    np.savez_compressed(
        output_dir / "multiplex_graph.npz",
        source=world.graph.source,
        target=world.graph.target,
        layer=world.graph.layer,
        strength=world.graph.strength,
        trust=world.graph.trust,
    )
    np.savez_compressed(
        output_dir / "city_capacities.npz",
        od_matrix=world.od_matrix,
        transport_capacity=world.transport_capacity,
        health_capacity=world.health_capacity,
    )
    validation = validate_city_world(world)
    manifest = {
        "world_version": world.world_version,
        "anchor_validation": validate_anchor_totals(world.anchors),
        "population_validation": validation,
        "sources": [source.model_dump() for source in world.anchors.config.sources],
        "assumptions": world.anchors.config.assumptions,
    }
    (output_dir / "world_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def build_city_demo(
    prototype_count: int = 15_000,
    seed: int = 2026,
    settings: Settings | None = None,
) -> CityWorld:
    world = build_suzhou_world(prototype_count, seed, load_suzhou_anchors())
    persist_city_world(world, city_artifact_root(settings) / "world")
    return world


def simulate_city_demo(
    prototype_count: int = 15_000,
    samples: int = 8,
    seed: int = 2026,
    settings: Settings | None = None,
    query: CityScopeQuery | None = None,
    world: CityWorld | None = None,
) -> tuple[CityForecast, dict[str, Any]]:
    root = city_artifact_root(settings)
    if world is None:
        world = build_city_demo(prototype_count, seed, settings)
    elif world.prototype_count != prototype_count:
        raise ValueError("cached city world prototype count does not match request")
    else:
        persist_city_world(world, root / "world")
    active_query = query or load_default_city_query()
    active_query = active_query.model_copy(
        update={"samples": samples, "random_seed": seed}, deep=True
    )
    forecast = run_city_scope_query(world, active_query, root / "runs")
    run_dir = Path(forecast.artifact_dir)
    write_city_report(world, forecast, run_dir / "city_report.html")
    replay = verify_city_replay(run_dir)
    latest = root / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for name in (
        "forecast.json",
        "trajectory.csv",
        "district_final.parquet",
        "run_manifest.json",
        "replay.jsonl",
        "city_report.html",
    ):
        shutil.copy2(run_dir / name, latest / name)
    summary = {
        "run_id": forecast.run_id,
        "model_version": forecast.model_version,
        "prototype_count": forecast.prototype_count,
        "represented_population": forecast.represented_population,
        "branches": list(forecast.branch_trajectories),
        "counterfactual_deltas": forecast.counterfactual_deltas,
        "replay": replay,
        "artifact_dir": forecast.artifact_dir,
    }
    (root / "latest_run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return forecast, summary
