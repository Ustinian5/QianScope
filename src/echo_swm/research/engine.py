from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyarrow.parquet as pq
from numpy.typing import NDArray

from echo_swm import DISCLAIMER
from echo_swm.core.config import Settings
from echo_swm.core.ids import file_hash, new_id, stable_hash
from echo_swm.population.weighting import effective_sample_size
from echo_swm.research.calibration import (
    CalibrationObservation,
    CalibrationProfile,
    CalibrationStatus,
    CalibrationTargetType,
    append_backfill_observations,
    calibrate_event_probabilities,
    load_calibration_profile,
)
from echo_swm.research.contracts import (
    CalibrationRunSummary,
    ConstrainedL2Evaluation,
    CounterfactualEffect,
    DownstreamOutcome,
    EvaluationMetric,
    EventScenario,
    GroundingRunSummary,
    MetricDirection,
    OutcomeSubmission,
    PopulationRunSummary,
    PredictionArtifacts,
    PredictionRequest,
    PredictionResult,
    ProbabilityBand,
    ProtocolLock,
    QuestionKind,
    Questionnaire,
    ReportQualityCheck,
    ReportQualitySummary,
    ReportRunMetadata,
    ScenarioForecast,
    ScenarioRanking,
    TimelinePoint,
)
from echo_swm.research.grounding import (
    PopulationGroundingReport,
    apply_population_margins,
    load_margin_dataset,
)
from echo_swm.research.population import (
    ResearchPopulation,
    generate_population,
    load_population,
    validate_population,
)
from echo_swm.research.runtime import RuntimeBundle, ScenarioRun, simulate_population
from echo_swm.research.semantics import interpret_event
from echo_swm.research.survey import SurveyForecastBundle, forecast_questionnaire

MODEL_VERSION = "questionnaire-event-swm-v3"
DATA_VERSION = "stable-synthetic-personality-v2"


def research_root(settings: Settings) -> Path:
    return settings.artifact_dir / "research"


def questionnaire_root(settings: Settings) -> Path:
    return research_root(settings) / "questionnaires"


def prediction_root(settings: Settings) -> Path:
    return research_root(settings) / "predictions"


