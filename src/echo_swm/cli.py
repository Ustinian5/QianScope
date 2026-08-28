from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import typer
import uvicorn

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.city.anchors import load_suzhou_anchors, validate_anchor_totals
from echo_swm.city.demo import (
    build_city_demo,
    city_artifact_root,
    load_default_city_query,
    simulate_city_demo,
)
from echo_swm.city.engine import verify_city_replay
from echo_swm.city.llm import compile_city_query
from echo_swm.city.population import validate_city_world
from echo_swm.core.config import Settings
from echo_swm.demo import (
    evaluate_demo,
    generate_demo,
    run_full_demo,
    simulate_demo,
    train_demo,
)
from echo_swm.event_forecasting.backtest import (
    ResolvedEventForecast,
    score_resolved_forecasts,
)
from echo_swm.event_forecasting.demo import (
    event_artifact_root,
    load_event_query,
    run_event_demo,
)
from echo_swm.event_forecasting.engine import verify_event_replay
from echo_swm.event_forecasting.llm import compile_event_query
from echo_swm.graph.generation import generate_homophilic_graph
from echo_swm.population.weighting import effective_sample_size
from echo_swm.research.contracts import PopulationSpec
from echo_swm.research.engine import run_prediction, verify_prediction_replay
from echo_swm.research.examples import example_prediction_request
from echo_swm.research.population import generate_population, validate_population
from echo_swm.serving.api import create_app
from echo_swm.simulation.snapshot import SnapshotStore
from echo_swm.world.contracts import WorldSimulationRequest
from echo_swm.world.engine import run_world_simulation, verify_world_replay
from echo_swm.world.examples import example_world_request

app = typer.Typer(help="Inspiral ECHO-SWM command line")
demo_app = typer.Typer(help="Synthetic end-to-end demo")
data_app = typer.Typer(help="Data validation commands")
population_app = typer.Typer(help="Population commands")
graph_app = typer.Typer(help="Graph commands")
train_app = typer.Typer(help="Training commands")
scenario_app = typer.Typer(help="Scenario commands")
city_app = typer.Typer(help="Suzhou coupled city simulation")
event_app = typer.Typer(help="Generic probabilistic event forecasting")
prediction_app = typer.Typer(help="Questionnaire-driven general event prediction")
world_app = typer.Typer(help="Location-aware Human Digital Twin social-world simulation")
app.add_typer(demo_app, name="demo")
app.add_typer(data_app, name="data")
app.add_typer(population_app, name="population")
app.add_typer(graph_app, name="graph")
app.add_typer(train_app, name="train")
app.add_typer(scenario_app, name="scenario")
app.add_typer(city_app, name="city")
app.add_typer(event_app, name="event")
app.add_typer(prediction_app, name="predict")
app.add_typer(world_app, name="world")


@demo_app.command("generate")
def demo_generate(size: int = 10_000, seed: int = 2026) -> None:
    typer.echo(str(generate_demo(size, seed).resolve()))


@demo_app.command("train")
def demo_train() -> None:
    typer.echo(str(train_demo().resolve()))


@demo_app.command("evaluate")
def demo_evaluate() -> None:
    typer.echo(json.dumps(evaluate_demo(), ensure_ascii=False, indent=2))


@demo_app.command("simulate")
def demo_simulate() -> None:
    result = simulate_demo()
    typer.echo(
        json.dumps(
            {"run_id": result.run_id, "results": result.branch_results},
            ensure_ascii=False,
            indent=2,
        )
    )


@demo_app.command("run")
def demo_run(size: int = 10_000, seed: int = 2026) -> None:
    typer.echo(json.dumps(run_full_demo(size, seed), ensure_ascii=False, indent=2))


@data_app.command("validate")
def data_validate(path: Path = Path("artifacts/demo/population.parquet")) -> None:
    table = pq.read_table(path)
    required = {"person_id", "available_at", "survey_weight", "treatment"}
    missing = sorted(required - set(table.column_names))
    if missing:
        raise typer.BadParameter(f"missing columns: {missing}")
    typer.echo(json.dumps({"valid": True, "rows": table.num_rows}, indent=2))


@data_app.command("harmonize")
def data_harmonize() -> None:
    typer.echo("Demo data is generated directly in canonical schema; no transformation required.")


