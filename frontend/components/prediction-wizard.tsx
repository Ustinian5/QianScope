'use client';

import { useEffect, useRef, useState } from 'react';
import { PredictionResults } from '@/components/prediction-results';
import type { PredictionResult } from '@/lib/research-types';
import { buildWorldRequest } from '@/lib/world-request';
import type { WorldSimulationResult } from '@/lib/world-types';

type QuestionKind = 'single_choice' | 'multiple_choice' | 'scale' | 'ranking' | 'numeric' | 'open_text';

type DraftQuestion = {
  id: string;
  text: string;
  kind: QuestionKind;
  construct: string;
  options: string[];
  scaleMin?: number;
  scaleMax?: number;
};

type ImportedDataset = {
  filename: string;
  datasetId: string;
  payload: Record<string, unknown>;
};

type MetricDirection = 'increase' | 'decrease';

const kindLabels: Record<QuestionKind, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  scale: '量表题',
  ranking: '排序题',
  numeric: '数值题',
  open_text: '开放题',
};

const constructLabels: Record<string, string> = {
  awareness: '知晓程度',
  support: '支持与反对',
  trust: '信任',
  risk: '风险感受',
  emotion: '情绪',
  participation: '参与意愿',
  sharing: '传播意愿',
  confidence: '态度确定性',
  fairness: '公平感受',
  personal_impact: '个人影响',
  general_attitude: '总体态度',
};

const defaultQuestions: DraftQuestion[] = [
  { id: 'q01_awareness', text: '在事件发生后，你认为自己会多快注意到这件事？', kind: 'single_choice', construct: 'awareness', options: ['很可能不会注意', '过一段时间才注意', '较快注意到', '几乎立即注意到'] },
  { id: 'q02_attitude', text: '你对这件事的总体态度如何？', kind: 'scale', construct: 'support', options: [], scaleMin: 1, scaleMax: 5 },
  { id: 'q03_stance', text: '如果现在必须表态，你最可能选择哪一种？', kind: 'single_choice', construct: 'support', options: ['反对', '保持观望', '支持'] },
  { id: 'q04_actions', text: '你接下来可能采取哪些行动？（可多选）', kind: 'multiple_choice', construct: 'participation', options: ['暂不行动', '继续了解', '与他人讨论', '实际参与'] },
  { id: 'q05_concerns', text: '请按你最在意的因素进行排序。', kind: 'ranking', construct: 'personal_impact', options: ['实际收益', '潜在风险', '是否公平', '信息是否清楚'] },
  { id: 'q06_trust', text: '你对事件相关信息的信任程度是多少？', kind: 'scale', construct: 'trust', options: [], scaleMin: 1, scaleMax: 7 },
  { id: 'q07_participation', text: '你实际参与相关行动的可能性是多少（0—100）？', kind: 'numeric', construct: 'participation', options: [], scaleMin: 0, scaleMax: 100 },
  { id: 'q08_sharing', text: '你最可能如何传播这件事？', kind: 'single_choice', construct: 'sharing', options: ['不主动传播', '私下告诉熟人', '公开分享或讨论'] },
  { id: 'q09_emotion', text: '这件事最可能让你产生怎样的情绪？', kind: 'single_choice', construct: 'emotion', options: ['担忧或不满', '平静或无明显感觉', '期待或认同'] },
  { id: 'q10_reason', text: '请简要说明你形成上述态度的主要原因。', kind: 'open_text', construct: 'general_attitude', options: [] },
];

const stepLabels = ['预测目标', '目标人群', '预测问卷', '时间与情景', '确认运行'];
const optionKinds: QuestionKind[] = ['single_choice', 'multiple_choice', 'ranking'];
const channelOptions = [
  { value: 'social_media', label: '社交网络' },
  { value: 'news', label: '新闻信息' },
  { value: 'interpersonal', label: '熟人交流' },
  { value: 'community', label: '社区渠道' },
  { value: 'search', label: '主动搜索' },
  { value: 'onsite', label: '现场接触' },
];

