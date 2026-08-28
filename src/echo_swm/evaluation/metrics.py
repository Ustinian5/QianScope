from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, log_loss, roc_auc_score


def expected_calibration_error(
    labels: ArrayLike, probabilities: ArrayLike, weights: ArrayLike, bins: int = 10
) -> float:
    truth = np.asarray(labels, dtype=float)
    probs = np.asarray(probabilities, dtype=float)
    sample_weight = np.asarray(weights, dtype=float)
    boundaries = np.linspace(0, 1, bins + 1)
    total = sample_weight.sum()
    error = 0.0
    for index in range(bins):
        upper_inclusive = index == bins - 1
        mask = (probs >= boundaries[index]) & (
            probs <= boundaries[index + 1] if upper_inclusive else probs < boundaries[index + 1]
        )
        if not mask.any():
            continue
        bin_weight = sample_weight[mask].sum()
        confidence = np.average(probs[mask], weights=sample_weight[mask])
        accuracy = np.average(truth[mask], weights=sample_weight[mask])
        error += bin_weight / total * abs(confidence - accuracy)
    return float(error)


def binary_metrics(
    labels: ArrayLike, probabilities: ArrayLike, weights: ArrayLike
) -> dict[str, Any]:
    truth = np.asarray(labels, dtype=int)
    probs = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1 - 1e-9)
    sample_weight = np.asarray(weights, dtype=float)
    predicted = (probs >= 0.5).astype(int)
    auc = (
        float("nan")
        if np.unique(truth).size < 2
        else float(roc_auc_score(truth, probs, sample_weight=sample_weight))
    )
    return {
        "accuracy": float(accuracy_score(truth, predicted, sample_weight=sample_weight)),
        "macro_f1": float(f1_score(truth, predicted, average="macro", sample_weight=sample_weight)),
        "auroc": None if math.isnan(auc) else auc,
        "log_loss": float(log_loss(truth, probs, sample_weight=sample_weight, labels=[0, 1])),
        "brier": float(brier_score_loss(truth, probs, sample_weight=sample_weight)),
        "ece": expected_calibration_error(truth, probs, sample_weight),
    }