@population_app.command("build")
def population_build(size: int = 10_000, seed: int = 2026) -> None:
    typer.echo(str(generate_demo(size, seed).resolve()))


@population_app.command("validate")
def population_validate(path: Path = Path("artifacts/demo/population.parquet")) -> None:
    table = pq.read_table(path)
    weights = table["survey_weight"].to_numpy()
    typer.echo(
        json.dumps(
            {"rows": table.num_rows, "effective_sample_size": effective_sample_size(weights)},
            indent=2,
        )
    )


@graph_app.command("build")
def graph_build(path: Path = Path("artifacts/demo/population.parquet"), seed: int = 2026) -> None:
    graph = generate_homophilic_graph(pq.read_table(path), seed=seed)
    typer.echo(json.dumps({"edges": graph.edge_count, "version": graph.graph_version}, indent=2))


@train_app.command("baseline")
def train_baseline() -> None:
    typer.echo(str(train_demo().resolve()))


@train_app.command("echo")
def train_echo() -> None:
    typer.echo(str(train_demo().resolve()))


@app.command("evaluate")
def evaluate() -> None:
    typer.echo(json.dumps(evaluate_demo(), ensure_ascii=False, indent=2))


@scenario_app.command("validate")
def scenario_validate(path: Path) -> None:
    from echo_swm.contracts import ScenarioSpec

    scenario = ScenarioSpec.model_validate_json(path.read_text(encoding="utf-8"))
    typer.echo(json.dumps({"valid": True, "scenario_id": scenario.scenario_id}, indent=2))


