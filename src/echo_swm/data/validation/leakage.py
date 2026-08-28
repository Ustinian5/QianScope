from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import pyarrow as pa


@dataclass(frozen=True)
class LeakageFinding:
    code: str
    field: str
    detail: str


def scan_table_for_leakage(
    table: pa.Table,
    feature_columns: Iterable[str],
    prediction_cutoff: datetime,
) -> list[LeakageFinding]:
    findings: list[LeakageFinding] = []
    features = list(feature_columns)
    for field in features:
        lowered = field.lower()
        if lowered.startswith("gt_") or lowered.endswith("_post") or "outcome" in lowered:
            findings.append(
                LeakageFinding("OUTCOME_FEATURE", field, "outcome-like field in features")
            )
    if "available_at" not in table.column_names:
        findings.append(
            LeakageFinding("MISSING_AVAILABILITY", "available_at", "availability time absent")
        )
        return findings
    for index, value in enumerate(table["available_at"].to_pylist()):
        if value is not None and value > prediction_cutoff:
            findings.append(
                LeakageFinding(
                    "FUTURE_AVAILABLE",
                    "available_at",
                    f"row {index} became available after prediction cutoff",
                )
            )
            break
    missing = sorted(set(features) - set(table.column_names))
    findings.extend(
        LeakageFinding("MISSING_FEATURE", field, "feature not present") for field in missing
    )
    return findings
