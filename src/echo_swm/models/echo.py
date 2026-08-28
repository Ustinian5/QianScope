from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import joblib
import numpy as np
import pyarrow as pa
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from echo_swm.data.synthetic import BRANCHES, TARGETS
from echo_swm.models.base import WorldBatch, WorldForecast
from echo_swm.models.calibration import apply_temperature, fit_temperature

NUMERIC_FEATURES: Final[tuple[str, ...]] = (
    "age",
    "education_level",
    "log_income",
    "student",
    "risk_preference",
    "price_sensitivity",
    "tech_acceptance",
    "brand_trust_pre",
    "peer_sensitivity",
    "prior_purchase",
    "purchase_intent_pre",
)


def build_feature_matrix(table: pa.Table, intervention: str | None = None) -> NDArray[np.float64]:
    missing = sorted(set(NUMERIC_FEATURES) - set(table.column_names))
    if missing:
        raise ValueError(f"missing model features: {missing}")
    columns = [np.asarray(table[name].to_numpy(), dtype=float) for name in NUMERIC_FEATURES]
    treatments = (
        np.full(table.num_rows, intervention, dtype=object)
        if intervention is not None
        else np.asarray(table["treatment"].to_pylist(), dtype=object)
    )
    if not set(treatments).issubset(set(BRANCHES)):
        raise ValueError("unknown intervention label")
    columns.extend((treatments == branch).astype(float) for branch in BRANCHES[1:])
    matrix = np.column_stack(columns).astype(float)
    if not np.all(np.isfinite(matrix)):
        raise ValueError(
            "model features must be finite; missing values require explicit imputation"
        )
    return matrix


@dataclass
class CalibratedTargetModel:
    estimator: Pipeline
    temperature: float

    def predict(self, matrix: NDArray[np.float64], calibrated: bool = True) -> NDArray[np.float64]:
        probabilities = self.estimator.predict_proba(matrix)[:, 1].astype(float)
        return apply_temperature(probabilities, self.temperature) if calibrated else probabilities


@dataclass
class EchoModelBundle:
    models: dict[str, CalibratedTargetModel]
    model_version: str = "echo-structured-logit-v1"
    data_version: str = "synthetic-demo-v1"

    def predict(
        self, table: pa.Table, intervention: str | None = None, *, calibrated: bool = True
    ) -> dict[str, NDArray[np.float64]]:
        matrix = build_feature_matrix(table, intervention)
        return {target: model.predict(matrix, calibrated) for target, model in self.models.items()}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path) -> EchoModelBundle:
        loaded = joblib.load(path)
        if not isinstance(loaded, cls):
            raise TypeError("model artifact has an unexpected type")
        return loaded


class ECHOModel:
    """Stable world-model interface backed by verified structured models."""

    def __init__(self, bundle: EchoModelBundle) -> None:
        self.bundle = bundle

    def forward(self, batch: WorldBatch) -> WorldForecast:
        return WorldForecast(
            probabilities=self.bundle.predict(batch.population, batch.intervention),
            model_version=self.bundle.model_version,
            calibration_status="temperature_scaled",
        )


def train_echo_model(
    table: pa.Table,
    train_indices: NDArray[np.int64],
    calibration_indices: NDArray[np.int64],
) -> EchoModelBundle:
    matrix = build_feature_matrix(table)
    weights = np.asarray(table["survey_weight"].to_numpy(), dtype=float)
    models: dict[str, CalibratedTargetModel] = {}
    for target in TARGETS:
        labels = np.asarray(table[target].to_numpy(), dtype=int)
        estimator = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(C=0.8, max_iter=800, random_state=2026),
                ),
            ]
        )
        estimator.fit(
            matrix[train_indices],
            labels[train_indices],
            classifier__sample_weight=weights[train_indices],
        )
        raw_calibration = estimator.predict_proba(matrix[calibration_indices])[:, 1]
        temperature = fit_temperature(
            raw_calibration, labels[calibration_indices], weights[calibration_indices]
        )
        models[target] = CalibratedTargetModel(estimator, temperature)
    return EchoModelBundle(models=models)


def respondent_split(
    size: int, seed: int = 2026
) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.int64]]:
    rng = np.random.default_rng(seed)
    indices = rng.permutation(size).astype(np.int64)
    train_end = int(size * 0.60)
    calibration_end = int(size * 0.80)
    return indices[:train_end], indices[train_end:calibration_end], indices[calibration_end:]