@city_app.command("inspect")
def city_inspect() -> None:
    anchors = load_suzhou_anchors()
    typer.echo(
        json.dumps(
            {
                "city": anchors.config.name_zh,
                "reference_date": anchors.config.reference_date.isoformat(),
                "metrics": {
                    name: value.model_dump(mode="json")
                    for name, value in anchors.config.city_metrics.items()
                },
                "districts": [
                    {
                        "district_id": item.anchor.district_id,
                        "name_zh": item.anchor.name_zh,
                        "population_2025": item.population_2025,
                        "gdp_2025_100m": item.gdp_2025_100m,
                    }
                    for item in anchors.districts
                ],
                "validation": validate_anchor_totals(anchors),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@city_app.command("build")
def city_build(prototypes: int = 15_000, seed: int = 2026) -> None:
    world = build_city_demo(prototypes, seed)
    typer.echo(json.dumps(validate_city_world(world), ensure_ascii=False, indent=2))


@city_app.command("compile")
def city_compile(prompt: str) -> None:
    settings = Settings.load()
    query = compile_city_query(
        prompt,
        load_suzhou_anchors(),
        OpenAICompatibleLLM(settings),
    )
    typer.echo(query.model_dump_json(indent=2))


@city_app.command("simulate")
def city_simulate(
    scenario: Path | None = None,
    prompt: str | None = None,
    prototypes: int = 15_000,
    samples: int = 8,
    seed: int = 2026,
) -> None:
    if scenario is not None and prompt is not None:
        raise typer.BadParameter("provide either --scenario or --prompt, not both")
    query = load_default_city_query(scenario)
    if prompt is not None:
        settings = Settings.load()
        query = compile_city_query(
            prompt,
            load_suzhou_anchors(),
            OpenAICompatibleLLM(settings),
        )
    _, summary = simulate_city_demo(prototypes, samples, seed, query=query)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@city_app.command("replay")
def city_replay(run_id: str) -> None:
    run_dir = city_artifact_root() / "runs" / run_id
    if not run_dir.exists():
        raise typer.BadParameter("city run not found")
    typer.echo(json.dumps(verify_city_replay(run_dir), ensure_ascii=False, indent=2))


@event_app.command("forecast")
def event_forecast(scenario: Path | None = None) -> None:
    _, summary = run_event_demo(load_event_query(scenario))
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@event_app.command("compile")
def event_compile(prompt: str, as_of: str | None = None) -> None:
    cutoff = datetime.fromisoformat(as_of) if as_of else datetime.now(UTC)
    query = compile_event_query(
        prompt,
        cutoff,
        OpenAICompatibleLLM(Settings.load()),
    )
    typer.echo(query.model_dump_json(indent=2))


@event_app.command("replay")
def event_replay(run_id: str) -> None:
    run_dir = event_artifact_root() / "runs" / run_id
    if not run_dir.exists():
        raise typer.BadParameter("event forecast run not found")
    typer.echo(json.dumps(verify_event_replay(run_dir), ensure_ascii=False, indent=2))


@event_app.command("backtest")
def event_backtest(path: Path, bins: int = 10) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = [ResolvedEventForecast.model_validate(item) for item in raw]
    report = score_resolved_forecasts(records, bins=bins)
    typer.echo(report.model_dump_json(indent=2))


@prediction_app.command("population")
def prediction_population(size: int = 5_000, seed: int = 2026) -> None:
    settings = Settings.load()
    population = generate_population(
        PopulationSpec(
            population_id=f"general_population_{size}",
            size=size,
            seed=seed,
        ),
        settings,
    )
    typer.echo(json.dumps(validate_population(population), ensure_ascii=False, indent=2))


@prediction_app.command("demo")
def prediction_demo(paths: int = 8) -> None:
    result = run_prediction(example_prediction_request(paths=paths), Settings.load())
    typer.echo(
        json.dumps(
            {
                "run_id": result.run_id,
                "conclusion": result.conclusion,
                "agent_count": result.population.agent_count,
                "tier_counts": result.population.tier_counts,
                "question_count": len(result.questionnaire_forecast),
                "scenario_count": len(result.scenarios),
                "artifacts": result.artifacts.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@prediction_app.command("replay")
def prediction_replay(run_id: str) -> None:
    try:
        verification = verify_prediction_replay(run_id, Settings.load())
    except FileNotFoundError as exc:
        raise typer.BadParameter("prediction run not found") from exc
    typer.echo(json.dumps(verification, ensure_ascii=False, indent=2))


@world_app.command("demo")
def world_demo(horizon_ticks: int = 72, paths: int = 3, seed: int = 2026) -> None:
    request = example_world_request(
        horizon_ticks=horizon_ticks,
        paths=paths,
        seed=seed,
    )
    result = run_world_simulation(request, Settings.load())
    typer.echo(
        json.dumps(
            {
                "run_id": result.run_id,
                "prototype_count": result.population.prototype_count,
                "represented_population": result.population.represented_population,
                "final_reached_population": result.diffusion_curve[
                    -1
                ].reached_population.model_dump(),
                "final_actions": {
                    name: band.model_dump()
                    for name, band in result.final_action_distribution.items()
                },
                "artifacts": result.artifacts.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@world_app.command("run")
def world_run(scenario: Path) -> None:
    request = WorldSimulationRequest.model_validate_json(scenario.read_text(encoding="utf-8"))
    result = run_world_simulation(request, Settings.load())
    typer.echo(result.model_dump_json(indent=2))


@world_app.command("replay")
def world_replay(run_id: str) -> None:
    try:
        verification = verify_world_replay(run_id, Settings.load())
    except FileNotFoundError as exc:
        raise typer.BadParameter("social-world run not found") from exc
    typer.echo(json.dumps(verification, ensure_ascii=False, indent=2))


@app.command("simulate")
def simulate() -> None:
    demo_simulate()


@app.command("branch")
def branch(run_id: str, intervention: str) -> None:
    path = Settings.load().artifact_dir / "demo" / "runs" / run_id / "results.json"
    result = json.loads(path.read_text(encoding="utf-8"))["branch_results"]
    if intervention not in result:
        raise typer.BadParameter("unknown intervention")
    typer.echo(json.dumps(result[intervention], ensure_ascii=False, indent=2))


@app.command("calibrate")
def calibrate() -> None:
    report = evaluate_demo()
    temperatures = {target: item["temperature"] for target, item in report["targets"].items()}
    typer.echo(json.dumps({"candidate_temperatures": temperatures, "promoted": False}, indent=2))


@app.command("replay")
def replay(run_dir: Path) -> None:
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    records = (run_dir / "replay.jsonl").read_text(encoding="utf-8").splitlines()
    last_tick = max(json.loads(line)["tick"] for line in records)
    for branch_name in ("control", "price_up_30", "price_up_30_discount"):
        SnapshotStore(run_dir / "snapshots").load(branch_name, last_tick)
    typer.echo(
        json.dumps(
            {"run_id": manifest["run_id"], "snapshots": len(records), "verified": True}, indent=2
        )
    )


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    uvicorn.run(create_app(), host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
