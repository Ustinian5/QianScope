from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from echo_swm import DISCLAIMER
from echo_swm.ai.contracts import AIExecutionMetadata
from echo_swm.core.ids import new_id, stable_hash
from echo_swm.event_forecasting.contracts import (
    BaselineOrigin,
    BranchEventForecast,
    CandidateEventForecast,
    ComparisonOperator,
    DailyEventProbability,
    DistributionBand,
    EventChainForecast,
    EventForecastBranch,
    EventForecastQuery,
    EventForecastResult,
    EventHypothesis,
)

MODEL_VERSION = "echo-event-hazard-chain-v1"


@dataclass(frozen=True)
class BranchPaths:
    occurrence_days: NDArray[np.int16]
    severities: NDArray[np.float64]
    final_metrics: dict[str, NDArray[np.float64]]


def _sigmoid(value: NDArray[np.float64]) -> NDArray[np.float64]:
    clipped = np.clip(value, -30, 30)
    return 1 / (1 + np.exp(-clipped))


def _logit(probability: float) -> float:
    return float(np.log(probability / (1 - probability)))


def _band(values: NDArray[np.float64]) -> DistributionBand:
    return DistributionBand(
        p10=float(np.quantile(values, 0.10)),
        p50=float(np.quantile(values, 0.50)),
        p90=float(np.quantile(values, 0.90)),
        mean=float(np.mean(values)),
        standard_deviation=float(np.std(values)),
    )


def _condition(
    values: NDArray[np.float64], operator: ComparisonOperator, threshold: float
) -> NDArray[np.bool_]:
    if operator == ComparisonOperator.LESS_THAN:
        return values < threshold
    if operator == ComparisonOperator.LESS_OR_EQUAL:
        return values <= threshold
    if operator == ComparisonOperator.GREATER_THAN:
        return values > threshold
    return values >= threshold


def _signal_contributions(
    query: EventForecastQuery,
    candidate: EventHypothesis,
    day: int,
) -> list[tuple[str, float]]:
    contributions: list[tuple[str, float]] = []
    for rule in candidate.signal_rules:
        for signal in query.signals:
            if rule.signal_tag not in signal.tags:
                continue
            age_at_forecast = (query.as_of - signal.observed_at).total_seconds() / 86_400
            effective_age = max(0.0, age_at_forecast + day - rule.minimum_lag_days)
            if age_at_forecast + day < rule.minimum_lag_days:
                continue
            decay = 2 ** (-effective_age / rule.half_life_days)
            contribution = (
                signal.standardized_value
                * signal.reliability
                * rule.log_odds_per_standard_deviation
                * decay
            )
            contributions.append((signal.signal_id, float(contribution)))
    return contributions


def _targets_candidate(intervention: Any, candidate: EventHypothesis) -> bool:
    no_selector = not (
        intervention.target_candidate_ids
        or intervention.target_event_types
        or intervention.target_tags
    )
    return bool(
        no_selector
        or candidate.candidate_id in intervention.target_candidate_ids
        or candidate.event_type in intervention.target_event_types
        or set(candidate.tags) & set(intervention.target_tags)
    )


def _active_interventions(branch: EventForecastBranch, day: int) -> list[Any]:
    return [
        intervention
        for intervention in branch.interventions
        if intervention.start_day <= day < intervention.start_day + intervention.duration_days
    ]


def _metric_names(query: EventForecastQuery) -> tuple[str, ...]:
    names = set(query.initial_metrics)
    for candidate in query.candidates:
        names.update(rule.metric for rule in candidate.state_rules)
        names.update(impact.metric for impact in candidate.impacts)
    for branch in query.branches:
        for intervention in branch.interventions:
            names.update(intervention.metric_shifts)
    return tuple(sorted(names))


