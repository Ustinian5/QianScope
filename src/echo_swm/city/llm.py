from __future__ import annotations

import json

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.city.anchors import SuzhouAnchors
from echo_swm.city.contracts import CityScopeQuery
from echo_swm.core.ids import new_id


class CityEventAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    intensity_multiplier: float = Field(ge=0.7, le=1.35)
    information_valence_shift: float = Field(ge=-0.15, le=0.15)
    credibility_shift: float = Field(ge=-0.1, le=0.1)


class CityInterventionAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    effectiveness_multiplier: float = Field(ge=0.8, le=1.2)


class CityScenarioVariation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_lens: str = Field(min_length=2, max_length=500)
    event_adjustments: list[CityEventAdjustment] = Field(default_factory=list)
    intervention_adjustments: list[CityInterventionAdjustment] = Field(default_factory=list)


def compile_city_query(
    prompt: str,
    anchors: SuzhouAnchors,
    llm: OpenAICompatibleLLM,
) -> CityScopeQuery:
    """Compile natural language into a validated query; never generate forecast values."""
    variation_id = new_id("variation")
    districts = [
        {"district_id": item.anchor.district_id, "name_zh": item.anchor.name_zh}
        for item in anchors.districts
    ]
    system_prompt = """
You are a scenario compiler for a synthetic Suzhou city simulation. Return one JSON object
matching the supplied CityScopeQuery schema. Do not predict outcomes and do not invent district
IDs. The first branch must be the no-intervention baseline. Use only these supported segments:
youth, elderly, migrant, manufacturing_worker, service_worker, student, low_income. Use only these
metrics: life_satisfaction, government_trust, economic_confidence, consumption_index,
employment_rate, congestion_index, health_system_load, rumor_belief, stress, commute_minutes,
organization_vitality, public_service_reliability, policy_cost_100m_cny. Translate the user's
narrative into explicit events and interventions.
Keep horizon_days at most 90 and samples at most 32 unless the user explicitly requests more.
Event effects are signed directions from -1 to 1, while intensity and credibility are 0 to 1.
All assumptions must remain inspectable in the returned object. Return JSON only.
""".strip()
    user_prompt = json.dumps(
        {
            "request": prompt,
            "city_id": anchors.config.city_id,
            "allowed_districts": districts,
            "default_random_seed": 2026,
            "variation_id": variation_id,
            "instruction": "Compile only; the deterministic simulator will calculate outcomes.",
        },
        ensure_ascii=False,
    )
    query = llm.complete_json(
        system_prompt,
        user_prompt,
        CityScopeQuery,
        max_output_tokens=3_000,
        temperature=0.85,
        cache=False,
        operation="city_scenario_compilation",
        variation_id=variation_id,
    )
    if query.city_id != anchors.config.city_id:
        raise ValueError("LLM compiled a query for the wrong city")
    return query


def vary_city_query(
    query: CityScopeQuery,
    llm: OpenAICompatibleLLM,
) -> CityScopeQuery:
    """Use live model reasoning to refresh bounded scenario assumptions."""

    variation_id = new_id("variation")
    interventions = [
        intervention.model_dump(mode="json")
        for branch in query.branches
        for intervention in branch.interventions
    ]
    variation = llm.complete_json(
        (
            "You refresh uncertain assumptions for a synthetic city scenario. Preserve all IDs, "
            "district targeting, timing, budgets, observed anchors, and branch structure. Return "
            "only conservative bounded adjustments to assumed event intensity/information "
            "valence/credibility and intervention effectiveness. The variation_id is a diversity "
            "cue for an independent plausible run. Do not calculate outcomes or invent evidence."
        ),
        json.dumps(
            {
                "variation_id": variation_id,
                "city_id": query.city_id,
                "horizon_days": query.horizon_days,
                "events": [item.model_dump(mode="json") for item in query.events],
                "interventions": interventions,
            },
            ensure_ascii=False,
        ),
        CityScenarioVariation,
        max_output_tokens=2_500,
        temperature=0.9,
        cache=False,
        operation="city_template_refresh",
        variation_id=variation_id,
    )
    event_adjustments = {item.event_id: item for item in variation.event_adjustments}
    intervention_adjustments = {
        item.intervention_id: item for item in variation.intervention_adjustments
    }
    known_events = {item.event_id for item in query.events}
    known_interventions = {item["intervention_id"] for item in interventions}
    if query.events and not known_events.intersection(event_adjustments):
        raise ValueError("LLM returned no known city event adjustments")
    if interventions and not known_interventions.intersection(intervention_adjustments):
        raise ValueError("LLM returned no known city intervention adjustments")
    refreshed_events = []
    for event in query.events:
        adjustment = event_adjustments.get(event.event_id)
        if adjustment is None:
            refreshed_events.append(event)
            continue
        refreshed_events.append(
            event.model_copy(
                update={
                    "intensity": float(
                        np.clip(event.intensity * adjustment.intensity_multiplier, 0, 1)
                    ),
                    "information_valence": float(
                        np.clip(
                            event.information_valence + adjustment.information_valence_shift,
                            -1,
                            1,
                        )
                    ),
                    "credibility": float(
                        np.clip(event.credibility + adjustment.credibility_shift, 0, 1)
                    ),
                },
                deep=True,
            )
        )
    refreshed_branches = []
    effectiveness_fields = (
        "transit_subsidy",
        "consumption_voucher_yuan",
        "sme_support",
        "health_capacity_boost",
        "public_information",
    )
    for branch in query.branches:
        refreshed_interventions = []
        for intervention in branch.interventions:
            intervention_adjustment = intervention_adjustments.get(intervention.intervention_id)
            if intervention_adjustment is None:
                refreshed_interventions.append(intervention)
                continue
            updates = {
                field: float(
                    np.clip(
                        getattr(intervention, field)
                        * intervention_adjustment.effectiveness_multiplier,
                        0,
                        10_000 if field == "consumption_voucher_yuan" else 1,
                    )
                )
                for field in effectiveness_fields
            }
            refreshed_interventions.append(intervention.model_copy(update=updates, deep=True))
        refreshed_branches.append(
            branch.model_copy(update={"interventions": refreshed_interventions}, deep=True)
        )
    return query.model_copy(
        update={"events": refreshed_events, "branches": refreshed_branches}, deep=True
    )


__all__ = ["compile_city_query", "vary_city_query"]
