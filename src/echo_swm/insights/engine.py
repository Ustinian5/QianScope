from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.config import Settings
from echo_swm.core.ids import new_id, stable_hash
from echo_swm.insights.contracts import (
    InsightBar,
    InsightPopulationSummary,
    InsightProvenance,
    InsightQuote,
    InsightRunRequest,
    InsightRunResult,
    _parse_prices,
    _split_values,
)
from echo_swm.insights.llm import generate_insight_narrative
from echo_swm.research.population import ResearchPopulation

MODEL_VERSION = "social-insight-agents-v1"
DATA_VERSION = "stable-personality-population-v2"

FloatArray = NDArray[np.float64]
ObjectArray = NDArray[np.object_]

ROLE_LABELS = {
    "student": "学生",
    "professional": "专业人士",
    "service_worker": "服务业从业者",
    "skilled_worker": "技术工人",
    "caregiver": "照护者",
    "self_employed": "个体经营者",
    "retired": "退休居民",
    "job_seeker": "求职者",
}
CHANNEL_LABELS = {
    "social_media": "社交媒体",
    "news": "新闻媒体",
    "interpersonal": "熟人关系",
    "community": "社区渠道",
    "search": "主动搜索",
}


@dataclass(frozen=True)
class _ResultParts:
    title: str
    context: str
    metric_label: str
    metric_value: str
    metric_detail: str
    bars: list[InsightBar]
    notes: list[str]
    quotes: list[InsightQuote]


class _Agents:
    def __init__(self, population: ResearchPopulation) -> None:
        self.population = population
        self.size = population.agents.num_rows
        self._floats: dict[str, FloatArray] = {}
        self._objects: dict[str, ObjectArray] = {}

    def f(self, name: str) -> FloatArray:
        if name not in self._floats:
            values = self.population.agents[name].combine_chunks().to_numpy(zero_copy_only=False)
            self._floats[name] = np.asarray(values, dtype=float)
        return self._floats[name]

    def s(self, name: str) -> ObjectArray:
        if name not in self._objects:
            values = self.population.agents[name].to_pylist()
            self._objects[name] = np.asarray(values, dtype=object)
        return self._objects[name]


def _sigmoid(value: FloatArray) -> FloatArray:
    return 1 / (1 + np.exp(-np.clip(value, -30, 30)))


def _mean_percent(value: FloatArray) -> int:
    return int(np.clip(np.rint(float(np.mean(value)) * 100), 0, 100))


def _partition(values: list[FloatArray]) -> list[int]:
    means = np.asarray([max(0.0, float(np.mean(value))) for value in values], dtype=float)
    if float(means.sum()) <= 0:
        means = np.ones(len(values), dtype=float)
    raw = means / means.sum() * 100
    rounded = np.floor(raw).astype(int)
    remainder = 100 - int(rounded.sum())
    order = np.argsort(-(raw - rounded))
    rounded[order[:remainder]] += 1
    return [int(value) for value in rounded]


def _query_seed(request: InsightRunRequest, salt: str) -> int:
    digest = stable_hash(
        {
            "tool": request.tool,
            "fields": request.fields,
            "seed": request.seed,
            "salt": salt,
        }
    )
    return int(digest[:8], 16)


def _unit(request: InsightRunRequest, salt: str) -> float:
    return _query_seed(request, salt) / 0xFFFFFFFF


def _noise(request: InsightRunRequest, salt: str, size: int, scale: float = 0.18) -> FloatArray:
    return np.asarray(
        np.random.default_rng(_query_seed(request, salt)).normal(0, scale, size),
        dtype=float,
    )


def _has_any(text: str, terms: tuple[str, ...]) -> float:
    lowered = text.casefold()
    return 1.0 if any(term.casefold() in lowered for term in terms) else 0.0


def _translated(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)


