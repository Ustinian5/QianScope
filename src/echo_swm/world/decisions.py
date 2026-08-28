from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

from echo_swm.core.ids import stable_hash
from echo_swm.personas.catalog import GIVEN_END, GIVEN_START, ROLE_LABELS, SURNAMES
from echo_swm.personas.definitions import group_value_label
from echo_swm.research.population import COGNITIVE_DIMENSIONS
from echo_swm.world.contracts import (
    DecisionOption,
    DecisionOptionResult,
    DecisionQuestion,
    DecisionRepresentative,
    DecisionRoundResult,
    IndependentDecisionReport,
    WorldEvent,
    WorldSimulationRequest,
)
from echo_swm.world.population import WorldPopulation

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
DecisionProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class DecisionRun:
    report: IndependentDecisionReport
    individual_decisions: pa.Table
    final_positions: FloatArray
    final_confidence: FloatArray


_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("price", ("价格", "涨价", "降价", "收费", "费用", "折扣", "优惠", "price", "cost")),
    ("risk", ("事故", "危机", "风险", "污染", "中断", "故障", "安全", "召回", "crisis", "risk")),
    ("technology", ("技术", "科技", "ai", "人工智能", "平台", "产品", "新品", "系统", "software")),
    ("policy", ("政策", "规定", "规则", "条例", "管理办法", "通知", "监管", "policy")),
    ("activity", ("活动", "招募", "开放日", "展览", "演出", "比赛", "报名", "邀请")),
    ("service", ("服务", "开放时间", "营业时间", "预约", "空间", "食堂", "交通", "课程")),
)

_CATEGORY_LABELS = {
    "price": "价格与成本变化",
    "risk": "风险与突发事件",
    "technology": "产品与技术变化",
    "policy": "规则与公共安排",
    "activity": "活动与参与机会",
    "service": "服务与日常安排",
    "generic": "通用社会事件",
}


def _column(population: WorldPopulation, name: str) -> FloatArray:
    return np.asarray(population.base.agents[name], dtype=float)


def _objects(population: WorldPopulation, name: str) -> NDArray[np.object_]:
    return np.asarray(population.base.agents[name].to_pylist(), dtype=object)


