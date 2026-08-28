from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from echo_swm.agents.policy import AgentObservation
from echo_swm.agents.selector import ActiveAgentSelector
from echo_swm.agents.statistical_policy import StatisticalPolicy
from echo_swm.contracts.person import DynamicAgentState
from echo_swm.data.synthetic import TARGETS, generate_synthetic_population
from echo_swm.evaluation.metrics import binary_metrics, expected_calibration_error
from echo_swm.models.calibration import apply_temperature, fit_temperature
from echo_swm.models.echo import respondent_split, train_echo_model


def test_temperature_and_metrics_are_bounded() -> None:
    labels = np.asarray([0, 0, 0, 1, 1, 1])
    probabilities = np.asarray([0.05, 0.2, 0.4, 0.6, 0.8, 0.95])
    weights = np.ones(6)
    temperature = fit_temperature(probabilities, labels, weights)
    calibrated = apply_temperature(probabilities, temperature)
    metrics = binary_metrics(labels, calibrated, weights)
    assert temperature > 0
    assert np.all((calibrated >= 0) & (calibrated <= 1))
    assert 0 <= metrics["brier"] <= 1
    assert 0 <= expected_calibration_error(labels, probabilities, weights) <= 1


def test_model_predicts_every_target_and_branch() -> None:
    table = generate_synthetic_population(5_000, seed=21)
    train, calibration, _ = respondent_split(table.num_rows, seed=21)
    bundle = train_echo_model(table, train, calibration)
    subset = table.slice(0, 20)
    predictions = bundle.predict(subset, intervention="price_up_30_discount")
    assert set(predictions) == set(TARGETS)
    assert all(values.shape == (20,) for values in predictions.values())
    assert all(np.all((values >= 0) & (values <= 1)) for values in predictions.values())


def test_selector_partitions_without_overlap() -> None:
    values = np.linspace(0, 1, 100)
    tiers = ActiveAgentSelector().select(
        values,
        values[::-1],
        np.abs(values - 0.5),
        values,
        values[::-1],
        key_count=5,
        representative_count=20,
    )
    merged = np.concatenate(
        [tiers.key_agents, tiers.representative_agents, tiers.background_agents]
    )
    assert np.unique(merged).size == 100
    assert tiers.key_agents.size == 5


def test_statistical_policy_is_deterministic_and_normalized() -> None:
    state = DynamicAgentState(
        agent_id="a",
        snapshot_id="s",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        purchase_intent=0.7,
        expression_intent=0.4,
        action_readiness=0.5,
        last_updated_by="test",
    )
    observation = AgentObservation(event_ids=["e"], exposure_strength=0.8, neighbor_stance=-0.3)
    actions = ["ignore", "share", "purchase"]
    first = StatisticalPolicy().act(state, observation, actions)
    second = StatisticalPolicy().act(state, observation, actions)
    assert first == second
    assert sum(first.action_probabilities.values()) == pytest.approx(1)
