"""Canonical defaults shared by the Guiyang social-world runtimes."""

GUIYANG_WORLD_ID = "guiyang_social_world"
GUIYANG_WORLD_NAME = "贵阳社会模拟器"
GUIYANG_CITY_ID = "guiyang"
GUIYANG_REPRESENTED_POPULATION = 6_668_900

# Provider-neutral logical locations used by the simulation contract.
GUIYANG_CONVENTION_CENTER_ID = "guiyang_convention_center"
GUIYANG_BIG_DATA_CITY_ID = "guiyang_big_data_city"
GUIZHOU_UNIVERSITY_WEST_ID = "guizhou_university_west"
JIAXIU_RIVERFRONT_ID = "jiaxiu_riverfront"
QINGYAN_ANCIENT_TOWN_ID = "qingyan_ancient_town"
GUIYANG_NORTH_STATION_ID = "guiyang_north_station"
HUAGUOYUAN_COMMUNITY_ID = "huaguoyuan_community"

# Stable scene ids consumed by the map. Keep these separate from logical ids so
# the backend contract can remain richer than any one map implementation.
GUIYANG_CONVENTION_SCENE_ID = "guiyang_convention"
GUIYANG_BIG_DATA_SCENE_ID = "guiyang_big_data"
GUIZHOU_UNIVERSITY_SCENE_ID = "guizhou_university"
JIAXIU_TOWER_SCENE_ID = "jiaxiu_tower"
QINGYAN_TOWN_SCENE_ID = "qingyan_town"
GUIYANG_NORTH_STATION_SCENE_ID = "guiyang_north_station"
HUAGUOYUAN_SCENE_ID = "huaguoyuan"

GUIYANG_SCENE_IDS = (
    GUIYANG_CONVENTION_SCENE_ID,
    GUIYANG_BIG_DATA_SCENE_ID,
    GUIZHOU_UNIVERSITY_SCENE_ID,
    JIAXIU_TOWER_SCENE_ID,
    QINGYAN_TOWN_SCENE_ID,
    GUIYANG_NORTH_STATION_SCENE_ID,
    HUAGUOYUAN_SCENE_ID,
)

__all__ = [
    "GUIYANG_BIG_DATA_CITY_ID",
    "GUIYANG_BIG_DATA_SCENE_ID",
    "GUIYANG_CITY_ID",
    "GUIYANG_CONVENTION_CENTER_ID",
    "GUIYANG_CONVENTION_SCENE_ID",
    "GUIYANG_NORTH_STATION_ID",
    "GUIYANG_NORTH_STATION_SCENE_ID",
    "GUIYANG_REPRESENTED_POPULATION",
    "GUIYANG_SCENE_IDS",
    "GUIYANG_WORLD_ID",
    "GUIYANG_WORLD_NAME",
    "GUIZHOU_UNIVERSITY_SCENE_ID",
    "GUIZHOU_UNIVERSITY_WEST_ID",
    "HUAGUOYUAN_COMMUNITY_ID",
    "HUAGUOYUAN_SCENE_ID",
    "JIAXIU_RIVERFRONT_ID",
    "JIAXIU_TOWER_SCENE_ID",
    "QINGYAN_ANCIENT_TOWN_ID",
    "QINGYAN_TOWN_SCENE_ID",
]