def _name_for_index(index: int) -> str:
    surname = SURNAMES[index % len(SURNAMES)]
    first = GIVEN_START[(index // len(SURNAMES)) % len(GIVEN_START)]
    second = GIVEN_END[(index // (len(SURNAMES) * len(GIVEN_START))) % len(GIVEN_END)]
    return f"{surname}{first}{second}"


def classify_event(event: WorldEvent) -> str:
    text = f"{event.title} {event.description}".casefold()
    scores = {
        category: sum(text.count(keyword) for keyword in keywords)
        for category, keywords in _CATEGORY_KEYWORDS
    }
    leading = max(scores, key=lambda item: scores[item])
    return leading if scores[leading] > 0 else "generic"


def _options(items: list[tuple[str, float]]) -> list[DecisionOption]:
    return [
        DecisionOption(option_id=f"o{index + 1}", label=label, position=position)
        for index, (label, position) in enumerate(items)
    ]


def _reaction_options(category: str) -> list[DecisionOption]:
    choices: dict[str, list[tuple[str, float]]] = {
        "price": [
            ("接受变化并继续使用", 0.9),
            ("比较实际成本后再决定", 0.35),
            ("暂时减少使用", -0.35),
            ("放弃或寻找替代", -0.9),
        ],
        "risk": [
            ("立即采取防护或退出", -0.95),
            ("要求处理并持续核验", -0.45),
            ("先观察权威证据", 0.05),
            ("接受现有说明并照常行动", 0.75),
        ],
        "technology": [
            ("立即尝试", 0.95),
            ("主动了解后再试", 0.5),
            ("等待更明确的信息", 0.0),
            ("继续使用原有方案", -0.5),
            ("明确拒绝", -0.95),
        ],
        "policy": [
            ("明确支持并配合", 0.9),
            ("有条件接受", 0.4),
            ("暂不表态", 0.0),
            ("提出异议", -0.5),
            ("明确反对", -0.95),
        ],
        "activity": [
            ("立即报名或参与", 0.95),
            ("先了解安排", 0.4),
            ("暂时观望", -0.05),
            ("不参与", -0.8),
        ],
        "service": [
            ("主动使用新安排", 0.9),
            ("看具体执行再决定", 0.3),
            ("维持原有习惯", -0.25),
            ("减少使用或退出", -0.9),
        ],
        "generic": [
            ("积极响应", 0.9),
            ("了解后再决定", 0.35),
            ("保持观望", -0.1),
            ("不响应", -0.75),
        ],
    }
    return _options(choices[category])


def _round_options(construct: str, category: str) -> list[DecisionOption]:
    if construct == "reaction":
        return _reaction_options(category)
    if construct == "evidence":
        if category == "risk":
            return _options(
                [
                    ("可核验的检测或处置结果", 0.75),
                    ("完整的时间线与责任说明", 0.35),
                    ("持续观察客观指标", 0.0),
                    ("现有信息不会改变判断", -0.65),
                ]
            )
        return _options(
            [
                ("查看可核验的实施细节", 0.8),
                ("比较成本与实际收益", 0.35),
                ("进行小范围亲自试用", 0.1),
                ("等待更长时间的数据", -0.25),
                ("当前没有继续了解的意愿", -0.85),
            ]
        )
    if construct == "action":
        return _options(
            [
                ("立即采取实际行动", 0.95),
                ("先做低成本尝试", 0.45),
                ("只继续关注", 0.05),
                ("维持原状", -0.35),
                ("主动回避或退出", -0.95),
            ]
        )
    if construct == "recommendation":
        return _options(
            [
                ("愿意明确推荐", 0.9),
                ("只在特定条件下推荐", 0.35),
                ("不主动推荐", -0.2),
                ("会明确劝阻", -0.9),
            ]
        )
    return _options(
        [
            ("保持原判断并继续行动", 0.85),
            ("保留态度但降低行动强度", 0.25),
            ("重新评估", -0.1),
            ("改变原判断", -0.65),
        ]
    )


def compile_questions(request: WorldSimulationRequest) -> tuple[str, list[DecisionQuestion]]:
    event = request.events[0]
    category = classify_event(event)
    if request.question_overrides:
        return category, request.question_overrides
    subject = event.title.strip().rstrip("。！？")[:80]
    constructs: tuple[
        Literal["reaction", "evidence", "action", "persistence", "recommendation"], ...
    ] = (
        "reaction",
        "evidence",
        "action",
        "persistence",
        "recommendation",
        "persistence",
        "action",
        "recommendation",
    )
    prompts = {
        "reaction": f"得知“{subject}”后，你当前最可能做出什么反应？",
        "evidence": f"围绕“{subject}”，什么样的下一步最符合你自己的判断方式？",
        "action": f"在不考虑他人选择的情况下，你会怎样实际应对“{subject}”？",
        "persistence": f"经过自己的复核后，你对“{subject}”的判断会如何变化？",
        "recommendation": f"基于你目前掌握的信息，你会怎样向他人表达对“{subject}”的看法？",
    }
    contexts = {
        "reaction": "初始信息已到达；本轮记录即时反应。",
        "evidence": "事件方补充了可核验的执行范围、时间和来源说明。",
        "action": "决策窗口已经开始；需要选择是否采取行动。",
        "persistence": "观察窗口推进；本轮只读取该 Agent 自己此前的判断。",
        "recommendation": "观察窗口接近结束；本轮评估表达与推荐意愿。",
    }
    questions = []
    for index in range(request.decision_rounds):
        construct = constructs[index]
        questions.append(
            DecisionQuestion(
                question_id=f"round_{index + 1}_{construct}",
                round_index=index + 1,
                prompt=prompts[construct],
                context=contexts[construct],
                construct=construct,
                options=_round_options(construct, category),
            )
        )
    return category, questions


def _semantic_polarity(event: WorldEvent, category: str) -> float:
    if abs(event.valence) >= 0.2:
        return float(event.valence)
    text = f"{event.title} {event.description}".casefold()
    positive = ("改善", "开放", "增加", "优惠", "成功", "便利", "支持", "提升", "免费")
    negative = ("事故", "危机", "涨价", "污染", "中断", "故障", "风险", "减少", "取消")
    lexical = sum(token in text for token in positive) - sum(token in text for token in negative)
    if lexical:
        return float(np.clip(lexical * 0.24, -0.8, 0.8))
    return -0.35 if category == "risk" else float(np.clip(event.valence, -0.25, 0.25))


def _event_latent(population: WorldPopulation, event: WorldEvent, category: str) -> FloatArray:
    openness = _column(population, "openness")
    conscientiousness = _column(population, "conscientiousness")
    extraversion = _column(population, "extraversion")
    agreeableness = _column(population, "agreeableness")
    skepticism = _column(population, "information_skepticism")
    social_attitude = _column(population, "belief_social_attitude")
    institutional = _column(population, "belief_institutional_trust")
    technology = _column(population, "belief_technology")
    economic = _column(population, "belief_economic_outlook")
    security = _column(population, "goal_security")
    growth = _column(population, "goal_growth")
    fairness = _column(population, "value_fairness")
    risk_financial = _column(population, "risk_financial")
    risk_technology = _column(population, "risk_technology")
    risk_health = _column(population, "risk_health")
    if category == "price":
        fit = (
            0.34 * economic
            + 0.28 * risk_financial
            + 0.2 * (1 - security)
            + 0.18 * conscientiousness
        )
    elif category == "risk":
        fit = (
            0.34 * risk_health
            + 0.25 * conscientiousness
            + 0.22 * institutional
            + 0.19 * (1 - skepticism)
        )
    elif category == "technology":
        fit = (
            0.31 * technology
            + 0.24 * openness
            + 0.2 * risk_technology
            + 0.15 * growth
            + 0.1 * (1 - skepticism)
        )
    elif category == "policy":
        fit = (
            0.3 * institutional
            + 0.24 * fairness
            + 0.2 * conscientiousness
            + 0.16 * agreeableness
            + 0.1 * (1 - skepticism)
        )
    elif category == "activity":
        fit = (
            0.3 * extraversion
            + 0.23 * openness
            + 0.2 * growth
            + 0.17 * social_attitude
            + 0.1 * agreeableness
        )
    elif category == "service":
        fit = (
            0.28 * social_attitude
            + 0.24 * fairness
            + 0.2 * conscientiousness
            + 0.16 * openness
            + 0.12 * institutional
        )
    else:
        fit = (
            0.24 * social_attitude
            + 0.2 * openness
            + 0.19 * conscientiousness
            + 0.18 * agreeableness
            + 0.19 * (1 - skepticism)
        )
    polarity = _semantic_polarity(event, category)
    event_signal = polarity * (0.45 + 0.55 * event.intensity) * (0.5 + 0.5 * event.credibility)
    centered_fit = 2 * fit - 1
    if category == "risk":
        # Higher protective capacity makes a negative risk event less acceptable, not more social.
        centered_fit = -np.abs(centered_fit) - 0.25 * security
    return np.clip(0.72 * centered_fit + 0.55 * event_signal, -1, 1)


def _round_latent(
    population: WorldPopulation,
    question: DecisionQuestion,
    event_latent: FloatArray,
    private_stance: FloatArray,
    private_confidence: FloatArray,
) -> FloatArray:
    analytical = (
        _column(
            population,
            f"cognitive_{COGNITIVE_DIMENSIONS[COGNITIVE_DIMENSIONS.index('analytical_intuitive')]}",
        )
        + 1
    ) / 2
    evidence = (
        _column(
            population,
            f"cognitive_{COGNITIVE_DIMENSIONS[COGNITIVE_DIMENSIONS.index('evidence_experience')]}",
        )
        + 1
    ) / 2
    action = _column(population, "action_tendency")
    expression = _column(population, "expression_tendency")
    conscientiousness = _column(population, "conscientiousness")
    if question.decision_construct == "reaction":
        latent = 0.82 * event_latent + 0.18 * private_stance
    elif question.decision_construct == "evidence":
        latent = 0.46 * private_stance + 0.24 * event_latent + 0.18 * evidence + 0.12 * analytical
    elif question.decision_construct == "action":
        latent = 0.58 * private_stance + 0.22 * event_latent + 0.28 * (2 * action - 1)
    elif question.decision_construct == "recommendation":
        latent = 0.66 * private_stance + 0.24 * (2 * expression - 1) + 0.1 * event_latent
    else:
        latent = 0.72 * private_stance + 0.18 * event_latent + 0.1 * (2 * conscientiousness - 1)
    return np.clip(latent * (0.82 + 0.18 * private_confidence), -1, 1)


def _stable_option_bias(agent_indices: IntArray, question_id: str, option_id: str) -> FloatArray:
    digest = int(stable_hash({"question": question_id, "option": option_id})[:8], 16)
    frequency = 0.006 + (digest % 1_000) / 100_000
    phase = ((digest // 1_000) % 6_283) / 1_000
    return 0.055 * np.sin(agent_indices * frequency + phase)


def _reason_codes(population: WorldPopulation, index: int) -> list[str]:
    candidates = [
        (float(population.base.agents["openness"][index].as_py()), "开放性"),
        (float(population.base.agents["conscientiousness"][index].as_py()), "尽责性"),
        (float(population.base.agents["goal_security"][index].as_py()), "安全目标"),
        (float(population.base.agents["goal_growth"][index].as_py()), "成长目标"),
        (float(population.base.agents["value_fairness"][index].as_py()), "公平价值"),
        (float(population.base.agents["information_skepticism"][index].as_py()), "信息审慎"),
        (float(population.base.agents["action_tendency"][index].as_py()), "行动倾向"),
    ]
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [label for _, label in candidates[:3]]


def _representatives(
    population: WorldPopulation,
    question: DecisionQuestion,
    choices: IntArray,
    confidence: FloatArray,
    weights: FloatArray,
) -> list[DecisionRepresentative]:
    roles = _objects(population, "social_role")
    segments = _objects(population, "segment")
    agent_ids = _objects(population, "agent_id")
    results: list[DecisionRepresentative] = []
    weighted_counts = np.asarray(
        [weights[choices == index].sum() for index in range(len(question.options))], dtype=float
    )
    observed = [int(index) for index in np.argsort(-weighted_counts) if weighted_counts[index] > 0]
    for option_index in observed[: min(5, len(question.options))]:
        candidates = np.flatnonzero(choices == option_index)
        median = float(np.median(confidence[candidates]))
        selected = int(candidates[np.argmin(np.abs(confidence[candidates] - median))])
        option = question.options[option_index]
        reason_codes = _reason_codes(population, selected)
        role_key = str(roles[selected])
        role = ROLE_LABELS.get(role_key, group_value_label("social_role", role_key))
        rationale = (
            f"我选择“{option.label}”。这更符合我当前的{reason_codes[0]}、"
            f"{reason_codes[1]}与{reason_codes[2]}；如果事件条件改变，我会重新独立判断。"
        )
        results.append(
            DecisionRepresentative(
                agent_id=str(agent_ids[selected]),
                name=_name_for_index(selected),
                role=role,
                segment=str(segments[selected]),
                round_index=question.round_index,
                choice=option.label,
                confidence=float(confidence[selected]),
                rationale=rationale,
                reason_codes=reason_codes,
                represented_weight=float(weights[selected]),
            )
        )
    return results


def _option_results(
    question: DecisionQuestion,
    choices: IntArray,
    weights: FloatArray,
) -> list[DecisionOptionResult]:
    total_weight = float(weights.sum())
    effective_n = float(total_weight**2 / np.sum(weights**2))
    results = []
    for option_index, option in enumerate(question.options):
        mask = choices == option_index
        represented = float(weights[mask].sum())
        share = represented / total_weight
        error = 1.96 * math.sqrt(max(1e-12, share * (1 - share)) / max(1.0, effective_n))
        results.append(
            DecisionOptionResult(
                option_id=option.option_id,
                label=option.label,
                agent_count=int(mask.sum()),
                represented_population=represented,
                share=share,
                ci_low=float(np.clip(share - error, 0, 1)),
                ci_high=float(np.clip(share + error, 0, 1)),
            )
        )
    return results


def run_independent_decisions(
    request: WorldSimulationRequest,
    population: WorldPopulation,
    *,
    progress_callback: DecisionProgressCallback | None = None,
    batch_size: int = 100,
) -> DecisionRun:
    """Run actual categorical decisions without graph or cross-agent inputs."""

    category, questions = compile_questions(request)
    event = request.events[0]
    size = population.size
    total_decisions = size * len(questions)
    weights = np.asarray(population.weights, dtype=float)
    agent_ids = _objects(population, "agent_id")
    roles = _objects(population, "social_role")
    segments = _objects(population, "segment")
    base_confidence = _column(population, "belief_confidence")
    private_confidence = np.clip(base_confidence.copy(), 0.08, 0.98)
    event_latent = _event_latent(population, event, category)
    private_stance = np.clip(0.35 * event_latent, -1, 1)
    previous_positions: FloatArray | None = None
    first_positions: FloatArray | None = None
    completed = 0
    rows: list[dict[str, Any]] = []
    round_results: list[DecisionRoundResult] = []
    rng = np.random.default_rng(request.seed + 708_311)

    for question in questions:
        positions = np.asarray([item.position for item in question.options], dtype=float)
        latent = _round_latent(
            population, question, event_latent, private_stance, private_confidence
        )
        choices = np.empty(size, dtype=np.int64)
        confidences = np.empty(size, dtype=float)
        stance_before = private_stance.copy()
        for start in range(0, size, batch_size):
            stop = min(size, start + batch_size)
            indices = np.arange(start, stop, dtype=np.int64)
            batch_latent = latent[start:stop]
            temperature = 0.44 + 0.42 * (1 - private_confidence[start:stop])
            logits = np.column_stack(
                [
                    -np.square(batch_latent - position) / temperature
                    + _stable_option_bias(indices, question.question_id, option.option_id)
                    for position, option in zip(positions, question.options, strict=True)
                ]
            )
            gumbel = -np.log(-np.log(np.clip(rng.random(logits.shape), 1e-12, 1 - 1e-12)))
            selected = np.argmax(logits + 0.75 * gumbel, axis=1).astype(np.int64)
            ordered = np.sort(logits, axis=1)
            margin = ordered[:, -1] - ordered[:, -2]
            selected_confidence = np.clip(
                0.34 + 0.38 * private_confidence[start:stop] + 0.22 * np.tanh(margin),
                0.05,
                0.99,
            )
            choices[start:stop] = selected
            confidences[start:stop] = selected_confidence
            completed += stop - start
            preview_index = stop - 1
            preview_option = question.options[int(selected[-1])]
            role_key = str(roles[preview_index])
            role_label = ROLE_LABELS.get(role_key, group_value_label("social_role", role_key))
            if progress_callback is not None:
                progress_callback(
                    {
                        "processed_decisions": completed,
                        "total_decisions": total_decisions,
                        "processed_agents": stop,
                        "total_agents": size,
                        "current_round": question.round_index,
                        "total_rounds": len(questions),
                        "question": question.prompt,
                        "preview": {
                            "round_index": question.round_index,
                            "total_rounds": len(questions),
                            "agent_id": str(agent_ids[preview_index]),
                            "name": _name_for_index(preview_index),
                            "role": role_label,
                            "question": question.prompt,
                            "choice": preview_option.label,
                            "confidence": float(selected_confidence[-1]),
                        },
                    }
                )

        chosen_positions = positions[choices]
        if first_positions is None:
            first_positions = chosen_positions.copy()
        changed = (
            None
            if previous_positions is None
            else np.abs(chosen_positions - previous_positions) >= 0.35
        )
        private_stance = np.clip(
            0.58 * private_stance + 0.34 * chosen_positions + 0.08 * event_latent,
            -1,
            1,
        )
        private_confidence = np.clip(0.68 * private_confidence + 0.32 * confidences, 0.05, 0.99)
        for index in range(size):
            option = question.options[int(choices[index])]
            reason_codes = _reason_codes(population, index)
            rows.append(
                {
                    "agent_id": str(agent_ids[index]),
                    "agent_name": _name_for_index(index),
                    "social_role": str(roles[index]),
                    "segment": str(segments[index]),
                    "round_index": question.round_index,
                    "question_id": question.question_id,
                    "question": question.prompt,
                    "option_id": option.option_id,
                    "choice": option.label,
                    "choice_position": float(option.position),
                    "confidence": float(confidences[index]),
                    "private_stance_before": float(stance_before[index]),
                    "private_stance_after": float(private_stance[index]),
                    "represented_weight": float(weights[index]),
                    "reason_codes": json.dumps(reason_codes, ensure_ascii=False),
                }
            )
        option_results = _option_results(question, choices, weights)
        shares = np.asarray([item.share for item in option_results], dtype=float)
        positive = shares[shares > 0]
        entropy = (
            float(-np.sum(positive * np.log(positive)) / np.log(len(shares)))
            if len(shares) > 1
            else 0.0
        )
        changed_share = None if changed is None else float(np.average(changed, weights=weights))
        round_results.append(
            DecisionRoundResult(
                round_index=question.round_index,
                question=question,
                options=option_results,
                agent_count=size,
                mean_confidence=float(np.average(confidences, weights=weights)),
                changed_from_previous_share=changed_share,
                response_entropy=float(np.clip(entropy, 0, 1)),
                representatives=_representatives(
                    population, question, choices, confidences, weights
                ),
            )
        )
        previous_positions = chosen_positions.copy()

    if first_positions is None or previous_positions is None:
        raise RuntimeError("decision engine produced no rounds")
    final_round = round_results[-1]
    leading = max(final_round.options, key=lambda item: item.share)
    changed_mind = float(
        np.average(np.abs(previous_positions - first_positions) >= 0.35, weights=weights)
    )
    mean_confidence = float(np.mean([item.mean_confidence for item in round_results]))
    signature_payload = {
        "mode": request.interaction_mode,
        "event": event.model_dump(mode="json"),
        "questions": [item.model_dump(mode="json") for item in questions],
        "choices": [
            {
                "round": item.round_index,
                "options": [
                    {"id": option.option_id, "count": option.agent_count, "share": option.share}
                    for option in item.options
                ],
            }
            for item in round_results
        ],
        "population_signature": population.personality_signature,
        "seed": request.seed,
    }
    report = IndependentDecisionReport(
        event_id=event.event_id,
        event_category=_CATEGORY_LABELS[category],
        agent_count=size,
        round_count=len(questions),
        total_decisions=total_decisions,
        completed_decisions=completed,
        rounds=round_results,
        final_leading_choice=leading.label,
        final_leading_share=leading.share,
        changed_mind_share=changed_mind,
        mean_confidence=mean_confidence,
        summary=[
            f"{size:,} 个 Agent 已完成 {len(questions)} 轮，共 {completed:,} 次真实分类决策。",
            f"末轮最多选择“{leading.label}”，加权占比 {leading.share:.1%}。",
            f"从首轮到末轮有 {changed_mind:.1%} 的 Agent 改变了反应位置。",
        ],
        methodology=[
            "每个 Agent 仅读取事件、自己的稳定人格和自己的上一轮状态。",
            "任何 Agent 的选项、比例或状态都不会作为另一个 Agent 的输入。",
            "所有占比均在个体决策完成后聚合；报告代表为本轮真实作答 Agent。",
            "结果是未校准的合成人格条件模拟，不是对真实个人的陈述。",
        ],
        deterministic_signature=stable_hash(signature_payload),
    )
    return DecisionRun(
        report=report,
        individual_decisions=pa.Table.from_pylist(rows),
        final_positions=previous_positions,
        final_confidence=private_confidence,
    )


__all__ = [
    "DecisionRun",
    "classify_event",
    "compile_questions",
    "run_independent_decisions",
]
