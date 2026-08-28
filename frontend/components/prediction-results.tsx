'use client';

import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import Link from 'next/link';
import { BrandMark } from '@/components/app-shell';
import { LineChart, type ChartSeries } from '@/components/line-chart';
import type {
  PredictionResult,
  ProbabilityBand,
  QuestionForecast,
} from '@/lib/research-types';
import type { WorldSimulationResult } from '@/lib/world-types';

const metricLabels: Record<string, string> = {
  awareness: '知晓',
  support: '支持',
  opposition: '反对',
  sharing: '分享',
  discussion: '讨论',
  silence: '沉默',
  participation: '参与',
  exit: '退出',
  polarization: '分化',
  trust: '信任',
};

const chartMetrics = [
  { key: 'support', label: '支持', color: '#8a829d' },
  { key: 'discussion', label: '讨论', color: '#bd7b62' },
  { key: 'participation', label: '参与', color: '#71877c' },
];

const actionLabels: Record<string, string> = {
  ignore: '忽略',
  consume: '继续了解',
  discuss: '讨论',
  share: '分享',
  support: '支持',
  oppose: '反对',
  participate: '参与',
  exit: '退出',
};

const segmentLabels: Record<string, string> = {
  age_group: '年龄',
  gender: '性别',
  social_role: '社会角色',
  organization_type: '单位类型',
  education_level: '教育背景',
  primary_channel: '主要信息渠道',
};

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function signedPoints(value: number) {
  const points = value * 100;
  return `${points >= 0 ? '+' : ''}${points.toFixed(1)} pp`;
}

function beijingTime(value: string) {
  const date = new Date(Date.parse(value) + 8 * 60 * 60 * 1000);
  const parts = [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, '0'),
    String(date.getUTCDate()).padStart(2, '0'),
  ];
  const time = [
    String(date.getUTCHours()).padStart(2, '0'),
    String(date.getUTCMinutes()).padStart(2, '0'),
    String(date.getUTCSeconds()).padStart(2, '0'),
  ];
  return `${parts.join('-')} ${time.join(':')}`;
}

function RangeBar({ band }: { band: ProbabilityBand }) {
  const style = {
    '--low': `${Math.max(0, Math.min(100, band.p10 * 100))}%`,
    '--mid': `${Math.max(0, Math.min(100, band.p50 * 100))}%`,
    '--high': `${Math.max(0, Math.min(100, band.p90 * 100))}%`,
  } as CSSProperties;
  return <span className="range-bar" style={style}><i /><b /></span>;
}

