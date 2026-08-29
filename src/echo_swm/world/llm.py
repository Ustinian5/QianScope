from __future__ import annotations

import json

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.ids import new_id
from echo_swm.research.population import BELIEF_DIMENSIONS, GOAL_DIMENSIONS, SCHWARTZ_DIMENSIONS
from echo_swm.world.contracts import DecisionQuestion, WorldSimulationRequest


class WorldEventAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    intensity_multiplier: float = Field(ge=0.7, le=1.3)
    valence_shift: float = Field(ge=-0.2, le=0.2)
    credibility_shift: float = Field(ge=-0.1, le=0.1)
    belief_signals: dict[str, float] = Field(default_factory=dict)
    value_signals: dict[str, float] = Field(default_factory=dict)
    goal_signals: dict[str, float] = Field(default_factory=dict)

    @field_validator("belief_signals", "value_signals", "goal_signals")
    @classmethod
    def bounded_signals(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < -1 or item > 1 for item in value.values()):
            raise ValueError("world event signals must be within [-1, 1]")
        return value


class WorldScenarioCompilation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative_lens: str = Field(min_length=2, max_length=800)
    event_adjustments: list[WorldEventAdjustment] = Field(min_length=1)
    questions: list[DecisionQuestion] = Field(min_length=1, max_length=8)


def compile_world_scenario(
    request: WorldSimulationRequest,
    base_questions: list[DecisionQuestion],
    llm: OpenAICompatibleLLM,
) -> WorldSimulationRequest:
    """Compile scenario semantics and event-specific independent-decision rounds."""

    variation_id = new_id("variation")
    compilation = llm.complete_json(
        (
            "You are the scenario director for a synthetic social-world simulation. Use the "
            "provided event text and stable request constraints to produce bounded semantic "
            "adjustments and a complete multi-round decision script. Never invent observed "
            "evidence or claim real people said anything. Preserve event IDs, round count, round "
            "order, decision constructs, and independent-agent methodology. Rewrite each base "
            "question into event-specific natural Chinese with 2-7 mutually exclusive options. "
            "Option positions must be distinct, span both cautious/negative and active/positive "
            "responses, and remain within [-1, 1]. Explicit user-supplied signals remain binding; "
            "new signals only fill semantic gaps. The variation_id is a diversity cue, so choose "
            "one plausible framing for this run rather than repeating boilerplate."
        ),
        json.dumps(
            {
                "variation_id": variation_id,
                "project_id": request.project_id,
                "world": {
                    "name": request.world.name,
                    "locations": [
                        {
                            "location_id": item.location_id,
                            "name": item.name,
                            "semantic_tags": item.semantic_tags,
                        }
                        for item in request.world.locations
                    ],
                },
                "events": [item.model_dump(mode="json") for item in request.events],
                "decision_rounds": request.decision_rounds,
                "base_questions": [item.model_dump(mode="json") for item in base_questions],
                "allowed_signal_dimensions": {
                    "belief": list(BELIEF_DIMENSIONS),
                    "value": list(SCHWARTZ_DIMENSIONS),
                    "goal": list(GOAL_DIMENSIONS),
                },
            },
            ensure_ascii=False,
        ),
        WorldScenarioCompilation,
        max_output_tokens=7_000,
        temperature=0.95,
        cache=False,
        operation="social_world_scenario_compilation",
        variation_id=variation_id,
    )
    if len(compilation.questions) != request.decision_rounds:
        raise ValueError("LLM world script did not return the requested round count")
    if [item.round_index for item in compilation.questions] != list(
        range(1, request.decision_rounds + 1)
    ):
        raise ValueError("LLM world script returned invalid round ordering")
    if any(
        len({option.position for option in question.options}) != len(question.options)
        or max(option.position for option in question.options)
        - min(option.position for option in question.options)
        < 0.8
        for question in compilation.questions
    ):
        raise ValueError("LLM world script returned a degenerate response space")
    adjustments = {item.event_id: item for item in compilation.event_adjustments}
    if not {item.event_id for item in request.events}.intersection(adjustments):
        raise ValueError("LLM world script returned no known event adjustments")
    events = []
    for event in request.events:
        adjustment = adjustments.get(event.event_id)
        if adjustment is None:
            events.append(event)
            continue
        belief_signals = {
            key: value
            for key, value in adjustment.belief_signals.items()
            if key in BELIEF_DIMENSIONS
        }
        value_signals = {
            key: value
            for key, value in adjustment.value_signals.items()
            if key in SCHWARTZ_DIMENSIONS
        }
        goal_signals = {
            key: value for key, value in adjustment.goal_signals.items() if key in GOAL_DIMENSIONS
        }
        events.append(
            event.model_copy(
                update={
                    "intensity": float(
                        np.clip(event.intensity * adjustment.intensity_multiplier, 0, 1)
                    ),
                    "valence": float(np.clip(event.valence + adjustment.valence_shift, -1, 1)),
                    "credibility": float(
                        np.clip(event.credibility + adjustment.credibility_shift, 0, 1)
                    ),
                    "belief_signals": {**belief_signals, **event.belief_signals},
                    "value_signals": {**value_signals, **event.value_signals},
                    "goal_signals": {**goal_signals, **event.goal_signals},
                },
                deep=True,
            )
        )
    return request.model_copy(
        update={"events": events, "question_overrides": compilation.questions}, deep=True
    )


__all__ = ["compile_world_scenario"]
