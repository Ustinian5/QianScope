from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from echo_swm.world.constants import GUIYANG_REPRESENTED_POPULATION

InsightTool = Literal[
    "marketing",
    "trend",
    "brand",
    "product",
    "pricing",
    "competitive",
    "funnel",
    "churn",
    "creator",
]

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "marketing": ("event", "horizon"),
    "trend": ("term", "horizon"),
    "brand": ("brand",),
    "product": ("features",),
    "pricing": ("product", "prices", "audience"),
    "competitive": ("brand", "competitor", "action"),
    "funnel": ("product", "channel"),
    "churn": ("change", "horizon"),
    "creator": ("brief", "platform"),
}


class InsightRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: InsightTool
    fields: dict[str, str]
    population_size: int = Field(default=5_000, ge=5_000, le=20_000)
    represented_population: int = Field(default=GUIYANG_REPRESENTED_POPULATION, ge=5_000)
    seed: int = 2026

    @model_validator(mode="after")
    def validate_tool_fields(self) -> InsightRunRequest:
        missing = [
            field for field in REQUIRED_FIELDS[self.tool] if not self.fields.get(field, "").strip()
        ]
        if missing:
            raise ValueError(f"missing required fields for {self.tool}: {', '.join(missing)}")
        if self.tool == "product" and len(_split_values(self.fields["features"])) < 2:
            raise ValueError("product insight requires at least two features")
        if self.tool == "pricing":
            prices = _parse_prices(self.fields["prices"])
            if len(prices) < 2:
                raise ValueError("pricing insight requires at least two positive price points")
        return self


class InsightBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: int = Field(ge=0, le=100)
    detail: str | None = None


class InsightQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    name: str
    role: str
    quote: str


class InsightPopulationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_count: int = Field(ge=5_000)
    represented_population: int = Field(ge=5_000)
    population_origin: Literal["synthetic"] = "synthetic"
    stable_personas: bool = True


class InsightProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str
    data_version: str
    calibrated: bool = False
    grounding_status: Literal["synthetic_unanchored", "synthetic_anchored"]
    limitations: list[str]


class InsightRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: Literal["complete"] = "complete"
    tool: InsightTool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_fields: dict[str, str]
    title: str
    context: str
    metric_label: str
    metric_value: str
    metric_detail: str
    bars: list[InsightBar]
    notes: list[str]
    quotes: list[InsightQuote]
    population: InsightPopulationSummary
    provenance: InsightProvenance


def _split_values(raw: str) -> list[str]:
    normalized = raw.replace("，", ",").replace("、", ",").replace("；", ",")
    return [
        item.strip() for line in normalized.splitlines() for item in line.split(",") if item.strip()
    ]


def _parse_prices(raw: str) -> list[float]:
    values: list[float] = []
    normalized = raw.replace("，", ",").replace("￥", "").replace("¥", "")
    for token in normalized.replace(";", ",").replace("；", ",").split(","):
        try:
            value = float(token.strip())
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return sorted(set(values))


__all__ = [
    "InsightBar",
    "InsightPopulationSummary",
    "InsightProvenance",
    "InsightQuote",
    "InsightRunRequest",
    "InsightRunResult",
    "InsightTool",
]
