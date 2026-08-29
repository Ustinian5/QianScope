'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  SocialWorldFlipbook,
  type FlipbookInteriorProfile,
} from '@/components/social-world-flipbook';
import { WorldQueryToolbar } from '@/vendor/openflipbook/components/PlayPage/WorldQueryToolbar';
import {
  DEFAULT_SOCIAL_MAP_CAMERA,
  SocialWorldMap,
  type SocialAgentActivityStatus,
  type SocialMapCamera,
  type SocialMapStatus,
  type SocialWeather,
} from '@/components/social-world-map';
import { buildWorldRequest } from '@/lib/world-request';
import type {
  PersonaInterviewResponse,
  PersonaProfile,
  PersonaSearchItem,
  PersonaSearchResult,
} from '@/lib/persona-types';
import type { WorldSimulationResult } from '@/lib/world-types';
import {
  stableUnit,
  SOCIAL_WORLD_CITY,
  WORLD_AGENTS,
  WORLD_LOCATIONS,
  WORLD_TOOLS,
  type ToolDefinition,
  type ToolKey,
  type WorldAgent,
  type WorldLevel,
  type WorldLocation,
} from '@/lib/social-world-fixtures';

type ToolFormState = Record<string, string>;
type InsightToolKey = Exclude<ToolKey, 'survey' | 'event' | 'demand'>;

type ToolResult = {
  title: string;
  context: string;
  metricLabel: string;
  metricValue: string;
  metricDetail: string;
  bars: Array<{ label: string; value: number; detail?: string }>;
  notes: string[];
  quotes: Array<{ name: string; role: string; quote: string }>;
  decisionRounds?: Array<{
    roundIndex: number;
    question: string;
    context: string;
    options: Array<{ label: string; value: number; detail: string }>;
    confidence: number;
    changedShare: number | null;
  }>;
  methodology?: string[];
  source: 'live';
};

type InsightApiResult = {
  run_id: string;
  tool: InsightToolKey;
  title: string;
  context: string;
  metric_label: string;
  metric_value: string;
  metric_detail: string;
  bars: Array<{ label: string; value: number; detail?: string | null }>;
  notes: string[];
  quotes: Array<{ agent_id: string; name: string; role: string; quote: string }>;
  population: { agent_count: number; represented_population: number };
  provenance: { calibrated: boolean; grounding_status: string };
};

type JobKind = 'insight' | 'prediction' | 'world';
type JobRecord = {
  job_id: string;
  kind: JobKind;
  status: 'queued' | 'running' | 'cancelling' | 'complete' | 'cancelled' | 'failed';
  progress: number;
  stage: string;
  processed_agents: number;
  total_agents: number;
  current_round: number;
  total_rounds: number;
  processed_decisions: number;
  total_decisions: number;
  decision_feed: Array<{
    round_index: number;
    total_rounds: number;
    agent_id: string;
    name: string;
    role: string;
    question: string;
    choice: string;
    confidence: number;
  }>;
  latest_trace: string;
  cancellation_requested: boolean;
  result_available: boolean;
  error: string | null;
};

type TaskHistoryItem = {
  jobId: string;
  kind: JobKind;
  toolKey: ToolKey;
  toolLabel: string;
  status: JobRecord['status'];
  progress: number;
  stage: string;
  latestTrace: string;
  createdAt: string;
  updatedAt: string;
  form: ToolFormState;
};

type JobHooks = {
  onCreated: (jobId: string) => void;
  onUpdate: (record: JobRecord) => void;
};

type SpeechRecognitionEventLike = {
  results: ArrayLike<{ 0: { transcript: string } }>;
};

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

class JobCancelledError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'JobCancelledError';
  }
}

const DEFAULT_FORMS: Record<ToolKey, ToolFormState> = {
  survey: { question: '你愿意根据社区预警调整当天的通勤与出行安排吗？', options: '愿意调整, 视情况而定, 不会调整' },
  event: { event: '贵阳市发布强降雨预警，并同步调整重点区域交通接驳与社区应急服务。', horizon: '3天', rounds: '4轮' },
  marketing: { event: '贵阳大数据科创城发布面向中小企业的算力服务体验计划。', horizon: '1周' },
  trend: { term: '贵阳数智生活', horizon: '1周' },
  brand: { brand: '黔镜 QianScope' },
  product: { features: '免安装开箱即用, 情景对比, 人群分层, 可解释报告, 数据导出' },
  demand: { question: '如果有一项可信的社会事件预测服务，你会使用吗？', options: '会使用, 看价格, 暂不需要' },
  pricing: { product: '通用事件预测服务', prices: '49, 99, 199, 399', audience: '研究者与产品团队' },
  competitive: { brand: '我们的产品', competitor: '主要竞品', action: '竞品降低价格并上线更快的事件推演能力。', context: '' },
  funnel: { product: '事件预测报告订阅，从内容触达到注册并完成首次推演。', channel: '内容社区 + 搜索 + 专业社群' },
  churn: { change: '订阅价格上调 30%，同时减少免费推演次数。', horizon: '1月' },
  creator: { brief: '面向高校与研究者推广通用事件预测平台', platform: '内容社区与专业社群' },
};

const TASK_HISTORY_KEY = 'qianscope:task-history:v1';
const LEGACY_TASK_HISTORY_KEY = 'echo-swm:task-history:v1';

function lastJobKey(toolKey: ToolKey) {
  return `qianscope:last-job:${toolKey}`;
}

function legacyLastJobKey(toolKey: ToolKey) {
  return `echo-swm:last-job:${toolKey}`;
}

function personaErrorMessage(reason: unknown) {
  const message = reason instanceof Error ? reason.message : '';
  if (/backend is unavailable|failed to fetch|network|load failed/i.test(message)) {
    return '稳定人格服务暂时未连接，请稍后重试。';
  }
  return message || '稳定人格服务暂时不可用，请稍后重试。';
}

const HORIZONS = ['1天', '3天', '1周', '1月', '1学期'];
const INTERVIEW_PROMPTS = [
  '你最先会向谁确认？',
  '什么会让你改变主意？',
  '你会采取什么行动？',
];

const GUIDED_STORIES = [
  {
    title: '数博会散场客流协同',
    summary: '会展闭馆、公共交通与旅客选择如何共同塑造散场压力。',
    event: '贵阳国际会议展览中心大型数智展会于晚高峰闭馆，主办方提前发布分区散场提示，并联动贵阳北站与公共交通增加接驳运力。',
    locationId: 'guiyang_convention', building: '国际会议中心', floor: 1, horizon: '1天', paths: 3,
    focusAgentId: 'agent_zhou_qihang', focus: '会展客流与交通协同网络',
  },
  {
    title: '算力服务进入科创城',
    summary: '一项新服务如何经过技术验证、同伴信任与政策解释形成采用意愿。',
    event: '贵阳大数据科创城上线面向中小企业的普惠算力服务，首批体验名额、数据授权说明与补贴规则同步发布。',
    locationId: 'guiyang_big_data', building: '数据要素路演厅', floor: 3, horizon: '1周', paths: 3,
    focusAgentId: 'agent_lin_rui', focus: '企业采用与数字治理信任',
  },
  {
    title: '强降雨下的社区响应',
    summary: '预警信息如何穿过楼栋、家庭与物业关系，转化为具体行动。',
    event: '贵阳市发布强降雨黄色预警，花果园社区启动重点居民联络、低洼点巡查和错峰出行提示，并持续更新公共交通信息。',
    locationId: 'huaguoyuan', building: '社区服务中心', floor: 2, horizon: '3天', paths: 3,
    focusAgentId: 'agent_jiang_wenlin', focus: '高密社区预警与互助网络',
  },
];

const EVENT_LOCATION_PATTERNS: Array<{ id: string; pattern: RegExp }> = [
  { id: 'guiyang_convention', pattern: /贵阳国际会议展览中心|贵阳会展|会展中心|数博发布厅|数博会/ },
  { id: 'guiyang_big_data', pattern: /贵阳大数据科创城|大数据科创城|科创城|算力|数据要素/ },
  { id: 'guizhou_university', pattern: /贵州大学西校区|贵大西校区|贵州大学|西区图书馆/ },
  { id: 'jiaxiu_tower', pattern: /甲秀楼|南明河|浮玉桥|翠微园/ },
  { id: 'qingyan_town', pattern: /青岩古镇|青岩|定广门|青石主街/ },
  { id: 'guiyang_north_station', pattern: /贵阳北站|北站|高铁|综合换乘/ },
  { id: 'huaguoyuan', pattern: /花果园社区|花果园|湿地公园|社区服务中心/ },
];

function eventLocationIds(eventText: string, explicitLocationId?: string) {
  const explicit = explicitLocationId && WORLD_LOCATIONS.some((location) => location.id === explicitLocationId)
    ? [explicitLocationId]
    : [];
  const inferred = EVENT_LOCATION_PATTERNS
    .filter(({ pattern }) => pattern.test(eventText))
    .map(({ id }) => id);
  return Array.from(new Set([...explicit, ...inferred]));
}

