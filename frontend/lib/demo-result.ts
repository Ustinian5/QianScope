import type {
  PredictionResult,
  ProbabilityBand,
  QuestionForecast,
  ScenarioForecast,
} from '@/lib/research-types';

function band(p50: number, spread = 0.07): ProbabilityBand {
  return {
    p10: Math.max(0, Number((p50 - spread).toFixed(3))),
    p50: Number(p50.toFixed(3)),
    p90: Math.min(1, Number((p50 + spread).toFixed(3))),
  };
}

function choiceQuestion(
  questionId: string,
  questionText: string,
  values: Array<[string, number, number]>,
  changeSummary: string,
): QuestionForecast {
  const ranks = [...values]
    .sort((left, right) => right[2] - left[2])
    .reduce<Record<string, number>>((result, item, index) => ({ ...result, [item[0]]: index + 1 }), {});
  const options = (phase: 'baseline' | 'post') => values.map(([label, before, after], index) => ({
    option_id: `option_${index + 1}`,
    label,
    probability: band(phase === 'baseline' ? before : after, 0.055),
    predicted_rank: phase === 'post' ? ranks[label] : null,
  }));
  const postDistribution = Object.fromEntries(values.map(([label, , after]) => [label, after]));
  const predicted = [...values].sort((left, right) => right[2] - left[2]);
  return {
    question_id: questionId,
    question_text: questionText,
    kind: 'single_choice',
    baseline: { phase: 'baseline', options: options('baseline'), numeric_value: null, themes: [] },
    post_event: { phase: 'post_event', options: options('post'), numeric_value: null, themes: [] },
    change_summary: changeSummary,
    group_differences: [],
    cross_tabs: [{
      group_field: 'social_role', group_label: '社会角色', response_type: 'distribution', rows: [
        { group_value: 'student', group_value_label: '高校学生', agent_count: 612, represented_population: 612, weighted_share: 0.122, response_distribution: postDistribution, leading_answer: predicted[0][0] },
        { group_value: 'professional', group_value_label: '专业从业者', agent_count: 1348, represented_population: 1348, weighted_share: 0.27, response_distribution: postDistribution, leading_answer: predicted[0][0] },
        { group_value: 'caregiver', group_value_label: '家庭照护者', agent_count: 477, represented_population: 477, weighted_share: 0.095, response_distribution: postDistribution, leading_answer: predicted[0][0] },
      ],
    }],
    representative_responses: predicted.slice(0, 3).map(([answer], index) => ({
      persona_id: `${questionId}_persona_${index + 1}`,
      persona_label: `合成人格 ${['7A21F0', '19C8B4', 'D3026E'][index]}`,
      role: ['高校学生', '专业从业者', '家庭照护者'][index],
      organization_type: ['高校与科研机构', '专业服务机构', '家庭与社区网络'][index],
      segment: ['18-24 · 城市核心区', '25-34 · 城市近郊', '35-44 · 城市核心区'][index],
      predicted_answer: answer,
      answer: `就“${questionText}”这个问题，我目前更接近“${answer}”。我会先看它是否影响自己的时间安排和实际收益，再通过可信来源与熟人体验核验；在执行细节还不充分时，我不会把当前判断当成最终结论。`,
      confidence: [0.78, 0.71, 0.66][index],
      represented_weight: 1,
      basis: ['主目标：生活稳定', '首要价值：自主', '主要渠道：熟人交流'],
      synthetic: true as const,
    })),
    key_drivers: ['实际可用性', '熟人讨论', '信息可信度'],
    out_of_distribution: false,
  };
}

