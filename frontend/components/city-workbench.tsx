'use client';

import { useMemo, useState } from 'react';
import { DataModeBadge } from './app-shell';
import { LineChart, type ChartSeries } from './line-chart';
import { sampleCityForecast } from '@/lib/sample-data';
import type { CityForecast, CitySimulationResponse, ReplayVerification } from '@/lib/types';

type RunState = 'idle' | 'running' | 'complete' | 'error';

const branchLabels: Record<string, string> = {
  control: '不新增干预',
  mobility_support: '交通支持',
  integrated_response: '综合响应',
};

const branchColors: Record<string, string> = {
  control: '#697872',
  mobility_support: '#f3c979',
  integrated_response: '#8ff2c7',
};

const metricLabels: Record<string, string> = {
  life_satisfaction: '生活满意度',
  government_trust: '政府信任',
  economic_confidence: '经济信心',
  consumption_index: '消费指数',
  employment_rate: '就业概率',
  congestion_index: '拥堵指数',
  health_system_load: '医疗负载',
  rumor_belief: '传言相信度',
  stress: '压力',
  organization_vitality: '组织活力',
};

async function responseMessage(response: Response) {
  try {
    const payload = await response.json() as { detail?: string; hint?: string };
    return [payload.detail, payload.hint].filter(Boolean).join(' ');
  } catch {
    return `请求失败（HTTP ${response.status}）`;
  }
}