const TOOL_FIELDS: Record<ToolKey, Array<{ key: string; label: string; multiline?: boolean; placeholder?: string; select?: string[] }>> = {
  survey: [
    { key: 'question', label: '问卷调查问题', multiline: true, placeholder: '输入你希望向人群提出的问题' },
    { key: 'options', label: '选项（可选 · 逗号分隔）', placeholder: '支持, 反对, 看情况' },
  ],
  event: [
    { key: 'event', label: '注入事件', multiline: true },
    { key: 'horizon', label: '推演时长', select: HORIZONS },
    { key: 'rounds', label: '独立决策轮数', select: ['3轮', '4轮', '5轮', '6轮'] },
  ],
  marketing: [
    { key: 'event', label: '营销活动', multiline: true },
    { key: 'horizon', label: '观察窗口', select: HORIZONS },
  ],
  trend: [
    { key: 'term', label: '趋势词' },
    { key: 'horizon', label: '观察窗口', select: HORIZONS },
  ],
  brand: [{ key: 'brand', label: '品牌名' }],
  product: [{ key: 'features', label: '候选功能', multiline: true, placeholder: '至少两个功能，用逗号或换行分隔' }],
  demand: [
    { key: 'question', label: '模拟需求问题', multiline: true },
    { key: 'options', label: '回答选项', placeholder: '会使用, 看价格, 暂不需要' },
  ],
  pricing: [
    { key: 'product', label: '产品 / 方案', multiline: true },
    { key: 'prices', label: '价格点', placeholder: '49, 99, 199' },
    { key: 'audience', label: '目标人群' },
  ],
  competitive: [
    { key: 'brand', label: '我方品牌' },
    { key: 'competitor', label: '竞品名称' },
    { key: 'action', label: '竞品动作', multiline: true },
    { key: 'context', label: '已有推演摘要（可选）', multiline: true },
  ],
  funnel: [
    { key: 'product', label: '转化方案', multiline: true },
    { key: 'channel', label: '主要渠道' },
  ],
  churn: [
    { key: 'change', label: '变化事件', multiline: true },
    { key: 'horizon', label: '观察窗口', select: HORIZONS },
  ],
  creator: [
    { key: 'brief', label: '传播任务', multiline: true },
    { key: 'platform', label: '主要渠道' },
  ],
};

const PERSONA_DEMOGRAPHIC_LABELS: Record<string, string> = {
  age: '年龄', age_group: '年龄段', gender: '性别', education_level: '教育背景',
  social_role: '社会角色', organization_type: '单位类型', region_type: '居住区域',
  household_type: '家庭结构',
};

function sanitizeOptions(raw: string, fallback = ['支持', '保持观望', '反对']) {
  const options = raw.split(/[,，、;；\n]+/).map((item) => item.trim()).filter(Boolean);
  return options.length >= 2 ? options : fallback;
}

function jobKindForTool(toolKey: ToolKey): JobKind {
  if (toolKey === 'event' || toolKey === 'survey' || toolKey === 'demand') return 'world';
  return 'insight';
}

function positionFor(index: number, count: number) {
  return count <= 1 ? 0 : .75 - (1.5 * index) / (count - 1);
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
    throw new Error(detail || '运行失败');
  }
  return body;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: 'no-store' });
  const body = await response.json() as T & { detail?: unknown };
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    throw new Error(detail || '读取失败');
  }
  return body;
}

async function awaitJobResult<T>(initialRecord: JobRecord, hooks: JobHooks): Promise<T> {
  let record = initialRecord;
  hooks.onUpdate(record);
  const startedAt = Date.now();
  const deadline = Date.now() + 300_000;
  while (!['complete', 'cancelled', 'failed'].includes(record.status)) {
    if (Date.now() >= deadline) throw new Error('任务运行超时，请稍后按任务 ID 恢复。');
    const elapsed = Date.now() - startedAt;
    const interval = elapsed < 8_000 ? 120 : elapsed < 60_000 ? 600 : 1_500;
    await new Promise((resolve) => window.setTimeout(resolve, interval));
    record = await getJson<JobRecord>(`/api/qianscope/v1/jobs/${record.job_id}`);
    hooks.onUpdate(record);
  }
  if (record.status === 'cancelled') throw new JobCancelledError('任务已由使用者终止。');
  if (record.status === 'failed') throw new Error(record.error || '后台任务运行失败。');
  return getJson<T>(`/api/qianscope/v1/jobs/${record.job_id}/result`);
}

async function runJob<T>(kind: JobKind, payload: unknown, hooks: JobHooks): Promise<T> {
  const record = await postJson<JobRecord>(`/api/qianscope/v1/jobs/${kind}`, payload);
  hooks.onCreated(record.job_id);
  return awaitJobResult<T>(record, hooks);
}

function personaToWorldAgent(profile: PersonaProfile): WorldAgent {
  const locationAliases: Record<string, string> = {
    guiyang_convention_center: 'guiyang_convention',
    convention_center: 'guiyang_convention',
    guiyang_big_data_city: 'guiyang_big_data',
    innovation_hub: 'guiyang_big_data',
    guizhou_university_west: 'guizhou_university',
    university_campus: 'guizhou_university',
    jiaxiu_riverfront: 'jiaxiu_tower',
    heritage_district: 'jiaxiu_tower',
    qingyan_ancient_town: 'qingyan_town',
    tourism_district: 'qingyan_town',
    north_station: 'guiyang_north_station',
    transit_hub: 'guiyang_north_station',
    huaguoyuan_community: 'huaguoyuan',
    community_center: 'huaguoyuan',
  };
  return {
    id: profile.persona_id,
    backendId: profile.persona_id,
    name: profile.name,
    role: profile.role,
    organization: profile.organization,
    locationId: locationAliases[profile.mobility.scene_location_id] || profile.mobility.scene_location_id,
    location: profile.state.current_location,
    bio: profile.bio,
    traits: profile.traits.map((item) => item.label),
    values: profile.values.map((item) => item.label),
    goal: profile.primary_goal,
    action: profile.state.current_action,
    mood: profile.state.mood,
    stress: profile.state.stress,
    intention: profile.state.intention,
    memories: [
      ...profile.memories,
      ...profile.schedule.map((item) => `${item.time} · ${item.activity} · ${item.location}`),
    ],
    relationships: profile.relationships.map((item) => ({
      agentId: item.persona_id,
      name: item.name,
      role: item.role,
      relation: item.relation,
      trust: item.trust,
    })),
    representedWeight: profile.represented_weight,
    profileHash: profile.profile_hash,
    profileCompleteness: profile.profile_completeness,
    definitionVersion: profile.definition_version,
    demographics: profile.demographics,
    frameworks: profile.frameworks.map((framework) => ({
      id: framework.framework_id,
      label: framework.label,
      reference: framework.reference,
      description: framework.description,
      dimensions: framework.dimensions.map((dimension) => ({
        key: dimension.key,
        label: dimension.label,
        description: dimension.description,
        score: dimension.score,
        scaleMin: dimension.scale_min,
        scaleMax: dimension.scale_max,
        lowPole: dimension.low_pole,
        highPole: dimension.high_pole,
        interpretation: dimension.interpretation,
      })),
    })),
    x: 18 + stableUnit(`${profile.persona_id}:x`) * 64,
    y: 32 + stableUnit(`${profile.persona_id}:y`) * 42,
  };
}

function horizonTicks(value: string) {
  return ({ '1天': 30, '3天': 72, '1周': 168, '1月': 180, '1学期': 180 } as Record<string, number>)[value] || 72;
}

async function runLiveSurvey(form: ToolFormState, demandMode: boolean, hooks: JobHooks): Promise<ToolResult> {
  const now = Date.now();
  const options = sanitizeOptions(form.options);
  const question = form.question.trim();
  const request = buildWorldRequest({
    projectId: `quick_survey_${now}`,
    eventId: `survey_context_${now}`,
    eventTitle: question.slice(0, 80),
    eventDescription: `请每个 Agent 根据自己的稳定人格独立回答：${question}`,
    populationSize: 5000,
    filters: {},
    channels: ['news'],
    horizon: 1,
    paths: 1,
    credibility: .72,
    eventImpact: 0,
    evidenceNotes: '',
    decisionRounds: 1,
    questionOverrides: [{
      question_id: 'survey_round_1',
      round_index: 1,
      prompt: question,
      context: '单轮问卷：每个 Agent 独立作答，完成后统一聚合。',
      construct: demandMode ? 'action' : 'reaction',
      options: options.map((label, index) => ({
        option_id: `option_${index + 1}`,
        label,
        position: positionFor(index, options.length),
      })),
    }],
  });
  const result = await runJob<WorldSimulationResult>('world', request, hooks);
  return formatDecisionResult(result, question, demandMode ? '模拟需求分布' : '问卷回答分布', '单轮问卷');
}

async function runLiveEvent(form: ToolFormState, hooks: JobHooks): Promise<ToolResult> {
  const now = Date.now();
  const eventText = form.event.trim();
  const horizon = horizonTicks(form.horizon);
  const targetLocationIds = eventLocationIds(eventText, form.targetLocationId);
  const request = buildWorldRequest({
    projectId: `quick_event_${now}`, eventId: `event_${now}`, eventTitle: eventText.slice(0, 80), eventDescription: eventText,
    populationSize: 5000, filters: {}, channels: ['social_media', 'interpersonal', 'community'], horizon, paths: 3,
    credibility: .72, eventImpact: .1, evidenceNotes: '', sourceLocationId: targetLocationIds[0] || null,
    targetLocationIds, decisionRounds: Number.parseInt(form.rounds || '4', 10),
  });
  const result = await runJob<WorldSimulationResult>('world', request, hooks);
  return formatEventResult(result, eventText, form.horizon);
}