def _segment_note(
    agents: _Agents,
    outcome: FloatArray,
    column: str,
    dimension_label: str,
    labels: dict[str, str] | None = None,
) -> str:
    groups = agents.s(column)
    summaries: list[tuple[str, float]] = []
    for value in np.unique(groups):
        indices = groups == value
        if int(np.sum(indices)) >= 30:
            summaries.append((str(value), float(np.mean(outcome[indices]))))
    summaries.sort(key=lambda item: item[1])
    if not summaries:
        return f"{dimension_label}暂无可报告的稳定分群差异。"
    low, high = summaries[0], summaries[-1]
    active_labels = labels or {}
    difference = max(0, round((high[1] - low[1]) * 100))
    return (
        f"{dimension_label}中，{_translated(high[0], active_labels)}比"
        f"{_translated(low[0], active_labels)}高 {difference} 个百分点。"
    )


def _representative_indices(agents: _Agents, score: FloatArray) -> list[int]:
    tiers = agents.s("tier")
    candidates = np.flatnonzero(tiers != "background")
    if candidates.size < 3:
        candidates = np.arange(agents.size)
    selected: list[int] = []
    candidate_scores = score[candidates]
    for quantile in (0.86, 0.52, 0.2):
        target = float(np.quantile(candidate_scores, quantile))
        order = candidates[np.argsort(np.abs(candidate_scores - target))]
        selected.append(next(int(index) for index in order if int(index) not in selected))
    return selected


def _quotes(
    agents: _Agents,
    score: FloatArray,
    messages: tuple[str, str, str],
) -> list[InsightQuote]:
    agent_ids = agents.s("agent_id")
    roles = agents.s("social_role")
    results: list[InsightQuote] = []
    for index, message in zip(_representative_indices(agents, score), messages, strict=True):
        agent_id = str(agent_ids[index])
        results.append(
            InsightQuote(
                agent_id=agent_id,
                name=f"人格 {agent_id[-6:].upper()}",
                role=_translated(str(roles[index]), ROLE_LABELS),
                quote=message,
            )
        )
    return results


def _population_detail(request: InsightRunRequest) -> str:
    return (
        f"{request.population_size:,} 个合成人格加权外推至 "
        f"{request.represented_population:,} 人 · 未经现实校准"
    )


