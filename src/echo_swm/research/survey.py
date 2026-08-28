from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

from echo_swm.personas.definitions import (
    PERSONA_FRAMEWORKS,
    group_field_label,
    group_value_label,
)
from echo_swm.research.calibration import (
    CalibrationProfile,
    calibrate_probability_matrix,
)
from echo_swm.research.contracts import (
    AgentTier,
    CrossTabRow,
    GroupDifference,
    OpenTheme,
    OptionEstimate,
    ParticipantReceipt,
    ProbabilityBand,
    QuestionCrossTab,
    QuestionForecast,
    QuestionKind,
    Questionnaire,
    QuestionOption,
    QuestionSnapshot,
    RepresentativeResponse,
    ResearchQuestion,
)
from echo_swm.research.population import ResearchPopulation
from echo_swm.research.runtime import ACTIONS, AgentState, RuntimeBundle, ScenarioRun

SUPPORTED_CONSTRUCTS = {
    "awareness",
    "support",
    "trust",
    "risk",
    "emotion",
    "participation",
    "sharing",
    "confidence",
    "fairness",
    "personal_impact",
    "general_attitude",
}

_DIMENSION_LABELS = {
    dimension.field: dimension.label
    for framework in PERSONA_FRAMEWORKS
    for dimension in framework.dimensions
}


@dataclass(frozen=True)
class SurveyForecastBundle:
    forecasts: list[QuestionForecast]
    individual_predictions: pa.Table
    group_insights: list[str]
    key_drivers: list[str]
    participant_receipts: list[ParticipantReceipt]


def _column(population: ResearchPopulation, name: str) -> NDArray[np.float64]:
    return np.asarray(population.agents[name], dtype=float)


def _latent(
    population: ResearchPopulation,
    state: AgentState,
    construct: str,
) -> NDArray[np.float64]:
    if construct == "awareness":
        value = 2 * state.awareness - 1
    elif construct in {"support", "general_attitude"}:
        value = state.support
    elif construct == "trust":
        value = 2 * state.trust - 1
    elif construct == "risk":
        value = 2 * state.risk - 1
    elif construct == "emotion":
        value = state.emotion
    elif construct == "participation":
        value = 2 * (0.55 * state.action_readiness + 0.45 * state.awareness) - 1
    elif construct == "sharing":
        value = 2 * (0.58 * _column(population, "expression_tendency") + 0.42 * state.awareness) - 1
    elif construct == "confidence":
        value = 2 * (np.abs(state.support) * (0.4 + 0.6 * state.belief)) - 1
    elif construct == "fairness":
        value = np.clip(
            0.52 * state.support + 0.48 * (2 * _column(population, "value_fairness") - 1),
            -1,
            1,
        )
    elif construct == "personal_impact":
        value = np.clip(
            0.48 * state.support
            + 0.28 * state.emotion
            + 0.24 * (2 * _column(population, "value_security") - 1),
            -1,
            1,
        )
    else:
        value = state.support
    return np.clip(value, -1, 1)


def _question_options(question: ResearchQuestion) -> list[QuestionOption]:
    if question.kind != QuestionKind.SCALE:
        return question.options
    low = int(question.scale_min if question.scale_min is not None else 1)
    high = int(question.scale_max if question.scale_max is not None else 5)
    return [
        QuestionOption(
            option_id=str(value),
            label=str(value),
            position=-1 + 2 * (value - low) / max(1, high - low),
        )
        for value in range(low, high + 1)
    ]


def _option_positions(options: list[QuestionOption]) -> NDArray[np.float64]:
    if all(item.position is not None for item in options):
        return np.asarray([float(cast(float, item.position)) for item in options], dtype=float)
    return np.linspace(-1, 1, len(options)).astype(np.float64)


def _stable_option_bias(
    question_id: str,
    option_id: str,
    size: int,
) -> NDArray[np.float64]:
    digest = hashlib.sha256(f"{question_id}:{option_id}".encode()).digest()
    frequency = 0.004 + int.from_bytes(digest[:2], "big") / 65_535 * 0.017
    phase = int.from_bytes(digest[2:4], "big") / 65_535 * 2 * np.pi
    return 0.055 * np.sin(np.arange(size) * frequency + phase)


