from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from echo_swm.agents.policy import ActionDistribution
from echo_swm.contracts import (
    DataSourceManifest,
    DynamicAgentState,
    EventSpec,
    EventType,
    GraphEdge,
    Hyperedge,
    PersonProfile,
    ProbabilityPrediction,
    QuestionSpec,
    ResponseType,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_source_manifest_requires_deidentification_for_personal_data() -> None:
    with pytest.raises(ValidationError):
        DataSourceManifest(
            source_id="s",
            source_name="source",
            source_type="survey",
            license="authorized",
            owner="owner",
            collection_method="survey",
            time_range=(NOW, NOW),
            content_hash="abc",
            contains_personal_data=True,
            allowed_uses=["research"],
        )


def test_person_profile_rejects_backwards_availability() -> None:
    with pytest.raises(ValidationError):
        PersonProfile(
            person_id="p",
            source_id="s",
            observed_at=NOW,
            available_at=NOW - timedelta(days=1),
        )


def test_dynamic_state_enforces_bounds() -> None:
    with pytest.raises(ValidationError):
        DynamicAgentState(
            agent_id="a",
            snapshot_id="x",
            beliefs={"price": 1.1},
            last_updated_by="test",
        )


def test_event_separates_occurrence_and_availability() -> None:
    event = EventSpec(
        event_id="e",
        event_type=EventType.PRICE_CHANGE,
        occurred_at=NOW,
        became_available_at=NOW + timedelta(hours=1),
        intensity=0.3,
    )
    assert event.became_available_at > event.occurred_at
    with pytest.raises(ValidationError):
        EventSpec(
            event_id="bad",
            event_type=EventType.PRICE_CHANGE,
            occurred_at=NOW,
            became_available_at=NOW,
            intensity=2,
        )


@pytest.mark.parametrize(
    ("response_type", "options", "minimum", "maximum"),
    [
        (ResponseType.BINARY, ["no", "yes"], None, None),
        (ResponseType.CONTINUOUS, [], 0.0, 10.0),
    ],
)
def test_valid_questions(
    response_type: ResponseType,
    options: list[str],
    minimum: float | None,
    maximum: float | None,
) -> None:
    question = QuestionSpec(
        question_id="q",
        question_text="Question?",
        response_type=response_type,
        options=options,
        scale_min=minimum,
        scale_max=maximum,
        source="test",
    )
    assert question.response_type is response_type


def test_probability_contract_requires_simplex() -> None:
    valid = ProbabilityPrediction(option_probabilities={"yes": 0.4, "no": 0.6}, confidence=0.7)
    assert sum(valid.option_probabilities.values()) == 1
    with pytest.raises(ValidationError):
        ProbabilityPrediction(option_probabilities={"yes": 0.8, "no": 0.8}, confidence=0.7)


def test_graph_and_hypergraph_invariants() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(
            source_id="a",
            target_id="a",
            relation_type="peer",
            strength=0.5,
            trust=0.5,
            authority=0.2,
            similarity=0.5,
            interaction_frequency=1,
            valid_from=NOW,
        )
    with pytest.raises(ValidationError):
        Hyperedge(
            hyperedge_id="h",
            hyperedge_type="group",
            member_ids=["a", "b"],
            membership_weights=[1.0],
            channel="chat",
            valid_from=NOW,
        )


def test_action_distribution_requires_normalization() -> None:
    with pytest.raises(ValidationError):
        ActionDistribution(
            action_probabilities={"read": 0.3, "ignore": 0.3},
            selected_action="read",
            confidence=0.5,
        )
