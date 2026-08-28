from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from echo_swm.world.constants import (
    GUIYANG_BIG_DATA_CITY_ID,
    GUIYANG_CITY_ID,
    GUIYANG_CONVENTION_CENTER_ID,
    GUIYANG_NORTH_STATION_ID,
    GUIYANG_REPRESENTED_POPULATION,
    GUIYANG_WORLD_ID,
    GUIYANG_WORLD_NAME,
    GUIZHOU_UNIVERSITY_WEST_ID,
    HUAGUOYUAN_COMMUNITY_ID,
    JIAXIU_RIVERFRONT_ID,
    QINGYAN_ANCIENT_TOWN_ID,
)


class LocationType(StrEnum):
    CITY = "city"
    DISTRICT = "district"
    CAMPUS = "campus"
    RESIDENTIAL = "residential"
    WORKPLACE = "workplace"
    SCHOOL = "school"
    LIBRARY = "library"
    CANTEEN = "canteen"
    COMMUNITY = "community"
    RETAIL = "retail"
    TRANSIT = "transit"
    ONLINE = "online"


class ChannelType(StrEnum):
    SOCIAL_MEDIA = "social_media"
    NEWS = "news"
    INTERPERSONAL = "interpersonal"
    COMMUNITY = "community"
    SEARCH = "search"
    ONSITE = "onsite"


class LocationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    name: str = Field(min_length=1, max_length=160)
    location_type: LocationType
    parent_id: str | None = None
    capacity: float = Field(default=1_000_000, gt=0)
    baseline_activity: float = Field(default=0.5, ge=0, le=1)
    semantic_tags: list[str] = Field(default_factory=list, max_length=30)
    supported_channels: list[ChannelType] = Field(default_factory=list)


def default_guiyang_locations() -> list[LocationSpec]:
    """Guiyang hierarchy behind the seven interactive map scenes."""

    return [
        LocationSpec(
            location_id=GUIYANG_CITY_ID,
            name="贵阳市",
            location_type=LocationType.CITY,
            capacity=GUIYANG_REPRESENTED_POPULATION,
            semantic_tags=["city", "provincial_capital", "big_data"],
            supported_channels=[ChannelType.NEWS, ChannelType.SOCIAL_MEDIA],
        ),
        LocationSpec(
            location_id=GUIYANG_CONVENTION_CENTER_ID,
            name="贵阳国际会议展览中心",
            location_type=LocationType.WORKPLACE,
            parent_id=GUIYANG_CITY_ID,
            capacity=3_000_000,
            baseline_activity=0.74,
            semantic_tags=["convention", "big_data_expo", "guike_hackathon", "business"],
            supported_channels=[ChannelType.NEWS, ChannelType.ONSITE, ChannelType.SOCIAL_MEDIA],
        ),
        LocationSpec(
            location_id=GUIYANG_BIG_DATA_CITY_ID,
            name="贵阳大数据科创城",
            location_type=LocationType.WORKPLACE,
            parent_id=GUIYANG_CITY_ID,
            capacity=2_500_000,
            baseline_activity=0.72,
            semantic_tags=["big_data", "technology", "innovation", "startup"],
            supported_channels=[ChannelType.NEWS, ChannelType.COMMUNITY, ChannelType.SEARCH],
        ),
        LocationSpec(
            location_id=GUIZHOU_UNIVERSITY_WEST_ID,
            name="贵州大学西校区",
            location_type=LocationType.CAMPUS,
            parent_id=GUIYANG_CITY_ID,
            capacity=1_500_000,
            baseline_activity=0.68,
            semantic_tags=["campus", "student", "learning", "innovation"],
            supported_channels=[ChannelType.COMMUNITY, ChannelType.ONSITE, ChannelType.SEARCH],
        ),
        LocationSpec(
            location_id=JIAXIU_RIVERFRONT_ID,
            name="甲秀楼·南明河",
            location_type=LocationType.COMMUNITY,
            parent_id=GUIYANG_CITY_ID,
            capacity=3_000_000,
            baseline_activity=0.62,
            semantic_tags=["landmark", "culture", "riverfront", "public_space"],
            supported_channels=[
                ChannelType.COMMUNITY,
                ChannelType.INTERPERSONAL,
                ChannelType.ONSITE,
            ],
        ),
        LocationSpec(
            location_id=QINGYAN_ANCIENT_TOWN_ID,
            name="青岩古镇",
            location_type=LocationType.RETAIL,
            parent_id=GUIYANG_CITY_ID,
            capacity=2_000_000,
            baseline_activity=0.64,
            semantic_tags=["culture", "tourism", "retail", "heritage"],
            supported_channels=[ChannelType.ONSITE, ChannelType.SOCIAL_MEDIA],
        ),
        LocationSpec(
            location_id=GUIYANG_NORTH_STATION_ID,
            name="贵阳北站",
            location_type=LocationType.TRANSIT,
            parent_id=GUIYANG_CITY_ID,
            capacity=GUIYANG_REPRESENTED_POPULATION,
            baseline_activity=0.76,
            semantic_tags=["mobility", "railway", "gateway"],
            supported_channels=[ChannelType.ONSITE, ChannelType.NEWS],
        ),
        LocationSpec(
            location_id=HUAGUOYUAN_COMMUNITY_ID,
            name="花果园社区",
            location_type=LocationType.RESIDENTIAL,
            parent_id=GUIYANG_CITY_ID,
            capacity=GUIYANG_REPRESENTED_POPULATION,
            baseline_activity=0.7,
            semantic_tags=["home", "community", "commerce", "dense_urban"],
            supported_channels=[ChannelType.INTERPERSONAL, ChannelType.COMMUNITY],
        ),
        LocationSpec(
            location_id="online_public_space",
            name="线上公共空间",
            location_type=LocationType.ONLINE,
            parent_id=GUIYANG_CITY_ID,
            capacity=GUIYANG_REPRESENTED_POPULATION,
            semantic_tags=["online", "big_data_expo", "guike_hackathon"],
            supported_channels=[ChannelType.SOCIAL_MEDIA, ChannelType.SEARCH],
        ),
    ]


class WorldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    world_id: str = GUIYANG_WORLD_ID
    name: str = GUIYANG_WORLD_NAME
    represented_population: float = Field(default=GUIYANG_REPRESENTED_POPULATION, ge=5_000)
    prototype_count: int = Field(default=5_000, ge=5_000, le=250_000)
    tick_minutes: int = Field(default=60, ge=15, le=1_440)
    start_hour: int = Field(default=0, ge=0, le=23)
    population_filters: dict[str, list[str]] = Field(default_factory=dict)
    locations: list[LocationSpec] = Field(default_factory=default_guiyang_locations, min_length=1)

    @model_validator(mode="after")
    def validate_location_tree(self) -> WorldSpec:
        if self.represented_population < self.prototype_count:
            raise ValueError("represented_population cannot be smaller than prototype_count")
        location_ids = [item.location_id for item in self.locations]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("location ids must be unique")
        known = set(location_ids)
        parents = {item.location_id: item.parent_id for item in self.locations}
        for item in self.locations:
            if item.parent_id is not None and item.parent_id not in known:
                raise ValueError(f"unknown parent location: {item.parent_id}")
            cursor = item.parent_id
            visited = {item.location_id}
            while cursor is not None:
                if cursor in visited:
                    raise ValueError("location hierarchy must be acyclic")
                visited.add(cursor)
                cursor = parents[cursor]
        return self


class WorldEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=3, max_length=10_000)
    start_tick: int = Field(default=1, ge=0)
    duration_ticks: int = Field(default=24, ge=1, le=720)
    source_location_id: str | None = None
    target_location_ids: list[str] = Field(default_factory=list)
    channels: list[ChannelType] = Field(
        default_factory=lambda: [ChannelType.SOCIAL_MEDIA, ChannelType.INTERPERSONAL],
        min_length=1,
    )
    audience_filters: dict[str, list[str]] = Field(default_factory=dict)
    intensity: float = Field(default=0.7, ge=0, le=1)
    credibility: float = Field(default=0.7, ge=0, le=1)
    novelty: float = Field(default=0.6, ge=0, le=1)
    valence: float = Field(default=0, ge=-1, le=1)
    belief_signals: dict[str, float] = Field(default_factory=dict)
    value_signals: dict[str, float] = Field(default_factory=dict)
    goal_signals: dict[str, float] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("belief_signals", "value_signals", "goal_signals")
    @classmethod
    def bounded_signals(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < -1 or item > 1 for item in value.values()):
            raise ValueError("event signals must be within [-1, 1]")
        return value

    @model_validator(mode="after")
    def validate_targeting(self) -> WorldEvent:
        if len(self.channels) != len(set(self.channels)):
            raise ValueError("event channels must be unique")
        if any(not values for values in self.audience_filters.values()):
            raise ValueError("audience filters cannot contain an empty choice list")
        return self


class DecisionOption(BaseModel):
    """One event-specific response available to every independent agent."""

    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=240)
    position: float = Field(ge=-1, le=1)