def _simulate_branch(
    query: EventForecastQuery,
    branch: EventForecastBranch,
    uniforms: NDArray[np.float64],
    intercept_noise: NDArray[np.float64],
    severity_noise: NDArray[np.float64],
    impact_noise: NDArray[np.float64],
    metric_names: tuple[str, ...],
) -> BranchPaths:
    sample_count = query.samples
    candidate_count = len(query.candidates)
    occurrence_days = np.full((sample_count, candidate_count), -1, dtype=np.int16)
    severities = np.full((sample_count, candidate_count), np.nan, dtype=float)
    metric_index = {name: index for index, name in enumerate(metric_names)}
    active_impacts = np.zeros((sample_count, candidate_count, len(metric_names)), dtype=float)
    base_metrics = {
        metric: np.full(sample_count, query.initial_metrics.get(metric, 0.0), dtype=float)
        for metric in metric_names
    }
    final_metrics: dict[str, NDArray[np.float64]] = {
        metric: np.asarray(values.copy(), dtype=np.float64)
        for metric, values in base_metrics.items()
    }
    candidate_index = {
        candidate.candidate_id: index for index, candidate in enumerate(query.candidates)
    }

    for day in range(1, query.horizon_days + 1):
        interventions = _active_interventions(branch, day)
        intervention_metric_shifts = {
            metric: sum(
                intervention.metric_shifts.get(metric, 0.0) for intervention in interventions
            )
            for metric in metric_names
        }
        current_metrics = {
            metric: base_metrics[metric]
            + active_impacts[:, :, metric_index[metric]].sum(axis=1)
            + intervention_metric_shifts[metric]
            for metric in metric_names
        }

        for index, candidate in enumerate(query.candidates):
            log_odds = np.full(
                sample_count,
                _logit(candidate.baseline_daily_hazard),
                dtype=float,
            )
            log_odds += intercept_noise[:, index]
            log_odds += sum(
                contribution for _, contribution in _signal_contributions(query, candidate, day)
            )
            for state_rule in candidate.state_rules:
                applies = _condition(
                    current_metrics[state_rule.metric],
                    state_rule.operator,
                    state_rule.threshold,
                )
                log_odds += state_rule.log_odds_shift * applies
            for parent_rule in candidate.parent_rules:
                parent_day = occurrence_days[:, candidate_index[parent_rule.parent_candidate_id]]
                lag = day - parent_day
                applies = (
                    (parent_day >= 0)
                    & (lag >= parent_rule.minimum_lag_days)
                    & (lag <= parent_rule.maximum_lag_days)
                )
                decay = np.where(
                    applies,
                    2
                    ** (
                        -np.maximum(lag - parent_rule.minimum_lag_days, 0)
                        / parent_rule.half_life_days
                    ),
                    0.0,
                )
                log_odds += parent_rule.log_odds_shift * decay
            for intervention in interventions:
                if _targets_candidate(intervention, candidate):
                    log_odds += intervention.hazard_log_odds_shift

            latest = candidate.latest_day or query.horizon_days
            eligible = (
                (occurrence_days[:, index] < 0) & (day >= candidate.earliest_day) & (day <= latest)
            )
            occurs = eligible & (uniforms[:, day - 1, index] < _sigmoid(log_odds))
            occurrence_days[occurs, index] = day
            severity = np.clip(
                candidate.severity_mean
                + candidate.severity_standard_deviation * severity_noise[:, index],
                0,
                1,
            )
            severities[occurs, index] = severity[occurs]
            for impact in candidate.impacts:
                amplitude = (
                    impact.mean_delta
                    + impact.standard_deviation
                    * impact_noise[:, index, metric_index[impact.metric]]
                ) * (0.5 + severity)
                if impact.lower_bound is not None:
                    amplitude = np.maximum(amplitude, impact.lower_bound)
                if impact.upper_bound is not None:
                    amplitude = np.minimum(amplitude, impact.upper_bound)
                active_impacts[occurs, index, metric_index[impact.metric]] = amplitude[occurs]

        final_metrics = {
            metric: np.asarray(
                base_metrics[metric]
                + active_impacts[:, :, metric_index[metric]].sum(axis=1)
                + intervention_metric_shifts[metric],
                dtype=np.float64,
            )
            for metric in metric_names
        }
        if day < query.horizon_days:
            for index, candidate in enumerate(query.candidates):
                for impact in candidate.impacts:
                    active_impacts[:, index, metric_index[impact.metric]] *= 2 ** (
                        -1 / impact.half_life_days
                    )
    return BranchPaths(
        occurrence_days=occurrence_days,
        severities=severities,
        final_metrics=final_metrics,
    )


