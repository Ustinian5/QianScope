'use client';

import { useMemo, useState } from 'react';
import { sampleRuns } from '@/lib/sample-data';
import type { ReplayVerification, RunKind, RunRecord } from '@/lib/types';

const kindLabels: Record<RunKind, string> = {
  event: '事件预测',
  city: '城市模拟',
  statistical: '统计样例',
};

const kindCodes: Record<RunKind, string> = { event: 'EV', city: 'CT', statistical: 'ST' };

type LoadedRun = {
  id: string;
  replay?: ReplayVerification;
  result: Record<string, unknown>;
};

function resultPath(run: RunRecord) {
  if (run.kind === 'event') return `/api/qianscope/v1/event-forecasts/${run.id}/results`;
  if (run.kind === 'city') return `/api/qianscope/v1/city-simulations/${run.id}/results`;
  return `/api/qianscope/v1/simulations/${run.id}/results`;
}

function replayPath(run: RunRecord) {
  if (run.kind === 'event') return `/api/qianscope/v1/event-forecasts/${run.id}/replay`;
  if (run.kind === 'city') return `/api/qianscope/v1/city-simulations/${run.id}/replay`;
  return `/api/qianscope/v1/simulations/${run.id}/replay`;
}

export function RunExplorer() {
  const [query, setQuery] = useState('');
  const [kind, setKind] = useState<'all' | RunKind>('all');
  const [selected, setSelected] = useState<RunRecord>(sampleRuns[0]);
  const [loaded, setLoaded] = useState<LoadedRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const filteredRuns = useMemo(() => sampleRuns.filter((run) => {
    const kindMatches = kind === 'all' || run.kind === kind;
    const queryMatches = !query || `${run.id} ${run.label} ${run.model}`.toLowerCase().includes(query.toLowerCase());
    return kindMatches && queryMatches;
  }), [kind, query]);

  async function inspect(run: RunRecord) {
    setSelected(run);
    setLoading(true);
    setError('');
    try {
      const [resultResponse, replayResponse] = await Promise.all([
        fetch(resultPath(run), { cache: 'no-store' }),
        fetch(replayPath(run), { cache: 'no-store' }),
      ]);
      if (!resultResponse.ok) throw new Error(`无法读取运行结果（HTTP ${resultResponse.status}）`);
      const result = await resultResponse.json() as Record<string, unknown>;
      const replay = replayResponse.ok ? await replayResponse.json() as ReplayVerification : undefined;
      setLoaded({ id: run.id, result, replay });
    } catch (cause) {
      setLoaded(null);
      setError(cause instanceof Error ? cause.message : '无法连接运行产物。');
    } finally {
      setLoading(false);
    }
  }

  const loadedForSelection = loaded?.id === selected.id ? loaded : null;

  return (
    <div className="runs-layout">
      <section className="run-list-panel panel">
        <div className="run-filters">
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <span className="sr-only">搜索运行</span>
            <input placeholder="搜索 run ID、模型或情景…" value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          <div className="filter-tabs" role="group" aria-label="运行类型筛选">
            {(['all', 'event', 'city', 'statistical'] as const).map((item) => (
              <button className={kind === item ? 'active' : ''} onClick={() => setKind(item)} type="button" key={item}>
                {item === 'all' ? '全部' : kindLabels[item]}
              </button>
            ))}
          </div>
        </div>

        <div className="run-list" aria-label="运行列表">
          <div className="run-list-heading"><span>{filteredRuns.length} 个可复现运行</span><span>最近更新</span></div>
          {filteredRuns.map((run) => (
            <button
              className={selected.id === run.id ? 'run-list-item active' : 'run-list-item'}
              onClick={() => inspect(run)}
              type="button"
              key={run.id}
            >
              <span className={`run-kind-icon ${run.kind}`}>{kindCodes[run.kind]}</span>
              <span className="run-primary"><strong>{run.label}</strong><small>{run.id}</small></span>
              <span className="run-scope">{run.scope}</span>
              <span className="run-time">{run.createdAt}</span>
              <span className="run-verified"><i className="status-dot" />已验证</span>
              <span className="run-arrow">›</span>
            </button>
          ))}
          {filteredRuns.length === 0 ? <div className="empty-state"><strong>没有匹配运行</strong><p>尝试缩短关键词或切换类型。</p></div> : null}
        </div>
      </section>

      <aside className="run-detail panel" aria-live="polite">
        <header className="panel-header compact">
          <div><p className="panel-kicker">RUN INSPECTOR</p><h2>运行详情</h2></div>
          <span className={`run-kind-icon ${selected.kind}`}>{kindCodes[selected.kind]}</span>
        </header>
        <div className="run-detail-body">
          <div className="detail-title"><span className="status-dot" /><div><strong>{selected.label}</strong><small>{selected.id}</small></div></div>
          <dl className="detail-list">
            <div><dt>运行类型</dt><dd>{kindLabels[selected.kind]}</dd></div>
            <div><dt>模型版本</dt><dd>{selected.model}</dd></div>
            <div><dt>创建时间</dt><dd>{selected.createdAt}</dd></div>
            <div><dt>校准状态</dt><dd className="amber-text">{selected.calibration}</dd></div>
          </dl>
          <div className="detail-stat-grid">
            {selected.stats.map((stat) => <div key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong></div>)}
          </div>

          {loading ? <div className="detail-loading"><span className="spinner" /> 正在读取产物与校验哈希…</div> : null}
          {error ? <div className="detail-error"><strong>实时产物不可用</strong><p>{error}</p><small>上方仍显示仓库内已验证的运行快照。</small></div> : null}
          {loadedForSelection ? (
            <div className="loaded-result">
              <div className="loaded-heading"><span>LIVE ARTIFACT</span><strong>{loadedForSelection.replay?.valid ? '哈希有效' : '结果已读取'}</strong></div>
              <dl>
                <div><dt>顶层字段</dt><dd>{Object.keys(loadedForSelection.result).length}</dd></div>
                <div><dt>回放记录</dt><dd>{loadedForSelection.replay?.record_count ?? '—'}</dd></div>
                <div><dt>完整性</dt><dd className={loadedForSelection.replay?.valid ? 'mint-text' : ''}>{loadedForSelection.replay?.valid ? '通过' : '未校验'}</dd></div>
              </dl>
            </div>
          ) : null}

          <button className="inspect-button" disabled={loading} onClick={() => inspect(selected)} type="button">
            {loading ? '正在读取…' : '读取实时产物'} <span>→</span>
          </button>
          <p className="detail-footnote">运行清单保存输入、配置、随机种子、模型版本与输出哈希。</p>
        </div>
      </aside>
    </div>
  );
}
