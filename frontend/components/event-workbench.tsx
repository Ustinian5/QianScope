'use client';

import { useEffect, useMemo, useState } from 'react';
import { DataModeBadge } from './app-shell';
import { LineChart, type ChartSeries } from './line-chart';
import { sampleEventForecast, sampleHealth } from '@/lib/sample-data';
import type { EventForecast, EventForecastResponse, ReplayVerification, RuntimeHealth } from '@/lib/types';

type QueryMode = 'template' | 'prompt';
type RunState = 'idle' | 'running' | 'complete' | 'error';

const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

async function readError(response: Response) {
  try {
    const payload = await response.json() as { detail?: string; hint?: string };
    return [payload.detail, payload.hint].filter(Boolean).join(' ');
  } catch {
    return `请求失败（HTTP ${response.status}）`;
  }
}

export function EventWorkbench() {
  const [forecast, setForecast] = useState<EventForecast>(sampleEventForecast);
  const [health, setHealth] = useState<RuntimeHealth>(sampleHealth);
  const [live, setLive] = useState(false);
  const [queryMode, setQueryMode] = useState<QueryMode>('template');
  const [prompt, setPrompt] = useState('根据订单、舆情和组织状态，预测未来 45 天关键事件及提前干预影响。');
  const [activeCandidate, setActiveCandidate] = useState('demand_downturn');
  const [runState, setRunState] = useState<RunState>('idle');
  const [error, setError] = useState('');
  const [replay, setReplay] = useState<ReplayVerification | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/qianscope/health', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('health check failed');
        setHealth(await response.json() as RuntimeHealth);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const branches = Object.values(forecast.branches);
  const control = forecast.branches.control ?? branches[0];
  const comparison = branches.find((branch) => branch.branch_id !== control.branch_id) ?? control;
  const controlCandidate = control.candidates.find((item) => item.candidate_id === activeCandidate) ?? control.candidates[0];
  const comparisonCandidate = comparison.candidates.find((item) => item.candidate_id === controlCandidate.candidate_id) ?? comparison.candidates[0];

  const probabilitySeries = useMemo<ChartSeries[]>(() => [
    {
      label: '基准预测',
      color: '#82918b',
      values: controlCandidate.probability_curve.map((point) => ({ x: point.day, y: point.cumulative_probability })),
    },
    {
      label: '提前响应',
      color: '#8ff2c7',
      values: comparisonCandidate.probability_curve.map((point) => ({ x: point.day, y: point.cumulative_probability })),
    },
  ], [comparisonCandidate, controlCandidate]);

  async function runForecast() {
    setRunState('running');
    setError('');
    setReplay(null);
    const body = queryMode === 'template'
      ? {}
      : { natural_language_prompt: prompt, as_of: new Date().toISOString() };
    try {
      const response = await fetch('/api/qianscope/v1/event-forecasts', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await readError(response));
      const payload = await response.json() as EventForecastResponse;
      setForecast(payload.forecast);
      setActiveCandidate(payload.forecast.branches.control?.candidates[0]?.candidate_id ?? activeCandidate);
      setReplay(payload.summary.replay);
      setLive(true);
      setRunState('complete');
    } catch (cause) {
      setRunState('error');
      setError(cause instanceof Error ? cause.message : '预测请求失败，请检查后端服务。');
    }
  }

  async function verifyReplay() {
    setError('');
    try {
      const response = await fetch(`/api/qianscope/v1/event-forecasts/${forecast.run_id}/replay`, { cache: 'no-store' });
      if (!response.ok) throw new Error(await readError(response));
      setReplay(await response.json() as ReplayVerification);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '回放校验失败。');
    }
  }

  function exportForecast() {
    const blob = new Blob([JSON.stringify(forecast, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${forecast.run_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="workbench-grid">
      <aside className="control-panel panel">
        <header className="panel-header compact">
          <div>
            <p className="panel-kicker">QUERY CONTRACT</p>
            <h2>预测设置</h2>
          </div>
          <span className="step-badge">01</span>
        </header>

        <div className="control-body">
          <fieldset className="segmented-field">
            <legend>查询来源</legend>
            <div className="segmented-control">
              <button className={queryMode === 'template' ? 'active' : ''} onClick={() => setQueryMode('template')} type="button">内置情景</button>
              <button className={queryMode === 'prompt' ? 'active' : ''} onClick={() => setQueryMode('prompt')} type="button">自然语言</button>
            </div>
          </fieldset>

          {queryMode === 'template' ? (
            <label className="form-field">
              <span>情景模板</span>
              <select defaultValue="market_event_chain_45d">
                <option value="market_event_chain_45d">市场—组织事件链 · AI 动态刷新</option>
              </select>
              <small>来自 scenarios/event_chain_forecast.json</small>
            </label>
          ) : (
            <label className="form-field">
              <span>预测问题</span>
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} />
              <small>{health.llm_configured ? `${health.llm_model || '大模型'} 会编译候选、机制与本次假设；概率仍由数值内核计算。` : '当前后端未配置 LLM，此模式运行时会被拒绝。'}</small>
            </label>
          )}

          <div className="form-grid three">
            <label className="form-field"><span>窗口</span><input value="45 天" readOnly /></label>
            <label className="form-field"><span>路径/分支</span><input value="2,048" readOnly /></label>
            <label className="form-field"><span>随机种子</span><input value="2026" readOnly /></label>
          </div>

          <div className="contract-summary">
            <p><span>候选事件</span><strong>4</strong></p>
            <p><span>反事实分支</span><strong>2</strong></p>
            <p><span>已知信号</span><strong>2</strong></p>
            <p><span>校准状态</span><strong className="amber-text">未校准先验</strong></p>
          </div>

          <button
            className="run-button"
            disabled={runState === 'running' || (queryMode === 'prompt' && !prompt.trim())}
            onClick={runForecast}
            type="button"
          >
            {runState === 'running' ? <><span className="spinner" /> 正在采样联合路径…</> : <>运行事件预测 <span>→</span></>}
          </button>
          <p className="run-note">每次运行都会实时调用 DeepSeek 刷新情景，并保存调用回执与带哈希清单的产物。</p>
        </div>
      </aside>

      <section className="result-stack" aria-live="polite">
        <div className="result-toolbar">
          <DataModeBadge live={live} />
          <span className="run-id">{forecast.run_id}</span>
          <div className="toolbar-spacer" />
          <button className="toolbar-button" onClick={verifyReplay} type="button">校验回放</button>
          <button className="toolbar-button" onClick={exportForecast} type="button">导出 JSON</button>
        </div>

        {error ? <div className="error-banner" role="alert"><span>!</span><div><strong>请求未完成</strong><p>{error}</p></div></div> : null}
        {runState === 'complete' ? <div className="success-banner"><span>✓</span> 新预测已完成并切换至实时结果。</div> : null}

        <article className="panel chart-panel">
          <header className="panel-header">
            <div>
              <p className="panel-kicker">CUMULATIVE EVENT PROBABILITY</p>
              <h2>{controlCandidate.label}</h2>
            </div>
            <div className="legend"><span><i className="control" />基准</span><span><i className="response" />提前响应</span></div>
          </header>
          <div className="candidate-tabs" role="tablist" aria-label="候选事件">
            {control.candidates.map((item) => (
              <button
                aria-selected={activeCandidate === item.candidate_id}
                className={activeCandidate === item.candidate_id ? 'active' : ''}
                key={item.candidate_id}
                onClick={() => setActiveCandidate(item.candidate_id)}
                role="tab"
                type="button"
              >
                <span>{formatPercent(item.occurrence_probability)}</span>{item.label}
              </button>
            ))}
          </div>
          <div className="chart-wrap">
            <LineChart
              label={`${controlCandidate.label}的基准与提前响应累计发生概率曲线`}
              series={probabilitySeries}
            />
          </div>
          <div className="chart-stat-row">
            <div><span>基准概率</span><strong>{formatPercent(controlCandidate.occurrence_probability)}</strong></div>
            <div><span>干预概率</span><strong>{formatPercent(comparisonCandidate.occurrence_probability)}</strong></div>
            <div><span>概率变化</span><strong className={comparisonCandidate.occurrence_probability <= controlCandidate.occurrence_probability ? 'mint-text' : 'amber-text'}>{((comparisonCandidate.occurrence_probability - controlCandidate.occurrence_probability) * 100).toFixed(1)}pp</strong></div>
            <div><span>条件中位时间</span><strong>D{Math.round(controlCandidate.conditional_time_to_event_days?.p50 ?? 0)}</strong></div>
          </div>
        </article>

        <div className="result-grid two">
          <article className="panel compact-panel">
            <header className="panel-header compact"><div><p className="panel-kicker">COUNTERFACTUAL DELTA</p><h2>全部候选事件</h2></div></header>
            <div className="result-table" role="table" aria-label="候选事件概率对比">
              <div className="result-table-head" role="row"><span>事件</span><span>基准</span><span>干预</span><span>Δ</span></div>
              {control.candidates.map((item) => {
                const compared = comparison.candidates.find((candidateItem) => candidateItem.candidate_id === item.candidate_id) ?? item;
                const delta = compared.occurrence_probability - item.occurrence_probability;
                return (
                  <div className="result-table-row" role="row" key={item.candidate_id}>
                    <strong>{item.label}</strong>
                    <span>{formatPercent(item.occurrence_probability)}</span>
                    <span>{formatPercent(compared.occurrence_probability)}</span>
                    <span className={delta <= 0 ? 'mint-text' : 'amber-text'}>{delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}pp</span>
                  </div>
                );
              })}
            </div>
          </article>

          <article className="panel compact-panel">
            <header className="panel-header compact"><div><p className="panel-kicker">EVENT CHAINS</p><h2>高频非空路径</h2></div></header>
            <ol className="chain-list">
              {control.top_event_chains.slice(0, 4).map((chain, index) => (
                <li key={`${chain.event_sequence.join('-')}-${index}`}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div>{chain.event_sequence.map((eventId) => <strong key={eventId}>{eventId}</strong>)}</div>
                  <em>{formatPercent(chain.probability)}</em>
                </li>
              ))}
            </ol>
          </article>
        </div>

        <article className="boundary-note">
          <span className="boundary-icon">i</span>
          <div><strong>解释边界</strong><p>{forecast.warnings[0] ?? forecast.disclaimer}</p></div>
          <div className="verification-state"><span className={replay?.valid ? 'status-dot' : 'status-dot muted'} />{replay?.valid ? `${replay.record_count} 条回放记录有效` : '可按需校验运行产物'}</div>
        </article>
      </section>
    </div>
  );
}