def _candidate_forecast(
    query: EventForecastQuery,
    candidate: EventHypothesis,
    index: int,
    paths: BranchPaths,
) -> CandidateEventForecast:
    occurrence = paths.occurrence_days[:, index]
    occurred = occurrence >= 0
    curve = [
        DailyEventProbability(
            day=day,
            first_occurrence_probability=float(np.mean(occurrence == day)),
            cumulative_probability=float(np.mean((occurrence >= 0) & (occurrence <= day))),
        )
        for day in range(1, query.horizon_days + 1)
    ]
    times = occurrence[occurred].astype(float)
    severities = paths.severities[occurred, index]
    contributions = _signal_contributions(query, candidate, 1)
    evidence: list[dict[str, float | str]] = [
        {"signal_id": signal_id, "log_odds_contribution": contribution}
        for signal_id, contribution in sorted(
            contributions,
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:10]
    ]
    matched_signal_count = len({signal_id for signal_id, _ in contributions})
    return CandidateEventForecast(
        candidate_id=candidate.candidate_id,
        event_type=candidate.event_type,
        label=candidate.label,
        occurrence_probability=float(np.mean(occurred)),
        probability_curve=curve,
        conditional_time_to_event_days=_band(times) if times.size else None,
        severity_if_occurred=_band(severities) if severities.size else None,
        leading_evidence=evidence,
        baseline_origin=candidate.baseline_origin,
        out_of_distribution=(
            candidate.baseline_origin in {BaselineOrigin.UNKNOWN, BaselineOrigin.SYNTHETIC}
            or (bool(candidate.signal_rules) and matched_signal_count == 0)
        ),
    )


