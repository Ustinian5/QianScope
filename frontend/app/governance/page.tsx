import { AppShell, PageIntro } from '@/components/app-shell';

const modelCards = [
  { code: 'EV', title: '事件危险率内核', version: 'echo-event-hazard-chain-v1', status: 'prior_predictive_uncalibrated', detail: '离散时间危险率、父事件时滞、影响反馈与共同随机数反事实。' },
  { code: 'CT', title: '贵阳 Social World 运行时', version: 'independent-agent-deliberation-v1', status: 'synthetic_microstate', detail: '5,000 个加权合成人格、七类产品场景、分层地点网络与独立事件决策。' },
  { code: 'ST', title: '结构化统计基线', version: 'echo-structured-logit-v1', status: 'synthetic_ground_truth_verified', detail: '加权逻辑回归、温度校准、图扩散和价格干预验证。' },
];

export const metadata = {
  title: '数据与模型',
  description: 'ECHO-SWM 的模型卡、数据边界、质量门和安全治理。',
};

export default function GovernancePage() {
  return (
    <AppShell active="governance" title="数据与模型">
      <PageIntro
        eyebrow="MODEL & DATA GOVERNANCE"
        title="把可信边界做成产品的一部分。"
        description="校准状态、数据来源、适用范围与已知限制和概率本身同等重要；每个结果页面都必须携带这些信息。"
        actions={<a className="secondary-button" href="https://github.com/Ustinian5/SWM-Guizhou/tree/main/docs" target="_blank" rel="noreferrer">查看完整文档 ↗</a>}
      />

      <section className="governance-stats">
        <article><span>源码文件</span><strong>90</strong><small>严格 mypy 通过</small></article>
        <article><span>自动化测试</span><strong>55</strong><small>全部通过</small></article>
        <article><span>分支覆盖率</span><strong>87.93%</strong><small>门槛 75%</small></article>
        <article><span>数据契约</span><strong>20</strong><small>JSON Schema</small></article>
      </section>

      <section className="model-card-grid">
        {modelCards.map((model) => (
          <article className="panel model-card" key={model.code}>
            <header><span className={`run-kind-icon ${model.code === 'EV' ? 'event' : model.code === 'CT' ? 'city' : 'statistical'}`}>{model.code}</span><span className="status-dot" /></header>
            <p className="panel-kicker">MODEL CARD</p>
            <h2>{model.title}</h2>
            <code>{model.version}</code>
            <p>{model.detail}</p>
            <div><span>状态</span><strong>{model.status}</strong></div>
          </article>
        ))}
      </section>

      <section className="governance-grid">
        <article className="panel lineage-panel">
          <header className="panel-header"><div><p className="panel-kicker">DATA LINEAGE</p><h2>时间与证据血缘</h2></div><span className="risk-badge green">强制约束</span></header>
          <div className="lineage-flow">
            <div><span>01</span><strong>observed_at</strong><small>现实中发生或测得</small></div>
            <i>→</i>
            <div><span>02</span><strong>available_at</strong><small>预测者实际可获得</small></div>
            <i>→</i>
            <div><span>03</span><strong>as_of</strong><small>不可越过的预测截止点</small></div>
          </div>
          <div className="constraint-code"><code>available_at ≤ as_of</code><span>否则 Schema 直接拒绝</span></div>
        </article>

        <article className="panel safety-panel">
          <header className="panel-header"><div><p className="panel-kicker">SAFETY BOUNDARY</p><h2>允许与禁止</h2></div></header>
          <div className="safety-columns">
            <div><strong className="mint-text">允许</strong><ul><li>授权、聚合或合成数据</li><li>群体级情景与敏感性分析</li><li>带人工审查的研究工作流</li></ul></div>
            <div><strong className="red-text">禁止</strong><ul><li>重新识别真实个人</li><li>高风险个体决策</li><li>歧视、操纵或规避合规</li></ul></div>
          </div>
        </article>
      </section>

      <article className="release-checklist panel">
        <header className="panel-header"><div><p className="panel-kicker">PROMOTION GATES</p><h2>从原型到真实领域预测</h2></div><span className="progress-label">3 / 7 READY</span></header>
        <div className="release-steps">
          {[
            ['类型化契约与防泄漏', true], ['确定性随机流与回放', true], ['离线工程质量门', true],
            ['目标领域历史基准率', false], ['滚动时间留出回测', false], ['分事件/窗口校准', false], ['外部验证与治理审批', false],
          ].map(([label, ready], index) => (
            <div className={ready ? 'ready' : ''} key={label as string}><span>{ready ? '✓' : index + 1}</span><strong>{label as string}</strong></div>
          ))}
        </div>
      </article>
    </AppShell>
  );
}
