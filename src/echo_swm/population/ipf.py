from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from echo_swm.population.weighting import validate_weights


@dataclass(frozen=True)
class IPFResult:
    weights: NDArray[np.float64]
    converged: bool
    iterations: int
    max_relative_error: float


def iterative_proportional_fitting(
    records: Sequence[Mapping[str, Hashable]],
    margins: Mapping[str, Mapping[Hashable, float]],
    initial_weights: Sequence[float] | None = None,
    *,
    tolerance: float = 1e-7,
    max_iterations: int = 500,
) -> IPFResult:
    """Rake record weights to categorical target totals without dropping unknown cells."""
    if not records or not margins:
        raise ValueError("records and margins must be non-empty")
    size = len(records)
    weights = (
        np.ones(size, dtype=float)
        if initial_weights is None
        else validate_weights(initial_weights).copy()
    )
    if weights.size != size:
        raise ValueError("initial weight count differs from record count")

    masks: dict[tuple[str, Hashable], NDArray[np.bool_]] = {}
    for variable, targets in margins.items():
        observed_categories = {record.get(variable) for record in records}
        missing_targets = set(targets) - observed_categories
        if missing_targets:
            raise ValueError(
                f"no records cover {variable} categories: {sorted(map(str, missing_targets))}"
            )
        for category in targets:
            masks[(variable, category)] = np.asarray(
                [record.get(variable) == category for record in records], dtype=bool
            )

    max_error = float("inf")
    for iteration in range(1, max_iterations + 1):
        for variable, targets in margins.items():
            for category, target in targets.items():
                if target < 0:
                    raise ValueError("margin targets must be non-negative")
                mask = masks[(variable, category)]
                current = float(weights[mask].sum())
                if current == 0 and target > 0:
                    raise ValueError(f"zero support for positive target {variable}={category}")
                if current > 0:
                    weights[mask] *= target / current

        errors: list[float] = []
        for variable, targets in margins.items():
            for category, target in targets.items():
                actual = float(weights[masks[(variable, category)]].sum())
                errors.append(abs(actual - target) / max(abs(target), 1e-12))
        max_error = max(errors, default=0.0)
        if max_error <= tolerance:
            return IPFResult(weights, True, iteration, max_error)

    return IPFResult(weights, False, max_iterations, max_error)
