from __future__ import annotations

import json
from pathlib import Path

from echo_swm.city.contracts import CityForecast, CityScopeQuery
from echo_swm.contracts import EventSpec, ForecastOutput, PersonProfile, QuestionSpec, ScenarioSpec
from echo_swm.event_forecasting.contracts import EventForecastQuery, EventForecastResult
from echo_swm.personas.contracts import PersonaProfile
from echo_swm.research.calibration import CalibrationDataset, CalibrationProfile
from echo_swm.research.contracts import (
    OutcomeSubmission,
    PopulationSpec,
    PredictionRequest,
    PredictionResult,
    Questionnaire,
)
from echo_swm.research.grounding import PopulationMarginDataset
from echo_swm.world.contracts import WorldSimulationRequest, WorldSimulationResult


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "data_contracts"
    root.mkdir(parents=True, exist_ok=True)
    models = {
        "person.schema.json": PersonProfile,
        "persona-profile.schema.json": PersonaProfile,
        "event.schema.json": EventSpec,
        "question.schema.json": QuestionSpec,
        "scenario.schema.json": ScenarioSpec,
        "forecast.schema.json": ForecastOutput,
        "city-scope.schema.json": CityScopeQuery,
        "city-forecast.schema.json": CityForecast,
        "event-forecast-query.schema.json": EventForecastQuery,
        "event-forecast-result.schema.json": EventForecastResult,
        "research-population.schema.json": PopulationSpec,
        "research-questionnaire.schema.json": Questionnaire,
        "research-prediction-request.schema.json": PredictionRequest,
        "research-prediction-result.schema.json": PredictionResult,
        "research-outcome-submission.schema.json": OutcomeSubmission,
        "research-population-margin.schema.json": PopulationMarginDataset,
        "research-calibration-dataset.schema.json": CalibrationDataset,
        "research-calibration-profile.schema.json": CalibrationProfile,
        "social-world-simulation-request.schema.json": WorldSimulationRequest,
        "social-world-simulation-result.schema.json": WorldSimulationResult,
    }
    for filename, model in models.items():
        (root / filename).write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
