from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from echo_swm import DISCLAIMER
from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.config import Settings
from echo_swm.core.ids import new_id
from echo_swm.personas.contracts import (
    PersonaCrossCheckCandidate,
    PersonaDimension,
    PersonaFramework,
    PersonaInterviewRequest,
    PersonaInterviewResponse,
    PersonaMapItem,
    PersonaMapSnapshot,
    PersonaProfile,
    PersonaRelationship,
    PersonaScheduleItem,
    PersonaSearchItem,
    PersonaSearchResult,
    PersonaState,
    PersonaTrait,
)
from echo_swm.personas.definitions import (
    PERSONA_DEFINITION_VERSION,
    PERSONA_FRAMEWORKS,
    group_value_label,
)
from echo_swm.research.population import ResearchPopulation
from echo_swm.world.constants import (
    GUIYANG_BIG_DATA_CITY_ID,
    GUIYANG_BIG_DATA_SCENE_ID,
    GUIYANG_CITY_ID,
    GUIYANG_CONVENTION_CENTER_ID,
    GUIYANG_CONVENTION_SCENE_ID,
    GUIYANG_NORTH_STATION_ID,
    GUIYANG_NORTH_STATION_SCENE_ID,
    GUIYANG_REPRESENTED_POPULATION,
    GUIZHOU_UNIVERSITY_SCENE_ID,
    GUIZHOU_UNIVERSITY_WEST_ID,
    HUAGUOYUAN_COMMUNITY_ID,
    HUAGUOYUAN_SCENE_ID,
    JIAXIU_RIVERFRONT_ID,
    JIAXIU_TOWER_SCENE_ID,
    QINGYAN_ANCIENT_TOWN_ID,
    QINGYAN_TOWN_SCENE_ID,
)

MODEL_VERSION = "stable-persona-catalog-guiyang-v1"
DATA_VERSION = "stable-personality-population-guiyang-2025-v1"

ObjectArray = NDArray[np.object_]
FloatArray = NDArray[np.float64]

SURNAMES = (
    "赵",
    "钱",
    "孙",
    "李",
    "周",
    "吴",
    "郑",
    "王",
    "冯",
    "陈",
    "褚",
    "卫",
    "蒋",
    "沈",
    "韩",
    "杨",
    "朱",
    "秦",
    "尤",
    "许",
    "何",
    "吕",
    "施",
    "张",
    "孔",
    "曹",
    "严",
    "华",
    "金",
    "魏",
    "陶",
    "姜",
    "戚",
    "谢",
    "邹",
    "喻",
    "柏",
    "水",
    "窦",
    "章",
    "云",
    "苏",
    "潘",
    "葛",
    "奚",
    "范",
    "彭",
    "郎",
    "鲁",
    "韦",
)
GIVEN_START = ("子", "若", "嘉", "思", "明", "清", "安", "知", "景", "予")
GIVEN_END = ("宁", "然", "辰", "言", "涵", "远", "月", "川", "桐", "一")

