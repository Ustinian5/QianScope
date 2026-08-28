from __future__ import annotations

import json
from datetime import datetime

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.event_forecasting.contracts import EventForecastQuery


def compile_event_query(
    prompt: str,
    as_of: datetime,
    llm: OpenAICompatibleLLM,
) -> EventForecastQuery:
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
            "instruction": "Compile assumptions and candidates only; do not output results.",
        },
        ensure_ascii=False,
    )
    query = llm.complete_json(
        system_prompt,
        user_prompt,
        EventForecastQuery,
        max_output_tokens=6_000,
    )
    if query.as_of != as_of:
        raise ValueError("compiled query changed the supplied prediction cutoff")
    return query
