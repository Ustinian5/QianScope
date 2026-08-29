from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import numpy as np
import pyarrow as pa
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from starlette.middleware.gzip import GZipMiddleware

from echo_swm import DISCLAIMER, __version__
from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.alignment.observations import RealityObservation, append_observation
from echo_swm.city.anchors import load_suzhou_anchors, validate_anchor_totals
from echo_swm.city.contracts import CityScopeQuery
from echo_swm.city.demo import (
    build_city_demo,
    city_artifact_root,
    load_default_city_query,
    simulate_city_demo,
)
from echo_swm.city.engine import DATA_VERSION as CITY_DATA_VERSION
from echo_swm.city.engine import MODEL_VERSION as CITY_MODEL_VERSION
from echo_swm.city.engine import verify_city_replay
from echo_swm.city.llm import compile_city_query, vary_city_query
from echo_swm.city.population import validate_city_world
from echo_swm.contracts import (
    DataSourceManifest,
    EventSpec,
    PersonProfile,
    QuestionSpec,
    ScenarioSpec,
)
from echo_swm.core.config import Settings
from echo_swm.core.exceptions import ConfigurationError, LLMResponseError
from echo_swm.core.ids import new_id, stable_hash
from echo_swm.demo import demo_dir, run_full_demo, simulate_demo
from echo_swm.event_forecasting.backtest import (
    EventBacktestReport,
    ResolvedEventForecast,
    score_resolved_forecasts,
)
from echo_swm.event_forecasting.contracts import EventForecastQuery
from echo_swm.event_forecasting.demo import event_artifact_root, load_event_query, run_event_demo
from echo_swm.event_forecasting.engine import MODEL_VERSION as EVENT_MODEL_VERSION
from echo_swm.event_forecasting.engine import verify_event_replay
from echo_swm.event_forecasting.llm import compile_event_query, vary_event_query
from echo_swm.insights.contracts import InsightRunRequest
from echo_swm.insights.engine import DATA_VERSION as INSIGHT_DATA_VERSION
from echo_swm.insights.engine import MODEL_VERSION as INSIGHT_MODEL_VERSION
from echo_swm.insights.engine import load_insight_result, run_insight
from echo_swm.jobs.manager import DATA_VERSION as JOB_DATA_VERSION
from echo_swm.jobs.manager import MODEL_VERSION as JOB_MODEL_VERSION
from echo_swm.jobs.manager import JobManager, ProgressReporter
from echo_swm.models.calibration import fit_temperature
from echo_swm.models.echo import EchoModelBundle
from echo_swm.personas.catalog import DATA_VERSION as PERSONA_DATA_VERSION
from echo_swm.personas.catalog import MODEL_VERSION as PERSONA_MODEL_VERSION
from echo_swm.personas.catalog import PersonaCatalog
from echo_swm.personas.contracts import PersonaInterviewRequest
from echo_swm.research.calibration import (
    CalibrationDataset,
    CalibrationFitRequest,
    fit_and_save_calibration,
    load_calibration_dataset,
    load_calibration_profile,
    save_calibration_dataset,
)
from echo_swm.research.contracts import (
    OutcomeSubmission,
    PopulationSpec,
    PredictionRequest,
    Questionnaire,
)
from echo_swm.research.engine import (
    DATA_VERSION as RESEARCH_DATA_VERSION,
)
from echo_swm.research.engine import (
    MODEL_VERSION as RESEARCH_MODEL_VERSION,
)
from echo_swm.research.engine import (
    list_predictions,
    load_prediction,
    prediction_export_path,
    run_prediction,
    save_questionnaire,
    submit_outcome,
    verify_prediction_replay,
)
from echo_swm.research.examples import (
    example_calibration_dataset,
    example_population_margins,
)
from echo_swm.research.grounding import (
    PopulationMarginDataset,
    load_margin_dataset,
    save_margin_dataset,
)
from echo_swm.research.population import ResearchPopulation
from echo_swm.research.population import (
    generate_population as generate_research_population,
)
from echo_swm.research.population import (
    load_population as load_research_population,
)
from echo_swm.research.population import validate_population as validate_research_population
from echo_swm.world.contracts import WorldSimulationRequest, WorldSpec
from echo_swm.world.engine import DATA_VERSION as WORLD_DATA_VERSION
from echo_swm.world.engine import MODEL_VERSION as WORLD_MODEL_VERSION
from echo_swm.world.engine import (
    get_world_agent,
    get_world_location,
    load_world_simulation,
    run_world_simulation,
    search_world_agents,
    verify_world_replay,
    world_artifact_root,
)
from echo_swm.world.examples import example_world_event


class DataValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["source", "person", "event", "question", "scenario"]
    payload: dict[str, Any]


class PopulationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    population_id: str = "synthetic_demo"
    size: int = Field(default=10_000, ge=5_000, le=20_000)
    seed: int = 2026


class FlatPersonFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: str
    age: float
    education_level: float
    income: float = Field(gt=0)
    student: int = Field(ge=0, le=1)
    risk_preference: float = Field(ge=0, le=1)
    price_sensitivity: float = Field(ge=0, le=1)
    tech_acceptance: float = Field(ge=0, le=1)
    brand_trust_pre: float = Field(ge=0, le=1)
    peer_sensitivity: float = Field(ge=0, le=1)
    prior_purchase: int = Field(ge=0, le=1)
    purchase_intent_pre: int = Field(ge=0, le=1)
    survey_weight: float = Field(default=1, gt=0)


class QuestionnairePredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    people: list[FlatPersonFeatures] = Field(min_length=1, max_length=10_000)
    intervention: Literal["control", "price_up_30", "price_up_30_discount"] = "control"


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    use_demo_population: bool = True


class BranchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intervention: Literal["control", "price_up_30", "price_up_30_discount"]


class CalibrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    probabilities: list[float] = Field(min_length=10)
    outcomes: list[int] = Field(min_length=10)
    weights: list[float] | None = None


class CityBuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prototype_count: int = Field(default=15_000, ge=5_000, le=250_000)
    seed: int = 2026


class CityCompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=3, max_length=10_000)


class CitySimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prototype_count: int = Field(default=15_000, ge=5_000, le=250_000)
    samples: int = Field(default=8, ge=1, le=256)
    seed: int = 2026
    query: CityScopeQuery | None = None
    natural_language_prompt: str | None = Field(default=None, min_length=3, max_length=10_000)

    @model_validator(mode="after")
    def validate_query_source(self) -> CitySimulationRequest:
        if self.query is not None and self.natural_language_prompt is not None:
            raise ValueError("provide either query or natural_language_prompt, not both")
        return self


class EventCompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=3, max_length=20_000)
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("as_of")
    @classmethod
    def require_aware_compile_cutoff(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value


class EventForecastRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: EventForecastQuery | None = None
    natural_language_prompt: str | None = Field(default=None, min_length=3, max_length=20_000)
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("as_of")
    @classmethod
    def require_aware_forecast_cutoff(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_event_query_source(self) -> EventForecastRunRequest:
        if self.query is not None and self.natural_language_prompt is not None:
            raise ValueError("provide either query or natural_language_prompt, not both")
        return self


class EventBacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[ResolvedEventForecast] = Field(min_length=1)
    bins: int = Field(default=10, ge=2, le=50)


def _feature_table(people: list[FlatPersonFeatures]) -> pa.Table:
    rows = []
    for person in people:
        row = person.model_dump()
        row["log_income"] = float(np.log(row.pop("income")))
        row["treatment"] = "control"
        rows.append(row)
    return pa.Table.from_pylist(rows)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.load()
    if runtime_settings.llm_required and not runtime_settings.llm_configured:
        raise ConfigurationError(
            "QIANSCOPE_LLM_REQUIRED is enabled but the model key or model name is missing"
        )
    app = FastAPI(
        title="QianScope API",
        version=__version__,
        description="Probabilistic social world model; synthetic demo is not real human data.",
    )
    app.add_middleware(GZipMiddleware, minimum_size=1_024, compresslevel=6)
    app.state.started_at = time.monotonic()
    app.state.request_count = 0
    app.state.idempotency = {}
    app.state.suzhou_world_cache = None
    app.state.insight_population_cache = {}
    app.state.persona_catalog = None
    app.state.persona_map_cache = None
    app.state.job_manager = JobManager(runtime_settings.artifact_dir)
    population_lock = threading.Lock()

    def stable_population(size: int, seed: int) -> ResearchPopulation:
        cache_key = (size, seed)
        with population_lock:
            population = app.state.insight_population_cache.get(cache_key)
            if population is None:
                population = generate_research_population(
                    PopulationSpec(
                        population_id=f"stable_population_{size}_{seed}",
                        name="通用社会人格底座",
                        size=size,
                        seed=seed,
                        filters={},
                    ),
                    runtime_settings,
                    persist=False,
                )
                app.state.insight_population_cache[cache_key] = population
            return population

    def persona_catalog() -> PersonaCatalog:
        if app.state.persona_catalog is None:
            app.state.persona_catalog = PersonaCatalog(
                stable_population(5_000, 2026), settings=runtime_settings
            )
        return app.state.persona_catalog

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID", new_id("req"))
        app.state.request_count += 1
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-AI-Enabled"] = str(runtime_settings.llm_configured).lower()
        if runtime_settings.llm_model:
            response.headers["X-AI-Model"] = runtime_settings.llm_model
        is_event = request.url.path.startswith("/v1/event-forecasts")
        is_city = request.url.path.startswith(("/v1/cities", "/v1/city-simulations"))
        is_world = request.url.path.startswith("/v1/social-world")
        is_insight = request.url.path.startswith("/v1/insights")
        is_persona = request.url.path.startswith("/v1/personas")
        is_job = request.url.path.startswith("/v1/jobs")
        is_research = request.url.path.startswith(
            (
                "/v1/predictions",
                "/v1/populations/generate",
                "/v1/questionnaires",
                "/v1/population-margins",
                "/v1/calibration-datasets",
                "/v1/calibrations",
            )
        )
        response.headers["X-Model-Version"] = (
            JOB_MODEL_VERSION
            if is_job
            else PERSONA_MODEL_VERSION
            if is_persona
            else INSIGHT_MODEL_VERSION
            if is_insight
            else WORLD_MODEL_VERSION
            if is_world
            else RESEARCH_MODEL_VERSION
            if is_research
            else EVENT_MODEL_VERSION
            if is_event
            else CITY_MODEL_VERSION
            if is_city
            else "echo-structured-logit-v1"
        )
        response.headers["X-Data-Version"] = (
            JOB_DATA_VERSION
            if is_job
            else PERSONA_DATA_VERSION
            if is_persona
            else INSIGHT_DATA_VERSION
            if is_insight
            else WORLD_DATA_VERSION
            if is_world
            else RESEARCH_DATA_VERSION
            if is_research
            else "query-supplied-signals-v1"
            if is_event
            else CITY_DATA_VERSION
            if is_city
            else "synthetic-demo-v1"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data: blob: https:; "
            "font-src 'self' data:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self' https:; worker-src 'self' blob:"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(self), microphone=(self), payment=(), usb=()"
        )
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/health")
    def health() -> dict[str, Any]:
        provider_host = urlparse(runtime_settings.llm_base_url).hostname or ""
        return {
            "status": "ok",
            "version": __version__,
            "llm_configured": runtime_settings.llm_configured,
            "llm_required": runtime_settings.llm_required,
            "llm_model": runtime_settings.llm_model,
            "llm_provider": (
                "deepseek"
                if provider_host == "api.deepseek.com" or provider_host.endswith(".deepseek.com")
                else provider_host or None
            ),
            "generative_operations_use_live_llm": runtime_settings.llm_configured,
            "statistical_runtime_ready": (
                demo_dir(runtime_settings) / "models" / "echo.joblib"
            ).exists(),
            "city_runtime_ready": (
                city_artifact_root(runtime_settings) / "world" / "world_manifest.json"
            ).exists(),
            "event_forecast_runtime_ready": (
                event_artifact_root(runtime_settings) / "latest_run_summary.json"
            ).exists(),
            "generic_prediction_runtime_ready": True,
            "social_world_runtime_ready": True,
            "insight_runtime_ready": True,
            "persona_runtime_ready": True,
            "job_runtime_ready": True,
            "personality_population_ready": (
                runtime_settings.artifact_dir
                / "research"
                / "populations"
                / "general_population_5000"
                / "manifest.json"
            ).exists(),
        }

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        uptime = time.monotonic() - app.state.started_at
        return (
            "# TYPE echo_requests_total counter\n"
            f"echo_requests_total {app.state.request_count}\n"
            "# TYPE echo_uptime_seconds gauge\n"
            f"echo_uptime_seconds {uptime:.3f}\n"
        )

    @app.post("/v1/data/validate")
    def validate_data(body: DataValidationRequest) -> dict[str, Any]:
        validators: dict[str, type[BaseModel]] = {
            "source": DataSourceManifest,
            "person": PersonProfile,
            "event": EventSpec,
            "question": QuestionSpec,
            "scenario": ScenarioSpec,
        }
        try:
            parsed = validators[body.kind].model_validate(body.payload)
        except ValidationError as exc:
            raise HTTPException(422, detail=exc.errors(include_url=False)) from exc
        return {"valid": True, "normalized": parsed.model_dump(mode="json")}

    @app.post("/v1/populations")
    def create_population(
        body: PopulationCreateRequest,
        idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        if idempotency_key and idempotency_key in app.state.idempotency:
            return app.state.idempotency[idempotency_key]
        summary = run_full_demo(size=body.size, seed=body.seed, settings=runtime_settings)
        result = {"population_id": body.population_id, "status": "ready", **summary}
        if idempotency_key:
            app.state.idempotency[idempotency_key] = result
        return result

    @app.get("/v1/populations/{population_id}")
    def get_population(population_id: str) -> dict[str, Any]:
        manifest_path = demo_dir(runtime_settings) / "data_manifest.json"
        if population_id == "synthetic_demo" and manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        try:
            population = load_research_population(population_id, runtime_settings)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(404, "population not found") from exc
        return population.manifest

    @app.post("/v1/populations/generate")
    def generate_population(
        body: PopulationSpec,
        idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        cache_key = f"population:{idempotency_key}" if idempotency_key else None
        if cache_key and cache_key in app.state.idempotency:
            return app.state.idempotency[cache_key]
        try:
            population = generate_research_population(body, runtime_settings, persist=True)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        result = {
            "status": "ready",
            "population_id": body.population_id,
            "validation": validate_research_population(population),
            "manifest": population.manifest,
        }
        if cache_key:
            app.state.idempotency[cache_key] = result
        return result

    @app.post("/v1/questionnaires")
    def create_questionnaire(body: Questionnaire) -> dict[str, Any]:
        path = save_questionnaire(body, runtime_settings)
        return {
            "status": "ready",
            "questionnaire_id": body.questionnaire_id,
            "question_count": len(body.questions),
            "artifact": str(path.resolve()),
        }

    @app.get("/v1/questionnaires/{questionnaire_id}")
    def get_research_questionnaire(questionnaire_id: str) -> dict[str, Any]:
        path = (
            runtime_settings.artifact_dir
            / "research"
            / "questionnaires"
            / f"{questionnaire_id}.json"
        )
        if not path.exists():
            raise HTTPException(404, "questionnaire not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/v1/population-margins")
    def create_population_margin_dataset(body: PopulationMarginDataset) -> dict[str, Any]:
        try:
            path = save_margin_dataset(body, runtime_settings)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {
            "status": "ready",
            "dataset_id": body.dataset_id,
            "covered_fields": sorted(body.margins),
            "source": body.source,
            "artifact": str(path.resolve()),
        }

    @app.get("/v1/examples/population-margin")
    def get_population_margin_example() -> dict[str, Any]:
        return example_population_margins().model_dump(mode="json")

    @app.get("/v1/examples/calibration-dataset")
    def get_calibration_dataset_example() -> dict[str, Any]:
        return example_calibration_dataset().model_dump(mode="json")

    @app.get("/v1/population-margins/{dataset_id}")
    def get_population_margin_dataset(dataset_id: str) -> dict[str, Any]:
        try:
            return load_margin_dataset(dataset_id, runtime_settings).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "population margin dataset not found") from exc

    @app.post("/v1/calibration-datasets")
    def create_calibration_dataset(body: CalibrationDataset) -> dict[str, Any]:
        try:
            path = save_calibration_dataset(body, runtime_settings)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        timestamps = [item.forecast_as_of for item in body.observations]
        return {
            "status": "ready",
            "dataset_id": body.dataset_id,
            "observation_count": len(body.observations),
            "forecast_period": [min(timestamps).isoformat(), max(timestamps).isoformat()],
            "artifact": str(path.resolve()),
        }

    @app.get("/v1/calibration-datasets/{dataset_id}")
    def get_calibration_dataset(dataset_id: str) -> dict[str, Any]:
        try:
            return load_calibration_dataset(dataset_id, runtime_settings).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "calibration dataset not found") from exc

    @app.post("/v1/calibrations")
    def create_research_calibration(body: CalibrationFitRequest) -> dict[str, Any]:
        try:
            profile = fit_and_save_calibration(body, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return profile.model_dump(mode="json")

    @app.get("/v1/calibrations/{calibration_id}")
    def get_research_calibration(calibration_id: str) -> dict[str, Any]:
        try:
            return load_calibration_profile(calibration_id, runtime_settings).model_dump(
                mode="json"
            )
        except FileNotFoundError as exc:
            raise HTTPException(404, "calibration profile not found") from exc

    @app.get("/v1/predictions")
    def get_predictions(limit: int = 20) -> dict[str, Any]:
        return {"items": list_predictions(runtime_settings, max(1, min(limit, 100)))}

    @app.post("/v1/predictions")
    def create_prediction(body: PredictionRequest) -> dict[str, Any]:
        try:
            result = run_prediction(body, runtime_settings)
        except (ConfigurationError, LLMResponseError) as exc:
            raise HTTPException(503, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/v1/predictions/{run_id}")
    def get_prediction(run_id: str) -> dict[str, Any]:
        try:
            return load_prediction(run_id, runtime_settings).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "prediction not found") from exc

    @app.get("/v1/predictions/{run_id}/replay")
    def replay_prediction(run_id: str) -> dict[str, Any]:
        try:
            return verify_prediction_replay(run_id, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, "prediction not found") from exc

    @app.post("/v1/predictions/{run_id}/outcomes")
    def record_prediction_outcome(run_id: str, body: OutcomeSubmission) -> dict[str, Any]:
        try:
            return submit_outcome(run_id, body, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, "prediction not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/v1/predictions/{run_id}/export", response_class=FileResponse)
    def export_prediction(run_id: str, format: str = "json") -> FileResponse:
        try:
            path = prediction_export_path(run_id, format, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, "prediction not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        media_type = "application/json" if format == "json" else "text/csv"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.post("/v1/insights")
    def create_insight(body: InsightRunRequest) -> dict[str, Any]:
        try:
            population = stable_population(body.population_size, body.seed)
            result = run_insight(body, population, runtime_settings)
        except (ConfigurationError, LLMResponseError) as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/v1/insights/{run_id}")
    def get_insight(run_id: str) -> dict[str, Any]:
        try:
            return load_insight_result(run_id, runtime_settings).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "insight run not found") from exc

    @app.get("/v1/personas")
    def search_personas(
        query: str = "",
        tier: str | None = None,
        location_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        return (
            persona_catalog()
            .search(
                query=query,
                tier=tier,
                location_id=location_id,
                offset=offset,
                limit=limit,
            )
            .model_dump(mode="json")
        )

    @app.get("/v1/personas/map")
    def persona_map_snapshot(request: Request) -> Response:
        cached = app.state.persona_map_cache
        if cached is None:
            payload = persona_catalog().map_snapshot().model_dump(mode="json")
            serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            etag = f'"{stable_hash(payload)}"'
            cached = (serialized, etag)
            app.state.persona_map_cache = cached
        serialized, etag = cached
        headers = {
            "ETag": etag,
            "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
            "Vary": "Accept-Encoding",
        }
        if request.headers.get("If-None-Match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(
            content=serialized,
            media_type="application/json",
            headers=headers,
        )

    @app.get("/v1/personas/{persona_id}")
    def get_persona(persona_id: str) -> dict[str, Any]:
        try:
            return persona_catalog().profile(persona_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "persona not found") from exc

    @app.post("/v1/personas/{persona_id}/interview")
    def interview_persona(
        persona_id: str,
        body: PersonaInterviewRequest,
    ) -> dict[str, Any]:
        try:
            return persona_catalog().interview(persona_id, body).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "persona not found") from exc
        except (ConfigurationError, LLMResponseError, ValueError) as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/v1/jobs/insight")
    def create_insight_job(body: InsightRunRequest) -> dict[str, Any]:
        def runner(
            report: ProgressReporter,
            _cancel_event: threading.Event,
        ) -> dict[str, Any]:
            report(14, "正在匹配目标人群", 0, "读取稳定人格、价值观与媒体习惯")
            population = stable_population(body.population_size, body.seed)
            report(
                46,
                "Agent 正在形成条件判断",
                body.population_size // 2,
                "关键、代表与背景人格均已进入本轮计算",
            )
            result = run_insight(body, population, runtime_settings)
            report(
                92,
                "正在汇总分群与解释",
                body.population_size,
                "生成代表性轨迹、分群差异与限制说明",
            )
            return result.model_dump(mode="json")

        return app.state.job_manager.submit("insight", body.population_size, runner).model_dump(
            mode="json"
        )

    @app.post("/v1/jobs/prediction")
    def create_prediction_job(body: PredictionRequest) -> dict[str, Any]:
        total_agents = body.population.size if body.population is not None else 5_000

        def runner(
            report: ProgressReporter,
            _cancel_event: threading.Event,
        ) -> dict[str, Any]:
            report(0, "正在匹配问卷与目标人群", 0, "加载题目语义与稳定人格")
            result = run_prediction(body, runtime_settings)
            report(
                99,
                "正在计算分群与不确定性",
                total_agents,
                "汇总 P10 / P50 / P90 与代表性回答",
            )
            return result.model_dump(mode="json")

        return app.state.job_manager.submit("prediction", total_agents, runner).model_dump(
            mode="json"
        )

    @app.post("/v1/jobs/world")
    def create_world_job(body: WorldSimulationRequest) -> dict[str, Any]:
        total_agents = body.world.prototype_count

        def runner(
            report: ProgressReporter,
            _cancel_event: threading.Event,
        ) -> dict[str, Any]:
            total_decisions = total_agents * body.decision_rounds

            def on_progress(update: dict[str, Any]) -> None:
                phase = str(update.get("phase", "decisions"))
                details: dict[str, Any] = {
                    key: update[key]
                    for key in (
                        "current_round",
                        "total_rounds",
                        "processed_decisions",
                        "total_decisions",
                        "preview",
                    )
                    if key in update
                }
                processed = int(update.get("processed_decisions", 0))
                current_agents = int(update.get("processed_agents", 0))
                if phase == "population":
                    report(
                        0,
                        "正在建立本次独立决策空间",
                        0,
                        f"已加载 {total_agents:,} 个稳定人格；尚未开始作答",
                        details,
                    )
                    return
                if phase == "world_state":
                    completed_paths = int(update.get("completed_paths", 0))
                    total_paths = max(1, int(update.get("total_paths", 1)))
                    progress = 90 + round(7 * completed_paths / total_paths)
                    report(
                        progress,
                        "正在生成世界状态与可回放轨迹",
                        total_agents,
                        f"独立决策已完成；正在计算场景路径 {completed_paths}/{total_paths}",
                        details,
                    )
                    return
                progress = min(90, round(90 * processed / max(1, total_decisions)))
                preview = update.get("preview")
                trace = (
                    f"{preview['name']} · {preview['role']} → {preview['choice']}"
                    if isinstance(preview, dict)
                    else "Agent 正在独立作答"
                )
                report(
                    progress,
                    f"第 {update['current_round']}/{update['total_rounds']} 轮 · Agent 独立决策",
                    current_agents,
                    trace,
                    details,
                )

            result = run_world_simulation(
                body,
                runtime_settings,
                progress_callback=on_progress,
            )
            report(
                99,
                "正在聚合本次真实决策",
                total_agents,
                "仅在全部个体决策完成后计算比例、代表 Agent 与报告",
                {
                    "current_round": body.decision_rounds,
                    "total_rounds": body.decision_rounds,
                    "processed_decisions": total_decisions,
                    "total_decisions": total_decisions,
                },
            )
            return result.model_dump(mode="json")

        return app.state.job_manager.submit(
            "world",
            total_agents,
            runner,
            total_rounds=body.decision_rounds,
            total_decisions=total_agents * body.decision_rounds,
        ).model_dump(mode="json")

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        try:
            return app.state.job_manager.get(job_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "job not found") from exc

    @app.get("/v1/jobs/{job_id}/result")
    def get_job_result(job_id: str) -> dict[str, Any]:
        try:
            return app.state.job_manager.result(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "job not found") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            return app.state.job_manager.cancel(job_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "job not found") from exc

    @app.get("/v1/social-world/preset")
    def get_social_world_preset() -> dict[str, Any]:
        return {
            "world": WorldSpec().model_dump(mode="json"),
            "example_event": example_world_event().model_dump(mode="json"),
            "capabilities": [
                "event_injection",
                "multi_channel_diffusion",
                "location_mobility",
                "human_state_transition",
                "memory_and_relationship_updates",
                "population_and_agent_drilldown",
                "deterministic_replay",
            ],
            "ui_provider_dependency": None,
            "disclaimer": DISCLAIMER,
        }

    @app.post("/v1/social-world/simulations")
    def create_social_world_simulation(body: WorldSimulationRequest) -> dict[str, Any]:
        try:
            result = run_world_simulation(body, runtime_settings)
        except (ConfigurationError, LLMResponseError) as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return result.model_dump(mode="json")

    @app.get("/v1/social-world/simulations/{run_id}")
    def get_social_world_simulation(run_id: str) -> dict[str, Any]:
        try:
            return load_world_simulation(run_id, runtime_settings).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, "social-world simulation not found") from exc

    @app.get("/v1/social-world/simulations/{run_id}/replay")
    def replay_social_world_simulation(run_id: str) -> dict[str, Any]:
        try:
            return verify_world_replay(run_id, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, "social-world simulation not found") from exc

    @app.get("/v1/social-world/simulations/{run_id}/agents")
    def find_social_world_agents(
        run_id: str,
        query: str = "",
        tier: str | None = None,
        location_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        try:
            return search_world_agents(
                run_id,
                runtime_settings,
                query=query,
                tier=tier,
                location_id=location_id,
                limit=limit,
            )
        except FileNotFoundError as exc:
            raise HTTPException(404, "social-world simulation not found") from exc

    @app.get("/v1/social-world/simulations/{run_id}/agents/{agent_id}")
    def get_social_world_agent(run_id: str, agent_id: str) -> dict[str, Any]:
        try:
            return get_world_agent(run_id, agent_id, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/v1/social-world/simulations/{run_id}/locations/{location_id}")
    def get_social_world_location(run_id: str, location_id: str) -> dict[str, Any]:
        try:
            return get_world_location(run_id, location_id, runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get(
        "/v1/social-world/simulations/{run_id}/snapshots/{path_index}/{tick}",
        response_class=FileResponse,
    )
    def get_social_world_snapshot(run_id: str, path_index: int, tick: int) -> FileResponse:
        runs_root = (world_artifact_root(runtime_settings) / "runs").resolve()
        run_dir = (runs_root / run_id).resolve()
        if not run_dir.is_relative_to(runs_root):
            raise HTTPException(404, "social-world snapshot not found")
        path = run_dir / "snapshots" / f"path_{path_index:03d}" / f"tick_{tick:04d}.npz"
        if not path.exists():
            raise HTTPException(404, "social-world snapshot not found")
        return FileResponse(path, media_type="application/octet-stream", filename=path.name)

    @app.post("/v1/scenarios/validate")
    def validate_scenario(scenario: ScenarioSpec) -> dict[str, Any]:
        return {"valid": True, "scenario_id": scenario.scenario_id}

    @app.get("/v1/cities/suzhou")
    def get_suzhou() -> dict[str, Any]:
        anchors = load_suzhou_anchors()
        return {
            "city": anchors.config.model_dump(mode="json"),
            "scaled_districts_2025": [
                {
                    "district_id": district.anchor.district_id,
                    "name_zh": district.anchor.name_zh,
                    "represented_population_2025": district.population_2025,
                    "gdp_2025_100m": district.gdp_2025_100m,
                    "derivation": "official_2024_district_share_scaled_to_official_2025_city_total",
                }
                for district in anchors.districts
            ],
            "anchor_validation": validate_anchor_totals(anchors),
            "microdata_status": "synthetic_only",
            "disclaimer": DISCLAIMER,
        }

    @app.post("/v1/cities/suzhou/build")
    def build_suzhou(body: CityBuildRequest) -> dict[str, Any]:
        world = build_city_demo(body.prototype_count, body.seed, runtime_settings)
        app.state.suzhou_world_cache = (body.prototype_count, body.seed, world)
        return {
            "status": "ready",
            "world_version": world.world_version,
            "validation": validate_city_world(world),
            "artifact_dir": str((city_artifact_root(runtime_settings) / "world").resolve()),
            "disclaimer": DISCLAIMER,
        }

    @app.post("/v1/cities/suzhou/compile")
    def compile_suzhou(body: CityCompileRequest) -> dict[str, Any]:
        try:
            llm = OpenAICompatibleLLM(runtime_settings)
            query = compile_city_query(
                body.prompt,
                load_suzhou_anchors(),
                llm,
            )
        except (ConfigurationError, LLMResponseError, ValueError) as exc:
            raise HTTPException(503, str(exc)) from exc
        return {
            "query": query.model_dump(mode="json"),
            "ai_execution": (
                llm.last_execution.model_dump(mode="json")
                if llm.last_execution is not None
                else None
            ),
            "execution_status": "not_started",
            "note": "The LLM compiled the scenario; it did not calculate forecast values.",
        }

    @app.post("/v1/cities/suzhou/simulate")
    def simulate_suzhou(body: CitySimulationRequest) -> dict[str, Any]:
        query = body.query
        ai_execution = []
        if body.natural_language_prompt is not None:
            try:
                llm = OpenAICompatibleLLM(runtime_settings)
                query = compile_city_query(
                    body.natural_language_prompt,
                    load_suzhou_anchors(),
                    llm,
                )
                if llm.last_execution is not None:
                    ai_execution.append(llm.last_execution)
            except (ConfigurationError, LLMResponseError, ValueError) as exc:
                raise HTTPException(503, str(exc)) from exc
        elif runtime_settings.llm_configured:
            try:
                llm = OpenAICompatibleLLM(runtime_settings)
                query = vary_city_query(query or load_default_city_query(), llm)
                if llm.last_execution is not None:
                    ai_execution.append(llm.last_execution)
            except (ConfigurationError, LLMResponseError, ValueError) as exc:
                raise HTTPException(503, str(exc)) from exc
        cached = app.state.suzhou_world_cache
        world = None
        if cached is not None and cached[0:2] == (body.prototype_count, body.seed):
            world = cached[2]
        try:
            forecast, summary = simulate_city_demo(
                prototype_count=body.prototype_count,
                samples=body.samples,
                seed=body.seed,
                settings=runtime_settings,
                query=query,
                world=world,
                ai_execution=ai_execution,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "status": "completed",
            "summary": summary,
            "forecast": forecast.model_dump(mode="json"),
        }

    def _city_run_file(run_id: str, filename: str) -> Path:
        path = city_artifact_root(runtime_settings) / "runs" / run_id / filename
        if not path.exists():
            raise HTTPException(404, "city simulation or artifact not found")
        return path

    @app.get("/v1/city-simulations/{run_id}/results")
    def get_city_results(run_id: str) -> dict[str, Any]:
        return json.loads(_city_run_file(run_id, "forecast.json").read_text(encoding="utf-8"))

    @app.get("/v1/city-simulations/{run_id}/replay")
    def replay_city(run_id: str) -> dict[str, Any]:
        run_dir = _city_run_file(run_id, "run_manifest.json").parent
        return verify_city_replay(run_dir)

    @app.get("/v1/city-simulations/{run_id}/report", response_class=FileResponse)
    def get_city_report(run_id: str) -> FileResponse:
        return FileResponse(_city_run_file(run_id, "city_report.html"), media_type="text/html")

    @app.post("/v1/event-forecasts/compile")
    def compile_event_forecast(body: EventCompileRequest) -> dict[str, Any]:
        try:
            llm = OpenAICompatibleLLM(runtime_settings)
            query = compile_event_query(
                body.prompt,
                body.as_of,
                llm,
            )
        except (ConfigurationError, LLMResponseError, ValueError) as exc:
            raise HTTPException(503, str(exc)) from exc
        return {
            "query": query.model_dump(mode="json"),
            "ai_execution": (
                llm.last_execution.model_dump(mode="json")
                if llm.last_execution is not None
                else None
            ),
            "execution_status": "not_started",
            "note": "The LLM compiled hypotheses and assumptions; it did not predict outcomes.",
        }

    @app.post("/v1/event-forecasts")
    def create_event_forecast(body: EventForecastRunRequest) -> dict[str, Any]:
        query = body.query
        ai_execution = []
        if body.natural_language_prompt is not None:
            try:
                llm = OpenAICompatibleLLM(runtime_settings)
                query = compile_event_query(
                    body.natural_language_prompt,
                    body.as_of,
                    llm,
                )
                if llm.last_execution is not None:
                    ai_execution.append(llm.last_execution)
            except (ConfigurationError, LLMResponseError, ValueError) as exc:
                raise HTTPException(503, str(exc)) from exc
        elif runtime_settings.llm_configured:
            try:
                llm = OpenAICompatibleLLM(runtime_settings)
                query = vary_event_query(query or load_event_query(), llm)
                if llm.last_execution is not None:
                    ai_execution.append(llm.last_execution)
            except (ConfigurationError, LLMResponseError, ValueError) as exc:
                raise HTTPException(503, str(exc)) from exc
        result, summary = run_event_demo(
            query,
            runtime_settings,
            ai_execution=ai_execution,
        )
        return {
            "status": "completed",
            "summary": summary,
            "forecast": result.model_dump(mode="json"),
        }

    def _event_run_file(run_id: str, filename: str) -> Path:
        path = event_artifact_root(runtime_settings) / "runs" / run_id / filename
        if not path.exists():
            raise HTTPException(404, "event forecast or artifact not found")
        return path

    @app.get("/v1/event-forecasts/{run_id}/results")
    def get_event_forecast(run_id: str) -> dict[str, Any]:
        path = _event_run_file(run_id, "forecast.json")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/v1/event-forecasts/{run_id}/replay")
    def replay_event_forecast(run_id: str) -> dict[str, Any]:
        run_dir = _event_run_file(run_id, "run_manifest.json").parent
        return verify_event_replay(run_dir)

    @app.post("/v1/event-forecasts/backtest", response_model=EventBacktestReport)
    def backtest_event_forecasts(body: EventBacktestRequest) -> EventBacktestReport:
        return score_resolved_forecasts(body.records, bins=body.bins)

    @app.post("/v1/questionnaires/predict")
    def predict_questionnaire(body: QuestionnairePredictRequest) -> dict[str, Any]:
        model_path = demo_dir(runtime_settings) / "models" / "echo.joblib"
        if not model_path.exists():
            raise HTTPException(503, "model not trained; run `qianscope demo run` first")
        bundle = EchoModelBundle.load(model_path)
        table = _feature_table(body.people)
        predictions = bundle.predict(table, body.intervention)
        individual = []
        for index, person in enumerate(body.people):
            individual.append(
                {
                    "person_id": person.person_id,
                    "probabilities": {
                        target: float(values[index]) for target, values in predictions.items()
                    },
                    "confidence": float(
                        np.mean(
                            [abs(float(values[index]) - 0.5) * 2 for values in predictions.values()]
                        )
                    ),
                }
            )
        weights = np.asarray([person.survey_weight for person in body.people], dtype=float)
        population = {
            target: float(np.average(values, weights=weights))
            for target, values in predictions.items()
        }
        return {
            "model_version": bundle.model_version,
            "data_version": bundle.data_version,
            "intervention": body.intervention,
            "individual_predictions": individual,
            "population_predictions": population,
            "disclaimer": DISCLAIMER,
        }

    @app.post("/v1/simulations")
    def create_simulation(body: SimulationRequest) -> dict[str, Any]:
        if not body.use_demo_population:
            raise HTTPException(400, "only the typed demo population is enabled in local v0.1")
        try:
            result = simulate_demo(runtime_settings)
        except FileNotFoundError as exc:
            raise HTTPException(503, "run `qianscope demo run` to prepare model and data") from exc
        return {"run_id": result.run_id, "status": "completed", "results": result.branch_results}

    def _run_file(run_id: str, filename: str) -> Path:
        path = demo_dir(runtime_settings) / "runs" / run_id / filename
        if not path.exists():
            raise HTTPException(404, "simulation or artifact not found")
        return path

    @app.get("/v1/simulations/{run_id}")
    def get_simulation(run_id: str) -> dict[str, Any]:
        manifest = json.loads(_run_file(run_id, "run_manifest.json").read_text(encoding="utf-8"))
        return {"run_id": run_id, "status": "completed", "manifest": manifest}

    @app.post("/v1/simulations/{run_id}/branch")
    def get_branch(run_id: str, body: BranchRequest) -> dict[str, Any]:
        results = json.loads(_run_file(run_id, "results.json").read_text(encoding="utf-8"))
        return {
            "run_id": run_id,
            "branch": body.intervention,
            "result": results["branch_results"][body.intervention],
        }

    @app.get("/v1/simulations/{run_id}/results")
    def get_results(run_id: str) -> dict[str, Any]:
        return json.loads(_run_file(run_id, "results.json").read_text(encoding="utf-8"))

    @app.get("/v1/simulations/{run_id}/trajectory")
    def get_trajectory(run_id: str) -> dict[str, Any]:
        import csv

        with _run_file(run_id, "trajectory.csv").open(encoding="utf-8") as handle:
            return {"run_id": run_id, "trajectory": list(csv.DictReader(handle))}

    @app.get("/v1/simulations/{run_id}/replay")
    def replay(run_id: str) -> dict[str, Any]:
        records = [
            json.loads(line)
            for line in _run_file(run_id, "replay.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        return {
            "run_id": run_id,
            "verified_records": len(records),
            "valid": all("snapshot_hash" in item for item in records),
        }

    @app.post("/v1/observations")
    def observations(observation: RealityObservation) -> dict[str, Any]:
        append_observation(runtime_settings.artifact_dir / "observations.jsonl", observation)
        return {"stored": True, "observation_id": observation.observation_id, "append_only": True}

    @app.post("/v1/calibration/run")
    def calibration(body: CalibrationRequest) -> dict[str, Any]:
        if len(body.probabilities) != len(body.outcomes):
            raise HTTPException(422, "probabilities and outcomes lengths differ")
        weights = body.weights or [1.0] * len(body.outcomes)
        if len(weights) != len(body.outcomes):
            raise HTTPException(422, "weights and outcomes lengths differ")
        temperature = fit_temperature(body.probabilities, body.outcomes, weights)
        return {
            "candidate_temperature": temperature,
            "promoted": False,
            "reason": "offline review required",
        }

    @app.get("/v1/models")
    def models() -> dict[str, Any]:
        path = demo_dir(runtime_settings) / "model_card.json"
        return {"models": [json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []}

    @app.get("/v1/models/{model_id}/card")
    def model_card(model_id: str) -> dict[str, Any]:
        if model_id != "echo-structured-logit-v1":
            raise HTTPException(404, "model not found")
        path = demo_dir(runtime_settings) / "model_card.json"
        if not path.exists():
            raise HTTPException(404, "model has not been trained")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/v1/llm/test")
    def llm_test() -> dict[str, Any]:
        try:
            return OpenAICompatibleLLM(runtime_settings).probe()
        except (ConfigurationError, LLMResponseError) as exc:
            raise HTTPException(503, str(exc)) from exc

    return app


app = create_app()