function QuestionResultCard({ forecast, index }: { forecast: QuestionForecast; index: number }) {
  const baseline = new Map(forecast.baseline.options.map((item) => [item.option_id, item]));
  const crossTabs = forecast.cross_tabs || [];
  const representativeResponses = forecast.representative_responses || [];
  return (
    <article className="question-result-card">
      <header>
        <span>Q{String(index + 1).padStart(2, '0')}</span>
        <div><h3>{forecast.question_text}</h3><p>{forecast.change_summary}</p></div>
        {forecast.out_of_distribution ? <em title="题目语义或事件证据不足">需谨慎解释</em> : null}
      </header>
      {forecast.post_event.options.length ? (
        <div className="answer-bars">
          {[...forecast.post_event.options]
            .sort((a, b) => (a.predicted_rank ?? 99) - (b.predicted_rank ?? 99))
            .map((option) => {
              const before = baseline.get(option.option_id);
              return (
                <div className="answer-row" key={option.option_id}>
                  <span>{option.predicted_rank ? `${option.predicted_rank}. ` : ''}{option.label}</span>
                  <RangeBar band={option.probability} />
                  <strong>{percent(option.probability.p50)}</strong>
                  <small>{before ? `事件前 ${percent(before.probability.p50)}` : ''}</small>
                </div>
              );
            })}
        </div>
      ) : null}
      {forecast.post_event.numeric_value ? (
        <div className="numeric-answer">
          <strong>{forecast.post_event.numeric_value.p50.toFixed(1)}</strong>
          <span>
            常见范围 {forecast.post_event.numeric_value.p10.toFixed(1)}—
            {forecast.post_event.numeric_value.p90.toFixed(1)}
          </span>
        </div>
      ) : null}
      {forecast.post_event.themes.length ? (
        <div className="theme-list">
          {forecast.post_event.themes.map((theme) => (
            <div key={theme.theme}>
              <strong>{theme.theme} · {percent(theme.share.p50)}</strong>
              <p>{theme.representative_answer}</p>
            </div>
          ))}
        </div>
      ) : null}
      {crossTabs.length || representativeResponses.length ? (
        <details className="question-evidence-details">
          <summary>查看交叉表与合成代表性回答</summary>
          {crossTabs.length ? (
            <div className="cross-tab-list">
              {crossTabs.map((table) => (
                <section key={table.group_field}>
                  <header><strong>{table.group_label}</strong><span>{table.rows.length} 个分组</span></header>
                  <div>
                    {table.rows.map((row) => {
                      const breakdown = Object.entries(row.response_distribution)
                        .sort(([, left], [, right]) => right - left)
                        .slice(0, 3)
                        .map(([label, value]) => `${label} ${table.response_type === 'numeric_mean' ? value.toFixed(1) : percent(value)}`)
                        .join(' · ');
                      return (
                        <article key={row.group_value}>
                          <p><strong>{row.group_value_label}</strong><span>{row.agent_count.toLocaleString('zh-CN')} 个原型 · 权重 {percent(row.weighted_share)}</span></p>
                          <small>{breakdown}</small>
                        </article>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          ) : null}
          {representativeResponses.length ? (
            <div className="representative-response-list">
              <header><strong>合成代表性回答</strong><span>不是现实受访者原话</span></header>
              {representativeResponses.map((response) => (
                <article key={response.persona_id}>
                  <p><strong>{response.persona_label}</strong><span>{response.role} · {response.organization_type}</span></p>
                  <blockquote>“{response.answer}”</blockquote>
                  <footer><span>预测回答：{response.predicted_answer}</span><span>档案置信 {percent(response.confidence)}</span></footer>
                </article>
              ))}
            </div>
          ) : null}
        </details>
      ) : null}
    </article>
  );
}

function OutcomeBackfill({ result }: { result: PredictionResult }) {
  const [sampleSize, setSampleSize] = useState('');
  const [raw, setRaw] = useState('{}');
  const [message, setMessage] = useState('');

  async function submit() {
    setMessage('');
    try {
      const questionnaireResults = JSON.parse(raw) as Record<string, unknown>;
      const response = await fetch(`/api/echo/v1/predictions/${result.run_id}/outcomes`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          sample_size: Number(sampleSize || 0),
          questionnaire_results: questionnaireResults,
          event_outcomes: {},
        }),
      });
      if (!response.ok) {
        const errorBody = await response.json() as { detail?: string };
        throw new Error(errorBody.detail || '保存失败');
      }
      setMessage('真实结果已保存，可用于后续校准。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '请输入有效 JSON。');
    }
  }

  return (
    <details className="advanced-card outcome-card">
      <summary>事件发生后，回填真实调查结果</summary>
      <p>键为题目 ID；选择题填写各选项真实占比，数值题填写真实均值。</p>
      <label>真实样本数<input value={sampleSize} onChange={(e) => setSampleSize(e.target.value)} type="number" min="0" /></label>
      <label>结果 JSON<textarea value={raw} onChange={(e) => setRaw(e.target.value)} rows={5} /></label>
      <button className="secondary-action" onClick={submit} type="button">保存真实结果</button>
      {message ? <span className="form-message">{message}</span> : null}
    </details>
  );
}

export function PredictionResults({
  result,
  worldResult,
  onNew,
  demo = false,
}: {
  result: PredictionResult;
  worldResult?: WorldSimulationResult | null;
  onNew: () => void;
  demo?: boolean;
}) {
  const [showAllQuestions, setShowAllQuestions] = useState(false);
  const defaultScenario = result.scenarios.find((item) => item.scenario_id === 'event_as_described')
    || result.scenarios[0];
  const [activeScenarioId, setActiveScenarioId] = useState(defaultScenario?.scenario_id || '');
  const [actionStatus, setActionStatus] = useState('');
  const primaryScenario = result.scenarios.find((item) => item.scenario_id === activeScenarioId)
    || defaultScenario;
  const timelinePoints = useMemo(() => {
    if (!primaryScenario?.timeline.length) return [];
    const last = primaryScenario.timeline.length - 1;
    return Array.from(new Set([0, Math.round(last / 3), Math.round(last * 2 / 3), last]))
      .map((index) => primaryScenario.timeline[index]);
  }, [primaryScenario]);
  const chartSeries = useMemo<ChartSeries[]>(() => chartMetrics.map((metric) => ({
    label: metric.label,
    color: metric.color,
    values: (primaryScenario?.timeline || []).map((point) => ({
      x: point.tick,
      y: point.metrics[metric.key]?.p50 || 0,
    })),
  })), [primaryScenario]);
  const finalPoint = primaryScenario?.timeline[primaryScenario.timeline.length - 1];
  const shownMetrics = ['awareness', 'support', 'opposition', 'discussion', 'participation', 'polarization'];
  const visibleQuestions = showAllQuestions
    ? result.questionnaire_forecast
    : result.questionnaire_forecast.slice(0, 4);
  const worldSeries = useMemo<ChartSeries[]>(() => worldResult ? [{
    label: '累计触达',
    color: '#bd7b62',
    values: worldResult.diffusion_curve.map((point) => ({
      x: point.tick,
      y: point.reached_fraction.p50,
    })),
  }] : [], [worldResult]);
  const finalDiffusion = worldResult?.diffusion_curve[worldResult.diffusion_curve.length - 1];
  const l2Evaluation = result.l2_evaluation;
  const reportMetadata = result.report_metadata;
  const reportQuality = result.report_quality;
  const primaryMetricId = l2Evaluation?.protocol_lock.metric_ids[0];
  const primaryEffects = l2Evaluation?.effects.filter(
    (item) => item.metric_id === primaryMetricId,
  ) || [];
  const actionRanking = worldResult
    ? Object.entries(worldResult.final_action_distribution)
        .sort(([, left], [, right]) => right.p50 - left.p50)
        .slice(0, 5)
    : [];

  async function shareReport() {
    const stableUrl = demo
      ? window.location.href
      : `${window.location.origin}/reports/${encodeURIComponent(result.run_id)}`;
    const shareData = {
      title: `${result.title} · ECHO 社会世界报告`,
      text: result.conclusion,
      url: stableUrl,
    };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
        setActionStatus('已打开系统分享');
      } else {
        await navigator.clipboard.writeText(shareData.url);
        setActionStatus('报告链接已复制');
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setActionStatus('分享不可用，请复制浏览器地址');
    }
  }

  return (
    <section className="results-view sw-report" aria-live="polite">
      <nav className="report-command-bar" aria-label="报告快速导航">
        <Link className="report-command-brand" href="/">
          <BrandMark />
          <span><strong>ECHO</strong><small>SOCIAL WORLD REPORT</small></span>
        </Link>
        <div className="report-section-links">
          <a href="#report-summary">摘要</a>
          <a href="#report-survey">问卷</a>
          <a href="#report-trajectory">推演</a>
          <a href="#report-method">口径</a>
        </div>
        <div className="report-command-actions">
          <span className="report-live-state"><i /> 推演已封存</span>
          <button type="button" onClick={() => window.print()}>打印 / PDF</button>
          <button type="button" onClick={() => void shareReport()}>分享</button>
        </div>
      </nav>
      {actionStatus ? <p className="report-action-status" role="status">{actionStatus}</p> : null}

      <header className="results-header" id="report-summary">
        <div>
          <span>{demo ? '演示报告 · 合成人格数据' : '预测完成'}</span>
          <h1>{result.title}</h1>
          <p className="report-byline">
            <b>{beijingTime(result.created_at)} 北京时间</b>
            <span>运行 {result.run_id}</span>
            <span>{result.population.agent_count.toLocaleString('zh-CN')} 个稳定人格原型</span>
          </p>
        </div>
        <button className="secondary-action" onClick={onNew} type="button">{demo ? '预测你的事件' : '新建预测'}</button>
      </header>

      {demo ? <div className="demo-notice"><strong>这是可交互的示例报告</strong><span>用于展示结果结构，所有数字均来自固定合成人格模拟，不代表真实人群调查。</span></div> : null}

      <div className="report-summary-layout">
        <section className="conclusion-card">
          <span>一句话结论</span>
          <h2>{result.conclusion}</h2>
          <p>
            {result.population.agent_count.toLocaleString('zh-CN')} 个虚拟参与者均完成了
            {primaryScenario?.timeline.length ? primaryScenario.timeline.length - 1 : 0} 轮观察、判断、行动与记忆。
          </p>
        </section>
        <aside className="report-run-receipt" aria-label="运行摘要">
          <header><span>WORLD STATE</span><i /></header>
          <div>
            <p><span>社会关系</span><strong>{result.population.relationship_count.toLocaleString('zh-CN')}</strong></p>
            <p><span>有效样本</span><strong>{Math.round(result.population.effective_sample_size || result.population.agent_count).toLocaleString('zh-CN')}</strong></p>
            <p><span>未来路径</span><strong>{reportMetadata?.paths || result.scenarios.length}</strong></p>
          </div>
          <footer><span>确定性签名</span><code>{result.deterministic_signature.slice(0, 18)}</code></footer>
        </aside>
      </div>

      <section className="data-quality-strip" aria-label="数据基础与校准状态">
        <div className={result.grounding.status === 'synthetic_anchored_to_authorized_aggregates' ? 'verified' : ''}>
          <span>人口基础</span>
          <strong>{result.grounding.status === 'synthetic_anchored_to_authorized_aggregates' ? '已按授权聚合分布加权' : '合成人格原型'}</strong>
          <small>{result.grounding.covered_fields.length ? `覆盖 ${result.grounding.covered_fields.join('、')}` : '未接入授权人口边际'}</small>
        </div>
        <div className={result.calibration.applied ? 'verified' : ''}>
          <span>历史校准</span>
          <strong>{result.calibration.applied ? '时间留出验证通过' : '未校准先验'}</strong>
          <small>{result.calibration.applied ? `${result.calibration.training_records} 条训练 · ${result.calibration.holdout_records} 条留出` : '未用历史结果修正概率'}</small>
        </div>
        <div>
          <span>代表规模</span>
          <strong>{Math.round(result.population.represented_population || result.population.agent_count).toLocaleString('zh-CN')}</strong>
          <small>有效样本量 {Math.round(result.population.effective_sample_size || result.population.agent_count).toLocaleString('zh-CN')}</small>
        </div>
      </section>

      {reportMetadata && reportQuality ? (
        <section className={`result-section report-assurance-section quality-${reportQuality.status}`} id="report-method">
          <div className="section-heading">
            <div><span>REPORT ASSURANCE · 运行口径</span><h2>这份报告通过了哪些检查</h2></div>
            <b>{reportQuality.failures ? `${reportQuality.failures} 项失败` : reportQuality.warnings ? `${reportQuality.warnings} 项提醒` : '全部通过'}</b>
          </div>
          <div className="report-meta-grid">
            <article><span>模型 / 数据</span><strong>{reportMetadata.model_version}</strong><small>{reportMetadata.data_version}</small></article>
            <article><span>随机与路径</span><strong>seed {reportMetadata.seed}</strong><small>{reportMetadata.paths} 条路径 · {reportMetadata.horizon_ticks} 步</small></article>
            <article><span>Agent 完成</span><strong>{reportMetadata.successful_agents.toLocaleString('zh-CN')} / {reportMetadata.requested_agents.toLocaleString('zh-CN')}</strong><small>失败 {reportMetadata.failed_agents} 个</small></article>
            <article><span>自动检查</span><strong>{reportQuality.passed} 通过</strong><small>{reportQuality.warnings} 提醒 · {reportQuality.failures} 失败</small></article>
          </div>
          <p className="interval-definition">{reportMetadata.interval_definition}</p>
          <details className="quality-check-details">
            <summary>逐项查看一致性检查</summary>
            <div>
              {reportQuality.checks.map((check) => (
                <article className={`check-${check.status}`} key={check.check_id}>
                  <i aria-hidden="true" />
                  <div><strong>{check.label}</strong><span>{check.observed}</span><p>{check.detail}</p></div>
                  <b>{check.status === 'pass' ? '通过' : check.status === 'warning' ? '提醒' : '失败'}</b>
                </article>
              ))}
            </div>
          </details>
        </section>
      ) : null}

      {l2Evaluation ? (
        <section className="result-section l2-decision-section">
          <div className="section-heading">
            <div><span>CONSTRAINED L2 · 方案对照</span><h2>哪一种未来更接近目标</h2></div>
            <b>口径已锁定</b>
          </div>
          <div className="l2-overview">
            <div className="l2-score-card">
              <span>反事实敏感性 COD</span>
              <strong>{Math.round(l2Evaluation.cod_score * 100)}</strong>
              <small>模型内分辨度 · 不是现实准确率</small>
            </div>
            <p>{l2Evaluation.cod_interpretation}</p>
          </div>
          <div className="l2-ranking-list">
            {l2Evaluation.scenario_ranking.map((scenario) => (
              <article key={scenario.scenario_id}>
                <em>{String(scenario.rank).padStart(2, '0')}</em>
                <div><strong>{scenario.label}</strong><span>{metricLabels[primaryMetricId || ''] || primaryMetricId}中位值 {percent(scenario.primary_metric_value.p50)}</span></div>
                <b>{signedPoints(scenario.primary_metric_delta.p50)}</b>
              </article>
            ))}
          </div>
          <div className="l2-effect-grid">
            {primaryEffects.map((effect) => (
              <article className={effect.effect_detected ? 'detected' : ''} key={`${effect.scenario_id}-${effect.metric_id}`}>
                <header><span>{effect.scenario_label}</span><b>{effect.effect_detected ? '变化清晰' : '谨慎解释'}</b></header>
                <strong>{signedPoints(effect.paired_delta.p50)}</strong>
                <p>配对范围 {signedPoints(effect.paired_delta.p10)} — {signedPoints(effect.paired_delta.p90)}</p>
                <small>{Math.round(effect.direction_consistency * 100)}% 路径方向一致 · COD {Math.round(effect.cod_score * 100)}</small>
              </article>
            ))}
          </div>
          {l2Evaluation.warnings.length ? (
            <div className="l2-warning-list">
              {l2Evaluation.warnings.slice(0, 4).map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          ) : null}
          <footer className="protocol-lock-row">
            <span>共享随机路径 <b>{l2Evaluation.common_random_numbers ? '开启' : '关闭'}</b></span>
            <span>未来信息 <b>{l2Evaluation.protocol_lock.future_information_forbidden ? '已隔离' : '未隔离'}</b></span>
            <span>锁定时点 <b>{beijingTime(l2Evaluation.protocol_lock.forecast_as_of)} 北京时间</b></span>
            <code>{l2Evaluation.protocol_lock.input_signature.slice(0, 16)}</code>
          </footer>
        </section>
      ) : null}

      <section className="result-section" id="report-survey">
        <div className="section-heading"><div><span>01 · 问卷预测</span><h2>事件前后，答案会怎样变化</h2></div><b>{result.questionnaire_forecast.length} 道题</b></div>
        <div className="question-results">
          {visibleQuestions.map((forecast, index) => (
            <QuestionResultCard forecast={forecast} index={index} key={forecast.question_id} />
          ))}
        </div>
        {result.questionnaire_forecast.length > 4 ? (
          <button className="show-more" onClick={() => setShowAllQuestions((value) => !value)} type="button">
            {showAllQuestions ? '收起其余题目' : `查看全部 ${result.questionnaire_forecast.length} 道题`}
          </button>
        ) : null}
      </section>

      <section className="result-section" id="report-segments">
        <div className="section-heading"><div><span>02 · 群体差异</span><h2>哪些人会有不同反应</h2></div></div>
        <div className="insight-list">
          {result.group_insights.length
            ? result.group_insights.map((item) => <p key={item}>{item}</p>)
            : <p>当前分组差异较小。</p>}
        </div>
      </section>

      <section className="result-section" id="report-trajectory">
        <div className="section-heading"><div><span>03 · 未来反应</span><h2>反应可能怎样展开</h2></div><b>{primaryScenario?.label}</b></div>
        {result.scenarios.length > 1 ? (
          <div className="scenario-switcher" role="group" aria-label="切换对比情景">
            {result.scenarios.map((scenario) => (
              <button
                aria-pressed={scenario.scenario_id === primaryScenario?.scenario_id}
                className={scenario.scenario_id === primaryScenario?.scenario_id ? 'active' : ''}
                key={scenario.scenario_id}
                onClick={() => setActiveScenarioId(scenario.scenario_id)}
                type="button"
              >
                <span>{scenario.label}</span>
                <small>{scenario.timeline.length ? `${scenario.timeline.length - 1} 步` : '单步'}</small>
              </button>
            ))}
          </div>
        ) : null}
        <div className="reaction-summary">
          {chartMetrics.map((metric) => (
            <div key={metric.key}><span>{metric.label}倾向</span><strong>{percent(finalPoint?.metrics[metric.key]?.p50 || 0)}</strong><i style={{ background: metric.color }} /></div>
          ))}
        </div>
        <div className="timeline-chart-card">
          <div className="chart-legend-row">
            <span>从事件发生到第 {finalPoint?.tick || 0} 步</span>
            <div>{chartMetrics.map((metric) => <b key={metric.key}><i style={{ background: metric.color }} />{metric.label}</b>)}</div>
          </div>
          <LineChart series={chartSeries} label="支持、讨论与参与倾向随预测步骤的变化" />
        </div>
        <details className="timeline-data">
          <summary>查看关键节点数据</summary>
          <div className="timeline-table">
            <div className="timeline-row timeline-head"><span>反应</span>{timelinePoints.map((point) => <b key={point.tick}>第 {point.tick} 步</b>)}</div>
            {shownMetrics.map((metric) => (
              <div className="timeline-row" key={metric}>
                <span>{metricLabels[metric]}</span>
                {timelinePoints.map((point) => <b key={point.tick}>{percent(point.metrics[metric]?.p50 || 0)}</b>)}
              </div>
            ))}
          </div>
        </details>
        <div className="scenario-grid">
          {result.scenarios.map((scenario) => (
            <article key={scenario.scenario_id}>
              <span>{scenario.label}</span>
              {scenario.downstream_outcomes.slice(0, 3).map((outcome) => (
                <p key={outcome.outcome_id}><b>{outcome.label}</b><strong>{percent(outcome.probability.p50)}</strong></p>
              ))}
            </article>
          ))}
        </div>
      </section>

      {worldResult ? (
        <section className="result-section world-result-section" id="report-world">
          <div className="section-heading">
            <div><span>04 · 社会世界</span><h2>这次反应如何在人群中发生</h2></div>
            <b>完整状态推演</b>
          </div>
          <div className="world-result-intro">
            <div>
              <span>最终触达人群</span>
              <strong>{percent(finalDiffusion?.reached_fraction.p50 || 0)}</strong>
              <small>
                常见范围 {percent(finalDiffusion?.reached_fraction.p10 || 0)}—
                {percent(finalDiffusion?.reached_fraction.p90 || 0)}
              </small>
            </div>
            <p>
              这不是把总体比例一次性随机出来。每个参与者都依次经历了信息触达、信念更新、
              情绪反应、目标激活、行动选择、记忆与关系变化。
            </p>
          </div>
          <div className="world-result-grid">
            <div className="world-diffusion-card">
              <header><span>信息扩散</span><small>累计首次触达比例</small></header>
              <LineChart series={worldSeries} label="事件在社会世界中的累计触达比例" />
            </div>
            <div className="world-actions-card">
              <header><span>最终行动</span><small>所有参与者的行动分布</small></header>
              <div>
                {actionRanking.map(([action, band]) => (
                  <p key={action}>
                    <span>{actionLabels[action] || action}</span>
                    <i><b style={{ width: `${Math.max(2, band.p50 * 100)}%` }} /></i>
                    <strong>{percent(band.p50)}</strong>
                  </p>
                ))}
              </div>
            </div>
          </div>
          <div className="world-segments">
            {worldResult.segment_difference.slice(0, 4).map((segment) => (
              <article key={`${segment.segment_field}-${segment.segment_value}`}>
                <span>{segmentLabels[segment.segment_field] || segment.segment_field}</span>
                <strong>{segment.segment_value}</strong>
                <p>{actionLabels[segment.leading_action] || segment.leading_action}是主要行动 · {percent(segment.leading_action_share.p50)}</p>
              </article>
            ))}
          </div>
          <footer className="world-receipt">
            <p><span>人格原型</span><strong>{worldResult.population.prototype_count.toLocaleString('zh-CN')}</strong></p>
            <p><span>代表人口</span><strong>{Math.round(worldResult.population.represented_population).toLocaleString('zh-CN')}</strong></p>
            <p><span>社会关系</span><strong>{worldResult.population.relationship_count.toLocaleString('zh-CN')}</strong></p>
            <p><span>关系类型</span><strong>{worldResult.population.relationship_types.length}</strong></p>
            <small>相同输入可通过确定性签名验证重放</small>
          </footer>
        </section>
      ) : null}

      <section className="result-two-column">
        <div className="result-section compact-section">
          <div className="section-heading"><div><span>{worldResult ? '05' : '04'} · 关键因素</span><h2>什么最影响结果</h2></div></div>
          <ol className="driver-list">{result.key_drivers.map((item) => <li key={item}>{item}</li>)}</ol>
        </div>
        <div className="result-section compact-section">
          <div className="section-heading"><div><span>{worldResult ? '06' : '05'} · 需要谨慎</span><h2>不确定性与边界</h2></div></div>
          <ul className="plain-list">{[...result.uncertainty, ...result.limitations].map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      </section>

      {demo ? (
        <section className="export-card demo-export">
          <div><span>换成你的问题</span><h2>五步完成一次真实预测</h2><p>描述事件、选择人群、调整问卷，然后交给 5,000+ 个稳定人格 Agent。</p></div>
          <a className="primary-action small" href="/predict">开始预测 <span>→</span></a>
        </section>
      ) : (
        <section className="export-card">
          <div><span>导出结果</span><h2>带走问卷预测或完整报告</h2></div>
          <div>
            <a className="primary-action small" href={`/api/echo/v1/predictions/${result.run_id}/export?format=csv`}>下载 CSV</a>
            <a className="secondary-action" href={`/api/echo/v1/predictions/${result.run_id}/export?format=json`}>下载 JSON</a>
          </div>
        </section>
      )}

      {demo ? null : <OutcomeBackfill result={result} />}
      <details className="advanced-card">
        <summary>高级信息与可复现记录</summary>
        <div className="advanced-grid">
          <p><span>运行 ID</span><code>{result.run_id}</code></p>
          <p><span>人格分层</span><code>50 / 450 / {result.population.tier_counts.background || 0}</code></p>
          <p><span>关系数量</span><code>{result.population.relationship_count.toLocaleString('zh-CN')}</code></p>
          <p><span>人口约束</span><code>{result.grounding.status}</code></p>
          <p><span>历史校准</span><code>{result.calibration.status}</code></p>
          {reportMetadata ? <p><span>模型版本</span><code>{reportMetadata.model_version}</code></p> : null}
          {reportMetadata ? <p><span>数据版本</span><code>{reportMetadata.data_version}</code></p> : null}
          {reportMetadata ? <p><span>随机种子 / 路径</span><code>{reportMetadata.seed} / {reportMetadata.paths}</code></p> : null}
          <p><span>语义解释</span><code>{result.semantic_interpretation.method}</code></p>
          {worldResult ? <p><span>社会世界运行</span><code>{worldResult.run_id}</code></p> : null}
          <p className="wide"><span>确定性签名</span><code>{result.deterministic_signature}</code></p>
          {worldResult ? <p className="wide"><span>社会世界签名</span><code>{worldResult.deterministic_signature}</code></p> : null}
        </div>
        {result.participant_receipts.length ? (
          <div className="receipt-list">
            <h3>参与者依据样例</h3>
            {result.participant_receipts.slice(0, 6).map((receipt) => (
              <div key={receipt.agent_id}>
                <code>{receipt.agent_id}</code>
                <span>{receipt.segment} · {receipt.tier} · {receipt.final_action}</span>
                <p>{receipt.response_summary}</p>
              </div>
            ))}
          </div>
        ) : null}
        {demo ? null : <a href={`/api/echo/v1/predictions/${result.run_id}/replay`} target="_blank" rel="noreferrer">检查回放记录 →</a>}
      </details>
    </section>
  );
}
