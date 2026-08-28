from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relation_type: str
    strength: float = Field(ge=0, le=1)
    trust: float = Field(ge=0, le=1)
    authority: float = Field(ge=0, le=1)
    similarity: float = Field(ge=0, le=1)
    interaction_frequency: float = Field(ge=0)
    valid_from: datetime
    valid_to: datetime | None = None
    provenance: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_self_loop_or_backwards_time(self) -> GraphEdge:
        if self.source_id == self.target_id:
            raise ValueError("self loops are not allowed in this graph contract")
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not precede valid_from")
        return self


class Hyperedge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hyperedge_id: str
    hyperedge_type: str
    member_ids: list[str]
    membership_weights: list[float]
    channel: str
    topic: str | None = None
    valid_from: datetime
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_membership(self) -> Hyperedge:
        if len(self.member_ids) < 2:
            raise ValueError("a hyperedge needs at least two members")
        if len(self.member_ids) != len(self.membership_weights):
            raise ValueError("member and weight lengths differ")
        if any(weight < 0 for weight in self.membership_weights):
            raise ValueError("membership weights must be non-negative")
        return self