class DecisionQuestion(BaseModel):
    """A generated or user-supplied question for one deliberation round."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    question_id: str = Field(min_length=1, max_length=80)
    round_index: int = Field(ge=1, le=8)
    prompt: str = Field(min_length=2, max_length=1_000)
    context: str = Field(default="", max_length=2_000)
    decision_construct: Literal[
        "reaction", "evidence", "action", "persistence", "recommendation"
    ] = Field(alias="construct")
    options: list[DecisionOption] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def validate_options(self) -> DecisionQuestion:
        option_ids = [item.option_id for item in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("decision option ids must be unique within a question")
        return self


class WorldSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    world: WorldSpec = Field(default_factory=WorldSpec)
    events: list[WorldEvent] = Field(min_length=1, max_length=10)
    horizon_ticks: int = Field(default=72, ge=1, le=720)
    paths: int = Field(default=3, ge=1, le=32)
    seed: int = 2026
    trace_agent_count: int = Field(default=12, ge=0, le=100)
    snapshot_interval: int = Field(default=6, ge=1, le=168)
    interaction_mode: Literal["independent"] = "independent"
    decision_rounds: int = Field(default=4, ge=1, le=8)
    question_overrides: list[DecisionQuestion] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_events(self) -> WorldSimulationRequest:
        location_ids = {item.location_id for item in self.world.locations}
        event_ids = [item.event_id for item in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("event ids must be unique")
        for event in self.events:
            referenced = set(event.target_location_ids)
            if event.source_location_id is not None:
                referenced.add(event.source_location_id)
            unknown = sorted(referenced - location_ids)
            if unknown:
                raise ValueError(f"event references unknown locations: {unknown}")
        if not any(event.start_tick <= self.horizon_ticks for event in self.events):
            raise ValueError("at least one event must start within the simulation horizon")
        if self.question_overrides and len(self.question_overrides) != self.decision_rounds:
            raise ValueError("question_overrides must contain exactly decision_rounds questions")
        if self.question_overrides:
            expected_rounds = list(range(1, self.decision_rounds + 1))
            actual_rounds = [item.round_index for item in self.question_overrides]
            if actual_rounds != expected_rounds:
                raise ValueError("question_overrides must be ordered from round 1")
        return self


class QuantileBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    mean: float


class DiffusionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    tick: int
    reached_fraction: QuantileBand
    reached_population: QuantileBand
    newly_reached_fraction: QuantileBand
    channel_reach: dict[str, QuantileBand]


class PopulationHeatCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int
    location_id: str
    metrics: dict[str, QuantileBand]


class EmotionDistributionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int
    metrics: dict[str, QuantileBand]


class BeliefDistributionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int
    beliefs: dict[str, QuantileBand]


class SegmentDifference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_field: str
    segment_value: str
    prototype_count: int
    represented_population: float
    reached_fraction: QuantileBand
    support: QuantileBand
    leading_action: str
    leading_action_share: QuantileBand


class LocationActivityPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int
    location_id: str
    present_population: float
    awareness: QuantileBand
    active_expression: QuantileBand
    dominant_action: str


class AgentTracePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    tier: str
    path: int
    tick: int
    location_id: str
    received_event_ids: list[str]
    aware_event_ids: list[str]
    received_channels: list[str]
    beliefs: dict[str, float]
    emotion: dict[str, float]
    goals: dict[str, float]
    action: str
    working_memory_salience: float
    episodic_memory_count: int
    semantic_memory_strength: float
    reason_codes: list[str]


class DecisionOptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str
    label: str
    agent_count: int = Field(ge=0)
    represented_population: float = Field(ge=0)
    share: float = Field(ge=0, le=1)
    ci_low: float = Field(ge=0, le=1)
    ci_high: float = Field(ge=0, le=1)


class DecisionRepresentative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    name: str
    role: str
    segment: str
    round_index: int = Field(ge=1, le=8)
    choice: str
    confidence: float = Field(ge=0, le=1)
    rationale: str
    reason_codes: list[str]
    represented_weight: float = Field(gt=0)


class DecisionRoundResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_index: int = Field(ge=1, le=8)
    question: DecisionQuestion
    options: list[DecisionOptionResult]
    agent_count: int = Field(ge=0)
    mean_confidence: float = Field(ge=0, le=1)
    changed_from_previous_share: float | None = Field(default=None, ge=0, le=1)
    response_entropy: float = Field(ge=0, le=1)
    representatives: list[DecisionRepresentative]


class IndependentDecisionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_mode: Literal["independent"] = "independent"
    event_id: str
    event_category: str
    agent_count: int = Field(ge=0)
    round_count: int = Field(ge=1, le=8)
    total_decisions: int = Field(ge=0)
    completed_decisions: int = Field(ge=0)
    rounds: list[DecisionRoundResult]
    final_leading_choice: str
    final_leading_share: float = Field(ge=0, le=1)
    changed_mind_share: float = Field(ge=0, le=1)
    mean_confidence: float = Field(ge=0, le=1)
    summary: list[str]
    methodology: list[str]
    deterministic_signature: str


class WorldPopulationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prototype_count: int
    represented_population: float
    tier_counts: dict[str, int]
    relationship_count: int
    relationship_types: list[str]
    location_count: int
    immutable_personality_signature: str


class WorldSimulationArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_json: str
    trajectory_csv: str
    agent_traces: str
    replay_log: str
    run_manifest: str
    snapshot_directory: str
    population_profiles: str
    relationships: str
    locations: str
    agent_decisions: str | None = None


class WorldSimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    world_id: str
    status: str = "completed"
    model_version: str
    data_version: str
    population: WorldPopulationSummary
    diffusion_curve: list[DiffusionPoint]
    population_heatmap: list[PopulationHeatCell]
    emotion_distribution: list[EmotionDistributionPoint]
    belief_distribution: list[BeliefDistributionPoint]
    segment_difference: list[SegmentDifference]
    location_activity: list[LocationActivityPoint]
    agent_trace: list[AgentTracePoint]
    decision_report: IndependentDecisionReport | None = None
    final_action_distribution: dict[str, QuantileBand]
    state_transition_order: list[str]
    deterministic_signature: str
    artifacts: WorldSimulationArtifacts
    limitations: list[str]
    disclaimer: str
