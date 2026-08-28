from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from echo_swm.core.ids import file_hash

TARGETS: Final[tuple[str, ...]] = (
    "purchase_post",
    "churn_post",
    "complain_post",
    "recommend_post",
    "trust_high_post",
)
BRANCHES: Final[tuple[str, ...]] = ("control", "price_up_30", "price_up_30_discount")


def _sigmoid(value: NDArray[np.float64]) -> NDArray[np.float64]:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30, 30)))


def _branch_probabilities(
    features: dict[str, NDArray[np.float64]], branch: str
) -> dict[str, NDArray[np.float64]]:
    price_delta = 0.0 if branch == "control" else 0.30
    has_discount = float(branch == "price_up_30_discount")
    student_relief = has_discount * features["student"]
    price_shock = price_delta * (0.7 + 1.6 * features["price_sensitivity"])

    trust_logit = (
        -0.25
        + 2.1 * features["brand_trust_pre"]
        + 0.35 * features["tech_acceptance"]
        - 2.2 * price_shock
        + 1.15 * student_relief
    )
    purchase_logit = (
        -0.7
        + 1.25 * features["tech_acceptance"]
        + 1.35 * features["brand_trust_pre"]
        + 0.65 * features["prior_purchase"]
        + 0.35 * features["purchase_intent_pre"]
        - 3.0 * price_shock
        + 1.8 * student_relief
        + 0.10 * features["log_income_centered"]
    )
    churn_logit = (
        -1.7
        + 2.9 * price_shock
        + 0.7 * features["risk_preference"]
        - 1.5 * features["brand_trust_pre"]
        - 1.3 * student_relief
    )
    complain_logit = (
        -2.1
        + 2.6 * price_shock
        + 0.8 * features["peer_sensitivity"]
        - 0.8 * features["brand_trust_pre"]
        - 0.8 * student_relief
    )
    recommend_logit = (
        -0.8
        + 1.3 * features["brand_trust_pre"]
        + 0.8 * features["tech_acceptance"]
        + 0.4 * features["prior_purchase"]
        - 2.2 * price_shock
        + 1.0 * student_relief
    )
    return {
        "purchase_post": _sigmoid(purchase_logit),
        "churn_post": _sigmoid(churn_logit),
        "complain_post": _sigmoid(complain_logit),
        "recommend_post": _sigmoid(recommend_logit),
        "trust_high_post": _sigmoid(trust_logit),
    }


