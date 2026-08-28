from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray


@dataclass(frozen=True)
class GeneratedGraph:
    source: NDArray[np.int64]
    target: NDArray[np.int64]
    strength: NDArray[np.float64]
    graph_version: str = "homophilic-config-v1"

    @property
    def edge_count(self) -> int:
        return int(self.source.size)

    def weighted_in_degree(self, node_count: int) -> NDArray[np.float64]:
        degree = np.zeros(node_count, dtype=float)
        np.add.at(degree, self.target, self.strength)
        return degree

    def aggregate_from_sources(
        self, values: NDArray[np.float64], node_count: int
    ) -> NDArray[np.float64]:
        numerator = np.zeros(node_count, dtype=float)
        denominator = np.zeros(node_count, dtype=float)
        np.add.at(numerator, self.target, self.strength * values[self.source])
        np.add.at(denominator, self.target, self.strength)
        fallback = float(values.mean())
        return np.divide(
            numerator,
            denominator,
            out=np.full(node_count, fallback, dtype=float),
            where=denominator > 0,
        )


def generate_homophilic_graph(
    population: pa.Table,
    *,
    neighbors_per_node: int = 6,
    homophily: float = 0.55,
    seed: int = 2026,
) -> GeneratedGraph:
    if neighbors_per_node < 1:
        raise ValueError("neighbors_per_node must be positive")
    if not 0 <= homophily <= 1:
        raise ValueError("homophily must be within [0, 1]")
    node_count = population.num_rows
    if node_count < 2:
        raise ValueError("at least two people are required")
    segments = np.asarray(population["segment"].to_pylist(), dtype=object)
    by_segment = {segment: np.flatnonzero(segments == segment) for segment in np.unique(segments)}
    rng = np.random.default_rng(seed)
    sources = np.repeat(np.arange(node_count, dtype=np.int64), neighbors_per_node)
    targets = np.empty(sources.size, dtype=np.int64)
    strengths = np.empty(sources.size, dtype=float)
    for edge_index, source in enumerate(sources):
        same_segment = rng.random() < homophily
        pool = by_segment[segments[source]] if same_segment else np.arange(node_count)
        target = int(rng.choice(pool))
        if target == source:
            target = int((target + 1 + rng.integers(0, node_count - 1)) % node_count)
        targets[edge_index] = target
        strengths[edge_index] = float(rng.beta(2.5, 2.0))
    return GeneratedGraph(sources, targets, strengths)
