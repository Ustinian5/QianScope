from __future__ import annotations

import json
from datetime import datetime

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.ids import new_id
from echo_swm.event_forecasting.contracts import EventForecastQuery


class EventCandidateAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    hazard_multiplier: float = Field(ge=0.65, le=1.45)
    severity_shift: float = Field(ge=-0.12, le=0.12)
    rationale: str = Field(min_length=2, max_length=500)


class EventScenarioVariation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_lens: str = Field(min_length=2, max_length=500)
    candidate_adjustments: list[EventCandidateAdjustment] = Field(min_length=1)


def compile_event_query(
    prompt: str,
    as_of: datetime,
    llm: OpenAICompatibleLLM,
) -> EventForecastQuery:
    variation_id = new_id("variation")
    system_prompt = """
You compile natural-language forecasting questions into a typed EventForecastQuery JSON object.
Do not claim that an event will occur and do not fabricate observed evidence. Separate observed
signals from assumptions using data_origin. Create a finite, decision-relevant candidate set,
explicit daily base hazards, signal coefficients, state thresholds, parent-event lag windows,
metric impacts, and a first no-intervention control branch. Base rates without supplied historical
evidence must use baseline_origin unknown, expert_prior, or synthetic and sample_size 0. Use at
least 256 Monte Carlo samples. All timestamps must include timezones and no signal may become
available after the supplied prediction cutoff. The numerical engine, not you, calculates event
probabilities. Return JSON only.
""".strip()
    user_prompt = json.dumps(
        {
            "forecast_request": prompt,
            "prediction_cutoff": as_of.isoformat(),
            "variation_id": variation_id,
            "instruction": "Compile assumptions and candidates only; do not output results.",
        },
        ensure_ascii=False,
    )
    query = llm.complete_json(
        system_prompt,
        user_prompt,
        EventForecastQuery,
        max_output_tokens=6_000,
        temperature=0.85,
        cache=False,
        operation="event_forecast_compilation",
        variation_id=variation_id,
    )
    if query.as_of != as_of:
        raise ValueError("compiled query changed the supplied prediction cutoff")
    return query


def vary_event_query(
    query: EventForecastQuery,
    llm: OpenAICompatibleLLM,
) -> EventForecastQuery:
    """Refresh uncertain priors in a structured/template query through a live model call."""

    variation_id = new_id("variation")
    candidates = [
        {
            "candidate_id": candidate.candidate_id,
            "label": candidate.label,
            "description": candidate.description,
            "baseline_daily_hazard": candidate.baseline_daily_hazard,
            "baseline_origin": candidate.baseline_origin.value,
            "baseline_sample_size": candidate.baseline_sample_size,
            "severity_mean": candidate.severity_mean,
            "tags": candidate.tags,
        }
        for candidate in query.candidates
    ]
    variation = llm.complete_json(
        (
            "You refresh uncertain assumptions for a typed event forecast before the numerical "
            "engine runs. Never alter observed signals, candidate identities, timestamps, or "
            "historical baselines with real sample sizes. For each synthetic, expert-prior, or "
            "unknown candidate, provide a conservative bounded hazard multiplier and severity "
            "shift. The variation_id is a diversity cue: choose a plausible independent framing "
            "for this run. Do not output forecast probabilities or claim real evidence."
        ),
        json.dumps(
            {
                "variation_id": variation_id,
                "domain": query.domain,
                "horizon_days": query.horizon_days,
                "initial_metrics": query.initial_metrics,
                "candidates": candidates,
            },
            ensure_ascii=False,
        ),
        EventScenarioVariation,
        max_output_tokens=2_500,
        temperature=0.9,
        cache=False,
        operation="event_template_refresh",
        variation_id=variation_id,
    )
    adjustments = {item.candidate_id: item for item in variation.candidate_adjustments}
    if not set(adjustments).intersection(candidate.candidate_id for candidate in query.candidates):
        raise ValueError("LLM returned no known event candidate adjustments")
    refreshed = []
    for candidate in query.candidates:
        adjustment = adjustments.get(candidate.candidate_id)
        is_fixed_historical = (
            candidate.baseline_origin.value == "historical" and candidate.baseline_sample_size > 0
        )
        if adjustment is None or is_fixed_historical:
            refreshed.append(candidate)
            continue
        refreshed.append(
            candidate.model_copy(
                update={
                    "baseline_daily_hazard": float(
                        np.clip(
                            candidate.baseline_daily_hazard * adjustment.hazard_multiplier,
                            1e-6,
                            0.999999,
                        )
                    ),
                    "severity_mean": float(
                        np.clip(candidate.severity_mean + adjustment.severity_shift, 0, 1)
                    ),
                },
                deep=True,
            )
        )
    return query.model_copy(update={"candidates": refreshed}, deep=True)


__all__ = ["compile_event_query", "vary_event_query"]
