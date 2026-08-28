from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResponseType(StrEnum):
    CATEGORICAL = "categorical"
    MULTI_LABEL = "multi_label"
    ORDINAL = "ordinal"
    CONTINUOUS = "continuous"
    BINARY = "binary"
    OPEN_TEXT = "open_text"


class QuestionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question_text: str
    response_type: ResponseType
    options: list[str] = Field(default_factory=list)
    scale_min: float | None = None
    scale_max: float | None = None
    is_ordinal: bool = False
    direction: int = Field(default=1, ge=-1, le=1)
    latent_constructs: list[str] = Field(default_factory=list)
    population_scope: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source: str

    @model_validator(mode="after")
    def validate_response_space(self) -> QuestionSpec:
        if self.response_type in {
            ResponseType.BINARY,
            ResponseType.CATEGORICAL,
            ResponseType.ORDINAL,
        }:
            if len(self.options) < 2:
                raise ValueError("discrete questions require at least two options")
        if self.response_type == ResponseType.CONTINUOUS:
            if self.scale_min is None or self.scale_max is None or self.scale_max <= self.scale_min:
                raise ValueError("continuous questions require an increasing scale")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not precede valid_from")
        return self
