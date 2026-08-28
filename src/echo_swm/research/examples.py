from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from echo_swm.research.calibration import (
    CalibrationDataset,
    CalibrationObservation,
    CalibrationTargetType,
)
from echo_swm.research.contracts import (
    EventScenario,
    PopulationSpec,
    PredictionRequest,
    QuestionKind,
    Questionnaire,
    QuestionOption,
    ResearchQuestion,
    ScenarioVariant,
)
from echo_swm.research.grounding import MarginScale, PopulationMarginDataset


def _options(*items: tuple[str, str, float]) -> list[QuestionOption]:
    return [
        QuestionOption(option_id=option_id, label=label, position=position)
        for option_id, label, position in items
    ]


def example_questionnaire() -> Questionnaire:
    return Questionnaire(
        questionnaire_id="general_event_reaction_10q",
        title="通用事件反应问卷",
        description="覆盖知晓、态度、信任、传播、参与、顾虑与开放原因。",
        questions=[
            ResearchQuestion(
                question_id="q01_awareness",
                text="在事件发生后，你认为自己会多快注意到这件事？",
                kind=QuestionKind.SINGLE_CHOICE,
                construct="awareness",
                options=_options(
                    ("unlikely", "很可能不会注意", -1),
                    ("later", "过一段时间才注意", -0.25),
                    ("soon", "较快注意到", 0.5),
                    ("immediate", "几乎立即注意到", 1),
                ),
            ),
            ResearchQuestion(
                question_id="q02_attitude",
                text="你对这件事的总体态度如何？",
                kind=QuestionKind.SCALE,
                construct="support",
                scale_min=1,
                scale_max=5,
            ),
            ResearchQuestion(
                question_id="q03_stance",
                text="如果现在必须表态，你最可能选择哪一种？",
                kind=QuestionKind.SINGLE_CHOICE,
                construct="support",
                options=_options(
                    ("oppose", "反对", -1),
                    ("wait", "保持观望", 0),
                    ("support", "支持", 1),
                ),
            ),
            ResearchQuestion(
                question_id="q04_actions",
                text="你接下来可能采取哪些行动？（可多选）",
                kind=QuestionKind.MULTIPLE_CHOICE,
                construct="participation",
                options=_options(
                    ("ignore", "暂不行动", -0.8),
                    ("learn", "继续了解", -0.15),
                    ("discuss", "与他人讨论", 0.35),
                    ("participate", "实际参与", 1),
                ),
            ),
            ResearchQuestion(
                question_id="q05_concerns",
                text="请按你最在意的因素进行排序。",
                kind=QuestionKind.RANKING,
                construct="personal_impact",
                options=_options(
                    ("benefit", "实际收益", 0.8),
                    ("risk", "潜在风险", -0.8),
                    ("fairness", "是否公平", 0.35),
                    ("clarity", "信息是否清楚", 0),
                ),
            ),
            ResearchQuestion(
                question_id="q06_trust",
                text="你对事件相关信息的信任程度是多少？",
                kind=QuestionKind.SCALE,
                construct="trust",
                scale_min=1,
                scale_max=7,
            ),
            ResearchQuestion(
                question_id="q07_participation",
                text="你实际参与相关行动的可能性是多少（0—100）？",
                kind=QuestionKind.NUMERIC,
                construct="participation",
                scale_min=0,
                scale_max=100,
            ),
            ResearchQuestion(
                question_id="q08_sharing",
                text="你最可能如何传播这件事？",
                kind=QuestionKind.SINGLE_CHOICE,
                construct="sharing",
                options=_options(
                    ("silent", "不主动传播", -1),
                    ("private", "私下告诉熟人", 0),
                    ("public", "公开分享或讨论", 1),
                ),
            ),
            ResearchQuestion(
                question_id="q09_emotion",
                text="这件事最可能让你产生怎样的情绪？",
                kind=QuestionKind.SINGLE_CHOICE,
                construct="emotion",
                options=_options(
                    ("negative", "担忧或不满", -1),
                    ("neutral", "平静或无明显感觉", 0),
                    ("positive", "期待或认同", 1),
                ),
            ),
            ResearchQuestion(
                question_id="q10_reason",
                text="请简要说明你形成上述态度的主要原因。",
                kind=QuestionKind.OPEN_TEXT,
                construct="general_attitude",
            ),
        ],
    )


