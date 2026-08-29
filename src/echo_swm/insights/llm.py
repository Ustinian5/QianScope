from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.ids import new_id
from echo_swm.insights.contracts import InsightRunRequest


class InsightQuoteRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    quote: str = Field(min_length=8, max_length=600)


class InsightNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=120)
    context: str = Field(min_length=1, max_length=500)
    metric_detail: str = Field(min_length=8, max_length=800)
    notes: list[str] = Field(min_length=2, max_length=8)
    quote_rewrites: list[InsightQuoteRewrite] = Field(default_factory=list)


def generate_insight_narrative(
    request: InsightRunRequest,
    base_result: dict[str, Any],
    llm: OpenAICompatibleLLM,
) -> InsightNarrative:
    variation_id = new_id("variation")
    return llm.complete_json(
        (
            "You write the interpretation layer for a synthetic-persona business insight. Keep "
            "every numeric metric and bar unchanged. Ground every statement in the supplied "
            "inputs, segment notes, and synthetic result; never invent live market data, observed "
            "behavior, or real-person quotes. Rewrite each supplied persona quote in natural "
            "first-person Chinese while preserving its agent_id, role, and stance. Include at "
            "least one limitation note. The variation_id is a diversity cue so repeated runs use "
            "fresh wording and a different defensible analytical angle."
        ),
        json.dumps(
            {
                "variation_id": variation_id,
                "tool": request.tool,
                "input_fields": request.fields,
                "synthetic_result": base_result,
            },
            ensure_ascii=False,
        ),
        InsightNarrative,
        max_output_tokens=3_500,
        temperature=0.95,
        cache=False,
        operation="insight_narrative_generation",
        variation_id=variation_id,
    )


__all__ = ["generate_insight_narrative"]
