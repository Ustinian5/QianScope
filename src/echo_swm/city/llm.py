from __future__ import annotations

import json

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.city.anchors import SuzhouAnchors
from echo_swm.city.contracts import CityScopeQuery


def compile_city_query(
    prompt: str,
    anchors: SuzhouAnchors,
    llm: OpenAICompatibleLLM,
) -> CityScopeQuery:
    """Compile natural language into a validated query; never generate forecast values."""
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
            "instruction": "Compile only; the deterministic simulator will calculate outcomes.",
        },
        ensure_ascii=False,
    )
    query = llm.complete_json(
        system_prompt,
        user_prompt,
        CityScopeQuery,
        max_output_tokens=3_000,
    )
    if query.city_id != anchors.config.city_id:
        raise ValueError("LLM compiled a query for the wrong city")
    return query
