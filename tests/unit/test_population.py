from __future__ import annotations

import numpy as np
import pytest

from echo_swm.population.ipf import iterative_proportional_fitting
from echo_swm.population.weighting import effective_sample_size, validate_weights, weighted_mean


def test_ipf_converges_and_preserves_target_total() -> None:
    records = [
        {"region": "east", "student": "yes"},
        {"region": "east", "student": "no"},
        {"region": "west", "student": "yes"},
        {"region": "west", "student": "no"},
    ]
    result = iterative_proportional_fitting(
        records,
        {
            "region": {"east": 70.0, "west": 30.0},
            "student": {"yes": 40.0, "no": 60.0},
        },
    )
    assert result.converged
    assert result.max_relative_error < 1e-6
    assert result.weights.sum() == pytest.approx(100)
    assert result.weights[[0, 1]].sum() == pytest.approx(70)


def test_ipf_rejects_unknown_target_category() -> None:
    with pytest.raises(ValueError, match="no records cover"):
        iterative_proportional_fitting([{"group": "a"}], {"group": {"b": 1.0}})


def test_weight_helpers() -> None:
    weights = validate_weights([1, 2, 3], expected_total=6)
    assert weighted_mean([0, 0, 1], weights) == pytest.approx(0.5)
    assert effective_sample_size(np.ones(10)) == pytest.approx(10)
    with pytest.raises(ValueError):
        validate_weights([1, -1])