def _option_probabilities(
    question: ResearchQuestion,
    latent: NDArray[np.float64],
    calibration: CalibrationProfile | None,
) -> tuple[list[QuestionOption], NDArray[np.float64]]:
    options = _question_options(question)
    positions = _option_positions(options) * question.direction
    scores = np.column_stack(
        [
            -((latent - position) ** 2) / 0.29
            + _stable_option_bias(question.question_id, option.option_id, latent.size)
            for option, position in zip(options, positions, strict=True)
        ]
    )
    if question.kind == QuestionKind.MULTIPLE_CHOICE:
        probabilities = 1 / (1 + np.exp(-(scores + 0.35)))
    else:
        scores -= scores.max(axis=1, keepdims=True)
        exponential = np.exp(scores)
        probabilities = exponential / exponential.sum(axis=1, keepdims=True)
    probabilities = calibrate_probability_matrix(
        probabilities,
        question_id=question.question_id,
        construct_name=question.latent_construct,
        option_ids=[item.option_id for item in options],
        profile=calibration,
        normalize=question.kind != QuestionKind.MULTIPLE_CHOICE,
    )
    return options, probabilities


def _band(values: NDArray[np.float64], effective_n: float) -> ProbabilityBand:
    values = np.asarray(values, dtype=float)
    median = float(np.median(values))
    if values.size == 1:
        standard_error = np.sqrt(max(1e-9, median * (1 - median)) / max(1, effective_n))
        lower = median - 1.282 * standard_error
        upper = median + 1.282 * standard_error
    else:
        lower, upper = np.quantile(values, [0.1, 0.9])
        sampling_error = np.sqrt(max(1e-9, median * (1 - median)) / max(1, effective_n))
        lower -= 0.35 * sampling_error
        upper += 0.35 * sampling_error
    return ProbabilityBand(
        p10=float(np.clip(lower, 0, 1)),
        p50=float(np.clip(median, 0, 1)),
        p90=float(np.clip(upper, 0, 1)),
    )


def _numeric_band(values: NDArray[np.float64]) -> ProbabilityBand:
    values = np.asarray(values, dtype=float)
    if values.size == 1:
        spread = max(0.01, abs(float(values[0])) * 0.015)
        quantiles = [float(values[0]) - spread, float(values[0]), float(values[0]) + spread]
    else:
        quantiles = np.quantile(values, [0.1, 0.5, 0.9]).tolist()
    return ProbabilityBand(p10=quantiles[0], p50=quantiles[1], p90=quantiles[2])


def _snapshot_options(
    phase: str,
    question: ResearchQuestion,
    states: list[AgentState],
    population: ResearchPopulation,
    calibration: CalibrationProfile | None,
) -> tuple[QuestionSnapshot, list[NDArray[np.float64]]]:
    weights = _column(population, "survey_weight")
    weights = weights / weights.sum()
    effective_n = float(weights.sum() ** 2 / np.sum(weights**2))
    probability_paths: list[NDArray[np.float64]] = []
    options: list[QuestionOption] = []
    for state in states:
        options, probabilities = _option_probabilities(
            question,
            _latent(population, state, question.latent_construct),
            calibration,
        )
        probability_paths.append(probabilities)
    aggregate = np.stack([np.sum(weights[:, None] * item, axis=0) for item in probability_paths])
    medians = np.median(aggregate, axis=0)
    ranks = np.empty(len(options), dtype=int)
    ranks[np.argsort(-medians)] = np.arange(1, len(options) + 1)
    estimates = [
        OptionEstimate(
            option_id=option.option_id,
            label=option.label,
            probability=_band(aggregate[:, index], effective_n),
            predicted_rank=int(ranks[index]) if question.kind == QuestionKind.RANKING else None,
        )
        for index, option in enumerate(options)
    ]
    return QuestionSnapshot(phase=phase, options=estimates), probability_paths


