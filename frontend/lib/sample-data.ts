import type {
  CandidateEventForecast,
  CityDistrictMetric,
  CityForecast,
  DistributionBand,
  EventForecast,
  RunRecord,
  RuntimeHealth,
} from './types';

const band = (value: number, spread = 0.02): DistributionBand => ({
  p10: Math.max(0, value - spread),
  p50: value,
  p90: value + spread,
  mean: value,
  standard_deviation: spread / 1.28,
});

const eventSpecs = [
  ['demand_downturn', 'market_demand_downturn', '需求进入显著下行', 0.5234375, 0.5234375, 14],
  ['production_adjustment', 'organizational_adjustment', '企业收缩生产与用工', 0.46728515625, 0.2470703125, 21],
  ['reputation_escalation', 'reputation_escalation', '负面叙事升级', 0.35205078125, 0.34130859375, 10],
  ['policy_support', 'policy_response', '纾困支持政策出台', 0.33984375, 0.56298828125, 25],
] as const;

function curve(finalProbability: number, horizon = 45) {
  const normalizer = 1 - Math.exp(-horizon / 17);
  return Array.from({ length: horizon }, (_, index) => {
    const cumulative = finalProbability * (1 - Math.exp(-(index + 1) / 17)) / normalizer;
    const previous = index === 0
      ? 0
      : finalProbability * (1 - Math.exp(-index / 17)) / normalizer;
    return {
      day: index + 1,
      first_occurrence_probability: cumulative - previous,
      cumulative_probability: cumulative,
    };
  });
}

function candidate(
  spec: (typeof eventSpecs)[number],
  branch: 'control' | 'early_response',
): CandidateEventForecast {
  const [candidateId, eventType, label, control, response, medianDay] = spec;
  const probability = branch === 'control' ? control : response;
  return {
    candidate_id: candidateId,
    event_type: eventType,
    label,
    occurrence_probability: probability,
    probability_curve: curve(probability),
    conditional_time_to_event_days: band(medianDay, 5),
    severity_if_occurred: band(candidateId === 'policy_support' ? 0.52 : 0.56, 0.13),
    leading_evidence: candidateId === 'demand_downturn'
      ? [{ signal_id: 'export_orders_momentum', log_odds_contribution: 0.91 }]
      : candidateId === 'reputation_escalation'
        ? [{ signal_id: 'negative_discussion_velocity', log_odds_contribution: 0.98 }]
        : [],
    baseline_origin: 'synthetic',
    out_of_distribution: true,
  };
}

export const sampleHealth: RuntimeHealth = {
  status: 'ok',
  version: '0.1.0',
  llm_configured: false,
  statistical_runtime_ready: true,
  city_runtime_ready: true,
  event_forecast_runtime_ready: true,
};

export const sampleEventForecast: EventForecast = {
  run_id: 'eventrun_99a449ac38cf4064',
  model_version: 'echo-event-hazard-chain-v1',
  query: {
    query_id: 'market_event_chain_45d',
    domain: 'market_and_organization',
    horizon_days: 45,
    samples: 2048,
    random_seed: 2026,
  },
  branches: {
    control: {
      branch_id: 'control',
      candidates: eventSpecs.map((spec) => candidate(spec, 'control')),
      final_metric_deltas: {},
      top_event_chains: [
        { event_sequence: ['demand_downturn', 'production_adjustment', 'policy_support'], probability: 0.126 },
        { event_sequence: ['reputation_escalation'], probability: 0.112 },
        { event_sequence: ['demand_downturn', 'reputation_escalation'], probability: 0.084 },
      ],
      expected_intervention_cost: 0,
    },
    early_response: {
      branch_id: 'early_response',
      candidates: eventSpecs.map((spec) => candidate(spec, 'early_response')),
      final_metric_deltas: {},
      top_event_chains: [
        { event_sequence: ['demand_downturn', 'policy_support'], probability: 0.182 },
        { event_sequence: ['policy_support'], probability: 0.141 },
      ],
      expected_intervention_cost: 20,
    },
  },
  counterfactual_probability_deltas: {
    early_response: {
      demand_downturn: 0,
      production_adjustment: -0.22021484375,
      reputation_escalation: -0.0107421875,
      policy_support: 0.22314453125,
    },
  },
  calibration_status: 'prior_predictive_uncalibrated',
  assumptions: [
    '候选事件在预测窗口内最多首次发生一次。',
    '已知信号与事件影响按显式半衰期衰减。',
    '反事实分支共享相同随机流。',
  ],
  warnings: ['当前示例使用合成基准率，尚未通过目标领域历史结果校准。'],
  disclaimer: '本结果为概率模拟与条件预测，不构成对现实结果的保证。',
};

const cityMetricNames = [
  'life_satisfaction',
  'government_trust',
  'economic_confidence',
  'consumption_index',
  'employment_rate',
  'congestion_index',
  'health_system_load',
  'rumor_belief',
  'stress',
  'organization_vitality',
] as const;

const initialMetrics: Record<(typeof cityMetricNames)[number], number> = {
  life_satisfaction: 0.513,
  government_trust: 0.668,
  economic_confidence: 0.577,
  consumption_index: 0.667,
  employment_rate: 0.932,
  congestion_index: 0.8,
  health_system_load: 0.65,
  rumor_belief: 0.139,
  stress: 0.383,
  organization_vitality: 0.82,
};

const terminalControl: typeof initialMetrics = {
  life_satisfaction: 0.005,
  government_trust: 0.169,
  economic_confidence: 0.263,
  consumption_index: 0.074,
  employment_rate: 0.889,
  congestion_index: 0.741,
  health_system_load: 0.925,
  rumor_belief: 0.01,
  stress: 0.873,
  organization_vitality: 0.743,
};

