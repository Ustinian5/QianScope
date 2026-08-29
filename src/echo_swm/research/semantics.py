from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echo_swm.agents.llm_adapter import OpenAICompatibleLLM
from echo_swm.core.config import Settings
from echo_swm.core.ids import new_id
from echo_swm.research.contracts import EventScenario

VALUE_DIMENSIONS = ("care", "fairness", "security", "tradition", "autonomy", "community")


class EventInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["explicit", "llm_compiled", "lexical_fallback"]
    summary: str
    value_signals: dict[str, float]
    valence: float = Field(ge=-1, le=1)
    confidence: Literal["low", "medium", "high"]
    detected_concepts: list[str]
    missing_inputs: list[str]

    @field_validator("value_signals")
    @classmethod
    def valid_signals(cls, value: dict[str, float]) -> dict[str, float]:
        if set(value) != set(VALUE_DIMENSIONS):
            raise ValueError(f"value_signals must contain exactly {VALUE_DIMENSIONS}")
        if any(item < -1 or item > 1 for item in value.values()):
            raise ValueError("value signals must be within [-1, 1]")
        return value


class _LLMInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    value_signals: dict[str, float]
    valence: float = Field(ge=-1, le=1)
    detected_concepts: list[str]
    confidence: Literal["low", "medium", "high"]
    missing_inputs: list[str]

    @field_validator("value_signals")
    @classmethod
    def valid_signals(cls, value: dict[str, float]) -> dict[str, float]:
        normalized = {dimension: float(value.get(dimension, 0)) for dimension in VALUE_DIMENSIONS}
        if any(item < -1 or item > 1 for item in normalized.values()):
            raise ValueError("value signals must be within [-1, 1]")
        return normalized


_CONCEPT_TERMS: dict[str, tuple[str, ...]] = {
    "care": ("照护", "健康", "福祉", "伤害", "care", "health", "welfare", "harm"),
    "fairness": ("公平", "平等", "机会", "歧视", "fair", "equal", "access", "bias"),
    "security": ("安全", "风险", "保护", "稳定", "safe", "risk", "protect", "stable"),
    "tradition": ("传统", "习惯", "历史", "延续", "tradition", "custom", "heritage"),
    "autonomy": ("自主", "选择", "自由", "隐私", "choice", "freedom", "privacy", "autonomy"),
    "community": ("社区", "共同", "邻里", "公共", "community", "shared", "public", "local"),
}
_POSITIVE_TERMS = (
    "改善",
    "提升",
    "开放",
    "支持",
    "便利",
    "benefit",
    "improve",
    "support",
    "enable",
)
_NEGATIVE_TERMS = (
    "取消",
    "限制",
    "关闭",
    "削减",
    "风险",
    "ban",
    "restrict",
    "close",
    "reduce",
    "harm",
)


def _lexical_interpretation(event: EventScenario) -> EventInterpretation:
    text = f"{event.title} {event.description}".lower()
    signals: dict[str, float] = {}
    detected: list[str] = []
    positive = sum(text.count(term) for term in _POSITIVE_TERMS)
    negative = sum(text.count(term) for term in _NEGATIVE_TERMS)
    polarity = (positive - negative) / max(1, positive + negative)
    for dimension, terms in _CONCEPT_TERMS.items():
        count = sum(text.count(term) for term in terms)
        if count:
            detected.append(dimension)
        signals[dimension] = float(max(-1, min(1, count * 0.22 * (polarity or 0.35))))
    supplied_valence = event.valence
    valence = supplied_valence if supplied_valence != 0 else float(0.45 * polarity)
    missing = []
    if not detected:
        missing.append("事件描述未明确触及可识别的价值维度")
    if not event.evidence:
        missing.append("未提供外部证据或历史基准")
    return EventInterpretation(
        method="lexical_fallback",
        summary="依据事件文本中的通用价值与影响词进行结构化解释。",
        value_signals=signals,
        valence=valence,
        confidence="medium" if detected else "low",
        detected_concepts=detected,
        missing_inputs=missing,
    )


def interpret_event(
    event: EventScenario,
    settings: Settings,
    *,
    llm: OpenAICompatibleLLM | None = None,
) -> EventInterpretation:
    if settings.llm_configured:
        active_llm = llm or OpenAICompatibleLLM(settings)
        variation_id = new_id("variation")
        compiled = active_llm.complete_json(
            (
                "You compile an arbitrary social event into neutral numeric semantics for a "
                "simulation. Do not predict outcomes and do not invent evidence. Return JSON "
                "only. value_signals must contain care, fairness, security, tradition, autonomy, "
                "and community, each within [-1, 1]. valence is the likely direct perceived "
                "benefit/harm direction, not the forecast. Explicit user-provided value_signals "
                "and evidence are binding inputs and must be respected. Mark missing evidence "
                "explicitly. The variation_id is a diversity cue for a fresh interpretation, but "
                "all changes must remain conservative and supported by the supplied text."
            ),
            json.dumps(
                {
                    "variation_id": variation_id,
                    "event": event.model_dump(mode="json"),
                },
                ensure_ascii=False,
            ),
            _LLMInterpretation,
            max_output_tokens=1_200,
            temperature=0.85,
            cache=False,
            operation="research_event_interpretation",
            variation_id=variation_id,
        )
        return EventInterpretation(method="llm_compiled", **compiled.model_dump())
    if event.value_signals:
        normalized = {
            dimension: float(event.value_signals.get(dimension, 0))
            for dimension in VALUE_DIMENSIONS
        }
        return EventInterpretation(
            method="explicit",
            summary="使用请求中明确给出的价值影响方向。",
            value_signals=normalized,
            valence=event.valence,
            confidence="high",
            detected_concepts=[key for key, value in normalized.items() if value != 0],
            missing_inputs=[] if event.evidence else ["未提供外部证据或历史基准"],
        )
    return _lexical_interpretation(event)