ROLE_LABELS = {
    "student": "高校学生",
    "professional": "专业从业者",
    "service_worker": "服务业从业者",
    "skilled_worker": "技术工人",
    "caregiver": "家庭照护者",
    "self_employed": "个体经营者",
    "retired": "退休居民",
    "job_seeker": "求职者",
}
ORGANIZATIONS = {
    "student": "贵州大学及花溪大学城高校网络",
    "professional": "贵阳专业机构",
    "service_worker": "贵阳城市生活服务网络",
    "skilled_worker": "贵阳大数据与工程技术网络",
    "caregiver": "花果园社区与家庭网络",
    "self_employed": "贵阳本地个体经营网络",
    "retired": "贵阳社区居民",
    "job_seeker": "贵阳就业服务网络",
}
GOAL_LABELS = {
    "security": "保持生活稳定并降低不确定性",
    "achievement": "完成有难度的目标并获得认可",
    "status": "提升影响力与职业位置",
    "belonging": "维持可信的人际连接与归属感",
    "growth": "学习新能力并拓展选择空间",
    "meaning": "做对他人和社会有意义的事",
    "survival": "先保障基本生活与安全",
}
INTEREST_LABELS = {
    "daily_life": "日常生活",
    "technology": "科技与新工具",
    "culture": "文化内容",
    "health": "健康生活",
    "community": "社区公共议题",
    "learning": "学习与成长",
}
CHANNEL_LABELS = {
    "social_media": "社交媒体",
    "news": "新闻媒体",
    "interpersonal": "熟人交流",
    "community": "社区渠道",
    "search": "主动搜索",
}
RELATION_LABELS = {
    "family": "家人",
    "acquaintance": "熟人",
    "friend": "朋友",
    "coworker": "同事",
    "online": "线上关注",
    "follower": "线上关注",
    "authority": "权威关系",
    "community": "社区熟人",
}
RELATION_CHANNELS = {
    "family": "熟人交流",
    "acquaintance": "熟人交流",
    "coworker": "社区渠道",
    "community": "社区渠道",
    "online": "社交媒体",
}
TRAIT_LABELS = {
    "openness": "开放求新",
    "conscientiousness": "尽责有序",
    "extraversion": "主动外向",
    "agreeableness": "合作体谅",
    "neuroticism": "情绪敏感",
}
VALUE_LABELS = {
    "self_direction": "自主",
    "stimulation": "探索",
    "achievement": "成就",
    "power": "影响力",
    "security": "安全",
    "conformity": "规则",
    "tradition": "传统",
    "benevolence": "善意",
    "universalism": "普遍关怀",
    "hedonism": "生活体验",
}
ACTION_LABELS = {
    "student": "整理课程与社群信息",
    "professional": "推进今天的工作任务",
    "service_worker": "处理现场服务安排",
    "skilled_worker": "检查设备与执行细节",
    "caregiver": "协调家庭与社区事务",
    "self_employed": "核对订单和经营成本",
    "retired": "安排今天的社区活动",
    "job_seeker": "查看岗位并准备申请材料",
}
SCENE_LOCATION_IDS = {
    GUIYANG_CITY_ID: GUIYANG_CONVENTION_SCENE_ID,
    GUIYANG_CONVENTION_CENTER_ID: GUIYANG_CONVENTION_SCENE_ID,
    GUIYANG_BIG_DATA_CITY_ID: GUIYANG_BIG_DATA_SCENE_ID,
    GUIZHOU_UNIVERSITY_WEST_ID: GUIZHOU_UNIVERSITY_SCENE_ID,
    JIAXIU_RIVERFRONT_ID: JIAXIU_TOWER_SCENE_ID,
    QINGYAN_ANCIENT_TOWN_ID: QINGYAN_TOWN_SCENE_ID,
    GUIYANG_NORTH_STATION_ID: GUIYANG_NORTH_STATION_SCENE_ID,
    HUAGUOYUAN_COMMUNITY_ID: HUAGUOYUAN_SCENE_ID,
    "online_public_space": GUIYANG_CONVENTION_SCENE_ID,
}
LOCATION_NAMES = {
    GUIYANG_CITY_ID: "贵阳市",
    GUIYANG_CONVENTION_CENTER_ID: "贵阳国际会议展览中心",
    GUIYANG_BIG_DATA_CITY_ID: "贵阳大数据科创城",
    GUIZHOU_UNIVERSITY_WEST_ID: "贵州大学西校区",
    JIAXIU_RIVERFRONT_ID: "甲秀楼·南明河",
    QINGYAN_ANCIENT_TOWN_ID: "青岩古镇",
    GUIYANG_NORTH_STATION_ID: "贵阳北站",
    HUAGUOYUAN_COMMUNITY_ID: "花果园社区",
    "online_public_space": "线上公共空间",
}


@dataclass(frozen=True)
class _Identity:
    name: str
    role_key: str
    role: str
    organization: str


class _PersonaInterviewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=10, max_length=1_500)
    confidence: float = Field(ge=0, le=1)
    cited_state: list[str] = Field(min_length=2, max_length=8)