def example_prediction_request(*, paths: int = 8) -> PredictionRequest:
    return PredictionRequest(
        project_id="project_general_event_demo",
        title="公共学习空间开放事件预测",
        population=PopulationSpec(
            population_id="general_population_5000",
            name="通用成年人群",
            size=5_000,
            seed=2026,
        ),
        questionnaire=example_questionnaire(),
        event=EventScenario(
            event_id="event_learning_space",
            title="公共学习空间延长开放时间",
            description=(
                "一个公共学习空间宣布，下月起将开放时间延长至夜间，并提供线上预约、"
                "安静学习区和小组交流区。"
            ),
            actors=["空间运营团队", "现有使用者", "潜在使用者"],
            audience="可能使用或受该空间影响的人群",
            channels=["online", "community", "interpersonal"],
            intensity=0.68,
            credibility=0.78,
            valence=0.35,
            value_signals={
                "care": 0.25,
                "fairness": 0.2,
                "security": 0.1,
                "tradition": -0.1,
                "autonomy": 0.45,
                "community": 0.55,
            },
            expected_outcomes=["知晓", "态度", "讨论", "参与"],
            alternatives=[
                ScenarioVariant(
                    variant_id="limited_capacity",
                    label="替代情景：名额有限且信息不完整",
                    description="预约名额较少，且使用规则尚未充分说明。",
                    intensity_multiplier=0.8,
                    credibility_shift=-0.2,
                    value_signal_adjustments={"fairness": -0.35, "autonomy": -0.2},
                )
            ],
        ),
        horizon_ticks=30,
        paths=paths,
        seed=2026,
    )


def example_population_margins() -> PopulationMarginDataset:
    """A format example only; replace these synthetic targets with authorized aggregates."""
    return PopulationMarginDataset(
        dataset_id="example_authorized_population_margins",
        name="人口边际数据格式示例（合成目标）",
        source="repository_generated_synthetic_example",
        scope="通用成年人群格式示例；不得作为真实人口事实使用",
        observed_at=datetime(2025, 12, 31, tzinfo=UTC),
        available_at=datetime(2026, 1, 15, tzinfo=UTC),
        authorization_confirmed=True,
        deidentified_or_aggregate=True,
        scale=MarginScale.PROPORTION,
        target_population=100_000,
        margins={
            "age_group": {
                "18-24": 0.12,
                "25-34": 0.24,
                "35-44": 0.23,
                "45-59": 0.25,
                "60+": 0.16,
            },
            "region_type": {
                "urban_core": 0.31,
                "suburban": 0.32,
                "town": 0.22,
                "rural": 0.15,
            },
        },
        notes="仅用于演示导入格式；生产环境必须替换为有权使用的聚合数据。",
    )


def _calibrated_share(probability: float) -> float:
    clipped = min(1 - 1e-7, max(1e-7, probability))
    logit = math.log(clipped / (1 - clipped))
    return 1 / (1 + math.exp(-(logit / 1.4 + 0.35)))


def example_calibration_dataset() -> CalibrationDataset:
    """Leakage-safe synthetic history used to demonstrate the accepted history contract."""
    targets = [
        (CalibrationTargetType.QUESTION_OPTION, "q03_stance", "support", None, "support"),
        (CalibrationTargetType.QUESTION_OPTION, "q08_sharing", "public", None, "sharing"),
        (CalibrationTargetType.EVENT_OUTCOME, None, None, "broad_awareness", "unknown"),
        (CalibrationTargetType.EVENT_OUTCOME, None, None, "discussion_surge", "unknown"),
    ]
    start = datetime(2024, 1, 1, tzinfo=UTC)
    observations = []
    for index in range(48):
        target_type, question_id, option_id, outcome_id, construct = targets[index % len(targets)]
        probability = 0.12 + ((index * 17) % 71) / 100
        forecast_at = start + timedelta(days=index * 7)
        observations.append(
            CalibrationObservation(
                observation_id=f"example_observation_{index + 1:03d}",
                target_type=target_type,
                question_id=question_id,
                option_id=option_id,
                outcome_id=outcome_id,
                construct=construct,
                forecast_as_of=forecast_at,
                outcome_available_at=forecast_at + timedelta(days=2),
                predicted_probability=probability,
                observed_share=_calibrated_share(probability),
                sample_size=800 if target_type == CalibrationTargetType.QUESTION_OPTION else 1,
                horizon_ticks=30,
                source="repository_generated_synthetic_history",
                provenance={"example": "true"},
            )
        )
    return CalibrationDataset(
        dataset_id="example_historical_calibration",
        name="历史校准格式示例（合成记录）",
        source="repository_generated_synthetic_example",
        authorization_confirmed=True,
        deidentified_or_aggregate=True,
        observations=observations,
        notes="仅演示数据契约与时间留出流程；不代表任何真实调查或事件结果。",
    )