export function CityWorkbench() {
  const [forecast, setForecast] = useState<CityForecast>(sampleCityForecast);
  const [prototypeCount, setPrototypeCount] = useState(5000);
  const [samples, setSamples] = useState(2);
  const [seed, setSeed] = useState(2026);
  const [metric, setMetric] = useState('economic_confidence');
  const [runState, setRunState] = useState<RunState>('idle');
  const [live, setLive] = useState(false);
  const [error, setError] = useState('');
  const [replay, setReplay] = useState<ReplayVerification | null>(null);

  const trajectorySeries = useMemo<ChartSeries[]>(() => Object.entries(forecast.branch_trajectories).map(([branchId, points]) => ({
    label: branchLabels[branchId] ?? branchId,
    color: branchColors[branchId] ?? '#b7c3be',
    values: points.map((point) => ({ x: point.day, y: point.metrics[metric]?.p50 ?? 0 })),
  })), [forecast, metric]);

  const selectedDistricts = forecast.final_district_metrics.filter((item) => item.branch_id === 'integrated_response');

  async function runCitySimulation() {
    setRunState('running');
    setError('');
    setReplay(null);
    try {
      const response = await fetch('/api/qianscope/v1/cities/suzhou/simulate', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ prototype_count: prototypeCount, samples, seed }),
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      const payload = await response.json() as CitySimulationResponse;
      setForecast(payload.forecast);
      setReplay(payload.summary.replay);
      setLive(true);
      setRunState('complete');
    } catch (cause) {
      setRunState('error');
      setError(cause instanceof Error ? cause.message : '城市模拟请求失败。');
    }
  }

  async function verifyReplay() {
    setError('');
    try {
      const response = await fetch(`/api/qianscope/v1/city-simulations/${forecast.run_id}/replay`, { cache: 'no-store' });
      if (!response.ok) throw new Error(await responseMessage(response));
      setReplay(await response.json() as ReplayVerification);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '回放校验失败。');
    }
  }

  const integrated = forecast.counterfactual_deltas.integrated_response ?? {};

  return (
    <div className="city-layout">
      <section className="city-main result-stack" aria-live="polite">
        <div className="result-toolbar">
          <DataModeBadge live={live} />
          <span className="run-id">{forecast.run_id}</span>
          <div className="toolbar-spacer" />
          <button className="toolbar-button" onClick={verifyReplay} type="button">校验回放</button>
          <a className="toolbar-button" href={`/api/qianscope/v1/city-simulations/${forecast.run_id}/report`} target="_blank" rel="noreferrer">HTML 报告 ↗</a>
        </div>

        {error ? <div className="error-banner" role="alert"><span>!</span><div><strong>请求未完成</strong><p>{error}</p></div></div> : null}
        {runState === 'complete' ? <div className="success-banner"><span>✓</span> 新城市路径已完成，所有指标已切换至实时结果。</div> : null}

        <section className="city-stat-grid" aria-label="苏州城市世界规模">
          <article><span>合成人口原型</span><strong>{forecast.prototype_count.toLocaleString('zh-CN')}</strong><small>加权微观状态</small></article>
          <article><span>代表常住人口</span><strong>{(forecast.represented_population / 10_000).toFixed(2)}<em> 万</em></strong><small>公开统计锚点</small></article>
          <article><span>区县</span><strong>10</strong><small>空间与服务容量</small></article>
          <article><span>反事实分支</span><strong>{Object.keys(forecast.branch_trajectories).length}</strong><small>共享随机流</small></article>
        </section>

        <article className="panel chart-panel city-chart-panel">
          <header className="panel-header responsive-header">
            <div>
              <p className="panel-kicker">30-DAY MEDIAN TRAJECTORY</p>
              <h2>{metricLabels[metric]}</h2>
            </div>
            <label className="inline-select">
              <span className="sr-only">选择指标</span>
              <select value={metric} onChange={(event) => setMetric(event.target.value)}>
                {Object.entries(metricLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
              </select>
            </label>
          </header>
          <div className="chart-legend-row">
            {trajectorySeries.map((series) => <span key={series.label}><i style={{ background: series.color }} />{series.label}</span>)}
          </div>
          <div className="chart-wrap city-chart">
            <LineChart label={`${metricLabels[metric]}的 30 日三分支中位轨迹`} series={trajectorySeries} />
          </div>
        </article>

        <section className="delta-card-grid">
          {[
            ['government_trust', '政府信任', true],
            ['consumption_index', '消费指数', true],
            ['stress', '压力', false],
            ['organization_vitality', '组织活力', true],
          ].map(([key, label, positiveIsGood]) => {
            const value = integrated[key as string] ?? 0;
            const beneficial = positiveIsGood ? value >= 0 : value <= 0;
            return (
              <article className="delta-card" key={key as string}>
                <span>{label as string}</span>
                <strong className={beneficial ? 'mint-text' : 'amber-text'}>{value > 0 ? '+' : ''}{value.toFixed(4)}</strong>
                <small>综合响应 vs control</small>
              </article>
            );
          })}
        </section>

        <article className="panel district-panel">
          <header className="panel-header">
            <div><p className="panel-kicker">DISTRICT FINAL STATE</p><h2>区县期末状态 · 综合响应 P50</h2></div>
            <span className="risk-badge">合成微观状态</span>
          </header>
          <div className="district-table-wrap">
            <table className="district-table">
              <thead><tr><th>区县</th><th>代表人口</th><th>满意度</th><th>经济信心</th><th>就业</th><th>拥堵</th><th>传言</th></tr></thead>
              <tbody>
                {selectedDistricts.map((district) => (
                  <tr key={district.district_id}>
                    <th>{district.district_name}</th>
                    <td>{(district.represented_population / 10_000).toFixed(1)} 万</td>
                    <td>{district.metrics.life_satisfaction?.p50.toFixed(3) ?? '—'}</td>
                    <td>{district.metrics.economic_confidence?.p50.toFixed(3) ?? '—'}</td>
                    <td>{(district.metrics.employment_probability ?? district.metrics.employment_rate)?.p50.toFixed(3) ?? '—'}</td>
                    <td>{district.metrics.congestion_index?.p50.toFixed(3) ?? '—'}</td>
                    <td>{district.metrics.rumor_belief?.p50.toFixed(3) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="boundary-note">
          <span className="boundary-icon">i</span>
          <div><strong>数据边界</strong><p>{forecast.warnings[0] ?? forecast.disclaimer}</p></div>
          <div className="verification-state"><span className={replay?.valid ? 'status-dot' : 'status-dot muted'} />{replay?.valid ? `${replay.verified_snapshot_count ?? replay.snapshot_count} 个快照已验证` : '等待本次回放校验'}</div>
        </article>
      </section>

      <aside className="city-controls panel">
        <header className="panel-header compact">
          <div><p className="panel-kicker">SCOPE QUERY</p><h2>城市模拟设置</h2></div>
          <span className="step-badge">01</span>
        </header>
        <div className="control-body">
          <div className="city-identity">
            <span>苏</span>
            <div><strong>苏州市</strong><small>10 districts · 2025 anchors</small></div>
            <i className="status-dot" />
          </div>
          <label className="form-field">
            <span>情景模板</span>
            <select defaultValue="suzhou_resilience_30d"><option value="suzhou_resilience_30d">城市韧性 · 30 天</option></select>
          </label>
          <label className="form-field">
            <span>合成人口原型 <output>{prototypeCount.toLocaleString('zh-CN')}</output></span>
            <input min="5000" max="25000" step="1000" type="range" value={prototypeCount} onChange={(event) => setPrototypeCount(Number(event.target.value))} />
            <small>允许范围 5,000–250,000；当前前端控制在 25,000 内。</small>
          </label>
          <label className="form-field">
            <span>蒙特卡洛路径/分支 <output>{samples}</output></span>
            <input min="1" max="16" step="1" type="range" value={samples} onChange={(event) => setSamples(Number(event.target.value))} />
          </label>
          <label className="form-field">
            <span>随机种子</span>
            <input min="0" type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
          </label>
          <div className="scenario-events">
            <span>事件</span>
            <p><i className="event-dot economic" />出口订单走弱<small>D3–D23</small></p>
            <p><i className="event-dot weather" />夏季热浪<small>D8–D17</small></p>
            <p><i className="event-dot info" />公共服务传言<small>D12–D19</small></p>
          </div>
          <button className="run-button" disabled={runState === 'running'} onClick={runCitySimulation} type="button">
            {runState === 'running' ? <><span className="spinner" /> 正在演化城市状态…</> : <>运行城市模拟 <span>→</span></>}
          </button>
          <p className="run-note">预计计算 {prototypeCount.toLocaleString('zh-CN')} × {samples} × 3 × 31 个主体状态切片。</p>
        </div>
      </aside>
    </div>
  );
}