const cityDeltas: Record<string, Record<string, number>> = {
  mobility_support: {
    life_satisfaction: 0.003825,
    government_trust: 0,
    economic_confidence: 0,
    consumption_index: 0.012717,
    employment_rate: 0,
    congestion_index: -0.009314,
    health_system_load: 0,
    rumor_belief: 0,
    stress: -0.056081,
    organization_vitality: 0,
    policy_cost_100m_cny: 5.6,
  },
  integrated_response: {
    life_satisfaction: 0.032188,
    government_trust: 0.111651,
    economic_confidence: 0.042731,
    consumption_index: 0.055593,
    employment_rate: 0.036312,
    congestion_index: 0.020634,
    health_system_load: 0,
    rumor_belief: -0.00923,
    stress: -0.116521,
    organization_vitality: 0.138145,
    policy_cost_100m_cny: 64.3,
  },
};

function cityTrajectory(branchName: string) {
  return Array.from({ length: 31 }, (_, day) => {
    const progress = day / 30;
    const shock = 1 - Math.pow(1 - progress, 1.3);
    const branchDelta = cityDeltas[branchName] ?? {};
    return {
      day,
      metrics: Object.fromEntries(cityMetricNames.map((metric) => {
        const controlValue = initialMetrics[metric] + (terminalControl[metric] - initialMetrics[metric]) * shock;
        const intervention = (branchDelta[metric] ?? 0) * Math.max(0, (day - 3) / 27);
        return [metric, band(controlValue + intervention, day === 0 ? 0.001 : 0.012)];
      })),
    };
  });
}

const districtSpecs = [
  ['gusu', '姑苏区', 928821, 0.030, 0.298, 0.928],
  ['wuzhong', '吴中区', 1424400, 0.029, 0.306, 0.927],
  ['xiangcheng', '相城区', 916900, 0.026, 0.283, 0.922],
  ['huxiu', '虎丘区（高新区）', 858900, 0.026, 0.306, 0.944],
  ['sip', '苏州工业园区', 1181000, 0.040, 0.313, 0.923],
  ['wujiang', '吴江区', 1582600, 0.037, 0.296, 0.931],
  ['changshu', '常熟市', 1688900, 0.040, 0.314, 0.919],
  ['zhangjiagang', '张家港市', 1446000, 0.036, 0.292, 0.919],
  ['kunshan', '昆山市', 2169300, 0.042, 0.319, 0.926],
  ['taicang', '太仓市', 851000, 0.025, 0.284, 0.915],
] as const;

const sampleDistricts: CityDistrictMetric[] = districtSpecs.map(([id, name, population, satisfaction, confidence, employment]) => ({
  branch_id: 'integrated_response',
  district_id: id,
  district_name: name,
  represented_population: population,
  metrics: {
    life_satisfaction: band(satisfaction, 0.003),
    economic_confidence: band(confidence, 0.012),
    employment_probability: band(employment, 0.008),
    congestion_index: band(id === 'sip' ? 0.759 : 0.766, 0.015),
    health_system_load: band(0.925, 0.01),
    rumor_belief: band(id === 'sip' ? 0.001 : 0, 0.001),
  },
}));

export const sampleCityForecast: CityForecast = {
  run_id: 'cityrun_504ebc149205449f',
  query_id: 'suzhou_resilience_30d',
  city_id: 'suzhou',
  model_version: 'suzhou-coupled-city-runtime-v1',
  data_version: 'suzhou-public-anchors-2025-v1',
  prototype_count: 5000,
  represented_population: 13047700,
  represented_scope_population: 13047700,
  branch_trajectories: {
    control: cityTrajectory('control'),
    mobility_support: cityTrajectory('mobility_support'),
    integrated_response: cityTrajectory('integrated_response'),
  },
  final_district_metrics: sampleDistricts,
  counterfactual_deltas: cityDeltas,
  assumptions: ['区县总量来自公开统计锚点。', '个人、家庭、组织和关系均为合成原型。'],
  warnings: ['区间表示模型内场景不确定性，不是经验置信区间。'],
  disclaimer: '本结果为概率模拟与条件预测，不构成对现实结果的保证。',
};

export const sampleRuns: RunRecord[] = [
  {
    id: 'eventrun_99a449ac38cf4064',
    kind: 'event',
    label: '市场—组织事件链 · 45 天',
    model: 'echo-event-hazard-chain-v1',
    createdAt: '2026-08-24 13:48',
    scope: '4 candidates · 2 branches · 2,048 paths',
    status: 'verified',
    calibration: '未校准先验',
    stats: [{ label: '最高事件概率', value: '52.3%' }, { label: '回放记录', value: '90 / 90' }],
  },
  {
    id: 'cityrun_504ebc149205449f',
    kind: 'city',
    label: '苏州城市韧性 · 30 天（Legacy）',
    model: 'suzhou-coupled-city-runtime-v1',
    createdAt: '2026-08-24 13:48',
    scope: '5,000 prototypes · 3 branches · 2 paths',
    status: 'verified',
    calibration: '合成微观状态',
    stats: [{ label: '代表人口', value: '1,304.77 万' }, { label: '回放记录', value: '186 / 186' }],
  },
  {
    id: 'run_91d0856ef4364751',
    kind: 'statistical',
    label: '价格干预统计验证 · 14 天',
    model: 'echo-structured-logit-v1',
    createdAt: '2026-08-24 13:48',
    scope: '10,000 synthetic respondents · 3 branches',
    status: 'verified',
    calibration: '合成真值验证',
    stats: [{ label: 'Brier', value: '0.1894' }, { label: 'ECE', value: '0.0222' }],
  },
];