class PersonaCatalog:
    def __init__(
        self,
        population: ResearchPopulation,
        represented_population: float = GUIYANG_REPRESENTED_POPULATION,
        settings: Settings | None = None,
    ) -> None:
        self.population = population
        self.table = population.agents
        self.size = self.table.num_rows
        base_weights = self._floats("survey_weight")
        self.weights = base_weights * (represented_population / float(base_weights.sum()))
        self.represented_population = float(represented_population)
        self.settings = settings
        self.agent_ids = self._objects("agent_id")
        self.roles = self._objects("social_role")
        self.goals = self._objects("primary_goal")
        self.interests = self._objects("primary_interest")
        self.channels = self._objects("primary_channel")
        self.tiers = self._objects("tier")
        self.home_location_ids, self.primary_location_ids, self.social_location_ids = (
            self._assign_locations()
        )
        self.names = np.asarray(
            [self._name_for_index(index) for index in range(self.size)], dtype=object
        )
        self._id_to_index = {str(agent_id): index for index, agent_id in enumerate(self.agent_ids)}
        self._location_names = LOCATION_NAMES
        self._search_text = np.asarray(
            [self._searchable_text(index) for index in range(self.size)], dtype=object
        )

    def _assign_locations(self) -> tuple[ObjectArray, ObjectArray, ObjectArray]:
        regions = self._objects("region_type")
        indices = np.arange(self.size)
        home = np.where(
            np.isin(regions, ["urban_core", "town"]),
            HUAGUOYUAN_COMMUNITY_ID,
            QINGYAN_ANCIENT_TOWN_ID,
        ).astype(object)
        primary = np.full(self.size, GUIYANG_BIG_DATA_CITY_ID, dtype=object)
        primary[self.roles == "student"] = GUIZHOU_UNIVERSITY_WEST_ID
        primary[(self.roles == "professional") & (indices % 2 == 0)] = GUIYANG_CONVENTION_CENTER_ID
        primary[(self.roles == "skilled_worker") & (indices % 3 == 0)] = GUIYANG_NORTH_STATION_ID
        primary[(self.roles == "service_worker") & (indices % 2 == 0)] = GUIYANG_NORTH_STATION_ID
        primary[(self.roles == "service_worker") & (indices % 2 == 1)] = QINGYAN_ANCIENT_TOWN_ID
        primary[(self.roles == "self_employed") & (indices % 2 == 0)] = QINGYAN_ANCIENT_TOWN_ID
        primary[(self.roles == "self_employed") & (indices % 2 == 1)] = JIAXIU_RIVERFRONT_ID
        primary[self.roles == "caregiver"] = HUAGUOYUAN_COMMUNITY_ID
        primary[self.roles == "retired"] = JIAXIU_RIVERFRONT_ID
        primary[self.roles == "job_seeker"] = GUIYANG_CONVENTION_CENTER_ID

        social = np.full(self.size, JIAXIU_RIVERFRONT_ID, dtype=object)
        social[self.interests == "learning"] = GUIZHOU_UNIVERSITY_WEST_ID
        social[self.interests == "daily_life"] = HUAGUOYUAN_COMMUNITY_ID
        social[self.interests == "technology"] = GUIYANG_BIG_DATA_CITY_ID
        social[self.interests == "culture"] = QINGYAN_ANCIENT_TOWN_ID
        social[self.interests == "health"] = HUAGUOYUAN_COMMUNITY_ID
        return (
            np.asarray(home, dtype=object),
            np.asarray(primary, dtype=object),
            np.asarray(social, dtype=object),
        )

    def _objects(self, name: str) -> ObjectArray:
        return np.asarray(self.table[name].to_pylist(), dtype=object)

    def _floats(self, name: str) -> FloatArray:
        values = self.table[name].combine_chunks().to_numpy(zero_copy_only=False)
        return np.asarray(values, dtype=float)

    @staticmethod
    def _name_for_index(index: int) -> str:
        surname = SURNAMES[index % len(SURNAMES)]
        first = GIVEN_START[(index // len(SURNAMES)) % len(GIVEN_START)]
        second = GIVEN_END[(index // (len(SURNAMES) * len(GIVEN_START))) % len(GIVEN_END)]
        return f"{surname}{first}{second}"

    def _identity(self, index: int) -> _Identity:
        role_key = str(self.roles[index])
        organization_type = str(self.table["organization_type"][index].as_py())
        organization = group_value_label("organization_type", organization_type)
        if organization == organization_type:
            organization = ORGANIZATIONS.get(role_key, "贵阳社会生活网络")
        if role_key == "student" and self._actual_location_id(index) == GUIZHOU_UNIVERSITY_WEST_ID:
            organization = "贵州大学"
        return _Identity(
            name=str(self.names[index]),
            role_key=role_key,
            role=ROLE_LABELS.get(role_key, role_key),
            organization=organization,
        )

    def _actual_location_id(self, index: int) -> str:
        return str(self.primary_location_ids[index])

    def _scene_location_id(self, actual_location_id: str) -> str:
        return SCENE_LOCATION_IDS.get(actual_location_id, GUIYANG_CONVENTION_SCENE_ID)

    def _route_actual_location_ids(self, index: int) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    str(self.home_location_ids[index]),
                    str(self.primary_location_ids[index]),
                    str(self.social_location_ids[index]),
                )
            )
        )

    def _searchable_text(self, index: int) -> str:
        identity = self._identity(index)
        actual_location = self._actual_location_id(index)
        route_locations = self._route_actual_location_ids(index)
        values = (
            self.agent_ids[index],
            identity.name,
            identity.role_key,
            identity.role,
            identity.organization,
            self.goals[index],
            GOAL_LABELS.get(str(self.goals[index]), str(self.goals[index])),
            self.interests[index],
            INTEREST_LABELS.get(str(self.interests[index]), str(self.interests[index])),
            self.channels[index],
            CHANNEL_LABELS.get(str(self.channels[index]), str(self.channels[index])),
            actual_location,
            self._location_names.get(actual_location, actual_location),
            *(
                value
                for location_id in route_locations
                for value in (
                    location_id,
                    self._location_names.get(location_id, location_id),
                )
            ),
            self.table["age_group"][index].as_py(),
        )
        return " ".join(str(value) for value in values).casefold()

    def _trait_items(self, index: int, limit: int | None = 3) -> list[PersonaTrait]:
        scored = [(key, float(self.table[f"big5_{key}"][index].as_py())) for key in TRAIT_LABELS]
        scored.sort(key=lambda item: item[1], reverse=True)
        selected = scored if limit is None else scored[:limit]
        return [
            PersonaTrait(key=key, label=TRAIT_LABELS[key], score=score) for key, score in selected
        ]

    def _value_items(self, index: int, limit: int | None = 3) -> list[PersonaTrait]:
        scored = [
            (key, float(self.table[f"schwartz_{key}"][index].as_py())) for key in VALUE_LABELS
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        selected = scored if limit is None else scored[:limit]
        return [
            PersonaTrait(key=key, label=VALUE_LABELS[key], score=score) for key, score in selected
        ]

    @staticmethod
    def _dimension_interpretation(
        score: float,
        scale_min: float,
        scale_max: float,
        low_pole: str,
        high_pole: str,
    ) -> str:
        normalized = (score - scale_min) / max(1e-12, scale_max - scale_min)
        if normalized <= 0.33:
            return f"更接近“{low_pole}”"
        if normalized >= 0.67:
            return f"更接近“{high_pole}”"
        return f"在“{low_pole}”与“{high_pole}”之间较为均衡"

    def _frameworks(self, index: int) -> list[PersonaFramework]:
        frameworks: list[PersonaFramework] = []
        for framework in PERSONA_FRAMEWORKS:
            dimensions = []
            for definition in framework.dimensions:
                score = float(self.table[definition.field][index].as_py())
                dimensions.append(
                    PersonaDimension(
                        key=definition.key,
                        field=definition.field,
                        label=definition.label,
                        description=definition.description,
                        score=score,
                        scale_min=definition.scale_min,
                        scale_max=definition.scale_max,
                        low_pole=definition.low_pole,
                        high_pole=definition.high_pole,
                        interpretation=self._dimension_interpretation(
                            score,
                            definition.scale_min,
                            definition.scale_max,
                            definition.low_pole,
                            definition.high_pole,
                        ),
                    )
                )
            frameworks.append(
                PersonaFramework(
                    framework_id=framework.framework_id,
                    label=framework.label,
                    reference=framework.reference,
                    description=framework.description,
                    dimensions=dimensions,
                )
            )
        return frameworks

    def _demographics(self, index: int) -> dict[str, str]:
        fields = (
            "age_group",
            "gender",
            "education_level",
            "social_role",
            "organization_type",
            "region_type",
            "household_type",
        )
        result = {
            field: group_value_label(field, str(self.table[field][index].as_py()))
            for field in fields
        }
        result["age"] = f"{int(self.table['age'][index].as_py())} 岁"
        return result

    def _field_origins(self, index: int) -> dict[str, str]:
        raw = str(self.table["field_origins"][index].as_py())
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items()}

    def _profile_completeness(self) -> float:
        expected = {
            definition.field
            for framework in PERSONA_FRAMEWORKS
            for definition in framework.dimensions
        }
        available = expected.intersection(self.table.column_names)
        return len(available) / max(1, len(expected))

    def _mood(self, index: int) -> str:
        stress = float(self.table["baseline_stress"][index].as_py())
        interest = float(self.table["baseline_interest"][index].as_py())
        if stress >= 0.66:
            return "略显紧绷"
        if interest >= 0.58:
            return "专注"
        if stress <= 0.35:
            return "放松"
        return "平静"

    def _bio(self, index: int) -> str:
        identity = self._identity(index)
        interest = INTEREST_LABELS.get(str(self.interests[index]), str(self.interests[index]))
        goal = GOAL_LABELS.get(str(self.goals[index]), str(self.goals[index]))
        channel = CHANNEL_LABELS.get(str(self.channels[index]), str(self.channels[index]))
        return (
            f"一位生活在贵阳的{identity.role}，长期关注{interest}。"
            f"当前最重要的目标是{goal}，通常通过{channel}形成判断。"
        )

    def _state(self, index: int) -> PersonaState:
        identity = self._identity(index)
        actual_location = self._actual_location_id(index)
        return PersonaState(
            mood=self._mood(index),
            stress=round(float(self.table["baseline_stress"][index].as_py()) * 100),
            intention=round(float(self.table["baseline_intention"][index].as_py()) * 100),
            confidence=round(float(self.table["baseline_confidence"][index].as_py()) * 100),
            current_action=ACTION_LABELS.get(identity.role_key, "处理今天的日常事务"),
            current_location=self._location_names.get(actual_location, actual_location),
        )

    def _memories(self, index: int) -> list[str]:
        identity = self._identity(index)
        interest = INTEREST_LABELS.get(str(self.interests[index]), str(self.interests[index]))
        channel = CHANNEL_LABELS.get(str(self.channels[index]), str(self.channels[index]))
        goal = GOAL_LABELS.get(str(self.goals[index]), str(self.goals[index]))
        return [
            f"最近一次与{interest}有关的经历，让{identity.name}重新评估了时间与收益。",
            f"过去通过{channel}接触到的消息中，来源是否可信会明显影响其态度。",
            f"今天仍在推进“{goal}”，因此会优先处理与此直接相关的信息。",
        ]

    def _schedule(self, index: int) -> list[PersonaScheduleItem]:
        state = self._state(index)
        home_id = str(self.home_location_ids[index])
        social_id = str(self.social_location_ids[index])
        return [
            PersonaScheduleItem(
                time="08:00",
                activity="通勤并查看当天消息",
                location=self._location_names.get(home_id, home_id),
            ),
            PersonaScheduleItem(
                time="11:00",
                activity=state.current_action,
                location=state.current_location,
            ),
            PersonaScheduleItem(
                time="19:00",
                activity="处理个人事务并与熟人交流",
                location=self._location_names.get(social_id, social_id),
            ),
        ]

    def _relationship_indices(self, index: int, limit: int = 8) -> list[int]:
        graph = self.population.graph
        connected = np.flatnonzero((graph.source == index) | (graph.target == index))
        ordered = connected[np.argsort(-graph.trust[connected])]
        return [int(edge_index) for edge_index in ordered[:limit]]

    def _relationships(self, index: int, limit: int = 8) -> list[PersonaRelationship]:
        graph = self.population.graph
        results: list[PersonaRelationship] = []
        seen: set[int] = set()
        for edge_index in self._relationship_indices(index, limit=limit * 2):
            source = int(graph.source[edge_index])
            target = int(graph.target[edge_index])
            peer_index = target if source == index else source
            if peer_index in seen:
                continue
            seen.add(peer_index)
            peer = self._identity(peer_index)
            relation_key = str(graph.relationship_type[edge_index])
            results.append(
                PersonaRelationship(
                    persona_id=str(self.agent_ids[peer_index]),
                    name=peer.name,
                    role=peer.role,
                    relation=RELATION_LABELS.get(relation_key, relation_key),
                    trust=float(graph.trust[edge_index]),
                    strength=float(graph.strength[edge_index]),
                    channel=RELATION_CHANNELS.get(relation_key, "熟人交流"),
                )
            )
            if len(results) >= limit:
                break
        return results

    def _summary(self, index: int) -> PersonaSearchItem:
        identity = self._identity(index)
        actual_location = self._actual_location_id(index)
        traits = self._trait_items(index)
        values = self._value_items(index)
        return PersonaSearchItem(
            persona_id=str(self.agent_ids[index]),
            name=identity.name,
            role=identity.role,
            organization=identity.organization,
            location_id=self._scene_location_id(actual_location),
            location=self._location_names.get(actual_location, actual_location),
            tier=str(self.tiers[index]),
            represented_weight=float(self.weights[index]),
            mood=self._mood(index),
            tags=[item.label for item in (*traits[:2], *values[:1])],
            bio=self._bio(index),
        )

    def search(
        self,
        *,
        query: str = "",
        tier: str | None = None,
        location_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> PersonaSearchResult:
        normalized = query.strip().casefold()
        indices = np.arange(self.size)
        mask = np.ones(self.size, dtype=bool)
        if normalized:
            mask &= np.asarray([normalized in str(text) for text in self._search_text], dtype=bool)
        if tier is not None:
            mask &= self.tiers == tier
        if location_id is not None:
            location_matches = np.asarray(
                [
                    location_id
                    in {
                        self._scene_location_id(actual_location_id)
                        for actual_location_id in self._route_actual_location_ids(int(index))
                    }
                    for index in indices
                ],
                dtype=bool,
            )
            mask &= location_matches
        matched = indices[mask]
        active_limit = max(1, min(limit, 100))
        active_offset = max(0, offset)
        selected = matched[active_offset : active_offset + active_limit]
        return PersonaSearchResult(
            query=query,
            prototype_matches=int(matched.size),
            represented_population=float(self.weights[matched].sum()),
            total_prototypes=self.size,
            total_represented_population=self.represented_population,
            offset=active_offset,
            limit=active_limit,
            items=[self._summary(int(index)) for index in selected],
            note="结果为加权合成人格原型，不是可识别的真实居民。",
        )

    def map_snapshot(self) -> PersonaMapSnapshot:
        items: list[PersonaMapItem] = []
        for index in range(self.size):
            route_location_ids = list(
                dict.fromkeys(
                    self._scene_location_id(str(location_id))
                    for location_id in self._route_actual_location_ids(index)
                )
            )
            items.append(
                PersonaMapItem(
                    persona_id=str(self.agent_ids[index]),
                    tier=str(self.tiers[index]),
                    represented_weight=float(self.weights[index]),
                    route_location_ids=route_location_ids,
                )
            )
        return PersonaMapSnapshot(
            total_prototypes=self.size,
            total_represented_population=self.represented_population,
            items=items,
            note="每个地图活动点对应一个稳定合成人格原型；路线由其居住、主要活动与社交地点生成。",
        )

    def profile(self, persona_id: str) -> PersonaProfile:
        try:
            index = self._id_to_index[persona_id]
        except KeyError as exc:
            raise FileNotFoundError(f"persona not found: {persona_id}") from exc
        identity = self._identity(index)
        actual_location = self._actual_location_id(index)
        home_id = str(self.home_location_ids[index])
        social_id = str(self.social_location_ids[index])
        return PersonaProfile(
            persona_id=persona_id,
            name=identity.name,
            role=identity.role,
            organization=identity.organization,
            age=int(self.table["age"][index].as_py()),
            age_group=str(self.table["age_group"][index].as_py()),
            gender=str(self.table["gender"][index].as_py()),
            education_level=str(self.table["education_level"][index].as_py()),
            region_type=str(self.table["region_type"][index].as_py()),
            household_type=str(self.table["household_type"][index].as_py()),
            tier=str(self.tiers[index]),
            represented_weight=float(self.weights[index]),
            bio=self._bio(index),
            traits=self._trait_items(index, limit=None),
            values=self._value_items(index, limit=None),
            demographics=self._demographics(index),
            frameworks=self._frameworks(index),
            primary_goal=GOAL_LABELS.get(str(self.goals[index]), str(self.goals[index])),
            primary_interest=INTEREST_LABELS.get(
                str(self.interests[index]), str(self.interests[index])
            ),
            primary_channel=CHANNEL_LABELS.get(
                str(self.channels[index]), str(self.channels[index])
            ),
            state=self._state(index),
            memories=self._memories(index),
            schedule=self._schedule(index),
            relationships=self._relationships(index),
            mobility={
                "home_location_id": home_id,
                "primary_location_id": actual_location,
                "social_location_id": social_id,
                "scene_location_id": self._scene_location_id(actual_location),
            },
            model_version=MODEL_VERSION,
            data_version=DATA_VERSION,
            definition_version=PERSONA_DEFINITION_VERSION,
            source_id=str(self.table["source_id"][index].as_py()),
            field_origins=self._field_origins(index),
            profile_completeness=self._profile_completeness(),
            profile_hash=str(self.table["profile_hash"][index].as_py()),
            disclaimer=DISCLAIMER,
        )

    def interview(
        self,
        persona_id: str,
        request: PersonaInterviewRequest,
    ) -> PersonaInterviewResponse:
        profile = self.profile(persona_id)
        question = request.question.strip()
        combined = f"{question} {request.event_context}".strip()
        relation_question = any(
            marker in question for marker in ("他", "她", "别人", "朋友", "同学", "同事", "家人")
        )
        candidates = []
        if relation_question:
            candidates = [
                PersonaCrossCheckCandidate(
                    persona_id=item.persona_id,
                    name=item.name,
                    relation=item.relation,
                )
                for item in profile.relationships[:2]
            ]
        if self.settings is not None and self.settings.llm_configured:
            llm = OpenAICompatibleLLM(self.settings)
            variation_id = new_id("variation")
            draft = llm.complete_json(
                (
                    "Answer as the supplied synthetic persona, in natural first-person Chinese. "
                    "Use only the profile, current state, memories, relationships, user question, "
                    "and event context supplied below. Never claim a real identity, hidden memory, "
                    "certain future, or another person's private thoughts. If asked about someone "
                    "else, clearly separate inference from knowledge and recommend cross-checking. "
                    "Keep the response specific to this persona. The variation_id is a diversity "
                    "cue so repeated interviews vary naturally without changing the persona."
                ),
                json.dumps(
                    {
                        "variation_id": variation_id,
                        "question": question,
                        "event_context": request.event_context,
                        "persona": {
                            "persona_id": profile.persona_id,
                            "name": profile.name,
                            "role": profile.role,
                            "organization": profile.organization,
                            "demographics": profile.demographics,
                            "bio": profile.bio,
                            "traits": [item.model_dump() for item in profile.traits],
                            "values": [item.model_dump() for item in profile.values],
                            "primary_goal": profile.primary_goal,
                            "primary_interest": profile.primary_interest,
                            "primary_channel": profile.primary_channel,
                            "state": profile.state.model_dump(),
                            "memories": profile.memories,
                            "relationships": [
                                item.model_dump() for item in profile.relationships[:4]
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                _PersonaInterviewDraft,
                max_output_tokens=1_800,
                temperature=1.0,
                cache=False,
                operation="persona_interview",
                variation_id=variation_id,
            )
            return PersonaInterviewResponse(
                interview_id=new_id("interview"),
                persona_id=persona_id,
                persona_name=profile.name,
                question=question,
                answer=draft.answer,
                confidence=draft.confidence,
                mode="llm_persona",
                cited_state=draft.cited_state,
                cross_check_candidates=candidates,
                cognitive_boundary=(
                    "回答由大模型生成，但只允许使用该合成人格档案、状态、关系与用户提供的事件条件。"
                ),
                ai_execution=([llm.last_execution] if llm.last_execution is not None else []),
            )
        if any(marker in question for marker in ("你是谁", "介绍一下", "做什么")):
            answer = (
                f"我是{profile.name}，目前是{profile.role}。"
                f"我主要关心{profile.primary_interest}，最近最想做的是{profile.primary_goal}。"
            )
        elif any(marker in question for marker in ("为什么", "怎么想", "态度", "选择", "影响")):
            context = (
                f"面对“{request.event_context.strip()}”，"
                if request.event_context.strip()
                else "面对这件事，"
            )
            answer = (
                f"{context}我会先判断它是否有助于{profile.primary_goal}。"
                f"我重视{profile.values[0].label}，目前情绪是{profile.state.mood}、"
                f"压力约 {profile.state.stress}%。所以我大概率会先{profile.state.current_action}，"
                "再结合可信来源和熟人的反馈决定是否行动。"
            )
        elif relation_question:
            related_name = profile.relationships[0].name if profile.relationships else "身边的人"
            answer = (
                "我只能描述自己观察到的关系和过往互动，不能替对方确认当前想法。"
                f"从我的角度看，{related_name}"
                "是否认同，会影响我对消息可信度的判断；最好直接向当事人交叉确认。"
            )
        elif any(marker in question for marker in ("记得", "过去", "最近", "经历")):
            answer = f"我能回忆到的一条相关线索是：{profile.memories[0]} 这会影响我现在的判断。"
        elif any(marker in combined for marker in ("精确结果", "一定会", "百分之百", "真实身份")):
            answer = (
                "我没有足够信息给出确定答案，也不能提供现实个人身份。"
                "我只能基于当前合成人格、状态和已提供的事件条件表达一种可能反应。"
            )
        else:
            answer = (
                f"我会从{profile.primary_interest}和“{profile.values[0].label}”出发看这个问题。"
                f"结合当前目标，我倾向先{profile.state.current_action}，"
                "收集能被验证的信息后再形成公开态度。"
            )
        return PersonaInterviewResponse(
            interview_id=new_id("interview"),
            persona_id=persona_id,
            persona_name=profile.name,
            question=question,
            answer=answer,
            confidence=profile.state.confidence / 100,
            mode="deterministic_persona",
            cited_state=[
                f"目标：{profile.primary_goal}",
                f"价值：{profile.values[0].label}",
                f"状态：{profile.state.mood} / 压力 {profile.state.stress}%",
                f"记忆：{profile.memories[0]}",
            ],
            cross_check_candidates=candidates,
            cognitive_boundary="回答只使用该合成人格的档案、状态、关系与用户提供的事件条件。",
        )


__all__ = ["DATA_VERSION", "MODEL_VERSION", "PersonaCatalog"]
