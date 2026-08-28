from __future__ import annotations

from collections import Counter

import numpy as np

from echo_swm.city.anchors import load_suzhou_anchors, validate_anchor_totals
from echo_swm.city.population import build_suzhou_world, validate_city_world


def test_suzhou_official_anchors_close_exactly() -> None:
    anchors = load_suzhou_anchors()
    validation = validate_anchor_totals(anchors)
    assert anchors.population == 13_047_700
    assert anchors.gdp_100m == 27_695.1
    assert len(anchors.districts) == 10
    assert validation["population_matches"] is True
    assert validation["gdp_matches"] is True
    assert all(source.url.startswith("https://") for source in anchors.config.sources)


def test_weighted_suzhou_world_respects_constraints_and_network() -> None:
    world = build_suzhou_world(5_000, seed=2026)
    validation = validate_city_world(world)
    assert validation["prototype_count"] == 5_000
    assert validation["represented_population"] == 13_047_700
    assert validation["population_relative_error"] < 1e-12
    assert validation["income_relative_error"] < 1e-12
    assert validation["max_district_population_error"] < 1e-12
    assert validation["max_district_urbanization_error"] < 0.0035
    assert validation["negative_weight_count"] == 0
    assert world.graph.edge_count == 40_000
    assert not np.any(world.graph.source == world.graph.target)
    assert np.allclose(world.graph.aggregate(np.ones(5_000), 5_000), 1)

    counts = Counter(world.institutions["institution_type"].to_pylist())
    assert counts["hospital"] == 288
    assert counts["school"] == 868
    assert np.isclose(world.od_matrix.sum(), validation["od_total_commuters"])
    assert np.all(world.transport_capacity > 0)
    assert np.all(world.health_capacity > 0)