function formatEventResult(result: WorldSimulationResult, eventText: string, horizon: string): ToolResult {
  return formatDecisionResult(result, eventText, '事件多轮推演', horizon);
}

function formatDecisionResult(result: WorldSimulationResult, context: string, title: string, horizon: string): ToolResult {
  const report = result.decision_report;
  if (!report || !report.rounds.length) throw new Error('后端未返回独立 Agent 决策记录。');
  const finalRound = report.rounds.at(-1)!;
  return {
    title,
    context,
    metricLabel: '已完成独立决策',
    metricValue: report.completed_decisions.toLocaleString('zh-CN'),
    metricDetail: `${report.agent_count.toLocaleString('zh-CN')} Agent × ${report.round_count} 轮 · ${horizon}`,
    bars: finalRound.options.map((item) => ({
      label: item.label,
      value: Math.round(item.share * 100),
      detail: `${item.agent_count.toLocaleString('zh-CN')} Agent · 95% 区间 ${Math.round(item.ci_low * 100)}–${Math.round(item.ci_high * 100)}%`,
    })),
    notes: report.summary,
    quotes: finalRound.representatives.map((item) => ({
      name: item.name,
      role: item.role,
      quote: item.rationale,
    })),
    decisionRounds: report.rounds.map((round) => ({
      roundIndex: round.round_index,
      question: round.question.prompt,
      context: round.question.context,
      options: round.options.map((item) => ({
        label: item.label,
        value: Math.round(item.share * 100),
        detail: `${item.agent_count.toLocaleString('zh-CN')} Agent`,
      })),
      confidence: Math.round(round.mean_confidence * 100),
      changedShare: round.changed_from_previous_share === null ? null : Math.round(round.changed_from_previous_share * 100),
    })),
    methodology: report.methodology,
    source: 'live',
  };
}

async function runLiveInsight(tool: InsightToolKey, form: ToolFormState, hooks: JobHooks): Promise<ToolResult> {
  const result = await runJob<InsightApiResult>('insight', {
    tool,
    fields: form,
    population_size: 5000,
    represented_population: SOCIAL_WORLD_CITY.representedPopulation,
    seed: 2026,
  }, hooks);
  return formatInsightResult(result);
}

function formatInsightResult(result: InsightApiResult): ToolResult {
  return {
    title: result.title,
    context: result.context,
    metricLabel: result.metric_label,
    metricValue: result.metric_value,
    metricDetail: result.metric_detail,
    bars: result.bars.map((bar) => ({
      label: bar.label,
      value: bar.value,
      detail: bar.detail || undefined,
    })),
    notes: result.notes,
    quotes: result.quotes.map((quote) => ({
      name: quote.name,
      role: quote.role,
      quote: quote.quote,
    })),
    source: 'live',
  };
}

