export type RuntimeHealth = {
  status: string;
  version: string;
  llm_configured: boolean;
  statistical_runtime_ready: boolean;
  city_runtime_ready: boolean;
  event_forecast_runtime_ready: boolean;
};

export type DistributionBand = {
  p10: number;
  p50: number;
  p90: number;
  mean: number;
  standard_deviation: number;
};

export type DailyEventProbability = {
  day: number;
  first_occurrence_probability: number;
  cumulative_probability: number;
};

export type CandidateEventForecast = {
  candidate_id: string;
  event_type: string;
  label: string;
  occurrence_probability: number;
  probability_curve: DailyEventProbability[];
  conditional_time_to_event_days: DistributionBand | null;
  severity_if_occurred: DistributionBand | null;
  leading_evidence: Array<{ signal_id: string; log_odds_contribution: number }>;
  baseline_origin: string;
  out_of_distribution: boolean;
};

export type EventBranchForecast = {
  branch_id: string;
  candidates: CandidateEventForecast[];
  final_metric_deltas: Record<string, DistributionBand>;
  top_event_chains: Array<{ event_sequence: string[]; probability: number }>;
  expected_intervention_cost: number;
};

export type EventForecast = {
  run_id: string;
  model_version: string;
  query: {
    query_id: string;
    domain: string;
    horizon_days: number;
    samples: number;
    random_seed: number;
  };
  branches: Record<string, EventBranchForecast>;
  counterfactual_probability_deltas: Record<string, Record<string, number>>;
  calibration_status: string;
  assumptions: string[];
  warnings: string[];
  disclaimer: string;
};

export type EventForecastResponse = {
  status: string;
  summary: {
    run_id: string;
    model_version: string;
    domain: string;
    candidate_probabilities: Record<string, Record<string, number>>;
    counterfactual_probability_deltas: Record<string, Record<string, number>>;
    calibration_status: string;
    replay: ReplayVerification;
  };
  forecast: EventForecast;
};

export type ReplayVerification = {
  run_id: string;
  valid: boolean;
  records_valid?: boolean;
  path_file_valid?: boolean;
  snapshots_valid?: boolean;
  record_count: number;
  expected_record_count?: number;
  expected_tick_count?: number;
  snapshot_count?: number;
  verified_snapshot_count?: number;
};

export type CityMetricPoint = {
  day: number;
  metrics: Record<string, DistributionBand>;
};

export type CityDistrictMetric = {
  branch_id: string;
  district_id: string;
  district_name: string;
  represented_population: number;
  metrics: Record<string, DistributionBand>;
};

export type CityForecast = {
  run_id: string;
  query_id: string;
  city_id: string;
  model_version: string;
  data_version: string;
  prototype_count: number;
  represented_population: number;
  represented_scope_population: number;
  branch_trajectories: Record<string, CityMetricPoint[]>;
  final_district_metrics: CityDistrictMetric[];
  counterfactual_deltas: Record<string, Record<string, number>>;
  assumptions: string[];
  warnings: string[];
  disclaimer: string;
};

export type CitySimulationResponse = {
  status: string;
  summary: {
    run_id: string;
    model_version: string;
    prototype_count: number;
    represented_population: number;
    branches: string[];
    counterfactual_deltas: Record<string, Record<string, number>>;
    replay: ReplayVerification;
  };
  forecast: CityForecast;
};

export type RunKind = 'event' | 'city' | 'statistical';

export type RunRecord = {
  id: string;
  kind: RunKind;
  label: string;
  model: string;
  createdAt: string;
  scope: string;
  status: 'verified' | 'snapshot';
  calibration: string;
  stats: Array<{ label: string; value: string }>;
};
