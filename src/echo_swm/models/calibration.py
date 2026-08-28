from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _logit(probabilities: NDArray[np.float64]) -> NDArray[np.float64]:
    clipped = np.clip(probabilities, 1e-7, 1 - 1e-7)
    return np.log(clipped / (1 - clipped))


def apply_temperature(probabilities: ArrayLike, temperature: float) -> NDArray[np.float64]:
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    probs = np.asarray(probabilities, dtype=float)
    logits = _logit(probs) / temperature
    return 1 / (1 + np.exp(-logits))


def fit_temperature(probabilities: ArrayLike, labels: ArrayLike, weights: ArrayLike) -> float:
    probs = np.asarray(probabilities, dtype=float)
    truth = np.asarray(labels, dtype=float)
    sample_weight = np.asarray(weights, dtype=float)
    if not (probs.shape == truth.shape == sample_weight.shape):
        raise ValueError("probabilities, labels and weights must have matching shapes")
    candidates = np.geomspace(0.35, 4.0, 160)
    losses: list[float] = []
    for temperature in candidates:
        calibrated = np.clip(apply_temperature(probs, float(temperature)), 1e-9, 1 - 1e-9)
        loss = -np.average(
            truth * np.log(calibrated) + (1 - truth) * np.log(1 - calibrated),
            weights=sample_weight,
        )
        losses.append(float(loss))
    return float(candidates[int(np.argmin(losses))])
