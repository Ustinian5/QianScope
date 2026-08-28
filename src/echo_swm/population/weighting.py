from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def validate_weights(
    weights: ArrayLike, expected_total: float | None = None
) -> NDArray[np.float64]:
    array = np.asarray(weights, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError("weights must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(array)) or np.any(array < 0):
        raise ValueError("weights must be finite and non-negative")
    if array.sum() <= 0:
        raise ValueError("at least one weight must be positive")
    if expected_total is not None and not np.isclose(array.sum(), expected_total, rtol=1e-8):
        raise ValueError("weight total does not match the expected population")
    return array


def weighted_mean(values: ArrayLike, weights: ArrayLike) -> float:
    value_array = np.asarray(values, dtype=float)
    weight_array = validate_weights(weights)
    if value_array.shape != weight_array.shape:
        raise ValueError("values and weights must have the same shape")
    return float(np.average(value_array, weights=weight_array))


def effective_sample_size(weights: ArrayLike) -> float:
    array = validate_weights(weights)
    return float(array.sum() ** 2 / np.square(array).sum())


def weighted_distribution(
    values: ArrayLike, weights: ArrayLike, categories: list[str]
) -> dict[str, float]:
    value_array = np.asarray(values, dtype=str)
    weight_array = validate_weights(weights)
    total = weight_array.sum()
    return {
        category: float(weight_array[value_array == category].sum() / total)
        for category in categories
    }