def _event_chains(
    query: EventForecastQuery,
    paths: BranchPaths,
    *,
    limit: int = 10,
) -> list[EventChainForecast]:
    counts: Counter[tuple[str, ...]] = Counter()
    candidate_ids = [candidate.candidate_id for candidate in query.candidates]
    for sample_days in paths.occurrence_days:
        ordered = sorted(
            (
                (int(day), index, candidate_ids[index])
                for index, day in enumerate(sample_days)
                if day >= 0
            ),
            key=lambda item: (item[0], item[1]),
        )
        sequence = tuple(item[2] for item in ordered)
        if sequence:
            counts[sequence] += 1
    return [
        EventChainForecast(
            event_sequence=list(sequence),
            probability=count / query.samples,
        )
        for sequence, count in counts.most_common(limit)
    ]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_event_forecast(
    query: EventForecastQuery,
    artifact_root: Path,
    ai_execution: list[AIExecutionMetadata] | None = None,
) -> EventForecastResult:
    run_id = new_id("eventrun")
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(query.random_seed)
    candidate_count = len(query.candidates)
    metric_names = _metric_names(query)
    uniforms = rng.random((query.samples, query.horizon_days, candidate_count))
    intercept_noise = rng.normal(0, 0.18, (query.samples, candidate_count))
    severity_noise = rng.normal(0, 1, (query.samples, candidate_count))
    impact_noise = rng.normal(
        0,
        1,
        (query.samples, candidate_count, len(metric_names)),
    )
    branch_paths: dict[str, BranchPaths] = {}
    branches: dict[str, BranchEventForecast] = {}
    probability_rows: list[dict[str, Any]] = []

    for branch in query.branches:
        paths = _simulate_branch(
            query,
            branch,
            uniforms,
            intercept_noise,
            severity_noise,
            impact_noise,
            metric_names,
        )
        branch_paths[branch.branch_id] = paths
        candidate_forecasts = [
            _candidate_forecast(query, candidate, index, paths)
            for index, candidate in enumerate(query.candidates)
        ]
        for candidate in candidate_forecasts:
            probability_rows.extend(
                {
                    "branch_id": branch.branch_id,
                    "candidate_id": candidate.candidate_id,
                    **point.model_dump(),
                }
                for point in candidate.probability_curve
            )
        metric_deltas = {
            metric: _band(values - query.initial_metrics.get(metric, 0.0))
            for metric, values in paths.final_metrics.items()
        }
        cost = sum(
            intervention.estimated_cost
            for intervention in branch.interventions
            if intervention.start_day <= query.horizon_days
        )
        branches[branch.branch_id] = BranchEventForecast(
            branch_id=branch.branch_id,
            candidates=candidate_forecasts,
            final_metric_deltas=metric_deltas,
            top_event_chains=_event_chains(query, paths),
            expected_intervention_cost=cost,
        )

    control_id = query.branches[0].branch_id
    control_probabilities = {
        item.candidate_id: item.occurrence_probability for item in branches[control_id].candidates
    }
    counterfactual = {
        branch_id: {
            item.candidate_id: item.occurrence_probability
            - control_probabilities[item.candidate_id]
            for item in forecast.candidates
        }
        for branch_id, forecast in branches.items()
        if branch_id != control_id
    }
    has_historical_baselines = all(
        candidate.baseline_origin == BaselineOrigin.HISTORICAL
        and candidate.baseline_sample_size > 0
        for candidate in query.candidates
    )
    calibration_status = (
        "historical_base_rates_not_yet_outcome_calibrated"
        if has_historical_baselines
        else "prior_predictive_uncalibrated"
    )
    warnings = [
        "Event probabilities are conditional on the supplied candidates, base rates, signals, "
        "and mechanism weights.",
        "Candidate omission can dominate forecast error; absence from this forecast does not "
        "mean impossibility.",
        "Probability calibration requires temporally held-out historical outcomes for the "
        "target domain.",
        "Intervention deltas use common random numbers and are model-based counterfactuals, "
        "not identified causal effects.",
    ]
    result = EventForecastResult(
        run_id=run_id,
        model_version=MODEL_VERSION,
        query=query,
        branches=branches,
        counterfactual_probability_deltas=counterfactual,
        calibration_status=calibration_status,
        artifact_dir=str(run_dir.resolve()),
        ai_execution=ai_execution or [],
        assumptions=[
            "Daily hazards are piecewise discrete and each candidate can first occur at most once.",
            "Known signals decay exponentially; parent events change descendant log odds "
            "within explicit lag windows.",
            "Event impacts decay exponentially and may alter downstream state-condition hazards.",
        ],
        warnings=warnings,
        disclaimer=DISCLAIMER,
    )
    (run_dir / "forecast.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    with (run_dir / "probability_curves.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(probability_rows[0]))
        writer.writeheader()
        writer.writerows(probability_rows)

    path_file = run_dir / "event_paths.npz"
    final_metric_paths = [
        np.column_stack([paths.final_metrics[name] for name in metric_names])
        if metric_names
        else np.empty((query.samples, 0), dtype=np.float64)
        for paths in branch_paths.values()
    ]
    np.savez_compressed(
        path_file,
        branch_ids=np.asarray(list(branch_paths)),
        candidate_ids=np.asarray([candidate.candidate_id for candidate in query.candidates]),
        metric_names=np.asarray(metric_names),
        occurrence_days=np.stack([paths.occurrence_days for paths in branch_paths.values()]),
        severities=np.stack([paths.severities for paths in branch_paths.values()]),
        final_metrics=np.stack(final_metric_paths),
    )
    replay_path = run_dir / "replay.jsonl"
    with replay_path.open("w", encoding="utf-8") as handle:
        for branch_id, paths in branch_paths.items():
            for day in range(1, query.horizon_days + 1):
                row = {
                    "branch_id": branch_id,
                    "day": day,
                    "first_occurrence_counts": {
                        query.candidates[index].candidate_id: int(
                            np.sum(paths.occurrence_days[:, index] == day)
                        )
                        for index in range(candidate_count)
                    },
                    "cumulative_counts": {
                        query.candidates[index].candidate_id: int(
                            np.sum(
                                (paths.occurrence_days[:, index] >= 0)
                                & (paths.occurrence_days[:, index] <= day)
                            )
                        )
                        for index in range(candidate_count)
                    },
                }
                row["record_hash"] = stable_hash(row)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "run_id": run_id,
        "model_version": MODEL_VERSION,
        "query_hash": stable_hash(query.model_dump(mode="json")),
        "root_seed": query.random_seed,
        "samples": query.samples,
        "horizon_days": query.horizon_days,
        "branch_count": len(query.branches),
        "candidate_count": candidate_count,
        "ai_execution": [item.model_dump(mode="json") for item in (ai_execution or [])],
        "path_file_sha256": _file_sha256(path_file),
        "forecast_hash": stable_hash(result.model_dump(mode="json")),
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def verify_event_replay(run_dir: Path) -> dict[str, Any]:
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (run_dir / "replay.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    expected = manifest["branch_count"] * manifest["horizon_days"]
    hashes_valid = all(record.pop("record_hash", None) == stable_hash(record) for record in records)
    path_hash = _file_sha256(run_dir / "event_paths.npz")
    return {
        "run_id": manifest["run_id"],
        "record_count": len(records),
        "expected_record_count": expected,
        "records_valid": len(records) == expected and hashes_valid,
        "path_file_valid": path_hash == manifest["path_file_sha256"],
        "valid": len(records) == expected
        and hashes_valid
        and path_hash == manifest["path_file_sha256"],
    }
