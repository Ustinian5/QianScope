from __future__ import annotations

from echo_swm.world.constants import (
    GUIYANG_BIG_DATA_CITY_ID,
    GUIYANG_CONVENTION_CENTER_ID,
    GUIZHOU_UNIVERSITY_WEST_ID,
)
from echo_swm.world.contracts import (
    ChannelType,
    WorldEvent,
    WorldSimulationRequest,
)


def example_world_event() -> WorldEvent:
    return WorldEvent(
        event_id="big_data_expo_guike_hackathon",
        title="数博会“贵客松”创新赛事开放报名",
        description=(
            "中国国际大数据产业博览会期间启动“贵客松”创新赛事，"
            "面向高校学生、技术从业者和创业团队开放报名。"
            "观察赛事信息从会展中心向科创城与高校网络传播后的认知、参与意愿与行动变化。"
        ),
        source_location_id=GUIYANG_CONVENTION_CENTER_ID,
        target_location_ids=[
            GUIYANG_CONVENTION_CENTER_ID,
            GUIYANG_BIG_DATA_CITY_ID,
            GUIZHOU_UNIVERSITY_WEST_ID,
        ],
        channels=[
            ChannelType.SOCIAL_MEDIA,
            ChannelType.NEWS,
            ChannelType.COMMUNITY,
            ChannelType.ONSITE,
        ],
        audience_filters={
            "social_role": ["student", "professional", "skilled_worker", "self_employed"]
        },
        intensity=0.86,
        credibility=0.8,
        novelty=0.88,
        valence=0.58,
        belief_signals={"institutional_trust": 0.28, "social_attitude": 0.4},
        value_signals={"self_direction": 0.4, "achievement": 0.35},
        goal_signals={"growth": 0.55, "achievement": 0.48, "belonging": 0.22},
    )


def example_world_request(
    *, horizon_ticks: int = 72, paths: int = 3, seed: int = 2026
) -> WorldSimulationRequest:
    return WorldSimulationRequest(
        project_id="guiyang_big_data_expo_guike_hackathon",
        events=[example_world_event()],
        horizon_ticks=horizon_ticks,
        paths=paths,
        seed=seed,
    )