function scenario(
  scenarioId: string,
  label: string,
  supportShift: number,
  discussionShift: number,
): ScenarioForecast {
  const timeline = Array.from({ length: 31 }, (_, tick) => {
    const progress = tick / 30;
    const attentionWave = Math.sin(progress * Math.PI) * 0.12;
    return {
      tick,
      metrics: {
        awareness: band(0.18 + progress * (0.64 + discussionShift), 0.055),
        support: band(0.46 + progress * supportShift, 0.065),
        opposition: band(0.25 - progress * supportShift * 0.35, 0.05),
        discussion: band(0.16 + attentionWave + progress * discussionShift, 0.06),
        participation: band(0.12 + progress * (supportShift * 0.55 + 0.09), 0.055),
        polarization: band(0.16 + attentionWave * 0.32, 0.045),
      },
    };
  });
  const final = timeline[timeline.length - 1];
  return {
    scenario_id: scenarioId,
    label,
    timeline,
    final_actions: {
      support: final.metrics.support,
      discussion: final.metrics.discussion,
      participation: final.metrics.participation,
    },
    downstream_outcomes: [
      { outcome_id: 'continued_use', label: '持续使用空间', probability: band(final.metrics.participation.p50 + 0.12, 0.07), likely_tick: band(16 / 30, 0.1) },
      { outcome_id: 'peer_recommendation', label: '向熟人推荐', probability: band(final.metrics.support.p50 - 0.09, 0.07), likely_tick: band(13 / 30, 0.1) },
      { outcome_id: 'public_discussion', label: '形成公开讨论', probability: band(final.metrics.discussion.p50 + 0.05, 0.07), likely_tick: band(9 / 30, 0.1) },
    ],
  };
}