const decisionMetricOptions = [
  { value: 'support', label: '支持', direction: 'increase' as const },
  { value: 'awareness', label: '知晓', direction: 'increase' as const },
  { value: 'discussion', label: '讨论', direction: 'increase' as const },
  { value: 'participation', label: '参与', direction: 'increase' as const },
  { value: 'trust', label: '信任', direction: 'increase' as const },
  { value: 'sharing', label: '传播', direction: 'increase' as const },
  { value: 'opposition', label: '反对', direction: 'decrease' as const },
  { value: 'polarization', label: '分化', direction: 'decrease' as const },
  { value: 'silence', label: '沉默', direction: 'decrease' as const },
  { value: 'exit', label: '退出', direction: 'decrease' as const },
];

function auxiliaryMetrics(primaryMetric: string) {
  return [
    { metric_id: 'awareness', label: '知晓', direction: 'increase', weight: 0.5 },
    { metric_id: 'polarization', label: '分化', direction: 'decrease', weight: 0.5 },
    { metric_id: 'discussion', label: '讨论', direction: 'increase', weight: 0.4 },
  ].filter((item) => item.metric_id !== primaryMetric).slice(0, 2);
}

function positionFor(index: number, count: number) {
  return count <= 1 ? 0 : -1 + (2 * index) / (count - 1);
}

function safeId(label: string, index: number) {
  const normalized = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  return normalized || `option_${index + 1}`;
}

function serializeQuestion(question: DraftQuestion, index: number) {
  const options = optionKinds.includes(question.kind)
    ? question.options.filter(Boolean).map((label, optionIndex, all) => ({
        option_id: safeId(label, optionIndex),
        label,
        position: positionFor(optionIndex, all.length),
      }))
    : [];
  return {
    question_id: question.id || `q${String(index + 1).padStart(2, '0')}`,
    text: question.text,
    kind: question.kind,
    construct: question.construct,
    direction: 1,
    options,
    scale_min: ['scale', 'numeric'].includes(question.kind) ? question.scaleMin : null,
    scale_max: ['scale', 'numeric'].includes(question.kind) ? question.scaleMax : null,
    required: true,
  };
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await response.json() as T & { detail?: unknown };
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    throw new Error(detail || '数据处理失败。');
  }
  return body;
}

