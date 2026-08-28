from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataSourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_name: str
    source_type: str
    license: str
    owner: str
    collection_method: str
    geographic_scope: list[str] = Field(default_factory=list)
    population_scope: list[str] = Field(default_factory=list)
    time_range: tuple[datetime, datetime]
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str
    contains_personal_data: bool
    deidentification_method: str | None = None
    allowed_uses: list[str]
    schema_version: str = "1.0.0"

    @model_validator(mode="after")
    def validate_time_and_privacy(self) -> DataSourceManifest:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("time_range end must not precede start")
        if self.contains_personal_data and not self.deidentification_method:
            raise ValueError("personal data requires a deidentification method")
        return self