export const demoResult: PredictionResult = {
  run_id: 'demo_public_learning_space_2026',
  project_id: 'demo_general_event_prediction',
  title: '公共学习空间延长开放时间',
  created_at: '2026-08-24T09:00:00+08:00',
  conclusion: '延长开放时间会先带来一轮集中讨论，随后支持度稳定上升；真正转化为持续参与，取决于预约体验与夜间安全感。',
  population: {
    population_id: 'demo_general_adults',
    agent_count: 5000,
    tier_counts: { key: 50, representative: 450, background: 4500 },
    relationship_count: 28412,
    agents_observed: 5000,
    agents_decided: 5000,
    agents_acted: 5000,
    agents_remembered: 5000,
    represented_population: 5000,
    effective_sample_size: 4318,
  },
  grounding: {
    status: 'synthetic_persona_prototype',
    population_margin_id: null,
    source: null,
    covered_fields: [],
    converged: null,
    design_effect: 1.158,
    warnings: ['演示运行未接入授权人口边际。'],
  },
  calibration: {
    status: 'uncalibrated_prior',
    calibration_id: null,
    dataset_id: null,
    training_records: 0,
    holdout_records: 0,
    holdout_brier_before: null,
    holdout_brier_after: null,
    applied: false,
    warnings: ['演示运行未使用历史真实结果校准。'],
  },
  report_metadata: {
    model_version: 'questionnaire-event-swm-v3',
    data_version: 'stable-synthetic-personality-v2',
    seed: 2026,
    paths: 8,
    horizon_ticks: 30,
    scenario_count: 3,
    requested_agents: 5000,
    successful_agents: 5000,
    failed_agents: 0,
    represented_population: 5000,
    effective_sample_size: 4318,
    population_source: '未接入现实人口边际的合成人格',
    weighting_method: '等权合成人格原型',
    interval_definition: 'P10 / P50 / P90 来自 8 条共享随机数路径；它表示模型路径差异，不是现实误差保证。',
    calibration_status: 'uncalibrated_prior',
    profile_signature: 'demo-profile-signature-v3',
  },
  report_quality: {
    status: 'warning', passed: 7, warnings: 2, failures: 0, checks: [
      { check_id: 'interval_order', label: '区间顺序', status: 'pass', observed: '0 个异常 / 428 个区间', expected: 'P10 ≤ P50 ≤ P90', detail: '问卷、时间线、行动与结果区间顺序一致。' },
      { check_id: 'probability_mass', label: '选择题概率守恒', status: 'pass', observed: '最大偏差 0.0000', expected: '互斥选项合计接近 1', detail: '多选题不要求合计为 1。' },
      { check_id: 'agent_completion', label: 'Agent 完成率', status: 'pass', observed: '5,000 / 5,000，失败 0', expected: '全量完成', detail: '不发布不完整结果。' },
      { check_id: 'cross_tab_coverage', label: '交叉表覆盖', status: 'pass', observed: '角色、性别、年龄等字段已覆盖', expected: '请求字段全部输出', detail: '每个分组同时显示原型数、权重和回答分布。' },
      { check_id: 'historical_calibration', label: '历史校准', status: 'warning', observed: '未加载校准记录', expected: '通过时间留出验证', detail: '当前概率属于模型先验，不能声称现实准确率。' },
      { check_id: 'population_grounding', label: '人口口径', status: 'warning', observed: '等权合成人格', expected: '现实人口来源可追溯', detail: '演示仅解释 5,000 个合成人格原型。' },
    ],
  },
  questionnaire_forecast: [
    choiceQuestion(
      'q01_awareness',
      '在事件发生后，你认为自己会多快注意到这件事？',
      [['很可能不会注意', 0.28, 0.1], ['过一段时间才注意', 0.35, 0.27], ['较快注意到', 0.25, 0.42], ['几乎立即注意到', 0.12, 0.21]],
      '较快注意到的人增加 17 个百分点，信息主要通过熟人讨论扩散。',
    ),
    choiceQuestion(
      'q02_stance',
      '如果现在必须表态，你最可能选择哪一种？',
      [['反对', 0.24, 0.17], ['保持观望', 0.43, 0.28], ['支持', 0.33, 0.55]],
      '支持成为最可能答案，但仍有约三成人等待看到实际运行体验。',
    ),
    choiceQuestion(
      'q03_action',
      '事件发生后，你最可能采取什么行动？',
      [['暂不行动', 0.46, 0.26], ['继续了解', 0.29, 0.31], ['与他人讨论', 0.16, 0.25], ['实际到访', 0.09, 0.18]],
      '讨论和实际到访同步增长，态度转化为行动仍存在明显落差。',
    ),
    {
      question_id: 'q04_participation',
      question_text: '你实际使用延时开放空间的可能性是多少（0—100）？',
      kind: 'numeric',
      baseline: { phase: 'baseline', options: [], numeric_value: { p10: 18, p50: 37, p90: 61 }, themes: [] },
      post_event: { phase: 'post_event', options: [], numeric_value: { p10: 29, p50: 53, p90: 78 }, themes: [] },
      change_summary: '使用意愿中位数从 37 上升至 53，夜间出行条件造成最大的群体差异。',
      group_differences: [],
      key_drivers: ['距离', '夜间安全感', '预约便利度'],
      out_of_distribution: false,
    },
    {
      question_id: 'q05_reason',
      question_text: '请简要说明你形成上述态度的主要原因。',
      kind: 'open_text',
      baseline: { phase: 'baseline', options: [], numeric_value: null, themes: [] },
      post_event: {
        phase: 'post_event', options: [], numeric_value: null, themes: [
          { theme: '时间更灵活', share: band(0.43, 0.06), representative_answer: '晚间也有安静、可靠的学习地点，会更容易安排自己的时间。' },
          { theme: '担心实际体验', share: band(0.31, 0.06), representative_answer: '是否支持要看预约是否方便，以及晚上会不会拥挤。' },
          { theme: '与自己关系不大', share: band(0.18, 0.05), representative_answer: '距离较远，开放时间变化不会明显改变我的选择。' },
        ],
      },
      change_summary: '便利性是主要正向理由，执行体验是最常见的保留意见。',
      group_differences: [],
      key_drivers: ['时间灵活性', '预约体验', '空间距离'],
      out_of_distribution: false,
    },
  ],
  group_insights: [
    '18—34 岁群体的持续使用倾向高于整体约 12 个百分点，但也更在意预约和座位透明度。',
    '照护者更认可延长开放，但实际到访意愿受晚间家庭安排影响，低于态度支持约 19 个百分点。',
    '主要依赖熟人获取信息的人群反应更慢；一旦获得可信的实际体验，支持增长更稳定。',
    '距离较近的人群最容易从“支持”转化为“到访”，空间距离是行动层面的首要分界。',
  ],
  scenarios: [
    scenario('baseline_no_event', '事件未发生', 0.015, 0.015),
    scenario('event_as_described', '事件按描述发生', 0.18, 0.095),
    scenario('alternative_context', '信息传播较慢', 0.105, 0.045),
  ],
  l2_evaluation: {
    capability_level: 'constrained_l2',
    baseline_scenario_id: 'baseline_no_event',
    common_random_numbers: true,
    protocol_lock: {
      forecast_as_of: '2026-08-24T09:00:00+08:00',
      horizon_ticks: 30,
      scenario_ids: ['baseline_no_event', 'event_as_described', 'alternative_context'],
      metric_ids: ['support', 'awareness', 'polarization'],
      baseline_scenario_id: 'baseline_no_event',
      future_information_forbidden: true,
      excluded_evidence_ids: [],
      untimestamped_evidence_ids: [],
      input_signature: 'demo-lock-86d8a9022f47a6c9',
    },
    scenario_ranking: [
      { scenario_id: 'event_as_described', label: '事件按描述发生', rank: 1, decision_score: 0.73, primary_metric_value: band(0.64, 0.065), primary_metric_delta: { p10: 0.12, p50: 0.165, p90: 0.21 } },
      { scenario_id: 'alternative_context', label: '信息传播较慢', rank: 2, decision_score: 0.61, primary_metric_value: band(0.565, 0.065), primary_metric_delta: { p10: 0.045, p50: 0.09, p90: 0.135 } },
      { scenario_id: 'baseline_no_event', label: '事件未发生', rank: 3, decision_score: 0.42, primary_metric_value: band(0.475, 0.065), primary_metric_delta: { p10: 0, p50: 0, p90: 0 } },
    ],
    effects: [
      { scenario_id: 'event_as_described', scenario_label: '事件按描述发生', metric_id: 'support', metric_label: '支持', direction: 'increase', weight: 1, baseline_value: band(0.475, 0.065), scenario_value: band(0.64, 0.065), paired_delta: { p10: 0.12, p50: 0.165, p90: 0.21 }, direction_consistency: 0.88, cod_score: 0.88, effect_detected: true },
      { scenario_id: 'alternative_context', scenario_label: '信息传播较慢', metric_id: 'support', metric_label: '支持', direction: 'increase', weight: 1, baseline_value: band(0.475, 0.065), scenario_value: band(0.565, 0.065), paired_delta: { p10: 0.032, p50: 0.09, p90: 0.145 }, direction_consistency: 0.74, cod_score: 0.74, effect_detected: true },
    ],
    cod_score: 0.81,
    cod_interpretation: '两个事件方案均与无事件基线形成稳定差异，完整开放方案在支持与参与指标上更容易被模型区分。',
    warnings: ['演示运行未接入历史真实结果；COD 只表示模型内干预分辨度。'],
  },
  key_drivers: [
    '预约是否顺畅、座位信息是否透明，会直接影响支持向实际使用的转化。',
    '首批使用者的熟人评价决定讨论高峰之后的支持能否继续增长。',
    '夜间安全感与返程便利度，是不同年龄和社会角色之间最稳定的差异来源。',
    '事件信息的可信度主要影响反应速度，而非最终态度方向。',
  ],
  uncertainty: [
    '尚无真实人口边际，因此分组占比只代表合成人格原型。',
    '实际空间容量、位置和交通条件未完整输入，会影响参与概率。',
  ],
  limitations: [
    '结果表达的是给定条件下的概率模拟，不是对现实结果的保证。',
    '突发新闻、线下事故或重大规则变化不在当前情景中。',
  ],
  participant_receipts: [
    { agent_id: 'agent_key_0017', tier: 'key', segment: '青年专业人员 · 熟人信息', final_action: 'discussion', response_summary: '认可延长开放，但会先询问朋友的实际体验再决定是否到访。', top_drivers: ['时间灵活性', '熟人评价'] },
    { agent_id: 'agent_rep_0214', tier: 'representative', segment: '照护者 · 社区信息', final_action: 'support', response_summary: '态度上支持公共资源延时开放，实际使用仍受家庭安排限制。', top_drivers: ['公共价值', '时间安排'] },
    { agent_id: 'agent_bg_3402', tier: 'background', segment: '退休人员 · 线下信息', final_action: 'silence', response_summary: '认为变化总体正面，但距离较远，不会主动传播或参与。', top_drivers: ['空间距离', '个人关联'] },
  ],
  semantic_interpretation: {
    method: 'deterministic_demo_semantics',
    summary: '将事件解释为公共空间可用性提升，同时包含预约、拥挤与夜间安全的不确定性。',
    confidence: 'medium',
    missing_inputs: ['空间位置', '容量', '夜间交通'],
  },
  deterministic_signature: 'demo:2026:public-learning-space:5000:30:8',
  disclaimer: '演示数据仅用于说明产品结构，不代表真实调查结论。',
};