export function PredictionWizard() {
  const [step, setStep] = useState(1);
  const [projectTitle, setProjectTitle] = useState('公共学习空间开放事件预测');
  const [eventTitle, setEventTitle] = useState('公共学习空间延长开放时间');
  const [eventDescription, setEventDescription] = useState('一个公共学习空间宣布，下月起将开放时间延长至夜间，并提供线上预约、安静学习区和小组交流区。');
  const [evidenceNotes, setEvidenceNotes] = useState('');
  const [learningGoal, setLearningGoal] = useState('了解人们的知晓、支持、讨论与参与反应');
  const [populationName, setPopulationName] = useState('通用成年人群');
  const [populationSize, setPopulationSize] = useState(5000);
  const [ageGroup, setAgeGroup] = useState('all');
  const [socialRole, setSocialRole] = useState('all');
  const [questions, setQuestions] = useState<DraftQuestion[]>(defaultQuestions);
  const [populationMargins, setPopulationMargins] = useState<ImportedDataset | null>(null);
  const [calibrationHistory, setCalibrationHistory] = useState<ImportedDataset | null>(null);
  const [editingQuestion, setEditingQuestion] = useState(0);
  const [horizon, setHorizon] = useState(30);
  const [paths, setPaths] = useState(8);
  const [eventImpact, setEventImpact] = useState(0.2);
  const [credibility, setCredibility] = useState(0.72);
  const [channels, setChannels] = useState(['social_media', 'interpersonal', 'community']);
  const [alternative, setAlternative] = useState('如果信息传播较慢、关键细节暂不明确');
  const [primaryMetric, setPrimaryMetric] = useState('support');
  const [metricDirection, setMetricDirection] = useState<MetricDirection>('increase');
  const [minimumEffect, setMinimumEffect] = useState(0.02);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [worldResult, setWorldResult] = useState<WorldSimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const questionnaireFileInput = useRef<HTMLInputElement>(null);
  const populationFileInput = useRef<HTMLInputElement>(null);
  const calibrationFileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const runId = search.get('run');
    const worldRunId = search.get('world');
    if (!runId) return;
    const predictionRequest = fetch(`/api/echo/v1/predictions/${runId}`, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error('没有找到这次预测。');
        return response.json() as Promise<PredictionResult>;
      });
    const worldRequest = worldRunId
      ? fetch(`/api/echo/v1/social-world/simulations/${worldRunId}`, { cache: 'no-store' })
          .then((response) => response.ok ? response.json() as Promise<WorldSimulationResult> : null)
          .catch(() => null)
      : Promise.resolve(null);
    Promise.all([predictionRequest, worldRequest])
      .then(([prediction, world]) => {
        setResult(prediction);
        setWorldResult(world);
        setStep(5);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : '读取失败'))
      .finally(() => setLoading(false));
  }, []);

  function toggleChannel(channel: string) {
    setChannels((current) => current.includes(channel)
      ? current.filter((item) => item !== channel)
      : [...current, channel]);
  }

  function updateQuestion(index: number, changes: Partial<DraftQuestion>) {
    setQuestions((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...changes } : item));
  }

  function changeKind(index: number, kind: QuestionKind) {
    const needsOptions = optionKinds.includes(kind);
    updateQuestion(index, {
      kind,
      options: needsOptions && !questions[index].options.length ? ['选项一', '选项二'] : questions[index].options,
      scaleMin: ['scale', 'numeric'].includes(kind) ? (questions[index].scaleMin ?? (kind === 'scale' ? 1 : 0)) : undefined,
      scaleMax: ['scale', 'numeric'].includes(kind) ? (questions[index].scaleMax ?? (kind === 'scale' ? 5 : 100)) : undefined,
    });
  }

  function addQuestion() {
    const next = questions.length + 1;
    setQuestions((current) => [...current, {
      id: `q${String(next).padStart(2, '0')}`,
      text: '输入你的问题',
      kind: 'single_choice',
      construct: 'support',
      options: ['选项一', '选项二'],
    }]);
    setEditingQuestion(questions.length);
  }

  async function importQuestionnaire(file: File) {
    setError('');
    try {
      const parsed = JSON.parse(await file.text()) as { questions?: Array<Record<string, unknown>> } | Array<Record<string, unknown>>;
      const imported = Array.isArray(parsed) ? parsed : parsed.questions;
      if (!imported?.length) throw new Error('文件中没有 questions 数组。');
      const normalized = imported.map((item, index): DraftQuestion => {
        const options = Array.isArray(item.options)
          ? item.options.map((option) => typeof option === 'string' ? option : String((option as { label?: string }).label || '')).filter(Boolean)
          : [];
        return {
          id: String(item.question_id || item.id || `q${index + 1}`),
          text: String(item.text || item.question_text || '未命名问题'),
          kind: String(item.kind || item.response_type || 'single_choice') as QuestionKind,
          construct: String(item.construct || item.latent_construct || 'support'),
          options,
          scaleMin: Number(item.scale_min ?? 1),
          scaleMax: Number(item.scale_max ?? 5),
        };
      });
      setQuestions(normalized);
      setEditingQuestion(0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '问卷导入失败。');
    }
  }

  async function importDataset(file: File, kind: 'population' | 'calibration') {
    setError('');
    try {
      const parsed = JSON.parse(await file.text()) as Record<string, unknown>;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('数据文件必须是一个 JSON 对象。');
      }
      const datasetId = String(parsed.dataset_id || '');
      if (!datasetId) throw new Error('数据文件缺少 dataset_id。');
      if (parsed.authorization_confirmed !== true || parsed.deidentified_or_aggregate !== true) {
        throw new Error('只接受已确认授权且去标识化或聚合的数据。');
      }
      if (kind === 'population' && (!parsed.margins || typeof parsed.margins !== 'object')) {
        throw new Error('人口数据文件缺少 margins。');
      }
      if (kind === 'calibration' && !Array.isArray(parsed.observations)) {
        throw new Error('历史数据文件缺少 observations 数组。');
      }
      const imported = { filename: file.name, datasetId, payload: parsed };
      if (kind === 'population') setPopulationMargins(imported);
      else setCalibrationHistory(imported);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '数据导入失败。');
    }
  }

  function canContinue() {
    if (step === 1) return projectTitle.trim() && eventTitle.trim() && eventDescription.trim().length >= 3 && channels.length > 0;
    if (step === 2) return populationSize >= 5000 && populationSize <= 20000;
    if (step === 3) return questions.length > 0 && questions.every((item) => item.text.trim());
    return true;
  }

  async function runPrediction() {
    setLoading(true);
    setError('');
    const now = Date.now();
    const filters: Record<string, string[]> = {};
    if (ageGroup !== 'all') filters.age_group = [ageGroup];
    if (socialRole !== 'all') filters.social_role = [socialRole];
    const projectId = `project_${now}`;
    const eventId = `event_${now}`;
    const payload: Record<string, unknown> = {
      project_id: projectId,
      title: projectTitle,
      population: {
        population_id: `population_${now}`,
        name: populationName,
        size: populationSize,
        seed: 2026,
        filters,
      },
      questionnaire: {
        questionnaire_id: `questionnaire_${now}`,
        title: `${projectTitle}问卷`,
        description: learningGoal,
        questions: questions.map(serializeQuestion),
      },
      event: {
        event_id: eventId,
        title: eventTitle,
        description: eventDescription,
        actors: [],
        audience: populationName,
        channels,
        evidence: evidenceNotes.trim() ? [{
          evidence_id: 'user_background',
          summary: evidenceNotes,
          source: 'user_supplied',
          credibility,
          available_at: new Date(now).toISOString(),
        }] : [],
        intensity: 0.68,
        credibility,
        valence: eventImpact,
        value_signals: {},
        expected_outcomes: [learningGoal],
        alternatives: alternative.trim() ? [{
          variant_id: 'alternative_context',
          label: `替代情景：${alternative}`,
          description: alternative,
          intensity_multiplier: 0.78,
          credibility_shift: -0.15,
          value_signal_adjustments: {},
        }] : [],
      },
      horizon_ticks: horizon,
      paths,
      seed: 2026,
      evaluation_protocol: {
        baseline_scenario_id: 'baseline_no_event',
        primary_metric: {
          metric_id: primaryMetric,
          label: decisionMetricOptions.find((item) => item.value === primaryMetric)?.label || primaryMetric,
          direction: metricDirection,
          weight: 1,
        },
        auxiliary_metrics: auxiliaryMetrics(primaryMetric),
        minimum_effect: minimumEffect,
        forecast_as_of: new Date(now).toISOString(),
        future_information_policy: 'exclude',
      },
      group_fields: ['age_group', 'gender', 'social_role', 'organization_type', 'education_level', 'primary_channel'],
    };
    try {
      if (populationMargins) {
        const registered = await postJson<{ dataset_id: string }>(
          '/api/echo/v1/population-margins',
          populationMargins.payload,
        );
        payload.population_margin_id = registered.dataset_id;
      }
      if (calibrationHistory) {
        const registered = await postJson<{ dataset_id: string }>(
          '/api/echo/v1/calibration-datasets',
          calibrationHistory.payload,
        );
        const profile = await postJson<{ calibration_id: string; status: string }>(
          '/api/echo/v1/calibrations',
          { dataset_id: registered.dataset_id },
        );
        payload.calibration_id = profile.calibration_id;
      }
      const worldPayload = buildWorldRequest({
        projectId,
        eventId,
        eventTitle,
        eventDescription,
        populationSize,
        filters,
        channels,
        horizon,
        paths,
        credibility,
        eventImpact,
        evidenceNotes,
      });
      const [predictionOutcome, worldOutcome] = await Promise.allSettled([
        postJson<PredictionResult>('/api/echo/v1/predictions', payload),
        postJson<WorldSimulationResult>('/api/echo/v1/social-world/simulations', worldPayload),
      ]);
      if (predictionOutcome.status === 'rejected') throw predictionOutcome.reason;
      const body = predictionOutcome.value;
      const world = worldOutcome.status === 'fulfilled' ? worldOutcome.value : null;
      setResult(body);
      setWorldResult(world);
      const worldQuery = world ? `&world=${encodeURIComponent(world.run_id)}` : '';
      window.history.replaceState({}, '', `/predict?run=${encodeURIComponent(body.run_id)}${worldQuery}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '预测未能完成。');
    } finally {
      setLoading(false);
    }
  }

  function startNew() {
    setResult(null);
    setWorldResult(null);
    setStep(1);
    setError('');
    window.history.replaceState({}, '', '/predict');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (result) return <PredictionResults result={result} worldResult={worldResult} onNew={startNew} />;

  return (
    <section className="wizard-shell">
      <header className="wizard-heading">
        <p>NEW FORECAST · 01</p>
        <h1>把你关心的事，<em>说清楚就好。</em></h1>
        <span>接下来的复杂工作，交给 ECHO 和 5,000 个稳定人格参与者。</span>
      </header>
      <div className="wizard-workspace">
        <aside className="wizard-progress">
          <div className="progress-label"><span>STEP {String(step).padStart(2, '0')} / 05</span><strong>{stepLabels[step - 1]}</strong></div>
          <ol className="stepper" aria-label="预测步骤">
            {stepLabels.map((label, index) => {
              const number = index + 1;
              return (
                <li className={number === step ? 'active' : number < step ? 'done' : ''} key={label}>
                  <button disabled={number > step} onClick={() => setStep(number)} type="button">
                    <span>{number < step ? '✓' : number}</span><b>{label}</b>
                  </button>
                </li>
              );
            })}
          </ol>
          <div className="wizard-proof">
            <span className="proof-dots" aria-hidden="true"><i /><i /><i /><i /><i /><i /></span>
            <strong>一次完整的社会推演</strong>
            <p>人们先接触信息，再更新信念、情绪、目标与行动，并把经历写入记忆。</p>
          </div>
        </aside>

        <div className="wizard-card">
        {step === 1 ? (
          <div className="form-step">
            <div className="form-step-intro"><span>01 · 预测目标</span><h2>你想提前知道什么？</h2><p>写下一件可能发生的事，以及你真正想知道的人群反应。</p></div>
            <label>项目名称<input value={projectTitle} onChange={(e) => setProjectTitle(e.target.value)} placeholder="给这次预测起一个名字" /></label>
            <label>将要发生或可能发生的事<input value={eventTitle} onChange={(e) => setEventTitle(e.target.value)} placeholder="一句话描述事件" /></label>
            <label>补充说明<textarea value={eventDescription} onChange={(e) => setEventDescription(e.target.value)} rows={6} placeholder="谁会受到影响、事情如何发生、已经知道哪些信息……" /><small>只写已经知道的事实；暂时不确定的部分可以留空。</small></label>
            <fieldset className="channel-field">
              <legend>人们可能从哪里知道这件事</legend>
              <div className="choice-chips">
                {channelOptions.map((channel) => (
                  <button
                    aria-pressed={channels.includes(channel.value)}
                    className={channels.includes(channel.value) ? 'selected' : ''}
                    key={channel.value}
                    onClick={() => toggleChannel(channel.value)}
                    type="button"
                  >
                    <i />{channel.label}
                  </button>
                ))}
              </div>
              <small>至少选择一种，ECHO 会分别模拟不同渠道的首次触达和后续传播。</small>
            </fieldset>
            <label>已知证据或背景（可选）<textarea value={evidenceNotes} onChange={(e) => setEvidenceNotes(e.target.value)} rows={3} placeholder="粘贴已经确认的信息、历史情况或来源摘要；不要填未来才知道的结果" /></label>
            <label>你最想知道什么<input value={learningGoal} onChange={(e) => setLearningGoal(e.target.value)} placeholder="例如：人们是否支持，会不会讨论和参与" /></label>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="form-step">
            <div className="form-step-intro"><span>02 · 目标人群</span><h2>谁会经历这件事？</h2><p>系统会从稳定人格人群中选出符合条件的参与者，并保留他们原有的关系与记忆。</p></div>
            <label>人群名称<input value={populationName} onChange={(e) => setPopulationName(e.target.value)} /></label>
            <div className="field-grid three">
              <label>虚拟参与者数量<input min="5000" max="20000" step="500" type="number" value={populationSize} onChange={(e) => setPopulationSize(Number(e.target.value))} /><small>正式运行至少 5,000 人</small></label>
              <label>年龄范围<select value={ageGroup} onChange={(e) => setAgeGroup(e.target.value)}><option value="all">不限年龄</option><option value="18-24">18—24 岁</option><option value="25-34">25—34 岁</option><option value="35-44">35—44 岁</option><option value="45-59">45—59 岁</option><option value="60+">60 岁以上</option></select></label>
              <label>主要社会角色<select value={socialRole} onChange={(e) => setSocialRole(e.target.value)}><option value="all">不限角色</option><option value="student">学生</option><option value="professional">专业人员</option><option value="service_worker">服务人员</option><option value="skilled_worker">技能工作者</option><option value="caregiver">照护者</option><option value="self_employed">自由职业/个体经营</option><option value="retired">退休人员</option></select></label>
            </div>
            <div className="agent-tier-preview">
              <div><strong>50</strong><span>关键参与者</span><small>更深的记忆与关系推演</small></div>
              <div><strong>450</strong><span>代表参与者</span><small>覆盖主要群体差异</small></div>
              <div><strong>{Math.max(4500, populationSize - 500).toLocaleString('zh-CN')}</strong><span>背景参与者</span><small>保持总体分布与传播规模</small></div>
            </div>
            <details className="data-upload-card">
              <summary>用授权人口分布约束这组 Agent（可选）</summary>
              <p>上传聚合人口边际 JSON 后，系统会用 raking 调整代表权重，并报告有效样本量；不会导入或复制真实个人。</p>
              <div className="upload-actions">
                <input ref={populationFileInput} hidden type="file" accept="application/json,.json" onChange={(e) => { const file = e.target.files?.[0]; if (file) void importDataset(file, 'population'); }} />
                <button className="secondary-action" onClick={() => populationFileInput.current?.click()} type="button">选择人口分布 JSON</button>
                <a href="/api/echo/v1/examples/population-margin" target="_blank" rel="noreferrer">查看格式示例</a>
                {populationMargins ? <button className="text-danger" onClick={() => setPopulationMargins(null)} type="button">移除</button> : null}
              </div>
              <span className={populationMargins ? 'dataset-status ready' : 'dataset-status'}>{populationMargins ? `已载入 ${populationMargins.filename} · ${populationMargins.datasetId}` : '未载入：本次将明确标记为合成人口原型'}</span>
            </details>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="form-step questionnaire-step">
            <div className="form-step-intro with-action">
              <div><span>03 · 预测问卷</span><h2>你想问他们什么？</h2><p>已准备 10 道通用题。保留真正有用的问题，也可以自由修改或导入。</p></div>
              <div><input ref={questionnaireFileInput} hidden type="file" accept="application/json,.json" onChange={(e) => { const file = e.target.files?.[0]; if (file) void importQuestionnaire(file); }} /><button className="secondary-action" onClick={() => questionnaireFileInput.current?.click()} type="button">导入问卷</button></div>
            </div>
            <div className="question-list">
              {questions.map((question, index) => (
                <article className={editingQuestion === index ? 'question-editor open' : 'question-editor'} key={`${question.id}-${index}`}>
                  <button className="question-summary" onClick={() => setEditingQuestion(editingQuestion === index ? -1 : index)} type="button">
                    <span>{String(index + 1).padStart(2, '0')}</span><strong>{question.text}</strong><em>{kindLabels[question.kind]}</em><b>{editingQuestion === index ? '−' : '+'}</b>
                  </button>
                  {editingQuestion === index ? (
                    <div className="question-fields">
                      <label>题目<input value={question.text} onChange={(e) => updateQuestion(index, { text: e.target.value })} /></label>
                      <div className="field-grid">
                        <label>题型<select value={question.kind} onChange={(e) => changeKind(index, e.target.value as QuestionKind)}>{Object.entries(kindLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                        <label>测量内容<select value={question.construct} onChange={(e) => updateQuestion(index, { construct: e.target.value })}>{Object.entries(constructLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
                      </div>
                      {optionKinds.includes(question.kind) ? <label>选项（每行一个）<textarea value={question.options.join('\n')} onChange={(e) => updateQuestion(index, { options: e.target.value.split('\n') })} rows={Math.max(3, question.options.length)} /></label> : null}
                      {['scale', 'numeric'].includes(question.kind) ? <div className="field-grid"><label>最小值<input type="number" value={question.scaleMin ?? 0} onChange={(e) => updateQuestion(index, { scaleMin: Number(e.target.value) })} /></label><label>最大值<input type="number" value={question.scaleMax ?? 100} onChange={(e) => updateQuestion(index, { scaleMax: Number(e.target.value) })} /></label></div> : null}
                      <button className="text-danger" disabled={questions.length === 1} onClick={() => { setQuestions((items) => items.filter((_, itemIndex) => itemIndex !== index)); setEditingQuestion(-1); }} type="button">删除此题</button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
            <button className="add-question" onClick={addQuestion} type="button">＋ 添加一道题</button>
            <details className="data-upload-card">
              <summary>用历史问卷与真实事件结果校准概率（可选）</summary>
              <p>记录必须包含当时预测、后来真实结果及各自时间。系统按时间切分训练/留出集；留出集没有同时改善 Brier 与 Log Loss 时不会应用。</p>
              <div className="upload-actions">
                <input ref={calibrationFileInput} hidden type="file" accept="application/json,.json" onChange={(e) => { const file = e.target.files?.[0]; if (file) void importDataset(file, 'calibration'); }} />
                <button className="secondary-action" onClick={() => calibrationFileInput.current?.click()} type="button">选择历史结果 JSON</button>
                <a href="/api/echo/v1/examples/calibration-dataset" target="_blank" rel="noreferrer">查看格式示例</a>
                {calibrationHistory ? <button className="text-danger" onClick={() => setCalibrationHistory(null)} type="button">移除</button> : null}
              </div>
              <span className={calibrationHistory ? 'dataset-status ready' : 'dataset-status'}>{calibrationHistory ? `已载入 ${calibrationHistory.filename} · ${calibrationHistory.datasetId}` : '未载入：本次概率将标记为未经过历史结果校准'}</span>
            </details>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="form-step">
            <div className="form-step-intro"><span>04 · 时间与情景</span><h2>向未来看多远？</h2><p>系统会比较“没有发生”“按描述发生”和你的替代情景。</p></div>
            <div className="field-grid three">
              <label>预测范围<select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}><option value="30">近期 · 约 30 个变化周期</option><option value="72">中期 · 约 72 个变化周期</option><option value="168">更长时间 · 约 168 个周期</option></select><small>每个周期都会更新人群状态</small></label>
              <label>结果稳健程度<select value={paths} onChange={(e) => setPaths(Number(e.target.value))}><option value="3">快速观察</option><option value="8">标准比较</option><option value="16">深入比较</option></select><small>越深入，不确定范围越稳定</small></label>
              <label>现有信息可信度<select value={credibility} onChange={(e) => setCredibility(Number(e.target.value))}><option value="0.45">仍有较多疑点</option><option value="0.72">基本可信</option><option value="0.9">已有充分依据</option></select><small>影响人群相信和传播的速度</small></label>
            </div>
            <label>若已知，事件本身带来的直接影响<select value={eventImpact} onChange={(e) => setEventImpact(Number(e.target.value))}><option value="-0.5">明显负担或损害</option><option value="-0.2">略偏负面</option><option value="0">暂不判断</option><option value="0.2">略偏正面</option><option value="0.5">明显收益或改善</option></select><small>这不是预测答案，只是对事件事实含义的补充。</small></label>
            <label>替代情景（可选）<textarea rows={4} value={alternative} onChange={(e) => setAlternative(e.target.value)} placeholder="例如：如果信息传播较慢、关键细节暂不明确" /></label>
            <div className="scenario-preview"><span>会比较</span><b>事件未发生</b><i>与</i><b>事件按描述发生</b>{alternative.trim() ? <><i>与</i><b>替代情景</b></> : null}</div>
            <div className="l2-protocol-card">
              <header><span>决策口径锁定</span><strong>先定义怎样算更好</strong><p>运行后不可改口径；所有方案会使用同一组随机路径做配对比较。</p></header>
              <div className="field-grid three">
                <label>核心判断指标<select value={primaryMetric} onChange={(e) => { const selected = decisionMetricOptions.find((item) => item.value === e.target.value); setPrimaryMetric(e.target.value); if (selected) setMetricDirection(selected.direction); }}>{decisionMetricOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                <label>期望方向<select value={metricDirection} onChange={(e) => setMetricDirection(e.target.value as MetricDirection)}><option value="increase">越高越好</option><option value="decrease">越低越好</option></select></label>
                <label>最小有意义变化<select value={minimumEffect} onChange={(e) => setMinimumEffect(Number(e.target.value))}><option value="0.01">1 个百分点</option><option value="0.02">2 个百分点</option><option value="0.05">5 个百分点</option></select></label>
              </div>
              <small>辅助检查：{auxiliaryMetrics(primaryMetric).map((item) => item.label).join('、')} · 预测时点后的信息自动排除</small>
            </div>
          </div>
        ) : null}

        {step === 5 ? (
          <div className="form-step confirm-step">
            <div className="form-step-intro"><span>05 · 确认运行</span><h2>让这群人先经历一次。</h2><p>运行后，你会先看到问卷答案，再看到人群差异、传播过程和未来反应。</p></div>
            <div className="confirm-grid">
              <div><span>事件</span><strong>{eventTitle}</strong><p>{eventDescription}</p></div>
              <div><span>目标人群</span><strong>{populationName}</strong><p>{populationSize.toLocaleString('zh-CN')} 个稳定人格参与者</p></div>
              <div><span>问卷</span><strong>{questions.length} 道题</strong><p>{Array.from(new Set(questions.map((item) => kindLabels[item.kind]))).join('、')}</p></div>
              <div><span>比较</span><strong>{alternative.trim() ? '3 个情景' : '2 个情景'}</strong><p>{horizon} 个变化周期 · {paths === 3 ? '快速' : paths === 8 ? '标准' : '深入'}比较</p></div>
              <div><span>决策口径</span><strong>{decisionMetricOptions.find((item) => item.value === primaryMetric)?.label} · {metricDirection === 'increase' ? '越高越好' : '越低越好'}</strong><p>最小变化 {Math.round(minimumEffect * 100)} 个百分点 · 共享随机路径</p></div>
            </div>
            <div className="grounding-confirm">
              <span className={populationMargins ? 'ready' : ''}>{populationMargins ? '✓ 已准备授权人口边际' : '○ 合成人口原型，未接人口边际'}</span>
              <span className={calibrationHistory ? 'ready' : ''}>{calibrationHistory ? '✓ 已准备历史结果时间校准' : '○ 未接历史结果，输出未校准先验'}</span>
            </div>
            <button className="run-action" disabled={loading} onClick={runPrediction} type="button">开始社会推演 <span>→</span></button>
            <p className="run-note">问卷预测与社会世界将同时运行；相同输入和种子可重新得到同样结果。</p>
          </div>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}
        {step < 5 ? (
          <footer className="wizard-actions">
            <button className="secondary-action" disabled={step === 1} onClick={() => setStep((value) => value - 1)} type="button">上一步</button>
            <button className="primary-action small" disabled={!canContinue()} onClick={() => setStep((value) => value + 1)} type="button">继续 <span>→</span></button>
          </footer>
        ) : <footer className="wizard-actions"><button className="secondary-action" onClick={() => setStep(4)} type="button">返回修改</button></footer>}
        </div>
      </div>

      {loading ? (
        <div className="running-overlay" role="status">
          <div className="running-card">
            <span className="running-orbit"><i /><i /><i /></span>
            <p className="running-kicker">SOCIAL WORLD IS RUNNING</p>
            <h2>正在让人群经历这件事</h2>
            <p>5,000+ 个稳定人格参与者正在接触信息、形成判断并彼此影响。</p>
            <ol><li className="done">准备人格与关系网络</li><li className="active">运行事件传播与状态更新</li><li>汇总问卷与未来路径</li></ol>
            <small>完整推演可能需要一点时间，请保留当前页面。</small>
          </div>
        </div>
      ) : null}
    </section>
  );
}
