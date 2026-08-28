from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from echo_swm.core.config import Settings
from echo_swm.research.calibration import (
    CalibrationDataset,
    CalibrationStatus,
    calibrate_event_probabilities,
    calibrate_probability_matrix,
    fit_calibration_profile,
)
from echo_swm.research.contracts import (
    EvaluationMetric,
    EvaluationProtocol,
    EventScenario,
    EvidenceItem,
    OutcomeSubmission,
    PopulationSpec,
    QuestionKind,
    Questionnaire,
    ResearchQuestion,
    ScenarioVariant,
)
from echo_swm.research.engine import (
    list_predictions,
    load_prediction,
    prediction_export_path,
    run_prediction,
    submit_outcome,
    verify_prediction_replay,
)
from echo_swm.research.examples import (
    example_calibration_dataset,
    example_population_margins,
    example_prediction_request,
    example_questionnaire,
)
from echo_swm.research.grounding import apply_population_margins
from echo_swm.research.population import (
    generate_population,
    load_population,
    validate_population,
)
from echo_swm.research.semantics import interpret_event


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_dir=tmp_path / "research-artifacts",
        min_segment_size=30,
        log_level="INFO",
        llm_api_key=None,
        llm_base_url="https://api.openai.com/v1",
        llm_model=None,
        llm_timeout_seconds=1,
        llm_max_calls=0,
    )


