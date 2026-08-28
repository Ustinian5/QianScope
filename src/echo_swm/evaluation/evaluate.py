from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

from echo_swm.data.synthetic import TARGETS
from echo_swm.evaluation.metrics import binary_metrics
from echo_swm.models.echo import EchoModelBundle


def evaluate_bundle(
    bundle: EchoModelBundle, table: pa.Table, test_indices: NDArray[np.int64]
) -> dict[str, Any]:
    subset = table.take(pa.array(test_indices))
    weights = np.asarray(subset["survey_weight"].to_numpy(), dtype=float)
    calibrated = bundle.predict(subset)
    uncalibrated = bundle.predict(subset, calibrated=False)
    report: dict[str, Any] = {"split": "respondent_holdout", "rows": subset.num_rows, "targets": {}}
    for target in TARGETS:
        labels = np.asarray(subset[target].to_numpy(), dtype=int)
        prevalence = float(np.average(labels, weights=weights))
        baseline_probs = np.full(labels.size, prevalence)
        report["targets"][target] = {
            "weighted_prevalence_baseline": binary_metrics(labels, baseline_probs, weights),
            "echo_uncalibrated": binary_metrics(labels, uncalibrated[target], weights),
            "echo_calibrated": binary_metrics(labels, calibrated[target], weights),
            "temperature": bundle.models[target].temperature,
        }
    return report


def write_evaluation(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rows: list[str] = []
    for target, variants in report["targets"].items():
        for model_name, metrics in variants.items():
            if not isinstance(metrics, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{target}</td><td>{model_name}</td>"
                f"<td>{metrics['log_loss']:.4f}</td><td>{metrics['brier']:.4f}</td>"
                f"<td>{metrics['ece']:.4f}</td><td>{metrics['auroc'] or 0:.4f}</td>"
                "</tr>"
            )
    html = (
        "<!doctype html><meta charset='utf-8'><title>QianScope evaluation</title>"
        "<style>body{font:15px system-ui;max-width:1100px;margin:40px auto;color:#17202a}"
        "table{border-collapse:collapse;width:100%}th,td{padding:8px;border:1px solid #ccd1d1}"
        "th{background:#eaf2f8}</style>"
        "<h1>Model evaluation</h1><p>SYNTHETIC DATA — NOT REAL HUMAN DATA</p>"
        "<p>Respondent holdout only; no training-set metrics are shown.</p>"
        "<table><thead><tr><th>Target</th><th>Model</th><th>Log loss</th><th>Brier</th>"
        "<th>ECE</th><th>AUROC</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table><p>本结果为概率模拟与条件预测，不构成对现实结果的保证。</p>"
    )
    (output_dir / "model_evaluation.html").write_text(html, encoding="utf-8")
