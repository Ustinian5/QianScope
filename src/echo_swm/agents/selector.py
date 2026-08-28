from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class AgentTiers:
    key_agents: NDArray[np.int64]
    representative_agents: NDArray[np.int64]
    background_agents: NDArray[np.int64]


class ActiveAgentSelector:
    def __init__(
        self,
        centrality_weight: float = 0.30,
        influence_weight: float = 0.20,
        uncertainty_weight: float = 0.25,
        exposure_weight: float = 0.15,
        diversity_weight: float = 0.10,
    ) -> None:
        self.weights = np.asarray(
            [
                centrality_weight,
                influence_weight,
                uncertainty_weight,
                exposure_weight,
                diversity_weight,
            ],
            dtype=float,
        )
        if np.any(self.weights < 0) or not np.isclose(self.weights.sum(), 1.0):
            raise ValueError("selector weights must be non-negative and sum to one")

    @staticmethod
    def _normalize(values: NDArray[np.float64]) -> NDArray[np.float64]:
        spread = float(values.max() - values.min())
        return np.zeros_like(values) if spread == 0 else (values - values.min()) / spread

    def select(
        self,
        centrality: NDArray[np.float64],
        influence: NDArray[np.float64],
        uncertainty: NDArray[np.float64],
        exposure: NDArray[np.float64],
        diversity: NDArray[np.float64],
        *,
        key_count: int,
        representative_count: int,
    ) -> AgentTiers:
        arrays = [centrality, influence, uncertainty, exposure, diversity]
        if len({array.shape for array in arrays}) != 1:
            raise ValueError("selector feature shapes differ")
        size = centrality.size
        if key_count < 0 or representative_count < 0 or key_count + representative_count > size:
            raise ValueError("invalid tier counts")
        features = np.column_stack([self._normalize(array.astype(float)) for array in arrays])
        score = features @ self.weights
        order = np.argsort(-score, kind="stable")
        return AgentTiers(
            key_agents=order[:key_count],
            representative_agents=order[key_count : key_count + representative_count],
            background_agents=order[key_count + representative_count :],
        )