def _numeric_snapshot(
    phase: str,
    question: ResearchQuestion,
    states: list[AgentState],
    population: ResearchPopulation,
) -> tuple[QuestionSnapshot, list[NDArray[np.float64]]]:
    low = float(cast(float, question.scale_min))
    high = float(cast(float, question.scale_max))
    weights = _column(population, "survey_weight")
    weights = weights / weights.sum()
    per_agent = [
        low + (high - low) * (_latent(population, state, question.latent_construct) + 1) / 2
        for state in states
    ]
    aggregates = np.asarray([np.sum(weights * values) for values in per_agent])
    return (
        QuestionSnapshot(phase=phase, numeric_value=_numeric_band(aggregates)),
        [values[:, None] for values in per_agent],
    )


def _theme_shares(
    state: AgentState,
    population: ResearchPopulation,
) -> tuple[NDArray[np.float64], list[str], list[str]]:
    weights = _column(population, "survey_weight")
    weights = weights / weights.sum()
    support = state.support
    masks = [support > 0.2, support < -0.2, np.abs(support) <= 0.2]
    shares = np.asarray([np.sum(weights * mask) for mask in masks])
    labels = ["倾向支持", "表达担忧或反对", "继续观察并等待信息"]
    answers = [
        "模拟回答：这与我重视的方向较一致，但仍需观察实际执行。",
        "模拟回答：我担心潜在风险和受影响方式，需要更具体的说明。",
        "模拟回答：现有信息不足，我会先观察他人的体验和后续证据。",
    ]
    return shares, labels, answers


def _open_snapshot(
    phase: str,
    states: list[AgentState],
    population: ResearchPopulation,
) -> tuple[QuestionSnapshot, list[NDArray[np.float64]]]:
    path_shares = []
    labels: list[str] = []
    answers: list[str] = []
    for state in states:
        shares, labels, answers = _theme_shares(state, population)
        path_shares.append(shares)
    matrix = np.stack(path_shares)
    weights = _column(population, "survey_weight")
    normalized_weights = weights / weights.sum()
    effective_n = float(1 / np.sum(normalized_weights**2))
    themes = [
        OpenTheme(
            theme=label,
            share=_band(matrix[:, index], effective_n),
            representative_answer=answers[index],
        )
        for index, label in enumerate(labels)
    ]
    per_agent = []
    for state in states:
        probabilities = np.column_stack(
            [
                (state.support > 0.2).astype(float),
                (state.support < -0.2).astype(float),
                (np.abs(state.support) <= 0.2).astype(float),
            ]
        )
        per_agent.append(probabilities)
    return QuestionSnapshot(phase=phase, themes=themes), per_agent


def _snapshot(
    phase: str,
    question: ResearchQuestion,
    states: list[AgentState],
    population: ResearchPopulation,
    calibration: CalibrationProfile | None,
) -> tuple[QuestionSnapshot, list[NDArray[np.float64]]]:
    if question.kind == QuestionKind.NUMERIC:
        return _numeric_snapshot(phase, question, states, population)
    if question.kind == QuestionKind.OPEN_TEXT:
        return _open_snapshot(phase, states, population)
    return _snapshot_options(phase, question, states, population, calibration)


def _leading_label(snapshot: QuestionSnapshot) -> tuple[str, float]:
    if snapshot.options:
        leading = max(snapshot.options, key=lambda item: item.probability.p50)
        return leading.label, leading.probability.p50
    if snapshot.themes:
        theme = max(snapshot.themes, key=lambda item: item.share.p50)
        return theme.theme, theme.share.p50
    if snapshot.numeric_value is not None:
        return f"{snapshot.numeric_value.p50:.2f}", snapshot.numeric_value.p50
    return "未确定", 0


