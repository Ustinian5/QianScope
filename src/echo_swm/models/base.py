from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray


@dataclass(frozen=True)
class WorldBatch:
    population: pa.Table
    intervention: str | None = None


@dataclass(frozen=True)
class WorldForecast:
    probabilities: dict[str, NDArray[np.float64]]
    model_version: str
    calibration_status: str


class WorldModel(Protocol):
    def forward(self, batch: WorldBatch) -> WorldForecast: ...