def test_population_is_stable_complete_tiered_and_multiplex(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    spec = PopulationSpec(
        population_id="filtered_population",
        size=5_000,
        seed=77,
        filters={"region_type": ["town"], "primary_channel": ["community"]},
    )
    first = generate_population(spec, settings)
    second = generate_population(spec, settings, persist=False)
    validation = validate_population(first)
    assert validation["valid"] is True
    assert validation["tier_counts"] == {
        "key": 50,
        "representative": 450,
        "background": 4_500,
    }
    assert first.graph.edge_count == 25_000
    assert set(first.graph.relationship_type.tolist()) == {
        "family",
        "acquaintance",
        "coworker",
        "community",
        "online",
    }
    assert first.agents["agent_id"].to_pylist() == second.agents["agent_id"].to_pylist()
    assert first.manifest["profile_signature"] == second.manifest["profile_signature"]
    assert set(first.manifest["field_provenance"]) == set(first.agents.column_names)
    assert all(
        item["source_type"] == "generated" for item in first.manifest["field_provenance"].values()
    )
    assert set(first.manifest["edge_provenance"]) == {
        "family",
        "acquaintance",
        "coworker",
        "community",
        "online",
    }
    assert "organization_type" in first.agents.column_names
    assert set(first.agents["organization_type"].to_pylist()) >= {
        "higher_education",
        "professional_services",
        "consumer_services",
    }
    assert first.manifest["missingness_policy"] == ("preserve_missing_and_never_autofill_with_llm")
    assert set(first.agents["region_type"].to_pylist()) == {"town"}
    stored = load_population(spec.population_id, settings)
    aggregated = stored.graph.aggregate_from_sources(
        np.linspace(0, 1, stored.agents.num_rows), stored.agents.num_rows
    )
    assert aggregated.shape == (5_000,)
    assert np.isfinite(aggregated).all()

    with pytest.raises(ValueError, match="unsupported population filters"):
        generate_population(
            PopulationSpec(population_id="bad", filters={"city": ["example"]}),
            settings,
            persist=False,
        )


def test_mixed_questionnaire_contract_and_semantic_fallback(tmp_path: Path) -> None:
    questionnaire = example_questionnaire()
    assert len(questionnaire.questions) == 10
    assert {item.kind for item in questionnaire.questions} == set(QuestionKind)
    dumped = questionnaire.model_dump(mode="json")
    assert dumped["questions"][0]["construct"] == "awareness"
    with pytest.raises(ValueError, match="numeric questions require"):
        ResearchQuestion(
            question_id="bad",
            text="invalid numeric",
            kind=QuestionKind.NUMERIC,
        )
    with pytest.raises(ValueError, match="question ids must be unique"):
        Questionnaire(
            questionnaire_id="duplicate",
            title="duplicate",
            questions=[questionnaire.questions[0], questionnaire.questions[0]],
        )
    custom_protocol = EvaluationProtocol(
        primary_metric=EvaluationMetric(metric_id="awareness", label="知晓")
    )
    assert "awareness" not in {item.metric_id for item in custom_protocol.auxiliary_metrics}
    with pytest.raises(ValueError, match="primary metric cannot"):
        EvaluationProtocol(
            primary_metric=EvaluationMetric(metric_id="awareness", label="知晓"),
            auxiliary_metrics=[EvaluationMetric(metric_id="awareness", label="知晓")],
        )

    settings = _settings(tmp_path)
    interpretation = interpret_event(
        EventScenario(
            event_id="free_text_event",
            title="共享空间改善开放方式",
            description="社区开放新的健康学习空间，让更多人自由选择使用时间。",
        ),
        settings,
    )
    assert interpretation.method == "lexical_fallback"
    assert "community" in interpretation.detected_concepts
    assert set(interpretation.value_signals) == {
        "care",
        "fairness",
        "security",
        "tradition",
        "autonomy",
        "community",
    }


def test_authorized_population_margins_rake_without_mutating_base(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    population = generate_population(PopulationSpec(), settings)
    dataset = example_population_margins()
    grounded, report = apply_population_margins(
        population,
        dataset,
        settings,
        persist=False,
    )
    weights = np.asarray(grounded.agents["survey_weight"], dtype=float)
    for field, targets in dataset.margins.items():
        values = np.asarray(grounded.agents[field].to_pylist(), dtype=object)
        actual = {
            category: float(weights[values == category].sum() / weights.sum())
            for category in targets
        }
        assert actual == pytest.approx(targets, abs=1e-7)
    assert report.converged is True
    assert report.target_population == 100_000
    assert report.effective_sample_size <= population.agents.num_rows
    stored_weights = np.asarray(
        load_population(population.spec.population_id, settings).agents["survey_weight"],
        dtype=float,
    )
    assert stored_weights.sum() == pytest.approx(5_000)

    invalid = dataset.model_dump(mode="json")
    invalid["authorization_confirmed"] = False
    with pytest.raises(ValueError, match="authorization_confirmed"):
        type(dataset).model_validate(invalid)


def test_temporal_calibration_covers_question_construct_and_event_results() -> None:
    dataset = example_calibration_dataset()
    profile = fit_calibration_profile(dataset)
    assert profile.status == CalibrationStatus.VALIDATED
    assert profile.after.brier_score < profile.before.brier_score
    assert profile.after.log_loss < profile.before.log_loss
    assert "support" in profile.constructs
    assert "broad_awareness" in profile.event_outcomes
    raw = np.asarray([[0.2, 0.8], [0.7, 0.3]], dtype=float)
    calibrated = calibrate_probability_matrix(
        raw,
        question_id="new_support_question",
        construct_name="support",
        option_ids=["no", "yes"],
        profile=profile,
        normalize=True,
    )
    assert calibrated.sum(axis=1) == pytest.approx(np.ones(2))
    assert not np.allclose(calibrated, raw)
    event = calibrate_event_probabilities(
        np.asarray([0.2, 0.5, 0.8]),
        outcome_id="broad_awareness",
        profile=profile,
    )
    assert not np.allclose(event, [0.2, 0.5, 0.8])

    leaked_payload = dataset.model_dump(mode="json")
    for observation in leaked_payload["observations"][:-2]:
        observation["outcome_available_at"] = "2035-01-01T00:00:00Z"
    leaked = CalibrationDataset.model_validate(leaked_payload)
    with pytest.raises(ValueError, match="leakage-safe"):
        fit_calibration_profile(leaked)


def test_full_prediction_uses_every_agent_and_supports_feedback(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    request = example_prediction_request(paths=3)
    request = request.model_copy(
        update={
            "evaluation_protocol": request.evaluation_protocol.model_copy(
                update={"forecast_as_of": datetime(2026, 1, 15, tzinfo=UTC)}
            ),
            "event": request.event.model_copy(
                update={
                    "evidence": [
                        EvidenceItem(
                            evidence_id="available_before_lock",
                            summary="预测时点前已公开的信息",
                            available_at=datetime(2026, 1, 10, tzinfo=UTC),
                        ),
                        EvidenceItem(
                            evidence_id="future_outcome",
                            summary="预测时点后才会知道的结果",
                            available_at=datetime(2026, 2, 1, tzinfo=UTC),
                        ),
                    ],
                    "alternatives": [
                        *request.event.alternatives,
                        ScenarioVariant(
                            variant_id="same_as_event",
                            label="一致性校验：与事件方案完全相同",
                            intensity_multiplier=1,
                            credibility_shift=0,
                            value_signal_adjustments={},
                        ),
                    ],
                }
            ),
        }
    )
    result = run_prediction(request, settings)
    assert result.population.agent_count == 5_000
    assert result.population.agents_observed == 5_000
    assert result.population.agents_decided == 5_000
    assert result.population.agents_acted == 5_000
    assert result.population.agents_remembered == 5_000
    assert len(result.questionnaire_forecast) == 10
    assert [item.scenario_id for item in result.scenarios] == [
        "baseline_no_event",
        "event_as_described",
        "limited_capacity",
        "same_as_event",
    ]
    assert all(len(item.timeline) == 31 for item in result.scenarios)
    assert all(item.baseline.phase == "baseline" for item in result.questionnaire_forecast)
    assert all(item.post_event.phase == "post_event" for item in result.questionnaire_forecast)
    assert result.group_insights
    assert result.participant_receipts
    assert result.report_metadata is not None
    assert result.report_metadata.model_version == "questionnaire-event-swm-v3"
    assert result.report_metadata.successful_agents == 5_000
    assert result.report_metadata.failed_agents == 0
    assert result.report_quality is not None
    assert result.report_quality.failures == 0
    assert all(len(item.cross_tabs) == 6 for item in result.questionnaire_forecast)
    assert all(
        1 <= len(item.representative_responses) <= 3 for item in result.questionnaire_forecast
    )
    assert any(len(item.representative_responses) == 3 for item in result.questionnaire_forecast)
    assert {item.group_label for item in result.questionnaire_forecast[0].cross_tabs} == {
        "年龄",
        "性别",
        "社会角色",
        "单位类型",
        "教育背景",
        "主要信息渠道",
    }
    assert all(
        response.synthetic for response in result.questionnaire_forecast[0].representative_responses
    )
    assert result.l2_evaluation is not None
    assert result.l2_evaluation.common_random_numbers is True
    assert result.l2_evaluation.protocol_lock.excluded_evidence_ids == ["future_outcome"]
    assert result.l2_evaluation.protocol_lock.metric_ids == [
        "support",
        "awareness",
        "polarization",
    ]
    event_forecast = next(
        item for item in result.scenarios if item.scenario_id == "event_as_described"
    )
    identical_forecast = next(
        item for item in result.scenarios if item.scenario_id == "same_as_event"
    )
    assert identical_forecast.timeline == event_forecast.timeline
    assert any("两项干预目前不可区分" in item for item in result.l2_evaluation.warnings)
    replay = verify_prediction_replay(result.run_id, settings)
    assert replay["valid"] is True
    assert replay["record_count"] == 360
    replay_records = [
        json.loads(line)
        for line in Path(result.artifacts.replay_log).read_text(encoding="utf-8").splitlines()
    ]
    baseline_tick = next(
        item
        for item in replay_records
        if item["scenario_id"] == "baseline_no_event" and item["path"] == 0 and item["tick"] == 1
    )
    event_tick = next(
        item
        for item in replay_records
        if item["scenario_id"] == "event_as_described" and item["path"] == 0 and item["tick"] == 1
    )
    assert baseline_tick["visibility_counts"]["cumulative_exposed"] == 0
    assert baseline_tick["visibility_counts"]["unexposed"] == 5_000
    assert 0 < event_tick["visibility_counts"]["cumulative_exposed"] < 5_000

    individual_path = Path(result.artifacts.individual_predictions)
    assert pq.read_table(individual_path).num_rows == 100_000
    loaded = load_prediction(result.run_id, settings)
    assert loaded.deterministic_signature == result.deterministic_signature
    assert list_predictions(settings)[0]["run_id"] == result.run_id
    assert prediction_export_path(result.run_id, "json", settings).exists()
    assert prediction_export_path(result.run_id, "csv", settings).exists()
    with pytest.raises(ValueError, match="json or csv"):
        prediction_export_path(result.run_id, "xlsx", settings)

    outcome = submit_outcome(
        result.run_id,
        OutcomeSubmission(
            sample_size=200,
            questionnaire_results={
                "q03_stance": {"oppose": 0.2, "wait": 0.35, "support": 0.45},
                "q07_participation": 57,
            },
            event_outcomes={"broad_awareness": True},
            scenario_metrics={
                "baseline_no_event": {
                    "support": result.scenarios[0].timeline[-1].metrics["support"].p50
                },
                "event_as_described": {
                    "support": result.scenarios[1].timeline[-1].metrics["support"].p50
                },
            },
        ),
        settings,
    )
    assert outcome["evaluation"]["matched_values"] == 7
    assert outcome["evaluation"]["mean_squared_error"] is not None
    assert outcome["evaluation"]["scenario_assessment"]["interval_coverage_80"] == 1
    assert outcome["evaluation"]["scenario_assessment"]["top_1_match"] is True
    assert outcome["evaluation"]["scenario_assessment"]["direction_accuracy"] == 1
    assert outcome["calibration_observations_appended"] == 4

    repeated = run_prediction(request, settings)
    assert repeated.deterministic_signature == result.deterministic_signature