function ToolPanel({ tool, initialForm, initialRecoveryId, onClose, onTaskChange }: { tool: ToolDefinition; initialForm?: ToolFormState | null; initialRecoveryId?: string | null; onClose: () => void; onTaskChange: (task: TaskHistoryItem) => void }) {
  const panelRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  const [form, setForm] = useState<ToolFormState>(() => ({ ...DEFAULT_FORMS[tool.key], ...initialForm }));
  const [result, setResult] = useState<ToolResult | null>(null);
  const resultRef = useRef<ToolResult | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [stage, setStage] = useState('正在创建任务');
  const [latestTrace, setLatestTrace] = useState('准备稳定人格与事件条件');
  const [processedAgents, setProcessedAgents] = useState(0);
  const [totalAgents, setTotalAgents] = useState(5000);
  const [currentRound, setCurrentRound] = useState(0);
  const [totalRounds, setTotalRounds] = useState(0);
  const [processedDecisions, setProcessedDecisions] = useState(0);
  const [totalDecisions, setTotalDecisions] = useState(0);
  const [decisionFeed, setDecisionFeed] = useState<JobRecord['decision_feed']>([]);
  const [activeJobId, setActiveJobId] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [recoveryId, setRecoveryId] = useState(initialRecoveryId || '');
  const taskCreatedAtRef = useRef(new Date().toISOString());

  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    resultRef.current = result;
  }, [result]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => panelRef.current?.querySelector<HTMLElement>('input, textarea, select, button')?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key !== 'Tab' || resultRef.current || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKeyDown);
      previousFocus?.focus();
    };
  }, []);

  useEffect(() => {
    if (initialRecoveryId) return;
    const saved = window.localStorage.getItem(lastJobKey(tool.key))
      ?? window.localStorage.getItem(legacyLastJobKey(tool.key));
    if (!saved) return;
    const kickoff = window.setTimeout(() => {
      try {
        const parsed = JSON.parse(saved) as { jobId?: string; form?: ToolFormState };
        if (parsed.jobId) setRecoveryId(parsed.jobId);
        if (parsed.form) setForm((current) => ({ ...current, ...parsed.form }));
      } catch {
        setRecoveryId(saved);
      }
    }, 0);
    return () => window.clearTimeout(kickoff);
  }, [initialRecoveryId, tool.key]);

  function jobHooks(): JobHooks {
    return {
      onCreated: (jobId) => {
        setActiveJobId(jobId);
        setRecoveryId(jobId);
        window.localStorage.setItem(
          lastJobKey(tool.key),
          JSON.stringify({ jobId, tool: tool.key, form }),
        );
        const timestamp = new Date().toISOString();
        onTaskChange({
          jobId,
          kind: jobKindForTool(tool.key),
          toolKey: tool.key,
          toolLabel: tool.label,
          status: 'queued',
          progress: 0,
          stage: '正在创建任务',
          latestTrace: '准备稳定人格与事件条件',
          createdAt: taskCreatedAtRef.current,
          updatedAt: timestamp,
          form: { ...form },
        });
      },
      onUpdate: (record) => {
        setProgress(record.progress);
        setStage(record.stage);
        setLatestTrace(record.latest_trace);
        setProcessedAgents(record.processed_agents);
        setTotalAgents(record.total_agents);
        setCurrentRound(record.current_round);
        setTotalRounds(record.total_rounds);
        setProcessedDecisions(record.processed_decisions);
        setTotalDecisions(record.total_decisions);
        setDecisionFeed(record.decision_feed);
        onTaskChange({
          jobId: record.job_id,
          kind: record.kind,
          toolKey: tool.key,
          toolLabel: tool.label,
          status: record.status,
          progress: record.progress,
          stage: record.stage,
          latestTrace: record.latest_trace,
          createdAt: taskCreatedAtRef.current,
          updatedAt: new Date().toISOString(),
          form: { ...form },
        });
      },
    };
  }

  function prepareRun() {
    taskCreatedAtRef.current = new Date().toISOString();
    setRunning(true); setResult(null); setStatusMessage(''); setProgress(0);
    setStage('正在创建任务'); setLatestTrace('准备稳定人格与事件条件');
    setProcessedAgents(0); setTotalAgents(5000); setCancelling(false);
    setCurrentRound(0); setTotalRounds(0); setProcessedDecisions(0); setTotalDecisions(0); setDecisionFeed([]);
  }

  async function run() {
    prepareRun();
    const hooks = jobHooks();
    try {
      let outcome: ToolResult;
      if (tool.key === 'survey' || tool.key === 'demand') outcome = await runLiveSurvey(form, tool.key === 'demand', hooks);
      else if (tool.key === 'event') outcome = await runLiveEvent(form, hooks);
      else outcome = await runLiveInsight(tool.key, form, hooks);
      setProgress(100); setResult(outcome);
    } catch (reason) {
      if (reason instanceof JobCancelledError) {
        setStatusMessage('任务已终止，未发布不完整结果。');
        setProgress(0);
        return;
      }
      const message = reason instanceof Error ? reason.message : '后台任务运行失败。';
      setStatusMessage(`推演未完成，因此没有生成报告：${message}`);
      setProgress(0);
    } finally {
      setActiveJobId(''); setCancelling(false); setRunning(false);
    }
  }

  async function recoverRun() {
    const jobId = recoveryId.trim();
    if (!jobId) {
      setStatusMessage('请输入需要恢复的任务 ID。');
      return;
    }
    prepareRun();
    setActiveJobId(jobId);
    const hooks = jobHooks();
    try {
      const record = await getJson<JobRecord>(`/api/qianscope/v1/jobs/${encodeURIComponent(jobId)}`);
      taskCreatedAtRef.current = new Date().toISOString();
      const expectedKind = jobKindForTool(tool.key);
      if (record.kind !== expectedKind) throw new Error(`该任务类型为 ${record.kind}，不属于当前工具。`);
      const raw = await awaitJobResult<WorldSimulationResult | InsightApiResult>(record, hooks);
      let restored: ToolResult;
      if (expectedKind === 'world') {
        const worldResult = raw as WorldSimulationResult;
        restored = tool.key === 'event'
          ? formatEventResult(worldResult, form.event, form.horizon)
          : formatDecisionResult(worldResult, form.question, tool.key === 'demand' ? '模拟需求分布' : '问卷回答分布', '单轮问卷');
      } else {
        const insight = raw as InsightApiResult;
        if (insight.tool !== tool.key) throw new Error(`该任务属于“${insight.title}”，请从对应工具恢复。`);
        restored = formatInsightResult(insight);
      }
      setProgress(100); setResult(restored);
    } catch (reason) {
      if (reason instanceof JobCancelledError) {
        setStatusMessage('该任务已终止，且没有可恢复的不完整结果。');
        return;
      }
      setStatusMessage(reason instanceof Error ? `无法恢复：${reason.message}` : '无法恢复该任务。');
    } finally {
      setActiveJobId(''); setCancelling(false); setRunning(false);
    }
  }

  async function cancelRun() {
    if (!activeJobId || cancelling) return;
    setCancelling(true);
    setStage('正在终止任务');
    setLatestTrace('已发送终止请求，等待当前安全计算边界');
    try {
      await postJson<JobRecord>(`/api/qianscope/v1/jobs/${activeJobId}/cancel`, {});
    } catch (reason) {
      setStatusMessage(reason instanceof Error ? `终止请求失败：${reason.message}` : '终止请求失败');
      setCancelling(false);
    }
  }

  return (
    <div className={`sw-modal-backdrop ${result ? 'result-docked' : ''}`} role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section ref={panelRef} className="sw-tool-panel" role="dialog" aria-modal={result ? undefined : true} aria-label={tool.label} tabIndex={-1}>
        <header>
          <div><span>{tool.icon}</span><div><h2>{tool.label}</h2><p>{tool.description}</p></div></div>
          <button type="button" aria-label="关闭" onClick={onClose}>×</button>
        </header>
        <div className="sw-tool-body">
          {!result && !running ? (
            <>
              <div className="sw-tool-intro">
                <span>5,000 个稳定人格原型</span>
                <p>每个 Agent 独立作答；单轮用于问卷，多轮用于事件推演。只有完整计算成功后才生成报告。</p>
              </div>
              {statusMessage ? <p className="sw-run-notice" role="status">{statusMessage}</p> : null}
              <div className="sw-tool-fields">
                {TOOL_FIELDS[tool.key].map((field) => (
                  <label key={field.key}>
                    <span>{field.label}</span>
                    {field.select ? (
                      <select value={form[field.key] || field.select[0]} onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}>
                        {field.select.map((option) => <option key={option}>{option}</option>)}
                      </select>
                    ) : field.multiline ? (
                      <textarea value={form[field.key] || ''} placeholder={field.placeholder} onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))} />
                    ) : (
                      <input value={form[field.key] || ''} placeholder={field.placeholder} onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))} />
                    )}
                  </label>
                ))}
              </div>
              <button className="sw-run-button" type="button" onClick={run}>开始运行 <span>→</span></button>
              <div className="sw-job-recovery">
                <span>恢复历史任务</span>
                <div>
                  <input aria-label="任务 ID" value={recoveryId} placeholder="job_…" onChange={(event) => setRecoveryId(event.target.value)} />
                  <button type="button" onClick={() => void recoverRun()}>恢复结果</button>
                </div>
              </div>
            </>
          ) : null}

          {running ? (
            <div className="sw-running">
              <div className="sw-running-orbit"><i /><i /><i /></div>
              <strong>{stage}</strong>
              <p>{latestTrace}</p>
              <div className="sw-progress"><i style={{ width: `${progress}%` }} /></div>
              <span>
                {progress}% · {totalDecisions
                  ? `${processedDecisions.toLocaleString('zh-CN')} / ${totalDecisions.toLocaleString('zh-CN')} 次决策`
                  : `${processedAgents.toLocaleString('zh-CN')} / ${totalAgents.toLocaleString('zh-CN')} Agent`}
              </span>
              {totalRounds ? <small className="sw-round-counter">第 {Math.max(1, currentRound)} / {totalRounds} 轮</small> : null}
              {decisionFeed.length ? (
                <div className="sw-decision-feed" aria-live="polite">
                  {decisionFeed.slice(-5).reverse().map((item) => (
                    <article key={`${item.round_index}-${item.agent_id}`}>
                      <span>{item.name} · {item.role}</span>
                      <p>选择「{item.choice}」</p>
                      <small>置信度 {Math.round(item.confidence * 100)}%</small>
                    </article>
                  ))}
                </div>
              ) : null}
              {activeJobId ? <small className="sw-job-id">任务 {activeJobId}</small> : null}
              {statusMessage ? <small className="sw-running-warning" role="status">{statusMessage}</small> : null}
              <button className="sw-cancel-button" type="button" disabled={!activeJobId || cancelling} onClick={() => void cancelRun()}>
                {cancelling ? '正在终止…' : '终止任务'}
              </button>
            </div>
          ) : null}

          {result ? (
            <div className="sw-tool-result">
              <div className="sw-result-context"><span>后端 Agent 真实运行</span><p>{result.context}</p></div>
              <div className="sw-result-hero"><span>{result.metricLabel}</span><strong>{result.metricValue}</strong><small>{result.metricDetail}</small></div>
              <h3>{result.title}</h3>
              <div className="sw-result-bars">
                {result.bars.map((bar) => (
                  <div key={`${bar.label}-${bar.value}`}>
                    <p><span>{bar.label}</span><strong>{bar.value}%</strong></p>
                    <i><b style={{ width: `${Math.min(100, Math.max(0, bar.value))}%` }} /></i>
                    {bar.detail ? <small>{bar.detail}</small> : null}
                  </div>
                ))}
              </div>
              {result.decisionRounds?.length ? (
                <div className="sw-round-results">
                  <h3>{result.decisionRounds.length === 1 ? '本轮问题与回答' : '逐轮决策记录'}</h3>
                  {result.decisionRounds.map((round) => (
                    <article key={round.roundIndex}>
                      <header>
                        <span>ROUND {String(round.roundIndex).padStart(2, '0')}</span>
                        <small>平均置信度 {round.confidence}%{round.changedShare === null ? '' : ` · 较上轮改变 ${round.changedShare}%`}</small>
                      </header>
                      <h4>{round.question}</h4>
                      <p>{round.context}</p>
                      <div>
                        {round.options.map((option) => (
                          <section key={option.label}>
                            <span>{option.label}</span>
                            <i><b style={{ width: `${option.value}%` }} /></i>
                            <strong>{option.value}%</strong>
                            <small>{option.detail}</small>
                          </section>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              ) : null}
              {result.notes.length ? <div className="sw-result-notes"><h3>关键解释</h3>{result.notes.map((note) => <p key={note}>{note}</p>)}</div> : null}
              {result.quotes.length ? <div className="sw-result-quotes"><h3>代表性轨迹</h3>{result.quotes.map((quote) => <article key={`${quote.name}-${quote.quote}`}><span>{quote.name} · {quote.role}</span><p>“{quote.quote}”</p></article>)}</div> : null}
              {result.methodology?.length ? <div className="sw-result-notes"><h3>计算口径</h3>{result.methodology.map((item) => <p key={item}>{item}</p>)}</div> : null}
              <button className="sw-run-button subtle" type="button" onClick={() => { setResult(null); setProgress(0); }}>调整条件，再运行一次</button>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function TaskCenter({ tasks, refreshing, onClose, onRefresh, onResume }: {
  tasks: TaskHistoryItem[];
  refreshing: boolean;
  onClose: () => void;
  onRefresh: () => void;
  onResume: (task: TaskHistoryItem) => void;
}) {
  const statusLabels: Record<TaskHistoryItem['status'], string> = {
    queued: '排队中', running: '运行中', cancelling: '终止中', complete: '已完成',
    cancelled: '已终止', failed: '失败',
  };
  return (
    <aside className="sw-task-center" role="dialog" aria-modal="true" aria-label="任务中心">
      <header>
        <div><span>TASK CENTER</span><h2>最近任务</h2><p>任务离开面板后仍可按 ID 恢复。</p></div>
        <button type="button" aria-label="关闭任务中心" onClick={onClose}>×</button>
      </header>
      <div className="sw-task-center-body">
        <button className="sw-task-refresh" disabled={refreshing || !tasks.length} type="button" onClick={onRefresh}>{refreshing ? '正在同步…' : '同步任务状态'}</button>
        {tasks.length ? tasks.map((task) => (
          <article className={`status-${task.status}`} key={task.jobId}>
            <header><span>{task.toolLabel}</span><b>{statusLabels[task.status]}</b></header>
            <strong>{task.stage}</strong>
            <p>{task.latestTrace}</p>
            <div><i style={{ width: `${task.progress}%` }} /></div>
            <footer>
              <code>{task.jobId}</code>
              <time dateTime={task.updatedAt}>{new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(task.updatedAt))}</time>
              <button type="button" onClick={() => onResume(task)}>打开任务</button>
            </footer>
          </article>
        )) : <div className="sw-task-empty"><strong>还没有任务</strong><p>运行问卷、事件或洞察工具后，进度会保存在这里。</p></div>}
      </div>
    </aside>
  );
}

function AgentPanel({ agent, onSelect, onSelectId, onClose }: {
  agent: WorldAgent;
  onSelect: (agent: WorldAgent) => void;
  onSelectId: (personaId: string) => void;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  const [question, setQuestion] = useState('这件事会怎样影响你的选择？');
  const [answer, setAnswer] = useState('');
  const [thinking, setThinking] = useState(false);
  const [interview, setInterview] = useState<PersonaInterviewResponse | null>(null);
  const [interviewError, setInterviewError] = useState('');
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const recognitionWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const kickoff = window.setTimeout(() => {
      setVoiceSupported(Boolean(recognitionWindow.SpeechRecognition || recognitionWindow.webkitSpeechRecognition));
    }, 0);
    return () => {
      window.clearTimeout(kickoff);
      recognitionRef.current?.stop();
    };
  }, []);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => panelRef.current?.querySelector<HTMLElement>('button, input')?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKeyDown);
      previousFocus?.focus();
    };
  }, []);
  const related = agent.relationships.map((relationship) => {
    const localAgent = WORLD_AGENTS.find((item) => item.id === relationship.agentId);
    return {
      ...relationship,
      localAgent,
      name: relationship.name || localAgent?.name,
      role: relationship.role || localAgent?.role,
    };
  }).filter((item) => item.name);

  async function ask() {
    if (!question.trim()) return;
    setThinking(true); setAnswer(''); setInterview(null); setInterviewError('');
    try {
      if (agent.backendId) {
        const result = await postJson<PersonaInterviewResponse>(
          `/api/qianscope/v1/personas/${encodeURIComponent(agent.backendId)}/interview`,
          { question, event_context: '' },
        );
        setInterview(result);
        setAnswer(result.answer);
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 720));
      setAnswer(`对我来说，${agent.goal} 我不会只看一条消息就决定。现在我更在意它是否与“${agent.values[0]}”一致，以及身边可信的人是否也得出了相似判断。结合今天的状态，我大概率会先${agent.action.replace(/^在|^赶往|^整理|^调试|^核对|^检查/, '')}，再决定是否公开表达。`);
    } catch (reason) {
      setInterviewError(reason instanceof Error ? reason.message : '访谈暂时不可用');
    } finally {
      setThinking(false);
    }
  }

  function startVoiceInput() {
    const recognitionWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition = recognitionWindow.SpeechRecognition || recognitionWindow.webkitSpeechRecognition;
    if (!Recognition || listening) return;
    const recognition = new Recognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript?.trim();
      if (transcript) setQuestion(transcript);
    };
    recognition.onerror = () => {
      setInterviewError('语音输入未能完成，请检查麦克风权限或直接键入问题。');
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setInterviewError('');
    setListening(true);
    recognition.start();
  }

  return (
    <aside ref={panelRef} className="sw-agent-panel" role="dialog" aria-modal="true" aria-label={`${agent.name}的人物访谈面板`} tabIndex={-1}>
      <header><div><span>PERSONA · {agent.id.slice(-6).toUpperCase()}</span><h2>{agent.name}</h2><p>{agent.role} · {agent.organization}</p></div><button type="button" aria-label="关闭人物面板" onClick={onClose}>×</button></header>
      <div className="sw-agent-body">
        <p className="sw-agent-disclaimer">AI 合成人格 · 用于模拟推演，不代表现实中的具体个人。{agent.representedWeight ? ` 当前原型加权代表约 ${Math.round(agent.representedWeight).toLocaleString('zh-CN')} 人。` : ''}</p>
        <p className="sw-agent-bio">{agent.bio}</p>
        <div className="sw-agent-tags">{[...agent.traits, ...agent.values].map((item) => <span key={item}>{item}</span>)}</div>
        {agent.demographics ? (
          <section className="sw-persona-demographics">
            <h3>基础画像</h3>
            <div>{Object.entries(agent.demographics).map(([key, value]) => <p key={key}><span>{PERSONA_DEMOGRAPHIC_LABELS[key] || key}</span><strong>{value}</strong></p>)}</div>
          </section>
        ) : null}
        {agent.frameworks?.length ? (
          <section className="sw-persona-frameworks">
            <header>
              <div><h3>完整人格定义</h3><p>稳定倾向与当前状态分离；分数不是能力、诊断或现实个人测量。</p></div>
              <b>{Math.round((agent.profileCompleteness || 0) * 100)}% 完整</b>
            </header>
            {agent.frameworks.map((framework) => (
              <details key={framework.id}>
                <summary><strong>{framework.label}</strong><span>{framework.dimensions.length} 维 · {framework.reference}</span></summary>
                <p>{framework.description}</p>
                <div>
                  {framework.dimensions.map((dimension) => {
                    const normalized = (dimension.score - dimension.scaleMin) / Math.max(.0001, dimension.scaleMax - dimension.scaleMin);
                    return (
                      <article key={dimension.key} title={dimension.description}>
                        <header><strong>{dimension.label}</strong><span>{dimension.score.toFixed(2)}</span></header>
                        <i><b style={{ width: `${Math.max(0, Math.min(100, normalized * 100))}%` }} /></i>
                        <small>{dimension.interpretation}</small>
                      </article>
                    );
                  })}
                </div>
              </details>
            ))}
            <footer>定义版本 · {agent.definitionVersion}</footer>
          </section>
        ) : null}
        <div className="sw-state-grid">
          <div><span>当前情绪</span><strong>{agent.mood}</strong></div>
          <div><span>压力</span><strong>{agent.stress}%</strong></div>
          <div><span>行动意图</span><strong>{agent.intention}%</strong></div>
          <div><span>当前位置</span><strong>{agent.location}</strong></div>
        </div>
        <section className="sw-memory-card"><h3>近期记忆与目标</h3><strong>{agent.goal}</strong>{agent.memories.map((memory) => <p key={memory}>{memory}</p>)}</section>
        {related.length ? <section className="sw-relationship-card"><h3>一度人脉关系</h3><div className="sw-relation-hub"><span>{agent.name}</span>{related.map((item) => <button key={item.agentId} type="button" onClick={() => item.localAgent ? onSelect(item.localAgent) : onSelectId(item.agentId)}><b>{item.name}</b><small>{item.relation} · 信任 {Math.round(item.trust * 100)}</small></button>)}</div></section> : null}
        <section className="sw-interview-card">
          <h3>向 TA 提问</h3>
          <div className="sw-interview-presets" aria-label="访谈问题预设">{INTERVIEW_PROMPTS.map((prompt) => <button type="button" key={prompt} onClick={() => setQuestion(prompt)}>{prompt}</button>)}</div>
          <div className="sw-interview-input"><input aria-label={`向${agent.name}提问`} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && void ask()} /><button className={listening ? 'listening' : ''} disabled={!voiceSupported || listening} title={voiceSupported ? '使用语音输入' : '当前浏览器不支持语音输入'} type="button" aria-label="语音输入问题" onClick={startVoiceInput}>{listening ? '…' : '声'}</button><button type="button" onClick={() => void ask()}>问</button></div>
          {thinking ? <p className="sw-thinking"><i /> TA 正在回想与判断…</p> : null}
          {interviewError ? <p className="sw-result-warning">访谈失败：{interviewError}</p> : null}
          {answer ? <article><span>当前叙述 · {agent.name}{interview ? ` · 置信 ${Math.round(interview.confidence * 100)}%` : ''}</span><p>{answer}</p><small>{interview?.cognitive_boundary || '回答引用了人格、目标、状态与记忆；不展示隐藏推理过程。'}</small>{interview?.cross_check_candidates.length ? <div className="sw-cross-check"><em>问问当事人</em>{interview.cross_check_candidates.map((candidate) => <button type="button" key={candidate.persona_id} onClick={() => onSelectId(candidate.persona_id)}>{candidate.name} · {candidate.relation}</button>)}</div> : null}</article> : null}
        </section>
        {agent.profileHash ? <p className="sw-profile-hash">稳定档案哈希 · {agent.profileHash.slice(0, 16)}</p> : null}
      </div>
    </aside>
  );
}