def _marketing(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    event = request.fields["event"].strip()
    horizon = request.fields["horizon"].strip()
    horizon_factor = {"1天": -0.25, "3天": -0.05, "1周": 0.18, "1月": 0.35, "1学期": 0.48}.get(
        horizon, 0.05
    )
    reach = _sigmoid(
        -1.05
        + 1.25 * agents.f("channel_social_media")
        + 0.55 * agents.f("channel_interpersonal")
        + 0.7 * agents.f("influence")
        + 0.45 * agents.f("baseline_interest")
        - 0.55 * agents.f("information_skepticism")
        + horizon_factor
        + (_unit(request, "marketing-context") - 0.5) * 0.35
        + _noise(request, "marketing-reach", agents.size)
    )
    favorable = _sigmoid(
        -0.85
        + 1.15 * agents.f("belief_brand_trust")
        + 0.55 * agents.f("openness")
        + 0.45 * agents.f("action_tendency")
        - 0.65 * agents.f("information_skepticism")
        + _noise(request, "marketing-favorable", agents.size)
    )
    positive = reach * favorable
    observe = reach * (1 - favorable) * 0.72 + (1 - reach) * 0.2
    resist = (1 - reach) * 0.8 + reach * (1 - favorable) * 0.28
    distribution = _partition([positive, observe, resist])
    reach_percent = _mean_percent(reach)
    return _ResultParts(
        title="营销活动反应",
        context=f"{event} · {horizon}",
        metric_label="关系网络触达",
        metric_value=f"{reach_percent}%",
        metric_detail=(
            f"预计触达 {round(request.represented_population * reach_percent / 100):,} 人 · "
            f"{_population_detail(request)}"
        ),
        bars=[
            InsightBar(label="积极反应", value=distribution[0]),
            InsightBar(label="保持观望", value=distribution[1]),
            InsightBar(label="抵触或无感", value=distribution[2]),
        ],
        notes=[
            _segment_note(agents, reach, "primary_channel", "渠道分群", CHANNEL_LABELS),
            _segment_note(agents, favorable, "social_role", "职业分群", ROLE_LABELS),
            "首轮触达由媒体习惯、关系影响力与信息怀疑度共同决定。",
        ],
        quotes=_quotes(
            agents,
            favorable,
            (
                "这项活动和我的兴趣较匹配；如果细节可信，我愿意主动分享。",
                "我会先看实际体验和身边人的反馈，再决定是否参与。",
                "目前的信息不足以抵消我的疑虑，我更可能忽略这次传播。",
            ),
        ),
    )


def _trend(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    term = request.fields["term"].strip()
    horizon = request.fields["horizon"].strip()
    horizon_factor = {"1天": -0.25, "3天": -0.05, "1周": 0.15, "1月": 0.28, "1学期": 0.38}.get(
        horizon, 0.05
    )
    attention = _sigmoid(
        -1.25
        + 1.15 * agents.f("baseline_interest")
        + 0.75 * agents.f("channel_search")
        + 0.55 * agents.f("openness")
        + 0.35 * agents.f("expression_tendency")
        - 0.48 * agents.f("information_skepticism")
        + horizon_factor
        + (_unit(request, "trend-term") - 0.5) * 0.5
        + _noise(request, "trend-attention", agents.size)
    )
    passive = np.clip(attention * (0.62 + 0.22 * agents.f("channel_social_media")), 0, 1)
    discussion = np.clip(attention * agents.f("expression_tendency") * 0.78, 0, 1)
    score = _mean_percent(attention)
    status = "进入增长区间" if score >= 60 else "形成局部热度" if score >= 40 else "仍属早期信号"
    return _ResultParts(
        title="趋势探测",
        context=f"{term} · {horizon}",
        metric_label="关注度",
        metric_value=f"{score}/100",
        metric_detail=(
            f"{status} · 预计主动关注 {round(request.represented_population * score / 100):,} 人"
        ),
        bars=[
            InsightBar(label="主动关注", value=score),
            InsightBar(label="被动接触", value=_mean_percent(passive)),
            InsightBar(label="形成讨论", value=_mean_percent(discussion)),
        ],
        notes=[
            _segment_note(agents, attention, "age_group", "年龄分群"),
            _segment_note(agents, discussion, "primary_channel", "传播渠道", CHANNEL_LABELS),
            "关注度是基于稳定人格和渠道暴露的条件信号，不等同于真实搜索指数。",
        ],
        quotes=_quotes(
            agents,
            attention,
            (
                f"我已经在主动寻找“{term}”的更多信息，也愿意和同伴讨论。",
                f"我注意到了“{term}”，但要看到更具体的案例才会持续关注。",
                f"“{term}”目前和我的生活关联较弱，我不会专门搜索。",
            ),
        ),
    )


def _brand(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    brand = request.fields["brand"].strip()
    affinity = _sigmoid(
        -1.0
        + 1.55 * agents.f("belief_brand_trust")
        + 0.45 * agents.f("agreeableness")
        + 0.28 * agents.f("openness")
        - 0.8 * agents.f("information_skepticism")
        + (_unit(request, "brand-name") - 0.5) * 0.42
        + _noise(request, "brand-affinity", agents.size)
    )
    recommend = affinity * _sigmoid(
        -0.45 + 0.85 * agents.f("expression_tendency") + 0.65 * agents.f("social_trust")
    )
    negative = (1 - affinity) * _sigmoid(
        -0.3 + 0.9 * agents.f("information_skepticism") + 0.35 * agents.f("neuroticism")
    )
    neutral = np.clip(1 - recommend - negative, 0.02, 1)
    distribution = _partition([recommend, neutral, negative])
    nps = distribution[0] - distribution[2]
    return _ResultParts(
        title="品牌印象",
        context=brand,
        metric_label="模拟 NPS",
        metric_value=f"{nps:+d}",
        metric_detail=_population_detail(request),
        bars=[
            InsightBar(label="推荐者", value=distribution[0]),
            InsightBar(label="中立者", value=distribution[1]),
            InsightBar(label="贬损者", value=distribution[2]),
        ],
        notes=[
            _segment_note(agents, affinity, "social_role", "职业分群", ROLE_LABELS),
            _segment_note(agents, recommend, "primary_channel", "渠道分群", CHANNEL_LABELS),
            "高频条件印象：可信、专业、克制，同时仍需要可验证的预测记录。",
        ],
        quotes=_quotes(
            agents,
            affinity,
            (
                f"{brand}给我的感觉比较专业；如果结果能被复核，我愿意推荐。",
                f"我对{brand}保持中立，先看它能否持续给出有用的结果。",
                f"我还不信任{brand}的预测能力，需要更多真实验证。",
            ),
        ),
    )


def _feature_score(
    request: InsightRunRequest,
    agents: _Agents,
    feature: str,
    index: int,
) -> FloatArray:
    rng = np.random.default_rng(_query_seed(request, f"feature-{index}-{feature}"))
    coefficients = np.asarray(rng.uniform(-0.35, 0.7, 5), dtype=float)
    matrix = np.column_stack(
        [
            agents.f("openness"),
            agents.f("conscientiousness"),
            agents.f("belief_technology"),
            agents.f("action_tendency"),
            1 - agents.f("information_skepticism"),
        ]
    )
    semantic = (
        0.22 * _has_any(feature, ("解释", "报告", "验证", "证据"))
        + 0.18 * _has_any(feature, ("导出", "数据", "接口", "api"))
        + 0.16 * _has_any(feature, ("快速", "开箱", "自动", "免安装"))
    )
    return _sigmoid(
        -0.45
        + 0.78 * np.mean(matrix, axis=1)
        + np.sum((matrix - 0.5) * coefficients, axis=1)
        + semantic
        + _noise(request, f"feature-noise-{index}", agents.size, 0.12)
    )


def _product(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    features = _split_values(request.fields["features"])
    scored = [
        (feature, _feature_score(request, agents, feature, index))
        for index, feature in enumerate(features)
    ]
    scored.sort(key=lambda item: float(np.mean(item[1])), reverse=True)
    leader, leader_score = scored[0]
    return _ResultParts(
        title="功能优先级",
        context=" · ".join(features),
        metric_label="参与投票",
        metric_value=f"{agents.size:,}",
        metric_detail=f"首选“{leader}” · {_population_detail(request)}",
        bars=[InsightBar(label=feature, value=_mean_percent(score)) for feature, score in scored],
        notes=[
            f"“{leader}”在当前目标人群中的条件偏好最高。",
            _segment_note(agents, leader_score, "social_role", "首选功能职业分群", ROLE_LABELS),
            "各功能独立评分，因此得票率不要求合计为 100%。",
        ],
        quotes=_quotes(
            agents,
            leader_score,
            (
                f"我最看重“{leader}”，它能直接减少完成任务的阻力。",
                f"“{leader}”有价值，但我还会比较使用频率和学习成本。",
                f"我暂时不会优先使用“{leader}”，它和我的当前目标关联较弱。",
            ),
        ),
    )


def _pricing(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    product = request.fields["product"].strip()
    audience = request.fields["audience"].strip()
    prices = _parse_prices(request.fields["prices"])
    low, high = min(prices), max(prices)
    span = max(high - low, max(low * 0.5, 1.0))
    affordability = np.clip(
        0.28 * agents.f("goal_achievement")
        + 0.25 * agents.f("belief_technology")
        + 0.2 * agents.f("risk_financial")
        + 0.17 * agents.f("conscientiousness")
        + 0.1 * agents.f("belief_brand_trust"),
        0,
        1,
    )
    willingness = low * 0.65 + (high + span * 0.25) * affordability
    demand_curves = [
        _sigmoid(
            (willingness - price) / max(span * 0.16, 1.0)
            + _noise(request, f"price-{price}", agents.size, 0.09)
        )
        for price in prices
    ]
    revenues = [
        price * float(np.mean(demand)) for price, demand in zip(prices, demand_curves, strict=True)
    ]
    best_index = int(np.argmax(revenues))
    best_price = prices[best_index]
    peak_revenue = max(revenues)
    bars = []
    for price, demand, revenue in zip(prices, demand_curves, revenues, strict=True):
        label = f"¥{price:g}"
        bars.append(
            InsightBar(
                label=label,
                value=_mean_percent(demand),
                detail=f"相对营收指数 {round(revenue / peak_revenue * 100)}",
            )
        )
    return _ResultParts(
        title="价格—需求曲线",
        context=f"{product} · {audience}",
        metric_label="建议测试价格",
        metric_value=f"¥{best_price:g}",
        metric_detail=f"当前价格点中的条件营收峰值 · {_population_detail(request)}",
        bars=bars,
        notes=[
            _segment_note(
                agents, demand_curves[best_index], "social_role", "职业分群", ROLE_LABELS
            ),
            f"¥{best_price:g} 在当前扫描范围内取得最高相对营收指数。",
            "结果未包含真实收入分布与历史成交数据，不能直接作为定价决策。",
        ],
        quotes=_quotes(
            agents,
            demand_curves[best_index],
            (
                f"如果{product}能稳定解决问题，¥{best_price:g}在我的接受范围内。",
                "我会比较使用频率、替代方案和实际效果，再判断是否付费。",
                "这个价格超出了我当前的使用价值，除非有更低频的方案。",
            ),
        ),
    )


def _competitive(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    brand = request.fields["brand"].strip()
    competitor = request.fields["competitor"].strip()
    action = request.fields["action"].strip()
    price_signal = _has_any(action, ("降价", "价格", "优惠", "免费", "补贴"))
    speed_signal = _has_any(action, ("更快", "提速", "实时", "效率"))
    feature_signal = _has_any(action, ("功能", "能力", "上线", "发布", "模型"))
    price_pressure = _sigmoid(
        -0.95
        + 1.05 * price_signal
        + 0.75 * (1 - agents.f("risk_financial"))
        + 0.35 * agents.f("information_skepticism")
        + _noise(request, "competitive-price", agents.size)
    )
    channel_pressure = _sigmoid(
        -0.75
        + 0.75 * agents.f("channel_social_media")
        + 0.65 * agents.f("expression_tendency")
        + 0.25 * speed_signal
        + (_unit(request, "competitive-channel") - 0.5) * 0.4
        + _noise(request, "competitive-channel-noise", agents.size)
    )
    substitution = _sigmoid(
        -1.0
        + 0.75 * feature_signal
        + 0.5 * speed_signal
        + 0.65 * agents.f("belief_technology")
        + 0.45 * agents.f("openness")
        - 0.5 * agents.f("belief_brand_trust")
        + _noise(request, "competitive-substitution", agents.size)
    )
    threat = np.mean(np.column_stack([price_pressure, channel_pressure, substitution]), axis=1)
    threat_value = _mean_percent(threat)
    level = "高" if threat_value >= 65 else "中" if threat_value >= 42 else "低"
    return _ResultParts(
        title="竞品反应",
        context=f"{competitor}：{action}",
        metric_label="威胁等级",
        metric_value=level,
        metric_detail=f"综合威胁指数 {threat_value}/100 · {_population_detail(request)}",
        bars=[
            InsightBar(label="价格压力", value=_mean_percent(price_pressure)),
            InsightBar(label="渠道声量", value=_mean_percent(channel_pressure)),
            InsightBar(label="功能替代", value=_mean_percent(substitution)),
        ],
        notes=[
            f"{brand}应优先守住最核心的可验证价值，而非跟随全部功能。",
            "将预测记录、误差和适用边界公开，建立可信差异。",
            _segment_note(agents, threat, "social_role", "受影响职业分群", ROLE_LABELS),
        ],
        quotes=_quotes(
            agents,
            threat,
            (
                f"{competitor}的动作会明显影响我的比较，我可能重新评估{brand}。",
                "我会同时比较价格、速度和结果是否可信，不会只看一个卖点。",
                f"我对{brand}已有稳定偏好，这次竞品动作暂时不会改变选择。",
            ),
        ),
    )


def _funnel(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    product = request.fields["product"].strip()
    channel = request.fields["channel"].strip()
    social_bonus = _has_any(channel, ("社交", "社区", "内容", "群")) * 0.18
    search_bonus = _has_any(channel, ("搜索", "seo", "检索")) * 0.16
    awareness = _sigmoid(
        -0.7
        + 1.0 * agents.f("channel_social_media")
        + 0.65 * agents.f("channel_search")
        + 0.45 * agents.f("influence")
        + social_bonus
        + search_bonus
        + _noise(request, "funnel-awareness", agents.size)
    )
    interest = awareness * _sigmoid(
        -0.35
        + 0.9 * agents.f("baseline_interest")
        + 0.65 * agents.f("openness")
        - 0.45 * agents.f("information_skepticism")
        + _noise(request, "funnel-interest", agents.size)
    )
    evaluation = interest * _sigmoid(
        -0.25
        + 0.8 * agents.f("cognitive_evidence_experience")
        + 0.75 * agents.f("conscientiousness")
        + 0.4 * agents.f("belief_brand_trust")
        + _noise(request, "funnel-evaluation", agents.size)
    )
    action = evaluation * _sigmoid(
        -0.15
        + 1.0 * agents.f("action_tendency")
        + 0.45 * agents.f("risk_technology")
        - 0.35 * agents.f("risk_financial")
        + _noise(request, "funnel-action", agents.size)
    )
    stages = [awareness, interest, evaluation, action]
    values = [_mean_percent(stage) for stage in stages]
    drops = [values[index] - values[index + 1] for index in range(3)]
    drop_labels = ["认知→兴趣", "兴趣→评估", "评估→行动"]
    largest_drop = int(np.argmax(drops))
    return _ResultParts(
        title="转化漏斗",
        context=f"{product} · {channel}",
        metric_label="最终行动",
        metric_value=f"{values[-1]}%",
        metric_detail=(
            f"约 {round(request.represented_population * values[-1] / 100):,} 人 · "
            f"{_population_detail(request)}"
        ),
        bars=[
            InsightBar(label="认知", value=values[0]),
            InsightBar(label="产生兴趣", value=values[1]),
            InsightBar(label="开始评估", value=values[2]),
            InsightBar(label="完成行动", value=values[3]),
        ],
        notes=[
            f"最大掉落发生在{drop_labels[largest_drop]}阶段，下降 {drops[largest_drop]} 个百分点。",
            _segment_note(agents, action, "primary_channel", "行动渠道分群", CHANNEL_LABELS),
            "降低首次理解成本并提供可复核案例，是当前条件下最直接的优化方向。",
        ],
        quotes=_quotes(
            agents,
            action,
            (
                "我已经理解它能解决什么问题，愿意完成第一次实际尝试。",
                "我有兴趣，但需要先比较案例、成本和操作复杂度。",
                "我在第一步就没有看懂它与我的关系，因此不会继续行动。",
            ),
        ),
    )


def _churn(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    change = request.fields["change"].strip()
    horizon = request.fields["horizon"].strip()
    price_signal = _has_any(change, ("涨价", "价格", "上调", "收费", "减少免费"))
    service_signal = _has_any(change, ("减少", "取消", "限制", "下降", "移除"))
    horizon_factor = {"1天": -0.2, "3天": -0.1, "1周": 0.0, "1月": 0.18, "1学期": 0.32}.get(
        horizon, 0.08
    )
    churn = _sigmoid(
        -1.6
        + 0.72 * price_signal
        + 0.62 * service_signal
        + 0.7 * (1 - agents.f("risk_financial"))
        + 0.48 * agents.f("information_skepticism")
        + 0.3 * agents.f("neuroticism")
        - 0.72 * agents.f("belief_brand_trust")
        - 0.38 * agents.f("conscientiousness")
        + horizon_factor
        + _noise(request, "churn", agents.size)
    )
    continue_use = 1 - churn
    reduce_use = churn * 0.58
    exit_use = churn * 0.42
    distribution = _partition([continue_use, reduce_use, exit_use])
    churn_percent = distribution[1] + distribution[2]
    return _ResultParts(
        title="流失预测",
        context=f"{change} · {horizon}",
        metric_label="预计受影响率",
        metric_value=f"{churn_percent}%",
        metric_detail=f"完全退出 {distribution[2]}% · {_population_detail(request)}",
        bars=[
            InsightBar(label="继续使用", value=distribution[0]),
            InsightBar(label="降低频率", value=distribution[1]),
            InsightBar(label="完全退出", value=distribution[2]),
        ],
        notes=[
            _segment_note(agents, churn, "social_role", "职业流失分群", ROLE_LABELS),
            _segment_note(agents, churn, "age_group", "年龄流失分群"),
            "保留历史项目、提供低用量档位并提前解释变化，可降低条件流失风险。",
        ],
        quotes=_quotes(
            agents,
            churn,
            (
                "这次变化明显削弱了使用价值，我会寻找替代方案。",
                "我可能降低频率，等真正有需要时再使用。",
                "目前的累积价值仍然足够，我会继续使用并观察后续变化。",
            ),
        ),
    )


def _creator(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    brief = request.fields["brief"].strip()
    platform = request.fields["platform"].strip()
    topic_match = _sigmoid(
        -0.55
        + 0.75 * agents.f("openness")
        + 0.55 * agents.f("belief_technology")
        + 0.35 * agents.f("cognitive_evidence_experience")
        + (_unit(request, "creator-topic") - 0.5) * 0.55
        + _noise(request, "creator-topic-noise", agents.size)
    )
    match = np.clip(
        0.35 * agents.f("influence")
        + 0.2 * agents.f("social_trust")
        + 0.25 * agents.f("expression_tendency")
        + 0.2 * topic_match,
        0,
        1,
    )
    top_indices = np.argsort(-match)[:24]
    professional = np.clip(
        0.5 * agents.f("conscientiousness") + 0.5 * agents.f("cognitive_evidence_experience"),
        0,
        1,
    )
    connector = np.clip(0.55 * agents.f("social_trust") + 0.45 * agents.f("value_community"), 0, 1)
    broadcaster = np.clip(
        0.55 * agents.f("influence") + 0.45 * agents.f("expression_tendency"), 0, 1
    )
    agent_ids = agents.s("agent_id")
    roles = agents.s("social_role")
    notes = []
    for rank, index in enumerate(top_indices[:3], start=1):
        notes.append(
            f"{rank}. 人格 {str(agent_ids[index])[-6:].upper()} · "
            f"{_translated(str(roles[index]), ROLE_LABELS)}："
            f"匹配度 {_mean_percent(match[index : index + 1])}%"
        )
    return _ResultParts(
        title="传播节点智配",
        context=f"{brief} · {platform}",
        metric_label="候选节点",
        metric_value="24",
        metric_detail=f"从 {agents.size:,} 个稳定人格中按信任、触达与主题匹配排序",
        bars=[
            InsightBar(label="专业解释型", value=_mean_percent(professional[top_indices])),
            InsightBar(label="圈层连接型", value=_mean_percent(connector[top_indices])),
            InsightBar(label="广域传播型", value=_mean_percent(broadcaster[top_indices])),
        ],
        notes=notes,
        quotes=_quotes(
            agents,
            match,
            (
                "这个议题与我的专业和受众高度匹配，我愿意做深入解释。",
                "我可以把信息带进几个相邻圈层，但需要清楚的证据材料。",
                "主题相关度有限；即使触达较高，也不适合由我主导传播。",
            ),
        ),
    )


def _build_parts(request: InsightRunRequest, agents: _Agents) -> _ResultParts:
    if request.tool == "marketing":
        return _marketing(request, agents)
    if request.tool == "trend":
        return _trend(request, agents)
    if request.tool == "brand":
        return _brand(request, agents)
    if request.tool == "product":
        return _product(request, agents)
    if request.tool == "pricing":
        return _pricing(request, agents)
    if request.tool == "competitive":
        return _competitive(request, agents)
    if request.tool == "funnel":
        return _funnel(request, agents)
    if request.tool == "churn":
        return _churn(request, agents)
    return _creator(request, agents)


def insight_artifact_root(settings: Settings) -> Path:
    return settings.artifact_dir / "insights" / "runs"


def run_insight(
    request: InsightRunRequest,
    population: ResearchPopulation,
    settings: Settings,
) -> InsightRunResult:
    if population.agents.num_rows != request.population_size:
        raise ValueError("insight population size does not match the request")
    parts = _build_parts(request, _Agents(population))
    ai_execution = []
    if settings.llm_configured:
        llm = OpenAICompatibleLLM(settings)
        narrative = generate_insight_narrative(
            request,
            {
                "title": parts.title,
                "context": parts.context,
                "metric_label": parts.metric_label,
                "metric_value": parts.metric_value,
                "metric_detail": parts.metric_detail,
                "bars": [item.model_dump(mode="json") for item in parts.bars],
                "notes": parts.notes,
                "quotes": [item.model_dump(mode="json") for item in parts.quotes],
            },
            llm,
        )
        quote_lookup = {item.agent_id: item.quote for item in narrative.quote_rewrites}
        parts = replace(
            parts,
            title=narrative.title,
            context=narrative.context,
            metric_detail=narrative.metric_detail,
            notes=narrative.notes,
            quotes=[
                item.model_copy(update={"quote": quote_lookup.get(item.agent_id, item.quote)})
                for item in parts.quotes
            ],
        )
        if llm.last_execution is not None:
            ai_execution.append(llm.last_execution)
    result = InsightRunResult(
        run_id=new_id("insight"),
        tool=request.tool,
        input_fields=request.fields,
        title=parts.title,
        context=parts.context,
        metric_label=parts.metric_label,
        metric_value=parts.metric_value,
        metric_detail=parts.metric_detail,
        bars=parts.bars,
        notes=parts.notes,
        quotes=parts.quotes,
        population=InsightPopulationSummary(
            agent_count=population.agents.num_rows,
            represented_population=request.represented_population,
        ),
        provenance=InsightProvenance(
            model_version=MODEL_VERSION,
            data_version=DATA_VERSION,
            grounding_status="synthetic_unanchored",
            ai_execution=ai_execution,
            limitations=[
                "The agents are synthetic personas and are not identifiable real people.",
                "The result has not been calibrated against observed outcomes for this query.",
                (
                    "Text-specific effects use deterministic conditional signals, "
                    "not live public data."
                ),
            ],
        ),
    )
    directory = insight_artifact_root(settings) / result.run_id
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "request.json").write_text(request.model_dump_json(indent=2), encoding="utf-8")
    (directory / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def load_insight_result(run_id: str, settings: Settings) -> InsightRunResult:
    root = insight_artifact_root(settings).resolve()
    path = (root / run_id / "result.json").resolve()
    if not path.is_relative_to(root) or not path.exists():
        raise FileNotFoundError(f"insight run not found: {run_id}")
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return InsightRunResult.model_validate(payload)


__all__ = [
    "DATA_VERSION",
    "MODEL_VERSION",
    "insight_artifact_root",
    "load_insight_result",
    "run_insight",
]
