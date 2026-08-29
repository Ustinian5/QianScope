from __future__ import annotations

import json
from dataclasses import replace

from pydantic import BaseModel, ConfigDict, Field

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.ids import new_id
from echo_swm.research.contracts import PredictionRequest, QuestionForecast
from echo_swm.research.semantics import EventInterpretation
from echo_swm.research.survey import SurveyForecastBundle


class RepresentativeAnswerRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    persona_id: str
    answer: str = Field(min_length=10, max_length=900)


class QuestionnaireNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conclusion: str = Field(min_length=20, max_length=1_500)
    group_insights: list[str] = Field(min_length=1, max_length=8)
    answer_rewrites: list[RepresentativeAnswerRewrite] = Field(default_factory=list)


def generate_questionnaire_narrative(
    request: PredictionRequest,
    interpretation: EventInterpretation,
    survey: SurveyForecastBundle,
    llm: OpenAICompatibleLLM,
) -> tuple[SurveyForecastBundle, str]:
    """Ground a variable narrative in already-computed questionnaire distributions."""

    variation_id = new_id("variation")
    forecast_payload = []
    for forecast in survey.forecasts:
        forecast_payload.append(
            {
                "question_id": forecast.question_id,
                "question_text": forecast.question_text,
                "kind": forecast.kind.value,
                "baseline": forecast.baseline.model_dump(mode="json"),
                "post_event": forecast.post_event.model_dump(mode="json"),
                "statistical_change_summary": forecast.change_summary,
                "key_drivers": forecast.key_drivers,
                "representative_responses": [
                    {
                        "persona_id": item.persona_id,
                        "role": item.role,
                        "organization_type": item.organization_type,
                        "segment": item.segment,
                        "predicted_answer": item.predicted_answer,
                        "confidence": item.confidence,
                        "basis": item.basis,
                    }
                    for item in forecast.representative_responses
                ],
            }
        )
    narrative = llm.complete_json(
        (
            "You write the final narrative layer for a synthetic questionnaire forecast. Every "
            "claim must stay anchored to the supplied numerical distributions, statistical change "
            "summaries, persona basis, and semantic interpretation. Do not change probabilities, "
            "predicted answers, persona identities, or present synthetic answers as real quotes. "
            "Write concise natural Chinese. Rewrite each supplied representative answer in first "
            "person with meaningful variation, while preserving its predicted_answer and basis. "
            "The conclusion must distinguish conditional simulation from fact. The variation_id "
            "is a diversity cue so repeated runs do not return identical prose."
        ),
        json.dumps(
            {
                "variation_id": variation_id,
                "project_title": request.title,
                "event": request.event.model_dump(mode="json"),
                "semantic_interpretation": interpretation.model_dump(mode="json"),
                "statistical_group_insights": survey.group_insights,
                "questionnaire_forecasts": forecast_payload,
            },
            ensure_ascii=False,
        ),
        QuestionnaireNarrative,
        max_output_tokens=12_000,
        temperature=0.95,
        cache=False,
        operation="questionnaire_narrative_generation",
        variation_id=variation_id,
    )
    rewrite_lookup = {
        (item.question_id, item.persona_id): item.answer for item in narrative.answer_rewrites
    }
    forecasts: list[QuestionForecast] = []
    for forecast in survey.forecasts:
        responses = [
            response.model_copy(
                update={
                    "answer": rewrite_lookup.get(
                        (forecast.question_id, response.persona_id), response.answer
                    )
                }
            )
            for response in forecast.representative_responses
        ]
        forecasts.append(
            forecast.model_copy(update={"representative_responses": responses}, deep=True)
        )
    return (
        replace(
            survey,
            forecasts=forecasts,
            group_insights=narrative.group_insights,
        ),
        narrative.conclusion,
    )


__all__ = ["generate_questionnaire_narrative"]