function CityScene({
  camera,
  mapStatus,
  onCameraChange,
  onAgentSelect,
  onAgentActivityChange,
  onEnter,
  onStatusChange,
  onWeatherChange,
  populationVisible,
}: {
  camera: SocialMapCamera;
  mapStatus: SocialMapStatus;
  onAgentSelect: (personaId: string) => void;
  onAgentActivityChange: (status: SocialAgentActivityStatus) => void;
  onCameraChange: (camera: SocialMapCamera) => void;
  onEnter: (location: WorldLocation) => void;
  onStatusChange: (status: SocialMapStatus) => void;
  onWeatherChange: (weather: SocialWeather) => void;
  populationVisible: boolean;
}) {
  return (
    <div className={`sw-city-scene provider-${mapStatus.provider} ${mapStatus.ready ? 'map-ready' : ''}`} aria-label={`${SOCIAL_WORLD_CITY.name}社会世界地图`}>
      <SocialWorldMap
        camera={camera}
        locations={WORLD_LOCATIONS}
        onAgentSelect={onAgentSelect}
        onAgentActivityChange={onAgentActivityChange}
        onCameraChange={onCameraChange}
        onEnter={onEnter}
        onStatusChange={onStatusChange}
        onWeatherChange={onWeatherChange}
        populationVisible={populationVisible}
      />
      <svg className="sw-map-art" viewBox="0 0 1000 700" preserveAspectRatio="none" aria-hidden="true">
        <defs><pattern id="streetGrid" width="52" height="52" patternUnits="userSpaceOnUse"><path d="M 52 0 L 0 0 0 52" fill="none" stroke="rgba(87,119,109,.14)" strokeWidth="2" /></pattern><filter id="softGlow"><feGaussianBlur stdDeviation="5" /></filter></defs>
        <rect width="1000" height="700" fill="url(#streetGrid)" />
        <path d="M-40 530 C180 390 290 480 430 358 S720 180 1050 235" className="sw-map-water" />
        <path d="M40 80 C210 175 340 90 480 208 S735 490 980 396" className="sw-map-ring" />
        <path d="M20 630 C205 510 380 610 566 430 S800 260 1020 120" className="sw-map-road" />
        <path d="M80 30 C180 220 270 300 420 380 S700 560 960 650" className="sw-map-road thin" />
        <path d="M100 610 C250 420 350 260 520 180 S760 110 910 10" className="sw-map-road thin" />
        <ellipse cx="345" cy="212" rx="84" ry="52" className="sw-map-park" />
        <ellipse cx="728" cy="438" rx="108" ry="64" className="sw-map-park muted" />
        <circle cx="490" cy="330" r="94" className="sw-map-glow" filter="url(#softGlow)" />
      </svg>
      {!mapStatus.ready ? WORLD_LOCATIONS.map((location) => (
        <button className={`sw-place-marker ${location.featured ? 'hero' : ''}`} key={location.id} style={{ left: `${location.x}%`, top: `${location.y}%` }} type="button" onClick={() => onEnter(location)}>
          <i /><span>{location.short}</span><small>{location.population} 活跃</small>
        </button>
      )) : null}
      <nav className="sw-mobile-locations" aria-label={`${SOCIAL_WORLD_CITY.name}地点快捷导航`}>
        {WORLD_LOCATIONS.map((location) => <button key={location.id} type="button" onClick={() => onEnter(location)}>{location.short}</button>)}
      </nav>
      <div className="sw-map-scale"><span>20 km</span></div>
    </div>
  );
}