def _group_differences(
    question: ResearchQuestion,
    snapshot: QuestionSnapshot,
    probability_paths: list[NDArray[np.float64]],
    population: ResearchPopulation,
    group_fields: list[str],
) -> list[GroupDifference]:
    overall_label, overall_probability = _leading_label(snapshot)
    if not probability_paths:
        return []
    probabilities = probability_paths[len(probability_paths) // 2]
    survey_weights = _column(population, "survey_weight")
    result: list[GroupDifference] = []
    for field in group_fields:
        if field not in population.agents.column_names:
            continue
        values = np.asarray(population.agents[field].to_pylist(), dtype=object)
        unique = np.unique(values)
        represented_mass = np.asarray(
            [survey_weights[values == group].sum() for group in unique],
            dtype=float,
        )
        top_groups = unique[np.argsort(-represented_mass)[:3]]
        for group in top_groups:
            mask = values == group
            group_weights = survey_weights[mask]
            group_weights = group_weights / group_weights.sum()
            if question.kind == QuestionKind.NUMERIC:
                group_probability = float(np.sum(group_weights * probabilities[mask, 0]))
                label = f"{group_probability:.2f}"
            else:
                group_average = np.sum(group_weights[:, None] * probabilities[mask], axis=0)
                option_index = int(np.argmax(group_average))
                if question.kind == QuestionKind.OPEN_TEXT:
                    labels = ["倾向支持", "表达担忧或反对", "继续观察并等待信息"]
                else:
                    labels = [item.label for item in _question_options(question)]
                label = labels[option_index]
                group_probability = float(group_average[option_index])
            result.append(
                GroupDifference(
                    group_field=field,
                    group_label=group_field_label(field),
                    group_value=str(group),
                    group_value_label=group_value_label(field, str(group)),
                    agent_count=int(mask.sum()),
                    represented_population=float(survey_weights[mask].sum()),
                    leading_answer=label,
                    probability=group_probability,
                    delta_vs_overall=group_probability - overall_probability,
                )
            )
    return sorted(result, key=lambda item: abs(item.delta_vs_overall), reverse=True)


def _response_labels(question: ResearchQuestion) -> list[str]:
    if question.kind == QuestionKind.OPEN_TEXT:
        return ["倾向支持", "表达担忧或反对", "继续观察并等待信息"]
    if question.kind == QuestionKind.NUMERIC:
        return ["预测均值"]
    return [item.label for item in _question_options(question)]


def _cross_tabs(
    question: ResearchQuestion,
    probability_paths: list[NDArray[np.float64]],
    population: ResearchPopulation,
    group_fields: list[str],
) -> list[QuestionCrossTab]:
    if not probability_paths:
        return []
    probabilities = probability_paths[len(probability_paths) // 2]
    survey_weights = _column(population, "survey_weight")
    total_weight = float(survey_weights.sum())
    labels = _response_labels(question)
    tables: list[QuestionCrossTab] = []
    for field in group_fields:
        if field not in population.agents.column_names:
            continue
        values = np.asarray(population.agents[field].to_pylist(), dtype=object)
        unique = np.unique(values)
        ordered = sorted(
            unique,
            key=lambda item: float(survey_weights[values == item].sum()),
            reverse=True,
        )
        rows: list[CrossTabRow] = []
        for group in ordered:
            mask = values == group
            group_weights = survey_weights[mask]
            represented_population = float(group_weights.sum())
            normalized = group_weights / represented_population
            averages = np.sum(normalized[:, None] * probabilities[mask], axis=0)
            distribution = {label: float(averages[index]) for index, label in enumerate(labels)}
            leading_answer = (
                f"{averages[0]:.2f}"
                if question.kind == QuestionKind.NUMERIC
                else labels[int(np.argmax(averages))]
            )
            rows.append(
                CrossTabRow(
                    group_value=str(group),
                    group_value_label=group_value_label(field, str(group)),
                    agent_count=int(mask.sum()),
                    represented_population=represented_population,
                    weighted_share=represented_population / total_weight,
                    response_distribution=distribution,
                    leading_answer=leading_answer,
                )
            )
        tables.append(
            QuestionCrossTab(
                group_field=field,
                group_label=group_field_label(field),
                response_type=(
                    "numeric_mean" if question.kind == QuestionKind.NUMERIC else "distribution"
                ),
                rows=rows,
            )
        )
    return tables


def _representative_responses(
    question: ResearchQuestion,
    probability_paths: list[NDArray[np.float64]],
    population: ResearchPopulation,
    limit: int = 3,
) -> list[RepresentativeResponse]:
    if not probability_paths:
        return []
    probabilities = probability_paths[len(probability_paths) // 2]
    labels = _response_labels(question)
    influence = _column(population, "influence")
    confidence = _column(population, "belief_confidence")
    selected: list[tuple[int, int]] = []
    if question.kind == QuestionKind.NUMERIC:
        values = probabilities[:, 0]
        for quantile in (0.2, 0.5, 0.8)[:limit]:
            target = float(np.quantile(values, quantile))
            available = np.ones(values.size, dtype=bool)
            if selected:
                available[[index for index, _ in selected]] = False
            distance = np.abs(values - target) + (~available) * 10
            selected.append((int(np.argmin(distance)), 0))
    else:
        survey_weights = _column(population, "survey_weight")
        aggregate = np.sum(survey_weights[:, None] * probabilities, axis=0)
        available_options = [
            int(option_index)
            for option_index in np.argsort(-aggregate)
            if aggregate[option_index] > 1e-9
        ][:limit]
        for option_index in available_options:
            score = probabilities[:, option_index] + 0.06 * influence + 0.03 * confidence
            if selected:
                score[[index for index, _ in selected]] = -1
            selected.append((int(np.argmax(score)), int(option_index)))

    agents = population.agents
    results: list[RepresentativeResponse] = []
    for index, response_index in selected:
        agent_id = str(agents["agent_id"][index].as_py())
        role_key = str(agents["social_role"][index].as_py())
        role = group_value_label("social_role", role_key)
        organization_key = str(agents["organization_type"][index].as_py())
        organization = group_value_label("organization_type", organization_key)
        channel_key = str(agents["primary_channel"][index].as_py())
        channel = group_value_label("primary_channel", channel_key)
        goal_key = str(agents["primary_goal"][index].as_py())
        goal_label = _DIMENSION_LABELS.get(f"goal_{goal_key}", goal_key)
        value_fields = [
            dimension.field
            for framework in PERSONA_FRAMEWORKS
            if framework.framework_id == "schwartz_values"
            for dimension in framework.dimensions
        ]
        value_field = max(
            value_fields,
            key=lambda field: float(agents[field][index].as_py()),
        )
        value_label = _DIMENSION_LABELS[value_field]
        predicted = (
            f"{float(probabilities[index, 0]):.2f}"
            if question.kind == QuestionKind.NUMERIC
            else labels[response_index]
        )
        age_group = str(agents["age_group"][index].as_py())
        region = group_value_label("region_type", str(agents["region_type"][index].as_py()))
        answer = (
            f"就“{question.text}”这个问题，我目前更接近“{predicted}”。"
            f"作为{role}，我会先看它是否影响我在“{goal_label}”上的安排，"
            f"也会特别留意是否符合我重视的“{value_label}”。"
            f"我通常通过{channel}补充和核验信息；在执行细节、来源可信度和身边人的实际反馈"
            "还不充分时，我不会把当前判断当成最终结论。"
        )
        results.append(
            RepresentativeResponse(
                persona_id=agent_id,
                persona_label=f"合成人格 {agent_id[-6:].upper()}",
                role=role,
                organization_type=organization,
                segment=f"{age_group} · {region}",
                predicted_answer=predicted,
                answer=answer,
                confidence=float(confidence[index]),
                represented_weight=float(agents["survey_weight"][index].as_py()),
                basis=[
                    f"主目标：{goal_label}",
                    f"首要价值：{value_label}",
                    f"主要渠道：{channel}",
                ],
            )
        )
    return results


_DRIVER_LABELS = {
    "openness": "开放性",
    "conscientiousness": "尽责性",
    "extraversion": "外向与表达倾向",
    "agreeableness": "合作倾向",
    "emotional_sensitivity": "情绪敏感度",
    "value_care": "关怀价值",
    "value_fairness": "公平价值",
    "value_security": "安全价值",
    "value_tradition": "传统价值",
    "value_autonomy": "自主价值",
    "value_community": "共同体价值",
    "social_trust": "社会信任",
    "institutional_trust": "机构信任",
    "information_skepticism": "信息怀疑度",
    "expression_tendency": "表达倾向",
    "action_tendency": "行动倾向",
}


def _drivers(population: ResearchPopulation, state: AgentState) -> list[str]:
    impacts: list[tuple[str, float]] = []
    weights = _column(population, "survey_weight")
    weights = weights / weights.sum()
    support_mean = float(np.sum(weights * state.support))
    support_centered = state.support - support_mean
    support_variance = float(np.sum(weights * np.square(support_centered)))
    for field, label in _DRIVER_LABELS.items():
        values = _column(population, field)
        value_centered = values - float(np.sum(weights * values))
        value_variance = float(np.sum(weights * np.square(value_centered)))
        if value_variance < 1e-12 or support_variance < 1e-12:
            correlation = 0.0
        else:
            covariance = float(np.sum(weights * value_centered * support_centered))
            correlation = covariance / np.sqrt(value_variance * support_variance)
        impacts.append((label, correlation))
    impacts.sort(key=lambda item: abs(item[1]), reverse=True)
    return [f"{label}（{'正向' if impact >= 0 else '负向'}关联）" for label, impact in impacts[:5]]


def _change_summary(baseline: QuestionSnapshot, post: QuestionSnapshot) -> str:
    baseline_label, baseline_value = _leading_label(baseline)
    post_label, post_value = _leading_label(post)
    delta = post_value - baseline_value
    if baseline_label == post_label:
        return f"主要答案仍为“{post_label}”，预测占比变化 {delta:+.1%}。"
    return f"主要答案由“{baseline_label}”转为“{post_label}”，后者预测占比 {post_value:.1%}。"


def _individual_rows(
    questionnaire: Questionnaire,
    population: ResearchPopulation,
    baseline_by_question: dict[str, NDArray[np.float64]],
    post_by_question: dict[str, NDArray[np.float64]],
) -> pa.Table:
    agent_ids = population.agents["agent_id"].to_pylist()
    tiers = population.agents["tier"].to_pylist()
    rows: list[dict[str, Any]] = []
    for question in questionnaire.questions:
        baseline = baseline_by_question[question.question_id]
        post = post_by_question[question.question_id]
        if question.kind == QuestionKind.OPEN_TEXT:
            labels = ["倾向支持", "表达担忧或反对", "继续观察并等待信息"]
        elif question.kind == QuestionKind.NUMERIC:
            labels = ["value"]
        else:
            labels = [item.option_id for item in _question_options(question)]
        for index, agent_id in enumerate(agent_ids):
            for phase, matrix in (("baseline", baseline), ("post_event", post)):
                values = [float(item) for item in matrix[index]]
                rows.append(
                    {
                        "agent_id": agent_id,
                        "tier": tiers[index],
                        "question_id": question.question_id,
                        "phase": phase,
                        "option_probabilities": json.dumps(
                            dict(zip(labels, values, strict=True)), sort_keys=True
                        ),
                    }
                )
    return pa.Table.from_pylist(rows)


def _receipts(
    population: ResearchPopulation,
    scenario: ScenarioRun,
    global_drivers: list[str],
    evidence_refs: list[str],
) -> list[ParticipantReceipt]:
    tiers = np.asarray(population.agents["tier"].to_pylist(), dtype=object)
    key_indices = np.flatnonzero(tiers == AgentTier.KEY.value)[:6]
    representative_indices = np.flatnonzero(tiers == AgentTier.REPRESENTATIVE.value)[:6]
    selected = np.concatenate([key_indices, representative_indices])
    state = scenario.final_states[len(scenario.final_states) // 2]
    actions = scenario.final_actions[len(scenario.final_actions) // 2]
    agent_ids = population.agents["agent_id"].to_pylist()
    segments = population.agents["segment"].to_pylist()
    receipts = []
    for index in selected:
        stance = (
            "支持"
            if state.support[index] > 0.2
            else "反对"
            if state.support[index] < -0.2
            else "观望"
        )
        receipts.append(
            ParticipantReceipt(
                agent_id=str(agent_ids[index]),
                tier=AgentTier(str(tiers[index])),
                segment=str(segments[index]),
                final_action=ACTIONS[int(actions[index])],
                response_summary=(
                    f"模拟参与者处于{stance}状态；事件知晓度 {state.awareness[index]:.0%}，"
                    f"信任状态 {state.trust[index]:.0%}。"
                ),
                top_drivers=global_drivers[:3],
                evidence_refs=evidence_refs,
                profile_origin="synthetic",
            )
        )
    return receipts


def forecast_questionnaire(
    questionnaire: Questionnaire,
    population: ResearchPopulation,
    runtime: RuntimeBundle,
    *,
    group_fields: list[str],
    calibration: CalibrationProfile | None = None,
) -> SurveyForecastBundle:
    primary_scenario = next(
        item for item in runtime.scenarios if item.scenario.scenario_id == "event_as_described"
    )
    baseline_states = [runtime.initial_state]
    post_states = primary_scenario.final_states
    forecasts: list[QuestionForecast] = []
    baseline_individual: dict[str, NDArray[np.float64]] = {}
    post_individual: dict[str, NDArray[np.float64]] = {}
    global_drivers = _drivers(
        population, primary_scenario.final_states[len(primary_scenario.final_states) // 2]
    )
    for question in questionnaire.questions:
        baseline, baseline_paths = _snapshot(
            "baseline", question, baseline_states, population, calibration
        )
        post, post_paths = _snapshot("post_event", question, post_states, population, calibration)
        baseline_individual[question.question_id] = baseline_paths[0]
        post_individual[question.question_id] = post_paths[len(post_paths) // 2]
        differences = _group_differences(question, post, post_paths, population, group_fields)
        lacks_positions = question.kind in {
            QuestionKind.SINGLE_CHOICE,
            QuestionKind.MULTIPLE_CHOICE,
            QuestionKind.RANKING,
        } and any(item.position is None for item in question.options)
        forecasts.append(
            QuestionForecast(
                question_id=question.question_id,
                question_text=question.text,
                kind=question.kind,
                baseline=baseline,
                post_event=post,
                change_summary=_change_summary(baseline, post),
                group_differences=differences,
                cross_tabs=_cross_tabs(
                    question,
                    post_paths,
                    population,
                    group_fields,
                ),
                representative_responses=_representative_responses(
                    question,
                    post_paths,
                    population,
                ),
                key_drivers=global_drivers[:4],
                missingness=0,
                out_of_distribution=(
                    question.latent_construct not in SUPPORTED_CONSTRUCTS
                    or lacks_positions
                    or runtime.interpretation.confidence == "low"
                ),
            )
        )
    all_differences = [item for forecast in forecasts for item in forecast.group_differences]
    strongest = sorted(all_differences, key=lambda item: abs(item.delta_vs_overall), reverse=True)
    group_insights = [
        (
            f"{item.group_label}中的“{item.group_value_label}”对“{item.leading_answer}”的预测占比"
            f"较总体 {item.delta_vs_overall:+.1%}（n={item.agent_count}）。"
        )
        for item in strongest[:5]
    ]
    return SurveyForecastBundle(
        forecasts=forecasts,
        individual_predictions=_individual_rows(
            questionnaire, population, baseline_individual, post_individual
        ),
        group_insights=group_insights,
        key_drivers=global_drivers,
        participant_receipts=_receipts(
            population,
            primary_scenario,
            global_drivers,
            runtime.evidence_refs,
        ),
    )