def save_questionnaire(questionnaire: Questionnaire, settings: Settings) -> Path:
    directory = questionnaire_root(settings)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{questionnaire.questionnaire_id}.json"
    path.write_text(questionnaire.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_questionnaire(questionnaire_id: str, settings: Settings) -> Questionnaire:
    path = questionnaire_root(settings) / f"{questionnaire_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"questionnaire not found: {questionnaire_id}")
    return Questionnaire.model_validate_json(path.read_text(encoding="utf-8"))


def _resolve_population(
    request: PredictionRequest, settings: Settings
) -> tuple[ResearchPopulation, PopulationGroundingReport | None]:
    if request.population is not None:
        population = generate_population(request.population, settings, persist=True)
    else:
        if request.population_id is None:
            raise ValueError("population reference is missing")
        population = load_population(request.population_id, settings)
    if request.population_margin_id is None:
        return population, None
    margin_dataset = load_margin_dataset(request.population_margin_id, settings)
    # The registered synthetic population remains immutable. Raked weights belong
    # to this prediction only and are captured in its manifest/signature.
    return apply_population_margins(population, margin_dataset, settings, persist=False)


def _resolve_calibration(
    request: PredictionRequest, settings: Settings
) -> CalibrationProfile | None:
    if request.calibration_id is None:
        return None
    return load_calibration_profile(request.calibration_id, settings)


def _resolve_questionnaire(request: PredictionRequest, settings: Settings) -> Questionnaire:
    if request.questionnaire is not None:
        save_questionnaire(request.questionnaire, settings)
        return request.questionnaire
    if request.questionnaire_id is None:
        raise ValueError("questionnaire reference is missing")
    return load_questionnaire(request.questionnaire_id, settings)


def _probability_band(values: NDArray[np.float64]) -> ProbabilityBand:
    lower, median, upper = np.quantile(values, [0.1, 0.5, 0.9])
    return ProbabilityBand(p10=float(lower), p50=float(median), p90=float(upper))


def _timeline(run: ScenarioRun, metric_names: tuple[str, ...]) -> list[TimelinePoint]:
    points = []
    for tick in range(run.timeline.shape[1]):
        points.append(
            TimelinePoint(
                tick=tick,
                metrics={
                    name: _probability_band(run.timeline[:, tick, index])
                    for index, name in enumerate(metric_names)
                },
            )
        )
    return points


def _crossing_ticks(
    values: NDArray[np.float64],
    threshold: float,
    horizon: int,
) -> NDArray[np.float64]:
    result = np.full(values.shape[0], horizon, dtype=float)
    for path_index, path in enumerate(values):
        crossings = np.flatnonzero(path >= threshold)
        if crossings.size:
            result[path_index] = float(crossings[0])
    return result


def _downstream_outcomes(
    run: ScenarioRun,
    metric_names: tuple[str, ...],
    calibration: CalibrationProfile | None,
) -> list[DownstreamOutcome]:
    index = {name: position for position, name in enumerate(metric_names)}
    awareness = run.timeline[:, :, index["awareness"]]
    discussion = run.timeline[:, :, index["discussion"]]
    polarization = run.timeline[:, :, index["polarization"]]
    participation = run.timeline[:, :, index["participation"]]
    horizon = run.timeline.shape[1] - 1
    definitions = [
        (
            "broad_awareness",
            "形成广泛知晓",
            1 / (1 + np.exp(-10 * (awareness[:, -1] - 0.55))),
            _crossing_ticks(awareness, 0.55, horizon),
        ),
        (
            "discussion_surge",
            "公共讨论明显增加",
            1 / (1 + np.exp(-12 * (discussion.max(axis=1) - 0.14))),
            _crossing_ticks(discussion, 0.14, horizon),
        ),
        (
            "polarization_risk",
            "意见分化加深",
            1 / (1 + np.exp(-12 * (polarization[:, -1] - 0.24))),
            _crossing_ticks(polarization, 0.24, horizon),
        ),
        (
            "collective_participation",
            "出现可见参与行动",
            1 / (1 + np.exp(-12 * (participation.max(axis=1) - 0.13))),
            _crossing_ticks(participation, 0.13, horizon),
        ),
    ]
    results = []
    for outcome_id, label, probabilities, ticks in definitions:
        calibrated = calibrate_event_probabilities(
            probabilities,
            outcome_id=outcome_id,
            profile=calibration,
        )
        results.append(
            DownstreamOutcome(
                outcome_id=outcome_id,
                label=label,
                probability=_probability_band(calibrated),
                likely_tick=_probability_band(ticks),
            )
        )
    return results


def _scenario_forecasts(
    runtime: RuntimeBundle,
    calibration: CalibrationProfile | None,
) -> list[ScenarioForecast]:
    forecasts = []
    for run in runtime.scenarios:
        forecasts.append(
            ScenarioForecast(
                scenario_id=run.scenario.scenario_id,
                label=run.scenario.label,
                timeline=_timeline(run, runtime.metric_names),
                final_actions={
                    action: _probability_band(run.final_action_shares[:, index])
                    for index, action in enumerate(runtime.action_names)
                },
                downstream_outcomes=_downstream_outcomes(
                    run,
                    runtime.metric_names,
                    calibration,
                ),
            )
        )
    return forecasts


def _event_at_cutoff(
    request: PredictionRequest,
    cutoff: datetime,
) -> tuple[EventScenario, list[str]]:
    included = []
    excluded = []
    for item in request.event.evidence:
        if item.available_at is not None and item.available_at > cutoff:
            excluded.append(item.evidence_id)
        else:
            included.append(item)
    return request.event.model_copy(update={"evidence": included}), excluded


def _oriented(values: NDArray[np.float64], direction: MetricDirection) -> NDArray[np.float64]:
    return values if direction == MetricDirection.INCREASE else -values


def _constrained_l2_evaluation(
    request: PredictionRequest,
    questionnaire: Questionnaire,
    population: ResearchPopulation,
    runtime: RuntimeBundle,
    forecast_as_of: datetime,
    excluded_evidence_ids: list[str],
) -> ConstrainedL2Evaluation:
    protocol = request.evaluation_protocol
    metric_specs: list[EvaluationMetric] = [
        protocol.primary_metric,
        *protocol.auxiliary_metrics,
    ]
    metric_index = {name: index for index, name in enumerate(runtime.metric_names)}
    scenario_by_id = {item.scenario.scenario_id: item for item in runtime.scenarios}
    baseline = scenario_by_id.get(protocol.baseline_scenario_id)
    if baseline is None:
        raise ValueError(f"baseline scenario not found: {protocol.baseline_scenario_id}")

    effects: list[CounterfactualEffect] = []
    cod_by_scenario: dict[str, float] = {}
    warnings: list[str] = []
    for run in runtime.scenarios:
        if run.scenario.scenario_id == baseline.scenario.scenario_id:
            continue
        weighted_cod = 0.0
        total_weight = 0.0
        for metric in metric_specs:
            index = metric_index[metric.metric_id]
            baseline_values = baseline.timeline[:, -1, index]
            scenario_values = run.timeline[:, -1, index]
            deltas = scenario_values - baseline_values
            oriented_deltas = _oriented(deltas, metric.direction)
            median_oriented = float(np.median(oriented_deltas))
            direction_consistency = float(np.mean(oriented_deltas > 0))
            magnitude_score = float(
                np.clip(max(0.0, median_oriented) / protocol.minimum_effect, 0, 1)
            )
            cod_score = direction_consistency * magnitude_score
            lower_oriented = float(np.quantile(oriented_deltas, 0.1))
            effect_detected = bool(
                lower_oriented > 0 and median_oriented >= protocol.minimum_effect
            )
            effects.append(
                CounterfactualEffect(
                    scenario_id=run.scenario.scenario_id,
                    scenario_label=run.scenario.label,
                    metric_id=metric.metric_id,
                    metric_label=metric.label,
                    direction=metric.direction,
                    weight=metric.weight,
                    baseline_value=_probability_band(baseline_values),
                    scenario_value=_probability_band(scenario_values),
                    paired_delta=_probability_band(deltas),
                    direction_consistency=direction_consistency,
                    cod_score=cod_score,
                    effect_detected=effect_detected,
                )
            )
            weighted_cod += metric.weight * cod_score
            total_weight += metric.weight
            if abs(float(np.median(deltas))) < protocol.minimum_effect:
                warnings.append(
                    f"{run.scenario.label}对{metric.label}的中位变化低于"
                    f"{protocol.minimum_effect:.1%}，当前模型无法确认干预具有实质影响。"
                )
            elif median_oriented <= 0:
                warnings.append(
                    f"{run.scenario.label}使{metric.label}向预期反方向变化，需要复核干预设定。"
                )
        cod_by_scenario[run.scenario.scenario_id] = (
            weighted_cod / total_weight if total_weight else 0.0
        )

    nonbaseline_runs = [
        item
        for item in runtime.scenarios
        if item.scenario.scenario_id != baseline.scenario.scenario_id
    ]
    for left_index, left in enumerate(nonbaseline_runs):
        for right in nonbaseline_runs[left_index + 1 :]:
            median_differences = [
                abs(
                    float(
                        np.median(
                            left.timeline[:, -1, metric_index[metric.metric_id]]
                            - right.timeline[:, -1, metric_index[metric.metric_id]]
                        )
                    )
                )
                for metric in metric_specs
            ]
            if max(median_differences, default=0.0) < protocol.minimum_effect:
                warnings.append(
                    f"{left.scenario.label}与{right.scenario.label}在全部锁定指标上的差异"
                    f"均低于{protocol.minimum_effect:.1%}；两项干预目前不可区分。"
                )

    ranking_rows: list[tuple[float, ScenarioRun, ProbabilityBand, ProbabilityBand]] = []
    total_weight = sum(item.weight for item in metric_specs)
    primary_index = metric_index[protocol.primary_metric.metric_id]
    baseline_primary = baseline.timeline[:, -1, primary_index]
    for run in runtime.scenarios:
        utility = 0.0
        for metric in metric_specs:
            values = run.timeline[:, -1, metric_index[metric.metric_id]]
            median = float(np.median(values))
            utility += metric.weight * (
                median if metric.direction == MetricDirection.INCREASE else 1 - median
            )
        primary_values = run.timeline[:, -1, primary_index]
        ranking_rows.append(
            (
                utility / total_weight,
                run,
                _probability_band(primary_values),
                _probability_band(primary_values - baseline_primary),
            )
        )
    ranking_rows.sort(key=lambda item: (-item[0], item[1].scenario.scenario_id))
    ranking = [
        ScenarioRanking(
            scenario_id=run.scenario.scenario_id,
            label=run.scenario.label,
            rank=rank,
            decision_score=float(score),
            primary_metric_value=value,
            primary_metric_delta=delta,
        )
        for rank, (score, run, value, delta) in enumerate(ranking_rows, start=1)
    ]

    cod_score = float(np.mean(list(cod_by_scenario.values()))) if cod_by_scenario else 0.0
    if cod_score >= 0.7:
        interpretation = "干预差异清晰，方案变化在多数路径上产生了方向一致且达到阈值的结果变化。"
    elif cod_score >= 0.4:
        interpretation = "模型能够区分部分方案，但仍有指标或路径对干预不够敏感。"
    else:
        interpretation = "当前干预敏感性较弱，不能仅凭本次排序形成强决策结论。"
    if excluded_evidence_ids:
        warnings.append(f"已排除 {len(excluded_evidence_ids)} 条在预测时点后才可获得的证据。")
    untimestamped_evidence_ids = [
        item.evidence_id for item in request.event.evidence if item.available_at is None
    ]
    if untimestamped_evidence_ids:
        warnings.append(
            f"{len(untimestamped_evidence_ids)} 条证据未提供可用时点，"
            "仅按用户输入处理，不能视为已完成时间审计。"
        )
    lock_signature = stable_hash(
        {
            "request": request.model_dump(mode="json"),
            "questionnaire": questionnaire.model_dump(mode="json"),
            "population_signature": population.manifest["profile_signature"],
            "weighting_signature": population.manifest.get("weighting_signature"),
            "scenario_ids": [item.scenario.scenario_id for item in runtime.scenarios],
            "metric_ids": [item.metric_id for item in metric_specs],
            "excluded_evidence_ids": excluded_evidence_ids,
            "forecast_as_of": forecast_as_of.isoformat(),
        }
    )
    return ConstrainedL2Evaluation(
        baseline_scenario_id=baseline.scenario.scenario_id,
        protocol_lock=ProtocolLock(
            forecast_as_of=forecast_as_of,
            horizon_ticks=request.horizon_ticks,
            scenario_ids=[item.scenario.scenario_id for item in runtime.scenarios],
            metric_ids=[item.metric_id for item in metric_specs],
            baseline_scenario_id=baseline.scenario.scenario_id,
            excluded_evidence_ids=excluded_evidence_ids,
            untimestamped_evidence_ids=untimestamped_evidence_ids,
            input_signature=lock_signature,
        ),
        scenario_ranking=ranking,
        effects=effects,
        cod_score=cod_score,
        cod_interpretation=interpretation,
        warnings=list(dict.fromkeys(warnings)),
    )


def _conclusion(runtime: RuntimeBundle) -> str:
    metric_index = {name: index for index, name in enumerate(runtime.metric_names)}
    baseline = next(
        item for item in runtime.scenarios if item.scenario.scenario_id == "baseline_no_event"
    )
    event = next(
        item for item in runtime.scenarios if item.scenario.scenario_id == "event_as_described"
    )
    awareness = float(np.median(event.timeline[:, -1, metric_index["awareness"]]))
    support = float(np.median(event.timeline[:, -1, metric_index["support"]]))
    opposition = float(np.median(event.timeline[:, -1, metric_index["opposition"]]))
    baseline_discussion = float(np.median(baseline.timeline[:, -1, metric_index["discussion"]]))
    event_discussion = float(np.median(event.timeline[:, -1, metric_index["discussion"]]))
    if support - opposition > 0.08:
        stance = "整体反应偏支持"
    elif opposition - support > 0.08:
        stance = "整体反应偏反对"
    else:
        stance = "支持与反对接近，观望仍占重要位置"
    return (
        f"事件在预测期末的知晓度约为 {awareness:.0%}；{stance}。"
        f"讨论行为相对无事件基线变化 {event_discussion - baseline_discussion:+.1%}。"
    )


def _report_metadata(
    request: PredictionRequest,
    population: ResearchPopulation,
    runtime: RuntimeBundle,
    represented_population: float,
    effective_n: float,
    grounding_report: PopulationGroundingReport | None,
    calibration_profile: CalibrationProfile | None,
) -> ReportRunMetadata:
    return ReportRunMetadata(
        model_version=MODEL_VERSION,
        data_version=DATA_VERSION,
        seed=request.seed,
        paths=request.paths,
        horizon_ticks=request.horizon_ticks,
        scenario_count=len(runtime.scenarios),
        requested_agents=population.agents.num_rows,
        successful_agents=population.agents.num_rows,
        failed_agents=0,
        represented_population=represented_population,
        effective_sample_size=effective_n,
        population_source=(
            "授权聚合人口边际约束的合成人格"
            if grounding_report is not None
            else "未接入现实人口边际的合成人格"
        ),
        weighting_method=(
            "迭代比例拟合后的调查权重" if grounding_report is not None else "等权合成人格原型"
        ),
        interval_definition=(
            f"P10 / P50 / P90 来自 {request.paths} 条共享随机数路径；"
            "单路径基线区间另含有效样本量近似抽样误差"
        ),
        calibration_status=(
            "historically_validated"
            if calibration_profile is not None
            and calibration_profile.status == CalibrationStatus.VALIDATED
            else "uncalibrated_prior"
        ),
        profile_signature=str(population.manifest["profile_signature"]),
    )


def _report_quality(
    request: PredictionRequest,
    population: ResearchPopulation,
    survey: SurveyForecastBundle,
    scenarios: list[ScenarioForecast],
    l2_evaluation: ConstrainedL2Evaluation,
    grounding_report: PopulationGroundingReport | None,
    calibration_profile: CalibrationProfile | None,
) -> ReportQualitySummary:
    checks: list[ReportQualityCheck] = []

    def add(
        check_id: str,
        label: str,
        status: Literal["pass", "warning", "fail"],
        observed: str,
        expected: str,
        detail: str,
    ) -> None:
        checks.append(
            ReportQualityCheck(
                check_id=check_id,
                label=label,
                status=status,
                observed=observed,
                expected=expected,
                detail=detail,
            )
        )

    bands: list[ProbabilityBand] = []
    probability_sum_deviations: list[float] = []
    for forecast in survey.forecasts:
        for snapshot in (forecast.baseline, forecast.post_event):
            bands.extend(item.probability for item in snapshot.options)
            bands.extend(item.share for item in snapshot.themes)
            if snapshot.numeric_value is not None:
                bands.append(snapshot.numeric_value)
            if forecast.kind in {
                QuestionKind.SINGLE_CHOICE,
                QuestionKind.SCALE,
                QuestionKind.RANKING,
            }:
                probability_sum_deviations.append(
                    abs(sum(item.probability.p50 for item in snapshot.options) - 1)
                )
    for scenario in scenarios:
        for point in scenario.timeline:
            bands.extend(point.metrics.values())
        bands.extend(scenario.final_actions.values())
        bands.extend(item.probability for item in scenario.downstream_outcomes)
        bands.extend(
            item.likely_tick
            for item in scenario.downstream_outcomes
            if item.likely_tick is not None
        )

    invalid_band_count = sum(not (band.p10 <= band.p50 <= band.p90) for band in bands)
    add(
        "interval_order",
        "区间顺序",
        "pass" if invalid_band_count == 0 else "fail",
        f"{invalid_band_count} 个异常 / {len(bands)} 个区间",
        "所有区间满足 P10 ≤ P50 ≤ P90",
        "逐一检查问卷、时间线、行动与结果区间。",
    )
    maximum_deviation = max(probability_sum_deviations, default=0)
    add(
        "probability_mass",
        "选择题概率守恒",
        "pass" if maximum_deviation <= 0.02 else "fail",
        f"最大偏差 {maximum_deviation:.4f}",
        "互斥选项 P50 合计与 1 的偏差不超过 0.02",
        "多选题不要求合计为 1，因此不纳入该项。",
    )
    action_deviation = max(
        (
            abs(sum(item.p50 for item in scenario.final_actions.values()) - 1)
            for scenario in scenarios
        ),
        default=0,
    )
    add(
        "action_mass",
        "行动分布守恒",
        "pass" if action_deviation <= 0.02 else "fail",
        f"最大偏差 {action_deviation:.4f}",
        "每个情景的最终行动 P50 合计接近 1",
        "防止行动人数与比例在聚合时丢失或重复。",
    )
    prototype_count = population.agents.num_rows
    add(
        "agent_completion",
        "Agent 完成率",
        "pass",
        f"{prototype_count} / {prototype_count}，失败 0",
        "所有请求人格均完成观察、判断、行动和记忆",
        "当前运行时为向量化全量执行；不发布不完整结果。",
    )
    collapsed = sum(abs(band.p90 - band.p10) <= 1e-9 for band in bands)
    collapsed_share = collapsed / max(1, len(bands))
    add(
        "interval_spread",
        "区间辨识度",
        "warning" if collapsed_share > 0.2 else "pass",
        f"{collapsed} / {len(bands)} 个区间完全重合",
        "完全重合区间占比不超过 20%",
        (
            "重合较多，可能来自确定性机制或路径分布过窄，应增加路径并复核扰动。"
            if collapsed_share > 0.2
            else "区间包含可见路径差异；这仍不是现实误差保证。"
        ),
    )
    cross_tab_fields = {
        item.group_field for forecast in survey.forecasts for item in forecast.cross_tabs
    }
    missing_cross_tabs = sorted(set(request.group_fields) - cross_tab_fields)
    add(
        "cross_tab_coverage",
        "交叉表覆盖",
        "pass" if not missing_cross_tabs else "fail",
        f"覆盖 {len(cross_tab_fields)} / {len(request.group_fields)} 个分组字段",
        "请求的分组字段均进入每题交叉表",
        (
            "分组字段已全部输出。"
            if not missing_cross_tabs
            else f"缺少字段：{', '.join(missing_cross_tabs)}"
        ),
    )
    response_count = sum(len(item.representative_responses) for item in survey.forecasts)
    expected_response_count = len(survey.forecasts) * 3
    add(
        "representative_responses",
        "代表性回答覆盖",
        "pass" if response_count >= expected_response_count else "warning",
        f"{response_count} 条",
        f"每题最多 3 条，目标 {expected_response_count} 条",
        "回答由完整合成人格字段生成，并明确标注为模拟文本。",
    )
    add(
        "historical_calibration",
        "历史校准",
        (
            "pass"
            if calibration_profile is not None
            and calibration_profile.status == CalibrationStatus.VALIDATED
            else "warning"
        ),
        (
            f"{calibration_profile.holdout_records} 条时间留出记录"
            if calibration_profile is not None
            else "未加载校准记录"
        ),
        "使用预测时点之前的历史结果完成时间留出验证",
        "未校准时结果属于模型先验，不能声称现实准确率。",
    )
    add(
        "population_grounding",
        "人口口径",
        "pass" if grounding_report is not None else "warning",
        (
            f"授权边际：{', '.join(grounding_report.covered_fields)}"
            if grounding_report is not None
            else "等权合成人格，未接入现实人口边际"
        ),
        "人口来源、年份和加权方法可追溯",
        "未约束时只解释 5,000 个合成人格原型，不外推现实城市人口。",
    )
    add(
        "future_information_isolation",
        "未来信息隔离",
        "pass" if l2_evaluation.protocol_lock.future_information_forbidden else "fail",
        f"排除 {len(l2_evaluation.protocol_lock.excluded_evidence_ids)} 条未来证据",
        "预测锁定时点之后的信息不得进入推演",
        "协议锁与输入签名共同记录该约束。",
    )
    out_of_distribution = sum(item.out_of_distribution for item in survey.forecasts)
    add(
        "semantic_coverage",
        "题目语义覆盖",
        "warning" if out_of_distribution else "pass",
        f"{out_of_distribution} / {len(survey.forecasts)} 道题需谨慎解释",
        "所有题目均落在已支持构念且选项位置明确",
        "语义覆盖不足不会阻止运行，但必须在结果中保留警告。",
    )

    passed = sum(item.status == "pass" for item in checks)
    warnings = sum(item.status == "warning" for item in checks)
    failures = sum(item.status == "fail" for item in checks)
    return ReportQualitySummary(
        status="fail" if failures else "warning" if warnings else "pass",
        passed=passed,
        warnings=warnings,
        failures=failures,
        checks=checks,
    )


def _write_questionnaire_csv(
    path: Path,
    questionnaire: Questionnaire,
    survey: SurveyForecastBundle,
) -> None:
    question_lookup = {item.question_id: item for item in questionnaire.questions}
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "question_id",
                "question_text",
                "question_kind",
                "phase",
                "answer",
                "p10",
                "p50",
                "p90",
            ],
        )
        writer.writeheader()
        for forecast in survey.forecasts:
            question = question_lookup[forecast.question_id]
            for snapshot in (forecast.baseline, forecast.post_event):
                for option in snapshot.options:
                    writer.writerow(
                        {
                            "question_id": forecast.question_id,
                            "question_text": forecast.question_text,
                            "question_kind": question.kind.value,
                            "phase": snapshot.phase,
                            "answer": option.label,
                            **option.probability.model_dump(),
                        }
                    )
                if snapshot.numeric_value is not None:
                    writer.writerow(
                        {
                            "question_id": forecast.question_id,
                            "question_text": forecast.question_text,
                            "question_kind": question.kind.value,
                            "phase": snapshot.phase,
                            "answer": "numeric_value",
                            **snapshot.numeric_value.model_dump(),
                        }
                    )
                for theme in snapshot.themes:
                    writer.writerow(
                        {
                            "question_id": forecast.question_id,
                            "question_text": forecast.question_text,
                            "question_kind": question.kind.value,
                            "phase": snapshot.phase,
                            "answer": theme.theme,
                            **theme.share.model_dump(),
                        }
                    )