type InteriorKind = 'dining' | 'auditorium' | 'lab' | 'library' | 'community';

const INTERIOR_FLOOR_NAMES: Record<InteriorKind, string[]> = {
  dining: ['到达与取餐层', '社区长桌层', '风味餐饮层', '后勤与营养层', '屋顶交流层'],
  auditorium: ['公共前厅', '主舞台与观众席', '排练与候场层', '制作控制层', '小型路演层'],
  lab: ['访客与安全层', '共享实验层', '项目协作层', '精密仪器层', '成果交流层'],
  library: ['借阅与到达层', '安静学习层', '协作讨论层', '专题资料层', '屋顶阅读层'],
  community: ['综合服务层', '邻里客厅层', '亲子与照护层', '社区议事层', '健康支持层'],
};

const INTERIOR_ACTIVITIES: Record<InteriorKind, string[]> = {
  dining: ['午间补给与人流分配', '小组用餐与熟人交流', '窗口选择与排队决策', '备餐、配送与质量检查', '非正式社群活动'],
  auditorium: ['检票、会合与消息交换', '公开演讲与群体反馈', '表演排练与角色协调', '直播、灯光与传播控制', '项目发布与小型讨论'],
  lab: ['访客登记与风险确认', '实验执行与数据记录', '跨团队评审与方案迭代', '预约仪器与样品分析', '成果展示与合作匹配'],
  library: ['借还、咨询与新信息暴露', '独立阅读与深度判断', '小组讨论与观点校正', '档案检索与证据核验', '开放阅读与偶遇交流'],
  community: ['办事咨询与服务分流', '邻里休息与弱关系交流', '家庭照护与活动协作', '公共议题讨论与表态', '健康咨询与持续支持'],
};

const INTERIOR_ROOMS: Record<InteriorKind, string[][]> = {
  dining: [
    ['入口闸机', '主取餐窗口', '流量指引', '无障碍餐区', '外卖取餐点'],
    ['社区长桌', '小组餐区', '临窗座位', '餐具回收', '饮水补给'],
    ['风味窗口', '开放餐区', '轻食岛台', '意见反馈屏', '弹性座位'],
    ['营养工作间', '后勤通道', '冷链存储', '安全监测', '配送调度'],
    ['屋顶餐吧', '社群长桌', '活动角', '观景座位', '设备间'],
  ],
  auditorium: [
    ['公共前厅', '检票台', '衣帽间', '媒体签到', '等候区'],
    ['主舞台', '阶梯观众席', '无障碍席位', '同传区', '演讲准备台'],
    ['排练厅', '候场区', '化妆间', '道具存放', '演员休息区'],
    ['直播控制台', '灯光控制室', '音频工作间', '媒体编辑区', '设备库'],
    ['路演厅', '圆桌讨论区', '项目展板', '茶歇区', '评审席'],
  ],
  lab: [
    ['安全登记', '访客展廊', '防护准备', '项目看板', '应急支持'],
    ['实验工作台', '数据监测区', '洁净操作间', '样品暂存', '协作工位'],
    ['项目战情室', '原型装配区', '远程协作间', '评审桌', '资料墙'],
    ['精密仪器区', '预约控制台', '暗室', '样品存储', '分析终端'],
    ['成果展廊', '路演工位', '合作洽谈区', '开放实验台', '屋顶测试区'],
  ],
  library: [
    ['借阅服务台', '到达大厅', '新书展架', '自助借还', '信息咨询'],
    ['安静学习区', '开放书架', '个人研读间', '资料扫描', '静音休息区'],
    ['共享讨论区', '小组研讨室', '数字白板', '协作客厅', '开放资料台'],
    ['专题档案室', '古籍阅览', '数据资源区', '研究咨询', '小型展陈'],
    ['屋顶阅读室', '公共沙龙', '观景书廊', '作家工位', '设备间'],
  ],
  community: [
    ['综合服务台', '业务等候区', '社区公告', '无障碍支持', '快递服务点'],
    ['邻里客厅', '共享厨房', '长者休息区', '社区书架', '志愿者工位'],
    ['亲子活动区', '托育支持站', '家庭咨询', '儿童阅读角', '母婴室'],
    ['社区议事厅', '圆桌讨论区', '居民提案墙', '调解室', '公共直播间'],
    ['健康支持站', '问诊室', '运动指导区', '心理支持间', '康复训练区'],
  ],
};

function interiorPresentation(building: string, floor: number): FlipbookInteriorProfile {
  const kind: InteriorKind = /食堂|餐厅|茶馆/.test(building)
    ? 'dining'
    : /礼堂|交流|路演|展演|会客厅|会议|发布|候车|大厅|展览/.test(building)
      ? 'auditorium'
      : /科创|科研|实验|制造|创新/.test(building)
        ? 'lab'
        : /图书|南雍|书店|资料/.test(building)
          ? 'library'
          : 'community';
  const labels: Record<InteriorKind, string> = {
    dining: '餐饮与交流空间', auditorium: '演讲与展演空间', lab: '实验与协作空间',
    library: '阅读与学习空间', community: '社区公共空间',
  };
  const baseCounts: Record<InteriorKind, number> = { dining: 104, auditorium: 116, lab: 64, library: 78, community: 82 };
  const capacityBases: Record<InteriorKind, number> = { dining: 280, auditorium: 420, lab: 96, library: 180, community: 150 };
  const index = Math.max(0, Math.min(4, floor - 1));
  const count = Math.max(18, baseCounts[kind] + [14, 4, -8, -18, -26][index]);
  const capacity = Math.max(count, capacityBases[kind] + [40, 0, -24, -42, -58][index]);
  return {
    kind: labels[kind],
    floorName: INTERIOR_FLOOR_NAMES[kind][index],
    activity: INTERIOR_ACTIVITIES[kind][index],
    count,
    capacity,
    openHours: index === 4 ? '09:00—21:00' : kind === 'lab' ? '08:30—22:00 · 预约制' : '07:30—22:30',
    transition: floor === 1 ? '城市入口与垂直交通' : `${floor - 1}F / ${Math.min(5, floor + 1)}F 连续动线`,
    rooms: INTERIOR_ROOMS[kind][index],
  };
}

