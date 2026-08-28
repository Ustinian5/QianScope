from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RealityObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    scenario_id: str
    run_id: str
    observed_at: datetime
    metric_name: str
    segment: str
    value: float
    sample_size: int = Field(ge=1)
    standard_error: float = Field(ge=0)
    source: str
    provenance: dict[str, Any] = Field(default_factory=dict)


def append_observation(path: Path, observation: RealityObservation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(observation.model_dump(mode="json"), ensure_ascii=False) + "\n")
