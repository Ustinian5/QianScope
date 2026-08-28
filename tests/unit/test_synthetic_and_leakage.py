from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from echo_swm.data.synthetic import TARGETS, generate_synthetic_population
from echo_swm.data.validation.leakage import scan_table_for_leakage
from echo_swm.models.echo import NUMERIC_FEATURES


def test_synthetic_generator_is_deterministic_and_labeled() -> None:
    first = generate_synthetic_population(5_000, seed=11)
    second = generate_synthetic_population(5_000, seed=11)
    assert first.equals(second)
    assert first.schema.metadata[b"classification"] == b"SYNTHETIC DATA - NOT REAL HUMAN DATA"
    assert set(TARGETS).issubset(first.column_names)
    assert np.isclose(first["survey_weight"].to_numpy().sum(), 5_000)


def test_leakage_scanner_accepts_features_and_rejects_outcomes() -> None:
    table = generate_synthetic_population(5_000, seed=12)
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    assert scan_table_for_leakage(table, NUMERIC_FEATURES + ("treatment",), cutoff) == []
    findings = scan_table_for_leakage(table, ["purchase_post", "gt_purchase_post_control"], cutoff)
    assert {finding.code for finding in findings} == {"OUTCOME_FEATURE"}
    future = table.set_column(
        table.schema.get_field_index("available_at"),
        "available_at",
        [[cutoff + timedelta(days=1)] * table.num_rows],
    )
    assert any(
        finding.code == "FUTURE_AVAILABLE"
        for finding in scan_table_for_leakage(future, NUMERIC_FEATURES, cutoff)
    )
