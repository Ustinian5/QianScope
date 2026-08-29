import type { AIExecutionMetadata } from '@/lib/types';

export type ProbabilityBand = { p10: number; p50: number; p90: number };

export type OptionEstimate = {
  option_id: string;
  label: string;
  probability: ProbabilityBand;
  predicted_rank?: number | null;
};

export type QuestionSnapshot = {
  phase: string;
  options: OptionEstimate[];
  numeric_value?: ProbabilityBand | null;
  themes: Array<{
    theme: string;
    share: ProbabilityBand;
    representative_answer: string;
  }>;
};

export type QuestionForecast = {
  question_id: string;
  question_text: string;
  kind: string;
  baseline: QuestionSnapshot;
  post_event: QuestionSnapshot;
  change_summary: string;
  group_differences: Array<{
    group_field: string;
    group_label?: string;
    group_value: string;
    group_value_label?: string;
    agent_count: number;
    represented_population?: number;
    leading_answer: string;
    probability: number;
    delta_vs_overall: number;
  }>;
  cross_tabs?: Array<{
    group_field: string;
    group_label: string;
    response_type: 'distribution' | 'numeric_mean';
    rows: Array<{
      group_value: string;
      group_value_label: string;
      agent_count: number;
      represented_population: number;
      weighted_share: number;
      response_distribution: Record<string, number>;
      leading_answer: string;
    }>;
  }>;
  representative_responses?: Array<{
    persona_id: string;
    persona_label: string;
    role: string;
    organization_type: string;
    segment: string;
    predicted_answer: string;
    answer: string;
    confidence: number;
    represented_weight: number;
    basis: string[];
    synthetic: true;
  }>;
  key_drivers: string[];
  missingness?: number;
  out_of_distribution: boolean;
};

export type ScenarioForecast = {
  scenario_id: string;
  label: string;
  timeline: Array<{ tick: number; metrics: Record<string, ProbabilityBand> }>;
  final_actions: Record<string, ProbabilityBand>;
  downstream_outcomes: Array<{
    outcome_id: string;
    label: string;
    probability: ProbabilityBand;
    likely_tick?: ProbabilityBand | null;
  }>;
};

export type CounterfactualEffect = {
  scenario_id: string;
  scenario_label: string;
  metric_id: string;
  metric_label: string;
  direction: 'increase' | 'decrease';
  weight: number;
  baseline_value: ProbabilityBand;
  scenario_value: ProbabilityBand;
  paired_delta: ProbabilityBand;
  direction_consistency: number;
  cod_score: number;
  effect_detected: boolean;
};

export type ConstrainedL2Evaluation = {
  capability_level: 'constrained_l2';
  baseline_scenario_id: string;
  common_random_numbers: boolean;
  protocol_lock: {
    forecast_as_of: string;
    horizon_ticks: number;
    scenario_ids: string[];
    metric_ids: string[];
    baseline_scenario_id: string;
    future_information_forbidden: boolean;
    excluded_evidence_ids: string[];
    untimestamped_evidence_ids: string[];
    input_signature: string;
  };
  scenario_ranking: Array<{
    scenario_id: string;
    label: string;
    rank: number;
    decision_score: number;
    primary_metric_value: ProbabilityBand;
    primary_metric_delta: ProbabilityBand;
  }>;
  effects: CounterfactualEffect[];
  cod_score: number;
  cod_interpretation: string;
  warnings: string[];
};

export type PredictionResult = {
  run_id: string;
  project_id: string;
  title: string;
  created_at: string;
  conclusion: string;
  population: {
    population_id: string;
    agent_count: number;
    tier_counts: Record<string, number>;
    relationship_count: number;
    agents_observed: number;
    agents_decided: number;
    agents_acted: number;
    agents_remembered: number;
    represented_population?: number | null;
    effective_sample_size?: number | null;
  };
  grounding: {
    status: string;
    population_margin_id?: string | null;
    source?: string | null;
    covered_fields: string[];
    converged?: boolean | null;
    design_effect?: number | null;
    warnings: string[];
  };
  calibration: {
    status: string;
    calibration_id?: string | null;
    dataset_id?: string | null;
    training_records: number;
    holdout_records: number;
    holdout_brier_before?: number | null;
    holdout_brier_after?: number | null;
    applied: boolean;
    warnings: string[];
  };
  report_metadata?: {
    model_version: string;
    data_version: string;
    seed: number;
    paths: number;
    horizon_ticks: number;
    scenario_count: number;
    requested_agents: number;
    successful_agents: number;
    failed_agents: number;
    represented_population: number;
    effective_sample_size: number;
    population_source: string;
    weighting_method: string;
    interval_definition: string;
    calibration_status: string;
    profile_signature: string;
  } | null;
  report_quality?: {
    status: 'pass' | 'warning' | 'fail';
    passed: number;
    warnings: number;
    failures: number;
    checks: Array<{
      check_id: string;
      label: string;
      status: 'pass' | 'warning' | 'fail';
      observed: string;
      expected: string;
      detail: string;
    }>;
  } | null;
  questionnaire_forecast: QuestionForecast[];
  group_insights: string[];
  scenarios: ScenarioForecast[];
  l2_evaluation?: ConstrainedL2Evaluation | null;
  key_drivers: string[];
  uncertainty: string[];
  limitations: string[];
  participant_receipts: Array<{
    agent_id: string;
    tier: string;
    segment: string;
    final_action: string;
    response_summary: string;
    top_drivers: string[];
  }>;
  semantic_interpretation: {
    method: string;
    summary: string;
    confidence: string;
    missing_inputs: string[];
  };
  ai_execution: AIExecutionMetadata[];
  deterministic_signature: string;
  disclaimer: string;
};