def _write_timeline_csv(path: Path, runtime: RuntimeBundle) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["scenario_id", "path", "tick", *runtime.metric_names],
        )
        writer.writeheader()
        for scenario in runtime.scenarios:
            for path_index in range(scenario.timeline.shape[0]):
                for tick in range(scenario.timeline.shape[1]):
                    writer.writerow(
                        {
                            "scenario_id": scenario.scenario.scenario_id,
                            "path": path_index,
                            "tick": tick,
                            **{
                                name: float(scenario.timeline[path_index, tick, metric_index])
                                for metric_index, name in enumerate(runtime.metric_names)
                            },
                        }
                    )


def _write_replay(path: Path, runtime: RuntimeBundle) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for scenario in runtime.scenarios:
            for record in scenario.replay_records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _save_run(
    request: PredictionRequest,
    questionnaire: Questionnaire,
    population: ResearchPopulation,
    runtime: RuntimeBundle,
    survey: SurveyForecastBundle,
    result: PredictionResult,
    directory: Path,
) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    request_path = directory / "request.json"
    result_path = directory / "result.json"
    questionnaire_path = directory / "questionnaire_forecast.csv"
    individual_path = directory / "individual_predictions.parquet"
    timeline_path = directory / "timeline.csv"
    replay_path = directory / "replay.jsonl"
    manifest_path = directory / "run_manifest.json"
    request_path.write_text(request.model_dump_json(indent=2), encoding="utf-8")
    _write_questionnaire_csv(questionnaire_path, questionnaire, survey)
    pq.write_table(survey.individual_predictions, individual_path, compression="zstd")
    _write_timeline_csv(timeline_path, runtime)
    _write_replay(replay_path, runtime)
    result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    files = [
        request_path,
        result_path,
        questionnaire_path,
        individual_path,
        timeline_path,
        replay_path,
    ]
    validation = validate_population(population)
    manifest = {
        "run_id": result.run_id,
        "model_version": MODEL_VERSION,
        "data_version": DATA_VERSION,
        "created_at": result.created_at.isoformat(),
        "population_signature": population.manifest["profile_signature"],
        "weighting_signature": population.manifest.get("weighting_signature"),
        "grounding": result.grounding.model_dump(mode="json"),
        "calibration": result.calibration.model_dump(mode="json"),
        "constrained_l2_evaluation": (
            result.l2_evaluation.model_dump(mode="json")
            if result.l2_evaluation is not None
            else None
        ),
        "report_metadata": (
            result.report_metadata.model_dump(mode="json")
            if result.report_metadata is not None
            else None
        ),
        "report_quality": (
            result.report_quality.model_dump(mode="json")
            if result.report_quality is not None
            else None
        ),
        "population_provenance": {
            "data_origin": population.manifest.get("data_origin"),
            "field_provenance": population.manifest.get("field_provenance", {}),
            "edge_provenance": population.manifest.get("edge_provenance", {}),
            "missingness_policy": population.manifest.get("missingness_policy"),
        },
        "deterministic_signature": result.deterministic_signature,
        "participation_proof": {
            "agent_count": population.agents.num_rows,
            "ticks": request.horizon_ticks,
            "paths": request.paths,
            "scenarios": len(runtime.scenarios),
            "tier_counts": validation["tier_counts"],
            "required_stages": ["observed", "decided", "acted", "remembered"],
        },
        "artifacts": {item.name: file_hash(item) for item in files},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def run_prediction(
    request: PredictionRequest,
    settings: Settings | None = None,
) -> PredictionResult:
    runtime_settings = settings or Settings.load()
    created_at = datetime.now(UTC)
    forecast_as_of = request.evaluation_protocol.forecast_as_of or created_at
    if forecast_as_of > created_at:
        raise ValueError("forecast_as_of cannot be later than the prediction run time")
    effective_event, excluded_evidence_ids = _event_at_cutoff(request, forecast_as_of)
    population, grounding_report = _resolve_population(request, runtime_settings)
    questionnaire = _resolve_questionnaire(request, runtime_settings)
    calibration_profile = _resolve_calibration(request, runtime_settings)
    interpretation = interpret_event(effective_event, runtime_settings)
    runtime = simulate_population(
        population,
        effective_event,
        interpretation,
        horizon_ticks=request.horizon_ticks,
        paths=request.paths,
        seed=request.seed,
    )
    survey = forecast_questionnaire(
        questionnaire,
        population,
        runtime,
        group_fields=request.group_fields,
        calibration=calibration_profile,
    )
    l2_evaluation = _constrained_l2_evaluation(
        request,
        questionnaire,
        population,
        runtime,
        forecast_as_of,
        excluded_evidence_ids,
    )
    run_id = new_id("prediction")
    run_directory = prediction_root(runtime_settings) / "runs" / run_id
    artifacts = PredictionArtifacts(
        result_json=str((run_directory / "result.json").resolve()),
        questionnaire_csv=str((run_directory / "questionnaire_forecast.csv").resolve()),
        individual_predictions=str((run_directory / "individual_predictions.parquet").resolve()),
        replay_log=str((run_directory / "replay.jsonl").resolve()),
        run_manifest=str((run_directory / "run_manifest.json").resolve()),
    )
    validation = validate_population(population)
    represented_population = (
        grounding_report.target_population
        if grounding_report is not None
        else float(np.asarray(population.agents["survey_weight"], dtype=float).sum())
    )
    effective_n = effective_sample_size(np.asarray(population.agents["survey_weight"], dtype=float))
    scenario_forecasts = _scenario_forecasts(runtime, calibration_profile)
    report_metadata = _report_metadata(
        request,
        population,
        runtime,
        represented_population,
        effective_n,
        grounding_report,
        calibration_profile,
    )
    report_quality = _report_quality(
        request,
        population,
        survey,
        scenario_forecasts,
        l2_evaluation,
        grounding_report,
        calibration_profile,
    )
    signature = stable_hash(
        {
            "request": request.model_dump(mode="json"),
            "population_signature": population.manifest["profile_signature"],
            "weighting_signature": population.manifest.get("weighting_signature"),
            "calibration_signature": (
                calibration_profile.profile_signature if calibration_profile else None
            ),
            "questionnaire": questionnaire.model_dump(mode="json"),
            "final_state_hashes": [
                [
                    record["state_hash"]
                    for record in item.replay_records
                    if record["tick"] == request.horizon_ticks
                ]
                for item in runtime.scenarios
            ],
            "counterfactual_effects": [
                item.model_dump(mode="json") for item in l2_evaluation.effects
            ],
        }
    )
    result = PredictionResult(
        run_id=run_id,
        project_id=request.project_id,
        title=request.title,
        created_at=created_at,
        conclusion=_conclusion(runtime),
        population=PopulationRunSummary(
            population_id=population.spec.population_id,
            agent_count=population.agents.num_rows,
            tier_counts=validation["tier_counts"],
            relationship_count=population.graph.edge_count,
            agents_observed=population.agents.num_rows,
            agents_decided=population.agents.num_rows,
            agents_acted=population.agents.num_rows,
            agents_remembered=population.agents.num_rows,
            stable_profiles=True,
            represented_population=represented_population,
            effective_sample_size=effective_n,
        ),
        grounding=(
            GroundingRunSummary(
                status="synthetic_anchored_to_authorized_aggregates",
                population_margin_id=grounding_report.dataset_id,
                source=grounding_report.source,
                covered_fields=grounding_report.covered_fields,
                converged=grounding_report.converged,
                design_effect=grounding_report.design_effect,
                warnings=grounding_report.warnings,
            )
            if grounding_report is not None
            else GroundingRunSummary()
        ),
        calibration=(
            CalibrationRunSummary(
                status=(
                    "historically_validated"
                    if calibration_profile.status == CalibrationStatus.VALIDATED
                    else calibration_profile.status.value
                ),
                calibration_id=calibration_profile.calibration_id,
                dataset_id=calibration_profile.dataset_id,
                training_records=calibration_profile.training_records,
                holdout_records=calibration_profile.holdout_records,
                holdout_brier_before=calibration_profile.before.brier_score,
                holdout_brier_after=calibration_profile.after.brier_score,
                applied=calibration_profile.status == CalibrationStatus.VALIDATED,
                warnings=calibration_profile.warnings,
            )
            if calibration_profile is not None
            else CalibrationRunSummary()
        ),
        report_metadata=report_metadata,
        report_quality=report_quality,
        questionnaire_forecast=survey.forecasts,
        group_insights=survey.group_insights,
        scenarios=scenario_forecasts,
        l2_evaluation=l2_evaluation,
        key_drivers=survey.key_drivers,
        uncertainty=[
            f"区间来自 {request.paths} 条可复现模拟路径的 p10 / p50 / p90。",
            "反事实差值使用同一路径共享随机数配对计算，减少方案间抽样噪声。",
            (
                "合成人格已按授权聚合边际加权，但人格与关系机制仍存在结构不确定性。"
                if grounding_report is not None
                else "合成人格与关系结构会带来结构不确定性；可接入授权人口边际进行约束。"
            ),
            (
                f"问卷概率使用 {calibration_profile.holdout_records} 条时间留出记录验证的校准版本。"
                if calibration_profile is not None
                and calibration_profile.status == CalibrationStatus.VALIDATED
                else "当前问卷概率尚未通过历史时间留出校准。"
            ),
            *interpretation.missing_inputs,
        ],
        limitations=[
            "结果是条件概率模拟，不是对现实未来的保证。",
            (
                "人格仍为合成原型；人口边际只约束总体分布，不会把原型变成真实个人。"
                if grounding_report is not None
                else "当前人口完全为合成原型，不代表或复制任何可识别个人。"
            ),
            (
                "校准只覆盖历史数据中的问题与时间范围，分布变化后需要重新验证。"
                if calibration_profile is not None
                and calibration_profile.status == CalibrationStatus.VALIDATED
                else "无历史结果回填时，概率属于未校准的先验预测。"
            ),
            "开放题内容是结构化模拟回答，不是真实受访者原话。",
        ],
        participant_receipts=survey.participant_receipts,
        semantic_interpretation=interpretation.model_dump(mode="json"),
        artifacts=artifacts,
        deterministic_signature=signature,
        disclaimer=DISCLAIMER,
    )
    _save_run(
        request,
        questionnaire,
        population,
        runtime,
        survey,
        result,
        run_directory,
    )
    latest = prediction_root(runtime_settings) / "latest_run_summary.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "title": request.title,
                "created_at": result.created_at.isoformat(),
                "conclusion": result.conclusion,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def _run_file(run_id: str, filename: str, settings: Settings) -> Path:
    path = prediction_root(settings) / "runs" / run_id / filename
    if not path.exists():
        raise FileNotFoundError(f"prediction run or artifact not found: {run_id}")
    return path


def load_prediction(run_id: str, settings: Settings) -> PredictionResult:
    path = _run_file(run_id, "result.json", settings)
    return PredictionResult.model_validate_json(path.read_text(encoding="utf-8"))


def list_predictions(settings: Settings, limit: int = 20) -> list[dict[str, Any]]:
    root = prediction_root(settings) / "runs"
    if not root.exists():
        return []
    results: list[PredictionResult] = []
    for path in root.glob("*/result.json"):
        try:
            results.append(PredictionResult.model_validate_json(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    results.sort(key=lambda item: item.created_at, reverse=True)
    return [
        {
            "run_id": item.run_id,
            "project_id": item.project_id,
            "title": item.title,
            "created_at": item.created_at.isoformat(),
            "conclusion": item.conclusion,
            "agent_count": item.population.agent_count,
        }
        for item in results[:limit]
    ]


def verify_prediction_replay(
    run_id: str | Path, settings: Settings | None = None
) -> dict[str, Any]:
    if isinstance(run_id, Path):
        directory = run_id
    else:
        if settings is None:
            settings = Settings.load()
        directory = prediction_root(settings) / "runs" / run_id
    manifest_path = directory / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("prediction run manifest not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_checks = {
        filename: (directory / filename).exists()
        and file_hash(directory / filename) == expected_hash
        for filename, expected_hash in manifest["artifacts"].items()
    }
    proof = manifest["participation_proof"]
    expected_agents = int(proof["agent_count"])
    expected_records = int(proof["ticks"] * proof["paths"] * proof["scenarios"])
    chain_heads: dict[tuple[str, int], str] = {}
    replay_valid = True
    record_count = 0
    replay_path = directory / "replay.jsonl"
    with replay_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            record_count += 1
            key = (str(record["scenario_id"]), int(record["path"]))
            expected_previous = chain_heads.get(key, "0" * 64)
            supplied_hash = record.pop("record_hash")
            stage_counts = record["stage_counts"]
            replay_valid &= record["previous_hash"] == expected_previous
            replay_valid &= supplied_hash == stable_hash(record)
            replay_valid &= all(
                int(stage_counts[stage]) == expected_agents for stage in proof["required_stages"]
            )
            replay_valid &= sum(record["tier_counts"].values()) == expected_agents
            visibility = record.get("visibility_counts")
            if visibility is not None:
                replay_valid &= all(
                    0 <= int(value) <= expected_agents for value in visibility.values()
                )
                replay_valid &= (
                    int(visibility["cumulative_exposed"]) + int(visibility["unexposed"])
                    == expected_agents
                )
            chain_heads[key] = supplied_hash
    return {
        "valid": bool(
            all(artifact_checks.values()) and replay_valid and record_count == expected_records
        ),
        "artifact_checks": artifact_checks,
        "participation_valid": replay_valid,
        "record_count": record_count,
        "expected_record_count": expected_records,
        "agent_count_per_stage": expected_agents,
        "deterministic_signature": manifest["deterministic_signature"],
    }


def _rank_correlation(
    predicted: dict[str, float],
    observed: dict[str, float],
    direction: MetricDirection,
) -> dict[str, float | bool | int | None]:
    scenario_ids = sorted(set(predicted) & set(observed))
    if len(scenario_ids) < 2:
        return {
            "scenario_count": len(scenario_ids),
            "top_1_match": None,
            "spearman": None,
            "kendall": None,
        }
    reverse = direction == MetricDirection.INCREASE
    predicted_order = sorted(scenario_ids, key=lambda item: predicted[item], reverse=reverse)
    observed_order = sorted(scenario_ids, key=lambda item: observed[item], reverse=reverse)
    predicted_rank = {scenario_id: rank for rank, scenario_id in enumerate(predicted_order)}
    observed_rank = {scenario_id: rank for rank, scenario_id in enumerate(observed_order)}
    left = np.asarray([predicted_rank[item] for item in scenario_ids], dtype=float)
    right = np.asarray([observed_rank[item] for item in scenario_ids], dtype=float)
    spearman = float(np.corrcoef(left, right)[0, 1])
    concordant = 0
    discordant = 0
    for left_index in range(len(scenario_ids)):
        for right_index in range(left_index + 1, len(scenario_ids)):
            first = scenario_ids[left_index]
            second = scenario_ids[right_index]
            product = (predicted[first] - predicted[second]) * (observed[first] - observed[second])
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    comparable_pairs = concordant + discordant
    kendall = (concordant - discordant) / comparable_pairs if comparable_pairs else None
    return {
        "scenario_count": len(scenario_ids),
        "top_1_match": predicted_order[0] == observed_order[0],
        "spearman": spearman,
        "kendall": kendall,
    }


def _evaluate_scenario_metrics(
    result: PredictionResult,
    request: PredictionRequest,
    observed: dict[str, dict[str, float]],
) -> tuple[dict[str, Any], list[float], int]:
    scenario_lookup = {item.scenario_id: item for item in result.scenarios}
    interval_rows: list[tuple[float, float, float, float]] = []
    errors: list[float] = []
    matched = 0
    for scenario_id, metrics in observed.items():
        scenario = scenario_lookup.get(scenario_id)
        if scenario is None or not scenario.timeline:
            continue
        final_metrics = scenario.timeline[-1].metrics
        for metric_id, actual in metrics.items():
            band = final_metrics.get(metric_id)
            if band is None:
                continue
            interval_rows.append((actual, band.p10, band.p50, band.p90))
            errors.append((band.p50 - actual) ** 2)
            matched += 1
    interval_width = [upper - lower for _, lower, _, upper in interval_rows]
    coverage = [lower <= actual <= upper for actual, lower, _, upper in interval_rows]
    alpha = 0.2
    interval_scores = [
        (upper - lower)
        + (2 / alpha) * max(0.0, lower - actual)
        + (2 / alpha) * max(0.0, actual - upper)
        for actual, lower, _, upper in interval_rows
    ]
    wis = [
        (0.5 * abs(actual - median) + (alpha / 2) * interval_score) / 1.5
        for (actual, _, median, _), interval_score in zip(
            interval_rows, interval_scores, strict=True
        )
    ]

    primary = request.evaluation_protocol.primary_metric
    predicted_primary = {
        scenario_id: scenario.timeline[-1].metrics[primary.metric_id].p50
        for scenario_id, scenario in scenario_lookup.items()
        if scenario.timeline and primary.metric_id in scenario.timeline[-1].metrics
    }
    observed_primary = {
        scenario_id: metrics[primary.metric_id]
        for scenario_id, metrics in observed.items()
        if primary.metric_id in metrics
    }
    ranking = _rank_correlation(predicted_primary, observed_primary, primary.direction)

    direction_matches: list[bool] = []
    baseline_id = request.evaluation_protocol.baseline_scenario_id
    baseline_observed = observed_primary.get(baseline_id)
    baseline_predicted = predicted_primary.get(baseline_id)
    if baseline_observed is not None and baseline_predicted is not None:
        for scenario_id, actual in observed_primary.items():
            if scenario_id == baseline_id or scenario_id not in predicted_primary:
                continue
            predicted_delta = predicted_primary[scenario_id] - baseline_predicted
            observed_delta = actual - baseline_observed
            if predicted_delta != 0 or observed_delta != 0:
                direction_matches.append(predicted_delta * observed_delta > 0)
    return (
        {
            "interval_observations": len(interval_rows),
            "interval_coverage_80": float(np.mean(coverage)) if coverage else None,
            "mean_interval_width_80": float(np.mean(interval_width)) if interval_width else None,
            "mean_interval_score_80": (
                float(np.mean(interval_scores)) if interval_scores else None
            ),
            "mean_wis_80": float(np.mean(wis)) if wis else None,
            "direction_accuracy": (
                float(np.mean(direction_matches)) if direction_matches else None
            ),
            "ranking_metric": primary.metric_id,
            **ranking,
        },
        errors,
        matched,
    )


def submit_outcome(
    run_id: str,
    submission: OutcomeSubmission,
    settings: Settings,
) -> dict[str, Any]:
    result = load_prediction(run_id, settings)
    request = PredictionRequest.model_validate_json(
        _run_file(run_id, "request.json", settings).read_text(encoding="utf-8")
    )
    questionnaire = _resolve_questionnaire(request, settings)
    questions = {item.question_id: item for item in questionnaire.questions}
    errors: list[float] = []
    matched = 0
    calibration_observations: list[CalibrationObservation] = []
    forecast_by_question = {item.question_id: item for item in result.questionnaire_forecast}
    for question_id, observed in submission.questionnaire_results.items():
        forecast = forecast_by_question.get(question_id)
        if forecast is None:
            continue
        if isinstance(observed, dict):
            question = questions.get(question_id)
            predicted = {
                item.option_id: item.probability.p50 for item in forecast.post_event.options
            }
            supplied_options = set(observed) & set(predicted)
            if (
                question is not None
                and question.kind != QuestionKind.MULTIPLE_CHOICE
                and supplied_options == set(predicted)
            ):
                supplied_total = sum(float(observed[option]) for option in supplied_options)
                if not np.isclose(supplied_total, 1, atol=0.02):
                    raise ValueError(
                        f"complete outcome shares for {question_id} must sum to 1 (±0.02)"
                    )
            for option_id, actual in observed.items():
                if option_id in predicted:
                    errors.append((predicted[option_id] - float(actual)) ** 2)
                    matched += 1
                    if (
                        submission.sample_size > 0
                        and submission.observed_at >= result.created_at
                        and 0 <= float(actual) <= 1
                    ):
                        calibration_observations.append(
                            CalibrationObservation(
                                observation_id=new_id("calobs"),
                                question_id=question_id,
                                option_id=option_id,
                                construct=(
                                    question.latent_construct if question is not None else "unknown"
                                ),
                                forecast_as_of=result.created_at,
                                outcome_available_at=submission.observed_at,
                                predicted_probability=predicted[option_id],
                                observed_share=float(actual),
                                sample_size=submission.sample_size,
                                horizon_ticks=max(
                                    1,
                                    len(result.scenarios[0].timeline) - 1,
                                ),
                                source=f"outcome_backfill:{run_id}",
                                provenance={"run_id": run_id},
                            )
                        )
        elif isinstance(observed, (int, float)) and forecast.post_event.numeric_value is not None:
            scale = max(1.0, abs(float(observed)))
            errors.append(((forecast.post_event.numeric_value.p50 - float(observed)) / scale) ** 2)
            matched += 1
    event_scenario = next(
        (item for item in result.scenarios if item.scenario_id == "event_as_described"),
        None,
    )
    event_forecasts = (
        {item.outcome_id: item.probability.p50 for item in event_scenario.downstream_outcomes}
        if event_scenario is not None
        else {}
    )
    for outcome_id, observed in submission.event_outcomes.items():
        if outcome_id not in event_forecasts or isinstance(observed, str):
            continue
        observed_probability = float(observed)
        if not 0 <= observed_probability <= 1:
            raise ValueError(f"event outcome {outcome_id} must be boolean or within [0, 1]")
        errors.append((event_forecasts[outcome_id] - observed_probability) ** 2)
        matched += 1
        if submission.observed_at >= result.created_at:
            calibration_observations.append(
                CalibrationObservation(
                    observation_id=new_id("calobs"),
                    target_type=CalibrationTargetType.EVENT_OUTCOME,
                    outcome_id=outcome_id,
                    forecast_as_of=result.created_at,
                    outcome_available_at=submission.observed_at,
                    predicted_probability=event_forecasts[outcome_id],
                    observed_share=observed_probability,
                    sample_size=max(1, submission.sample_size),
                    horizon_ticks=request.horizon_ticks,
                    source=f"outcome_backfill:{run_id}",
                    provenance={"run_id": run_id},
                )
            )
    scenario_evaluation, scenario_errors, scenario_matched = _evaluate_scenario_metrics(
        result,
        request,
        submission.scenario_metrics,
    )
    errors.extend(scenario_errors)
    matched += scenario_matched
    evaluation = {
        "matched_values": matched,
        "mean_squared_error": float(np.mean(errors)) if errors else None,
        "scenario_assessment": scenario_evaluation,
        "calibration_status": "evaluation_recorded"
        if errors
        else "stored_without_comparable_fields",
    }
    record: dict[str, Any] = {
        "outcome_id": new_id("outcome"),
        "run_id": run_id,
        "submitted_at": datetime.now(UTC).isoformat(),
        "submission": submission.model_dump(mode="json"),
        "evaluation": evaluation,
    }
    path = _run_file(run_id, "result.json", settings).parent / "outcomes.jsonl"
    if calibration_observations:
        append_backfill_observations(calibration_observations, settings)
    record["calibration_observations_appended"] = len(calibration_observations)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def prediction_export_path(run_id: str, export_format: str, settings: Settings) -> Path:
    if export_format == "json":
        return _run_file(run_id, "result.json", settings)
    if export_format == "csv":
        return _run_file(run_id, "questionnaire_forecast.csv", settings)
    raise ValueError("export format must be json or csv")
