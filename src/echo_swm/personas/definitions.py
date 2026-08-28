from __future__ import annotations

from dataclasses import dataclass

PERSONA_DEFINITION_VERSION = "echo-persona-definition-v3"


@dataclass(frozen=True)
class DimensionDefinition:
    key: str
    field: str
    label: str
    description: str
    low_pole: str
    high_pole: str
    scale_min: float = 0
    scale_max: float = 1


@dataclass(frozen=True)
class FrameworkDefinition:
    framework_id: str
    label: str
    reference: str
    description: str
    dimensions: tuple[DimensionDefinition, ...]


def _dimension(
    key: str,
    field: str,
    label: str,
    description: str,
    low_pole: str,
    high_pole: str,
    *,
    scale_min: float = 0,
    scale_max: float = 1,
) -> DimensionDefinition:
    return DimensionDefinition(
        key=key,
        field=field,
        label=label,
        description=description,
        low_pole=low_pole,
        high_pole=high_pole,
        scale_min=scale_min,
        scale_max=scale_max,
    )


PERSONA_FRAMEWORKS = (
    FrameworkDefinition(
        framework_id="big_five",
        label="大五人格",
        reference="Big Five / OCEAN",
        description="描述稳定的人格倾向；不把分数解释为能力高低或临床诊断。",
        dimensions=(
            _dimension(
                "openness",
                "big5_openness",
                "开放求新",
                "接受新经验与抽象观念的倾向",
                "偏熟悉与具体",
                "偏探索与开放",
            ),
            _dimension(
                "conscientiousness",
                "big5_conscientiousness",
                "尽责有序",
                "计划、坚持与自我约束的倾向",
                "偏灵活随性",
                "偏计划自律",
            ),
            _dimension(
                "extraversion",
                "big5_extraversion",
                "主动外向",
                "主动社交与表达活力的倾向",
                "偏安静内省",
                "偏主动表达",
            ),
            _dimension(
                "agreeableness",
                "big5_agreeableness",
                "合作体谅",
                "信任、合作与体谅他人的倾向",
                "偏竞争审慎",
                "偏合作体谅",
            ),
            _dimension(
                "neuroticism",
                "big5_neuroticism",
                "情绪敏感",
                "对压力和负面线索的敏感程度",
                "偏情绪稳定",
                "偏压力敏感",
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="schwartz_values",
        label="施瓦茨价值观",
        reference="Schwartz Basic Human Values",
        description="描述长期价值优先级；多个价值可以同时较高。",
        dimensions=(
            _dimension(
                "self_direction",
                "schwartz_self_direction",
                "自主",
                "独立思考与选择",
                "偏遵循既有路径",
                "偏自主选择",
            ),
            _dimension(
                "stimulation",
                "schwartz_stimulation",
                "探索",
                "变化、新鲜感与挑战",
                "偏稳定熟悉",
                "偏变化挑战",
            ),
            _dimension(
                "achievement",
                "schwartz_achievement",
                "成就",
                "通过能力表现获得认可",
                "较少追求外部成就",
                "重视成就认可",
            ),
            _dimension(
                "power",
                "schwartz_power",
                "影响力",
                "资源、地位与社会影响",
                "较少追求支配",
                "重视影响与位置",
            ),
            _dimension(
                "security",
                "schwartz_security",
                "安全",
                "个人、关系与社会稳定",
                "容忍不确定",
                "重视稳定安全",
            ),
            _dimension(
                "conformity",
                "schwartz_conformity",
                "规则",
                "克制可能伤害规范的行为",
                "偏自主变通",
                "偏遵循规范",
            ),
            _dimension(
                "tradition",
                "schwartz_tradition",
                "传统",
                "尊重延续已久的习惯与文化",
                "偏重新解释传统",
                "偏维护传统",
            ),
            _dimension(
                "benevolence",
                "schwartz_benevolence",
                "善意",
                "维护熟悉群体的福祉",
                "偏个人边界",
                "偏照顾身边人",
            ),
            _dimension(
                "universalism",
                "schwartz_universalism",
                "普遍关怀",
                "理解、公平与保护广泛人群",
                "偏局部利益",
                "偏广泛关怀",
            ),
            _dimension(
                "hedonism",
                "schwartz_hedonism",
                "生活体验",
                "愉悦、舒适与感官体验",
                "较少追求即时体验",
                "重视愉悦体验",
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="moral_foundations",
        label="道德基础",
        reference="Moral Foundations Theory",
        description="表示不同道德线索被激活的敏感度，而非道德优劣。",
        dimensions=(
            _dimension(
                "care",
                "moral_care",
                "关怀 / 伤害",
                "对照顾与伤害线索的敏感度",
                "较低敏感",
                "高度敏感",
            ),
            _dimension(
                "fairness",
                "moral_fairness",
                "公平 / 欺骗",
                "对公平、互惠和欺骗线索的敏感度",
                "较低敏感",
                "高度敏感",
            ),
            _dimension(
                "loyalty",
                "moral_loyalty",
                "忠诚 / 背叛",
                "对群体归属与背叛线索的敏感度",
                "较低敏感",
                "高度敏感",
            ),
            _dimension(
                "authority",
                "moral_authority",
                "权威 / 颠覆",
                "对秩序、角色与权威线索的敏感度",
                "较低敏感",
                "高度敏感",
            ),
            _dimension(
                "purity",
                "moral_purity",
                "纯洁 / 污染",
                "对洁净、边界与污染线索的敏感度",
                "较低敏感",
                "高度敏感",
            ),
            _dimension(
                "liberty",
                "moral_liberty",
                "自由 / 压迫",
                "对自主与强制线索的敏感度",
                "较低敏感",
                "高度敏感",
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="risk_preferences",
        label="风险偏好",
        reference="Domain-specific synthetic risk vector",
        description="按领域区分风险容忍度；高分表示更愿意承受该领域不确定性。",
        dimensions=(
            _dimension(
                "general",
                "risk_preference",
                "总体风险容忍",
                "跨领域的风险接受倾向",
                "偏规避风险",
                "偏接受风险",
            ),
            _dimension(
                "financial",
                "risk_financial",
                "财务风险",
                "面对财务波动的容忍度",
                "偏财务保守",
                "偏财务冒险",
            ),
            _dimension(
                "social",
                "risk_social",
                "社交风险",
                "面对公开表达与关系摩擦的容忍度",
                "偏避免摩擦",
                "偏敢于表达",
            ),
            _dimension(
                "technology",
                "risk_technology",
                "技术风险",
                "尝试未充分验证技术的倾向",
                "偏等待验证",
                "偏先行尝试",
            ),
            _dimension(
                "health",
                "risk_health",
                "健康风险",
                "面对健康不确定性的容忍度",
                "偏健康谨慎",
                "偏接受风险",
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="cognitive_style",
        label="认知风格",
        reference="Synthetic bipolar cognitive-style axes",
        description="四条双极轴描述形成判断的偏好；中间值表示情境化使用两种方式。",
        dimensions=(
            _dimension(
                "analytical_intuitive",
                "cognitive_analytical_intuitive",
                "分析—直觉",
                "形成判断时依赖分析或直觉的相对倾向",
                "偏直觉",
                "偏分析",
                scale_min=-1,
                scale_max=1,
            ),
            _dimension(
                "independent_social",
                "cognitive_independent_social",
                "社会参照—独立判断",
                "形成判断时依赖社会线索或独立判断的相对倾向",
                "偏社会参照",
                "偏独立判断",
                scale_min=-1,
                scale_max=1,
            ),
            _dimension(
                "long_short_term",
                "cognitive_long_short_term",
                "短期—长期",
                "权衡即时与长期结果的相对倾向",
                "偏短期结果",
                "偏长期结果",
                scale_min=-1,
                scale_max=1,
            ),
            _dimension(
                "evidence_experience",
                "cognitive_evidence_experience",
                "经验—证据",
                "依赖个人经验或可核验证据的相对倾向",
                "偏个人经验",
                "偏可核证据",
                scale_min=-1,
                scale_max=1,
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="goals",
        label="目标系统",
        reference="Synthetic motivational goal vector",
        description="表示当前较稳定的目标优先级；主目标由最高分确定。",
        dimensions=tuple(
            _dimension(key, f"goal_{key}", label, description, "当前优先级较低", "当前优先级较高")
            for key, label, description in (
                ("security", "生活稳定", "保持稳定并降低不确定性"),
                ("achievement", "完成与认可", "完成有难度的目标并获得认可"),
                ("status", "位置与影响", "提升影响力与职业位置"),
                ("belonging", "关系与归属", "维持可信的人际连接与归属感"),
                ("growth", "学习与成长", "学习新能力并拓展选择空间"),
                ("meaning", "意义与贡献", "做对他人与社会有意义的事"),
                ("survival", "基本保障", "优先保障基本生活与安全"),
            )
        ),
    ),
    FrameworkDefinition(
        framework_id="beliefs",
        label="稳定信念",
        reference="Synthetic prior-belief vector",
        description="表示事件发生前的领域信念与判断置信度，可在推演中更新。",
        dimensions=(
            _dimension(
                "technology",
                "belief_technology",
                "技术接受",
                "对技术改善现实问题的先验信念",
                "偏怀疑",
                "偏接受",
            ),
            _dimension(
                "economic_outlook",
                "belief_economic_outlook",
                "经济预期",
                "对近期经济环境的先验判断",
                "偏谨慎",
                "偏乐观",
            ),
            _dimension(
                "brand_trust",
                "belief_brand_trust",
                "品牌信任",
                "对一般品牌承诺的先验信任",
                "偏怀疑",
                "偏信任",
            ),
            _dimension(
                "institutional_trust",
                "belief_institutional_trust",
                "机构信任",
                "对一般机构信息的先验信任",
                "偏怀疑",
                "偏信任",
            ),
            _dimension(
                "social_attitude",
                "belief_social_attitude",
                "社会合作",
                "对合作与公共行动的先验态度",
                "偏个人防御",
                "偏社会合作",
            ),
            _dimension(
                "confidence",
                "belief_confidence",
                "判断置信",
                "对自身当前判断的置信程度",
                "置信较低",
                "置信较高",
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="information_behavior",
        label="信息与行动倾向",
        reference="Synthetic media-and-action vector",
        description="描述接触、验证、表达和行动信息时的稳定倾向。",
        dimensions=(
            _dimension(
                "social_trust",
                "social_trust",
                "社会信任",
                "对一般社会关系的信任",
                "偏谨慎",
                "偏信任",
            ),
            _dimension(
                "institutional_trust",
                "institutional_trust",
                "机构信任",
                "对一般机构的信任",
                "偏谨慎",
                "偏信任",
            ),
            _dimension(
                "information_skepticism",
                "information_skepticism",
                "信息怀疑",
                "核验信息与质疑来源的倾向",
                "较少质疑",
                "偏主动核验",
            ),
            _dimension(
                "expression_tendency",
                "expression_tendency",
                "表达倾向",
                "公开或向关系网络表达观点的倾向",
                "偏保持沉默",
                "偏主动表达",
            ),
            _dimension(
                "action_tendency",
                "action_tendency",
                "行动倾向",
                "从态度转向实际行动的倾向",
                "偏观望",
                "偏行动",
            ),
            _dimension(
                "influence",
                "influence",
                "网络影响",
                "在合成关系网络中的潜在传播影响",
                "影响较弱",
                "影响较强",
            ),
        ),
    ),
    FrameworkDefinition(
        framework_id="media_channels",
        label="信息渠道偏好",
        reference="Synthetic channel-affinity simplex",
        description="五类信息渠道的相对使用权重，分数总和约为 1。",
        dimensions=tuple(
            _dimension(key, f"channel_{key}", label, description, "使用较少", "使用较多")
            for key, label, description in (
                ("social_media", "社交媒体", "通过内容平台与社交网络获取信息"),
                ("news", "新闻媒体", "通过专业新闻与资讯渠道获取信息"),
                ("interpersonal", "熟人交流", "通过朋友、同事与家人获取信息"),
                ("community", "社区渠道", "通过组织、社区和线下渠道获取信息"),
                ("search", "主动搜索", "通过主动检索补充与核验信息"),
            )
        ),
    ),
)


GROUP_FIELD_LABELS = {
    "age_group": "年龄",
    "gender": "性别",
    "social_role": "社会角色",
    "organization_type": "单位类型",
    "education_level": "教育背景",
    "region_type": "居住区域",
    "household_type": "家庭结构",
    "primary_channel": "主要信息渠道",
}

GROUP_VALUE_LABELS = {
    "gender": {
        "female": "女性",
        "male": "男性",
        "non_binary": "非二元性别",
        "undisclosed": "未披露",
    },
    "social_role": {
        "student": "高校学生",
        "professional": "专业从业者",
        "service_worker": "服务业从业者",
        "skilled_worker": "技术工人",
        "caregiver": "家庭照护者",
        "self_employed": "个体经营者",
        "retired": "退休居民",
        "job_seeker": "求职者",
    },
    "organization_type": {
        "higher_education": "高校与科研机构",
        "professional_services": "专业服务机构",
        "technology": "科技与研发企业",
        "public_service": "公共服务机构",
        "consumer_services": "生活服务企业",
        "manufacturing": "制造与技术服务企业",
        "household_community": "家庭与社区网络",
        "small_business": "个体与小微经营",
        "retired_community": "退休与社区网络",
        "employment_services": "就业服务网络",
    },
    "education_level": {
        "secondary_or_below": "高中及以下",
        "vocational": "职业教育",
        "undergraduate": "本科",
        "postgraduate": "研究生及以上",
    },
    "region_type": {
        "urban_core": "城市核心区",
        "suburban": "城市近郊",
        "town": "城镇",
        "rural": "乡村",
    },
    "household_type": {
        "single": "单人居住",
        "couple": "伴侣家庭",
        "with_children": "有子女家庭",
        "multigenerational": "多代家庭",
        "shared": "合租家庭",
    },
    "primary_channel": {
        "social_media": "社交媒体",
        "news": "新闻媒体",
        "interpersonal": "熟人交流",
        "community": "社区渠道",
        "search": "主动搜索",
    },
}


ORGANIZATION_TYPE_OPTIONS = {
    "student": ("higher_education",),
    "professional": ("professional_services", "technology", "public_service"),
    "service_worker": ("consumer_services", "public_service"),
    "skilled_worker": ("manufacturing", "technology"),
    "caregiver": ("household_community",),
    "self_employed": ("small_business",),
    "retired": ("retired_community",),
    "job_seeker": ("employment_services",),
}


def organization_type_for(role: str, index: int) -> str:
    options = ORGANIZATION_TYPE_OPTIONS.get(role, ("public_service",))
    return options[index % len(options)]


def group_field_label(field: str) -> str:
    return GROUP_FIELD_LABELS.get(field, field)


def group_value_label(field: str, value: str) -> str:
    return GROUP_VALUE_LABELS.get(field, {}).get(value, value)


__all__ = [
    "GROUP_FIELD_LABELS",
    "GROUP_VALUE_LABELS",
    "PERSONA_DEFINITION_VERSION",
    "PERSONA_FRAMEWORKS",
    "DimensionDefinition",
    "FrameworkDefinition",
    "group_field_label",
    "group_value_label",
    "organization_type_for",
]