def generate_synthetic_population(size: int = 10_000, seed: int = 2026) -> pa.Table:
    if not 5_000 <= size <= 20_000:
        raise ValueError("the public demo size must be between 5,000 and 20,000")
    rng = np.random.default_rng(seed)
    age = np.clip(rng.normal(35, 12, size).round(), 18, 75).astype(np.int16)
    education_level = rng.choice(4, size=size, p=[0.12, 0.34, 0.42, 0.12]).astype(np.int8)
    student = ((age < 28) & (rng.random(size) < 0.42)).astype(np.int8)
    log_income = rng.normal(10.65 + 0.13 * education_level - 0.35 * student, 0.55, size)
    income = np.exp(log_income).round(2)
    risk_preference = np.clip(rng.beta(2.2, 2.7, size), 0, 1)
    price_sensitivity = np.clip(
        rng.beta(2.4, 2.0, size) + 0.18 * student - 0.08 * (log_income - log_income.mean()),
        0,
        1,
    )
    tech_acceptance = np.clip(rng.beta(2.8, 1.9, size) - 0.003 * (age - 35), 0, 1)
    brand_trust_pre = np.clip(rng.beta(2.5, 2.2, size) + 0.12 * tech_acceptance, 0, 1)
    peer_sensitivity = np.clip(rng.beta(2.0, 2.5, size), 0, 1)
    prior_purchase_prob = _sigmoid(-1.1 + 1.8 * tech_acceptance + 0.9 * brand_trust_pre)
    prior_purchase = rng.binomial(1, prior_purchase_prob).astype(np.int8)
    pre_intent_prob = _sigmoid(
        -0.6 + 1.1 * tech_acceptance + brand_trust_pre - 0.8 * price_sensitivity
    )
    purchase_intent_pre = rng.binomial(1, pre_intent_prob).astype(np.int8)
    survey_weight = rng.lognormal(0, 0.35, size)
    survey_weight *= size / survey_weight.sum()
    treatment = rng.choice(BRANCHES, size=size, p=[0.34, 0.33, 0.33])
    region = rng.choice(["east", "central", "west", "northeast"], size, p=[0.38, 0.27, 0.25, 0.10])
    segment = np.where(
        student == 1, "student_users", np.where(prior_purchase == 1, "existing_users", "prospects")
    )

    feature_values = {
        "student": student.astype(float),
        "risk_preference": risk_preference,
        "price_sensitivity": price_sensitivity,
        "tech_acceptance": tech_acceptance,
        "brand_trust_pre": brand_trust_pre,
        "peer_sensitivity": peer_sensitivity,
        "prior_purchase": prior_purchase.astype(float),
        "purchase_intent_pre": purchase_intent_pre.astype(float),
        "log_income_centered": log_income - log_income.mean(),
    }
    branch_probs = {branch: _branch_probabilities(feature_values, branch) for branch in BRANCHES}
    assigned_probs = {
        target: np.choose(
            np.select(
                [treatment == "price_up_30", treatment == "price_up_30_discount"],
                [1, 2],
                default=0,
            ),
            [branch_probs[branch][target] for branch in BRANCHES],
        )
        for target in TARGETS
    }
    outcomes = {
        target: rng.binomial(1, assigned_probs[target]).astype(np.int8) for target in TARGETS
    }
    base_time = datetime(2026, 1, 1, tzinfo=UTC)

    columns: dict[str, object] = {
        "person_id": [f"syn_{index:06d}" for index in range(size)],
        "source_id": ["synthetic_demo"] * size,
        "observed_at": [base_time] * size,
        "available_at": [base_time] * size,
        "age": age,
        "education_level": education_level,
        "income": income,
        "log_income": log_income,
        "student": student,
        "region": region,
        "segment": segment,
        "risk_preference": risk_preference,
        "price_sensitivity": price_sensitivity,
        "tech_acceptance": tech_acceptance,
        "brand_trust_pre": brand_trust_pre,
        "peer_sensitivity": peer_sensitivity,
        "prior_purchase": prior_purchase,
        "purchase_intent_pre": purchase_intent_pre,
        "survey_weight": survey_weight,
        "treatment": treatment,
        **outcomes,
    }
    for target, probs in assigned_probs.items():
        columns[f"gt_{target}_assigned"] = probs
    for branch, target_probs in branch_probs.items():
        for target, probs in target_probs.items():
            columns[f"gt_{target}_{branch}"] = probs
    table = pa.table(columns)
    metadata = dict(table.schema.metadata or {})
    metadata[b"classification"] = b"SYNTHETIC DATA - NOT REAL HUMAN DATA"
    metadata[b"generator_version"] = b"synthetic-demo-v1"
    metadata[b"seed"] = str(seed).encode()
    return table.replace_schema_metadata(metadata)


def write_synthetic_demo(output_dir: Path, size: int = 10_000, seed: int = 2026) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    table = generate_synthetic_population(size=size, seed=seed)
    data_path = output_dir / "population.parquet"
    pq.write_table(table, data_path, compression="zstd")
    manifest = {
        "label": "SYNTHETIC DATA — NOT REAL HUMAN DATA",
        "data_version": "synthetic-demo-v1",
        "rows": table.num_rows,
        "seed": seed,
        "content_hash": file_hash(data_path),
        "generated_at": datetime.now(UTC).isoformat(),
        "ground_truth_columns": [name for name in table.column_names if name.startswith("gt_")],
    }
    (output_dir / "data_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data_path
