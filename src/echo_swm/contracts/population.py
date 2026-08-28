from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PopulationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    population_id: str
    prototype_id: str
    weight: float = Field(ge=0)
    attributes: dict[str, Any]
    uncertainty: dict[str, float] = Field(default_factory=dict)
    data_version: str = "synthetic-demo-v1"