export function SocialWorldExperience() {
  const [level, setLevel] = useState<WorldLevel>('city');
  const [location, setLocation] = useState<WorldLocation>(WORLD_LOCATIONS[0]);
  const [building, setBuilding] = useState<string>(SOCIAL_WORLD_CITY.defaultBuilding);
  const [floor, setFloor] = useState(3);
  const [activeTool, setActiveTool] = useState<ToolDefinition | null>(null);
  const [activeToolForm, setActiveToolForm] = useState<ToolFormState | null>(null);
  const [activeRecoveryId, setActiveRecoveryId] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<WorldAgent | null>(null);
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [remoteSearch, setRemoteSearch] = useState<PersonaSearchResult | null>(null);
  const [searchingPersonas, setSearchingPersonas] = useState(false);
  const [personaError, setPersonaError] = useState('');
  const [loadingPersonaId, setLoadingPersonaId] = useState('');
  const [now, setNow] = useState<Date | null>(null);
  const [toolOpen, setToolOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStory, setTourStory] = useState('');
  const [taskOpen, setTaskOpen] = useState(false);
  const [tasks, setTasks] = useState<TaskHistoryItem[]>([]);
  const [refreshingTasks, setRefreshingTasks] = useState(false);
  const [populationVisible, setPopulationVisible] = useState(true);
  const [mapCamera, setMapCamera] = useState<SocialMapCamera>(DEFAULT_SOCIAL_MAP_CAMERA);
  const [mapStatus, setMapStatus] = useState<SocialMapStatus>({
    provider: 'loading',
    ready: false,
    detail: '正在连接高德城市空间…',
  });
  const [weather, setWeather] = useState<SocialWeather | null>(null);
  const [agentActivity, setAgentActivity] = useState<SocialAgentActivityStatus>({
    ready: false,
    total: 0,
    moving: 0,
    detail: '正在同步稳定数字人格…',
  });

  useEffect(() => {
    const kickoff = window.setTimeout(() => setNow(new Date()), 0);
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => {
      window.clearTimeout(kickoff);
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!window.matchMedia('(max-width: 620px)').matches) return;
    const kickoff = window.setTimeout(() => setToolOpen(false), 0);
    return () => window.clearTimeout(kickoff);
  }, []);

  useEffect(() => {
    if (!searchOpen) return;
    function closeSearch(event: PointerEvent) {
      if (!(event.target as HTMLElement | null)?.closest('.sw-search')) setSearchOpen(false);
    }
    document.addEventListener('pointerdown', closeSearch);
    return () => document.removeEventListener('pointerdown', closeSearch);
  }, [searchOpen]);

  useEffect(() => {
    const saved = window.localStorage.getItem(TASK_HISTORY_KEY)
      ?? window.localStorage.getItem(LEGACY_TASK_HISTORY_KEY);
    if (!saved) return;
    const kickoff = window.setTimeout(() => {
      try {
        const parsed = JSON.parse(saved) as TaskHistoryItem[];
        setTasks(parsed.slice(0, 12));
      } catch {
        window.localStorage.removeItem(TASK_HISTORY_KEY);
      }
    }, 0);
    return () => window.clearTimeout(kickoff);
  }, []);

  useEffect(() => {
    const activeQuery = query.trim();
    if (!activeQuery) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setSearchingPersonas(true);
      setPersonaError('');
      try {
        const result = await getJson<PersonaSearchResult>(
          `/api/qianscope/v1/personas?query=${encodeURIComponent(activeQuery)}&limit=8`,
        );
        if (!cancelled) setRemoteSearch(result);
      } catch (reason) {
        if (!cancelled) setPersonaError(personaErrorMessage(reason));
      } finally {
        if (!cancelled) setSearchingPersonas(false);
      }
    }, 240);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const localSearchResults = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];
    return WORLD_AGENTS.filter((agent) => [agent.name, agent.role, agent.organization, agent.location, ...agent.traits, ...agent.values].join(' ').toLowerCase().includes(normalized)).slice(0, 6);
  }, [query]);

  const remoteSearchResults = remoteSearch?.query.trim() === query.trim()
    ? remoteSearch.items.filter((item) => !localSearchResults.some((local) => local.name === item.name))
    : [];

  function recordTask(task: TaskHistoryItem) {
    setTasks((current) => {
      const next = [task, ...current.filter((item) => item.jobId !== task.jobId)]
        .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
        .slice(0, 12);
      window.localStorage.setItem(TASK_HISTORY_KEY, JSON.stringify(next));
      return next;
    });
  }

  async function refreshTasks() {
    if (!tasks.length || refreshingTasks) return;
    setRefreshingTasks(true);
    const next = await Promise.all(tasks.map(async (task) => {
      try {
        const record = await getJson<JobRecord>(`/api/qianscope/v1/jobs/${encodeURIComponent(task.jobId)}`);
        return {
          ...task,
          kind: record.kind,
          status: record.status,
          progress: record.progress,
          stage: record.stage,
          latestTrace: record.latest_trace,
          updatedAt: new Date().toISOString(),
        } satisfies TaskHistoryItem;
      } catch {
        return task;
      }
    }));
    setTasks(next);
    window.localStorage.setItem(TASK_HISTORY_KEY, JSON.stringify(next));
    setRefreshingTasks(false);
  }

  function resumeTask(task: TaskHistoryItem) {
    const tool = WORLD_TOOLS.find((item) => item.key === task.toolKey);
    if (!tool) return;
    window.localStorage.setItem(
      lastJobKey(task.toolKey),
      JSON.stringify({ jobId: task.jobId, tool: task.toolKey, form: task.form }),
    );
    setTaskOpen(false);
    setSelectedAgent(null);
    setActiveToolForm(task.form);
    setActiveRecoveryId(task.jobId);
    setActiveTool(tool);
  }

  function enterLocation(next: WorldLocation) {
    setLocation(next); setLevel('campus'); setSelectedAgent(null); setTourStory(''); setToolOpen(false); setSearchOpen(false);
  }

  function selectStory(story: (typeof GUIDED_STORIES)[number]) {
    const storyLocation = WORLD_LOCATIONS.find((item) => item.id === story.locationId) || WORLD_LOCATIONS[0];
    setTourStory(story.title);
    setTourOpen(false);
    setLocation(storyLocation);
    setBuilding(story.building);
    setFloor(story.floor);
    setLevel('interior');
    setSelectedAgent(null);
    setActiveTool(null);
    setActiveToolForm(null);
    setActiveRecoveryId('');
    setTaskOpen(false);
    setToolOpen(false);
    setSearchOpen(false);
  }

  function showAgent(agent: WorldAgent, preserveCity = false) {
    const home = WORLD_LOCATIONS.find((item) => item.id === agent.locationId) || WORLD_LOCATIONS[0];
    const locationChanged = home.id !== location.id;
    setLocation(home);
    if (locationChanged) {
      setBuilding(home.buildings?.[0] || SOCIAL_WORLD_CITY.defaultBuilding);
      setFloor(1);
      if (!preserveCity) setLevel('campus');
    } else if (level === 'city' && !preserveCity) {
      setLevel('campus');
    }
    setActiveTool(null); setActiveToolForm(null); setActiveRecoveryId(''); setTaskOpen(false); setSelectedAgent(agent); setSearchOpen(false); setQuery('');
  }

  async function showRemotePersona(personaId: string, preserveCity = false) {
    setLoadingPersonaId(personaId); setPersonaError('');
    try {
      const profile = await getJson<PersonaProfile>(`/api/qianscope/v1/personas/${encodeURIComponent(personaId)}`);
      showAgent(personaToWorldAgent(profile), preserveCity);
    } catch (reason) {
      setPersonaError(personaErrorMessage(reason));
    } finally {
      setLoadingPersonaId('');
    }
  }

  function openTool(tool: ToolDefinition, initialForm: ToolFormState | null = null) {
    setSelectedAgent(null);
    setTaskOpen(false);
    setToolOpen(false);
    setSearchOpen(false);
    setActiveRecoveryId('');
    setActiveToolForm(initialForm);
    setActiveTool(tool);
  }

  const timeLabel = now ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(now) : '--:--:--';
  const dateLabel = now ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'long', day: 'numeric', weekday: 'short' }).format(now) : '中国标准时间';
  const activeStory = GUIDED_STORIES.find((story) => story.title === tourStory);
  const activeTaskCount = tasks.filter((task) => ['queued', 'running', 'cancelling'].includes(task.status)).length;
  const contextLabel = level === 'city'
    ? `${SOCIAL_WORLD_CITY.fullName} · 社会世界`
    : level === 'campus'
      ? `${location.short} · 地点画页`
      : `${location.short} / ${building} / ${floor}F`;

  return (
    <main className={`social-world sw-level-${level} ${populationVisible ? 'sw-view-activity' : 'sw-view-calm'} ${toolOpen ? 'sw-tools-open' : 'sw-tools-collapsed'}`}>
      <div className="sw-world-canvas">
        {level === 'city' ? (
          <CityScene
            camera={mapCamera}
            mapStatus={mapStatus}
            onAgentSelect={(personaId) => void showRemotePersona(personaId, true)}
            onAgentActivityChange={setAgentActivity}
            onCameraChange={setMapCamera}
            onEnter={enterLocation}
            onStatusChange={setMapStatus}
            onWeatherChange={setWeather}
            populationVisible={populationVisible}
          />
        ) : null}
        {level !== 'city' ? (
          <SocialWorldFlipbook
            level={level}
            location={location}
            building={building}
            floor={floor}
            selectedAgentId={selectedAgent?.id}
            interiorProfile={interiorPresentation(building, floor)}
            onAgentSelect={showAgent}
            onEnterInterior={(nextBuilding) => { setBuilding(nextBuilding); setFloor(1); setLevel('interior'); }}
            onFloorChange={setFloor}
            onReturnCity={() => { setSelectedAgent(null); setLevel('city'); }}
            onReturnLocation={() => { setSelectedAgent(null); setLevel('campus'); }}
          />
        ) : null}
      </div>

      <header className="sw-command-bar" aria-label="黔镜工作台">
        <div className="sw-command-brand sw-glass">
          <span className="sw-command-mark" aria-hidden="true">
            <svg viewBox="0 0 40 40"><ellipse cx="20" cy="20" rx="15" ry="7" /><ellipse cx="20" cy="20" rx="15" ry="7" transform="rotate(60 20 20)" /><ellipse cx="20" cy="20" rx="15" ry="7" transform="rotate(120 20 20)" /><circle cx="20" cy="20" r="3" /></svg>
          </span>
          <span className="sw-command-name"><strong>黔镜</strong><small>QIANSCOPE</small></span>
          <i aria-hidden="true" />
          <span className="sw-command-context">{contextLabel}</span>
        </div>

        <WorldQueryToolbar
          value={query}
          placeholder={`搜索 ${SOCIAL_WORLD_CITY.prototypeCount.toLocaleString('zh-CN')} 个稳定人格…`}
          open={searchOpen}
          controlsId="persona-search-results"
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => setSearchOpen(true)}
          onToggle={() => setSearchOpen((value) => !value)}
          onEscape={() => setSearchOpen(false)}
        >
          {searchOpen ? <div id="persona-search-results" className="sw-search-results" aria-label="人物搜索结果">
            {query ? <>
              {remoteSearch?.query.trim() === query.trim() ? <p className="sw-search-meta"><b>{remoteSearch.prototype_matches.toLocaleString('zh-CN')}</b> 个原型匹配 · 加权代表 {Math.round(remoteSearch.represented_population).toLocaleString('zh-CN')} 人</p> : null}
              {localSearchResults.map((agent) => <button type="button" key={agent.id} onClick={() => showAgent(agent)}><strong>{agent.name}</strong><span>{agent.role}</span><small>{agent.location} · 精选人物</small></button>)}
              {remoteSearchResults.map((agent: PersonaSearchItem) => <button type="button" key={agent.persona_id} onClick={() => void showRemotePersona(agent.persona_id)} disabled={loadingPersonaId === agent.persona_id}><strong>{agent.name}</strong><span>{agent.role}</span><small>{agent.location} · {loadingPersonaId === agent.persona_id ? '正在读取档案…' : `代表约 ${Math.round(agent.represented_weight).toLocaleString('zh-CN')} 人`}</small></button>)}
              {searchingPersonas ? <p className="sw-search-loading"><i /> 正在检索 5,000 个稳定人格…</p> : null}
              {personaError ? <p className="sw-search-error">{personaError}</p> : null}
              {!searchingPersonas && !personaError && !localSearchResults.length && !remoteSearchResults.length ? <p>没有匹配的人物</p> : null}
            </> : <div className="sw-search-empty"><strong>搜索稳定人格</strong><span>输入姓名、职业、地点、特质或价值观，打开可访谈的完整人物档案。</span></div>}
          </div> : null}
        </WorldQueryToolbar>

        <nav className="sw-command-actions sw-glass" aria-label="工作台操作">
          <button className={taskOpen ? 'active' : ''} type="button" aria-expanded={taskOpen} onClick={() => { setTaskOpen((value) => !value); setTourOpen(false); setToolOpen(false); setSearchOpen(false); }}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5.5h10M7 12h10M7 18.5h6" /><circle cx="4" cy="5.5" r=".8" /><circle cx="4" cy="12" r=".8" /><circle cx="4" cy="18.5" r=".8" /></svg><span>任务</span><b>{activeTaskCount || tasks.length}</b>
          </button>
          <button className={tourOpen ? 'active' : ''} type="button" aria-expanded={tourOpen} onClick={() => { setTourOpen((value) => !value); setTaskOpen(false); setToolOpen(false); setSearchOpen(false); }}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 7 7 5-7 5Z" /></svg><span>剧本</span>
          </button>
          <button className={toolOpen ? 'active' : ''} type="button" aria-expanded={toolOpen} aria-controls="world-tools" onClick={() => { setToolOpen((value) => !value); setTaskOpen(false); setTourOpen(false); setSearchOpen(false); }}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg><span>工具</span>
          </button>
        </nav>
      </header>

      {level === 'city' ? <section className="sw-brand-card sw-glass">
        <p><i /> GUIYANG SOCIAL WORLD</p>
        <h1>贵阳社会世界</h1>
        <p>在真实城市空间上观察合成人群、关系网络与事件传播。选择地点进入 OpenFlipbook 交互画页，或直接发起社会推演。</p>
        <div className="sw-overview-metrics">
          <article><strong>{SOCIAL_WORLD_CITY.prototypeCount.toLocaleString('zh-CN')}</strong><span>稳定人格原型</span></article>
          <article><strong>{SOCIAL_WORLD_CITY.representedPopulationLabel}</strong><span>加权代表人口</span></article>
          <article><strong>{timeLabel}</strong><span>{weather ? `${weather.weather} ${weather.temperature}°C` : dateLabel}</span></article>
        </div>
        <footer className="sw-overview-live">
          <span><i />{mapStatus.provider === 'amap' ? '高德城市空间已连接' : mapStatus.detail}</span>
          <button type="button" aria-pressed={populationVisible} onClick={() => setPopulationVisible((value) => !value)}>{populationVisible ? '隐藏人格活动' : '显示人格活动'}</button>
          <small>{populationVisible ? agentActivity.ready ? `${agentActivity.total.toLocaleString('zh-CN')} 个数字人格在线 · ${agentActivity.moving.toLocaleString('zh-CN')} 个移动中` : agentActivity.detail : '当前仅显示城市空间'}</small>
        </footer>
      </section> : null}

      {tourOpen ? <section className="sw-tour-menu sw-glass"><header><div><span>GUIDED STORIES</span><h2>选择一个可运行剧本</h2></div><button type="button" aria-label="关闭剧本列表" onClick={() => setTourOpen(false)}>×</button></header>{GUIDED_STORIES.map((story) => <button className={tourStory === story.title ? 'active' : ''} type="button" key={story.title} onClick={() => selectStory(story)}>{story.title}<span>→</span></button>)}</section> : null}
      {activeStory ? <section className="sw-story-card sw-glass"><span>示例剧本 · 场景与参数已装载</span><h3>{activeStory.title}</h3><p className="sw-story-summary">{activeStory.summary}</p><small className="sw-story-location">{location.short} · 剧本起点：{activeStory.building} {activeStory.floor}F · {activeStory.focus}</small><div><p><strong>5,000</strong><span>稳定人格原型</span></p><p><strong>{activeStory.paths}</strong><span>可复现路径</span></p><p><strong>{activeStory.horizon}</strong><span>推演窗口</span></p></div><button className="sw-story-run" type="button" onClick={() => { const eventTool = WORLD_TOOLS.find((item) => item.key === 'event'); if (eventTool) openTool(eventTool, { event: activeStory.event, horizon: activeStory.horizon, targetLocationId: activeStory.locationId }); }}>运行这个剧本 →</button><button className="sw-story-close" type="button" onClick={() => setTourStory('')}>结束导览</button></section> : null}

      <section id="world-tools" className={`sw-tool-launcher sw-glass ${toolOpen ? 'open' : 'collapsed'}`}>
        <header><div><span>QIANSCOPE TOOLKIT</span><strong>推演与洞察工具</strong></div><button type="button" aria-label="关闭工具面板" aria-expanded={toolOpen} aria-controls="world-tool-list" onClick={() => setToolOpen(false)}>×</button></header>
        {toolOpen ? <>
          <div id="world-tool-list"><p>社会推演</p><div className="sw-tool-grid primary">{WORLD_TOOLS.filter((tool) => tool.group === 'simulation').map((tool) => <button type="button" key={tool.key} onClick={() => openTool(tool)}><span className="sw-tool-icon">{tool.icon}</span><span className="sw-tool-copy"><strong>{tool.label}</strong><small>{tool.description}</small></span></button>)}</div>
          <p>研究与洞察</p><div className="sw-tool-grid">{WORLD_TOOLS.filter((tool) => tool.group === 'insight').map((tool) => <button type="button" key={tool.key} onClick={() => openTool(tool)}><span className="sw-tool-icon">{tool.icon}</span><span className="sw-tool-copy"><strong>{tool.label}</strong><small>{tool.description}</small></span></button>)}</div></div>
        </> : null}
      </section>

      {level === 'city' ? <p className="sw-disclaimer sw-glass"><b>AI</b><span>合成人格与推演结果用于研究辅助，不代表现实个人，也不替代真实调查。</span></p> : null}

      {taskOpen ? <TaskCenter tasks={tasks} refreshing={refreshingTasks} onClose={() => setTaskOpen(false)} onRefresh={() => void refreshTasks()} onResume={resumeTask} /> : null}
      {activeTool ? <ToolPanel tool={activeTool} initialForm={activeToolForm} initialRecoveryId={activeRecoveryId} onTaskChange={recordTask} onClose={() => { setActiveTool(null); setActiveToolForm(null); setActiveRecoveryId(''); }} /> : null}
      {selectedAgent ? <AgentPanel key={selectedAgent.id} agent={selectedAgent} onSelect={showAgent} onSelectId={(personaId) => void showRemotePersona(personaId)} onClose={() => setSelectedAgent(null)} /> : null}
    </main>
  );
}
