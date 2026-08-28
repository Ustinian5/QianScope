from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class MultiLayerCityGraph:
    source: NDArray[np.int64]
    target: NDArray[np.int64]
    layer: NDArray[np.int8]
    strength: NDArray[np.float64]
    trust: NDArray[np.float64]
    layer_names: tuple[str, ...] = ("household", "workplace", "local", "online")
    graph_version: str = "suzhou-multiplex-v1"

    @property
    def edge_count(self) -> int:
        return int(self.source.size)

    def aggregate(
        self,
        values: NDArray[np.float64],
        node_count: int,
        *,
        layer_weights: tuple[float, ...] = (1.0, 0.65, 0.45, 0.30),
    ) -> NDArray[np.float64]:
        if values.shape != (node_count,):
            raise ValueError("value vector does not match graph node count")
        if len(layer_weights) != len(self.layer_names):
            raise ValueError("one weight is required for every graph layer")
        multipliers = np.asarray(layer_weights, dtype=float)[self.layer]
        edge_weight = self.strength * self.trust * multipliers
        numerator = np.zeros(node_count, dtype=float)
        denominator = np.zeros(node_count, dtype=float)
        np.add.at(numerator, self.target, values[self.source] * edge_weight)
        np.add.at(denominator, self.target, edge_weight)
        fallback = float(np.mean(values))
        return np.divide(
            numerator,
            denominator,
            out=np.full(node_count, fallback, dtype=float),
            where=denominator > 0,
        )

    def weighted_degree(self, node_count: int) -> NDArray[np.float64]:
        result = np.zeros(node_count, dtype=float)
        np.add.at(result, self.source, self.strength)
        np.add.at(result, self.target, self.strength)
        return result


def _sample_other(
    rng: np.random.Generator, pool: NDArray[np.int64], source: int, size: int
) -> NDArray[np.int64]:
    if pool.size <= 1:
        return np.full(size, (source + 1) % max(source + 2, 2), dtype=np.int64)
    targets = rng.choice(pool, size=size, replace=pool.size < size + 1).astype(np.int64)
    collision = targets == source
    if collision.any():
        alternatives = pool[pool != source]
        targets[collision] = rng.choice(alternatives, size=int(collision.sum()), replace=True)
    return targets


def build_multiplex_graph(
    household_ids: NDArray[np.int64],
    home_district: NDArray[np.int64],
    workplace_district: NDArray[np.int64],
    sector: NDArray[np.int8],
    digital_affinity: NDArray[np.float64],
    *,
    seed: int,
) -> MultiLayerCityGraph:
    size = household_ids.size
    rng = np.random.default_rng(seed)
    all_nodes = np.arange(size, dtype=np.int64)

    def group_pools(keys: NDArray[np.int64]) -> dict[int, NDArray[np.int64]]:
        grouped: dict[int, list[int]] = {}
        for index, key in enumerate(keys):
            grouped.setdefault(int(key), []).append(index)
        return {key: np.asarray(indices, dtype=np.int64) for key, indices in grouped.items()}

    household_pools = group_pools(household_ids)
    district_pools = group_pools(home_district.astype(np.int64))
    workplace_keys = workplace_district.astype(np.int64) * 10 + sector.astype(np.int64)
    workplace_pools = group_pools(workplace_keys)
    digital_keys = np.minimum((digital_affinity * 5).astype(np.int64), 4)
    digital_pools = group_pools(digital_keys)
    sources: list[NDArray[np.int64]] = []
    targets: list[NDArray[np.int64]] = []
    layers: list[NDArray[np.int8]] = []
    strengths: list[NDArray[np.float64]] = []
    trusts: list[NDArray[np.float64]] = []

    for layer, per_node in ((0, 2), (1, 2), (2, 2), (3, 2)):
        layer_source = np.repeat(np.arange(size, dtype=np.int64), per_node)
        layer_target = np.empty(layer_source.size, dtype=np.int64)
        for node in range(size):
            edge_slice = slice(node * per_node, (node + 1) * per_node)
            if layer == 0:
                pool = household_pools[int(household_ids[node])]
                if pool.size <= 1:
                    pool = district_pools[int(home_district[node])]
            elif layer == 1:
                pool = workplace_pools[int(workplace_keys[node])]
            elif layer == 2:
                pool = district_pools[int(home_district[node])]
            else:
                pool = digital_pools[int(digital_keys[node])]
            if pool.size <= 1:
                pool = all_nodes
            layer_target[edge_slice] = _sample_other(rng, pool, node, per_node)
        sources.append(layer_source)
        targets.append(layer_target)
        layers.append(np.full(layer_source.size, layer, dtype=np.int8))
        base_strength = (0.85, 0.65, 0.48, 0.36)[layer]
        base_trust = (0.90, 0.70, 0.60, 0.42)[layer]
        strengths.append(np.clip(rng.normal(base_strength, 0.12, layer_source.size), 0.05, 1))
        trusts.append(np.clip(rng.normal(base_trust, 0.14, layer_source.size), 0.05, 1))

    return MultiLayerCityGraph(
        source=np.concatenate(sources),
        target=np.concatenate(targets),
        layer=np.concatenate(layers),
        strength=np.concatenate(strengths),
        trust=np.concatenate(trusts),
    )
