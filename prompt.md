# Module A：Human Digital Twin Personality Architecture

## 目标

实现一个面向 Social World Model 的动态人格系统。

不要将 Agent 表示为简单 Persona Prompt。

Agent 必须被建模为：

Human Digital Twin：

[
H_i(t)=
(I_i,P_i,V_i,B_i,G_i,M_i,R_i,C_i)
]

其中：

* I：Identity 身份事实
* P：Personality 人格特征
* V：Values 价值体系
* B：Beliefs 信念系统
* G：Goals 动机目标
* M：Memory 记忆
* R：Relationships 社会关系
* C：Current State 当前心理状态

---

# Personality Layer

实现多理论融合人格模型。

## Big Five

保存：

```
openness
conscientiousness
extraversion
agreeableness
neuroticism
```

## Schwartz Values

保存：

```
self_direction
stimulation
achievement
power
security
conformity
tradition
benevolence
universalism
```

## Moral Foundation

保存：

```
care
fairness
loyalty
authority
purity
liberty
```

## Risk Profile

保存：

```
financial_risk
social_risk
technology_risk
health_risk
```

## Cognitive Style

保存：

```
analytical_intuitive
independent_social
long_short_term
evidence_experience
```

人格必须是结构化向量，而不是自然语言描述。

---

# Belief Model

建立动态信念系统：

[
B_i(t+1)=f(B_i(t),E,R,M)
]

例如：

```
technology_belief

economic_outlook

brand_trust

institutional_trust

social_attitude
```

事件不能直接修改人格。

事件必须通过：

Event

↓

Belief Update

↓

Emotion

↓

Goal Change

↓

Action

---

# Goal Model

实现：

```
security
achievement
status
belonging
growth
meaning
survival
```

每个 Agent 根据目标产生行为偏好。

---

# Memory System

参考 Generative Agents，但升级为：

三层记忆：

## Working Memory

当前上下文。

## Episodic Memory

事件经历。

## Semantic Memory

长期人格总结。

每条 Memory 保存：

```
content

timestamp

importance

emotion

confidence

decay_rate

source

```

实现：

memory retrieval

memory consolidation

memory reflection

memory decay

---

# Dynamic Mental State

每个 Agent 保存：

```
emotion

attention

stress

trust

confidence

interest

intention

awareness

```

事件驱动状态变化：

[
State_{t+1}=Transition(State_t,Event,SocialContext)
]

---

# Social Relationship

实现：

```
friend

family

coworker

follower

authority

community
```

关系包含：

```
strength

trust

similarity

influence

frequency
```

---

# 行为输出

行为必须来自：

```
Identity

+
Personality

+
Values

+
Beliefs

+
Goals

+
Memory

+
Relationship

+
Current State

```

输出：

```json
{
"action_probability":{},
"emotion":{},
"belief_change":{},
"goal_change":{},
"confidence":0
}
```

禁止：

直接 Prompt：

"You are a student..."

代替：

结构化 Human State → Policy Model

---

# Module B：Social World Model Visualization Architecture

## 目标

支持类似城市/校园社会模拟 Demo。

系统必须支持：

```
Human Layer

+
Location Layer

+
Event Layer

+
Relationship Layer

+
Simulation Layer
```

---

# World State

定义：

[
W_t=(H_t,G_t,L_t,E_t)
]

其中：

H：

Human Digital Twins

G：

Social Graph

L：

Location Environment

E：

Events

---

# Environment Model

地点必须成为一等实体。

Location:

```
location_id

type

capacity

population_flow

social_activity

semantic_tags
```

例如：

校园：

```
Dorm

Library

Classroom

Canteen

Club
```

---

# Mobility Model

实现：

```
Home

↓

Work

↓

Social Place

↓

Home
```

预测：

```
where_people_are

who_meets

what_context_exists
```

---

# Event Simulation

事件流程：

```
Event Injection

↓

Awareness Propagation

↓

Individual State Update

↓

Social Diffusion

↓

Behavior Change

↓

Population Aggregation

↓

Future World State
```

---

# Visualization API

输出：

```
population_heatmap

emotion_distribution

belief_distribution

diffusion_curve

segment_difference

location_activity

agent_trace
```

支持：

```
Map View

Timeline View

Population View

Event View
```

---

# 核心模型目标

最终学习：

[
P(W_{t+h}|W_t,E)
]

而不是：

[
P(action|prompt)
]

最终目标：

建立：

Human Digital Twin

*

Social World Graph

*

World State Transition Model

形成：

Social World Foundation Model。

---

# 实现级补充规范：人格构建与底层架构

下列内容用于消除上述概念定义中的实现歧义。若存在“列出字段但未定义状态更新、数据契约或验收方法”的情况，以本节为实现标准。

## 1. 硬性系统边界

本轮范围：

```
Human Digital Twin 人格与动态心智
Social Graph 与传播
Location / Mobility
Event Injection 与 World State Transition
Population / Location / Agent 聚合
API / Snapshot / Replay / Evaluation
```

本轮不要求：

```
高德地图联动
地图底图
3D 建筑渲染
镜头和人物动画
前端 UI 还原
```

禁止把 UI 缺失解释为后端字段可以缺失。Map、Timeline、Population、Event View 所需数据必须由稳定 API 输出。

## 2. Human Digital Twin 状态分区

必须把状态分为不可直接变化的慢变量与事件驱动的快变量。

### 2.1 慢变量

```
Identity
Big Five
Schwartz Values
Moral Foundations
Risk Profile
Cognitive Style
Baseline Goals
```

慢变量必须进入：

```
profile_hash
personality_signature
version
origin / provenance
uncertainty
```

任何 Event Transition 都不得写入慢变量。每个 replay record 必须保存同一个 `personality_signature`。

### 2.2 快变量

```
Beliefs + confidence + evidence_refs
Goal activation
Emotion (valence/arousal/dominance + discrete emotions)
attention / stress / trust / confidence / interest / intention / awareness
Working / Episodic / Semantic Memory
Relationship trust
Current location
Last action
```

快变量必须带：

```
timestamp or tick
state_version
last_updated_by
state_uncertainty
```

## 3. 完整人格向量

### Big Five `[0,1]`

```
openness
conscientiousness
extraversion
agreeableness
neuroticism
```

### Schwartz `[0,1]`

```
self_direction
stimulation
achievement
power
security
conformity
tradition
benevolence
universalism
hedonism
```

### Moral Foundations `[0,1]`

```
care
fairness
loyalty
authority
purity
liberty
```

### Risk `[0,1]`

```
financial
social
technology
health
```

### Cognitive Style `[-1,1]`

`+1` 偏向左侧，`-1` 偏向右侧：

```
analytical_intuitive
independent_social
long_short_term
evidence_experience
```

### Goals `[0,1]`

```
security
achievement
status
belonging
growth
meaning
survival
```

### Beliefs `[-1,1]` + confidence `[0,1]`

```
technology
economic_outlook
brand_trust
institutional_trust
social_attitude
```

人格生成不得将全部维度作为相互独立的均匀随机数。必须使用相关潜变量或已校准联合分布，并保存每组字段来源。合成字段必须明确标记为 synthetic，不得冒充真实个人测量。

## 4. 事件因果链

每个 tick 必须使用固定阶段顺序：

```
1. mobility_and_context
2. event_and_social_exposure
3. belief_update
4. emotion_appraisal
5. goal_activation
6. intention_and_action
7. memory_consolidation
8. relationship_update
```

必要不变量：

```
未触达 Agent 不得因事件注入而瞬间改变 Belief。
Personality / Values 不得由事件直接更新。
Action 必须在 Belief / Emotion / Goal 更新之后产生。
Memory 和 Relationship 必须在 Action 之后更新。
所有连续状态更新后必须 clip 到契约范围。
```

Belief 更新必须至少依赖：

```
prior belief
event signal
source credibility
channel match
information skepticism
cognitive style
value alignment
social neighbor state
belief confidence
```

Action Policy 必须至少依赖：

```
Identity
Personality
Values
Beliefs
Goals
Memory
Relationships
Current Mental State
Location Context
Allowed Action Space
```

行为集合至少包括：

```
ignore
consume
discuss
share
support
oppose
participate
exit
```

## 5. 三层记忆实现

### Working Memory

保存当前显著信息；每 tick 衰减。新触达、情绪唤醒和互动提高显著度。

### Episodic Memory

当：

```
importance = f(exposure, emotion_arousal, action, personal_relevance)
```

超过个体阈值时编码。记录 event、source、timestamp、importance、emotion、confidence、decay_rate。

### Semantic Memory

由重复的 Episodic Memory 巩固形成，不得在首次触达时直接生成稳定人格总结。巩固和衰减必须可重放。

## 6. Social Graph

关系类型至少覆盖：

```
family
friend
coworker
follower
authority
community
```

每条边必须保存：

```
source
target
relationship_type
strength
trust
similarity
influence
frequency
channel
```

传播权重不得只使用 adjacency；至少组合 strength、trust、similarity、influence 和 frequency。互动后的立场距离用于小幅更新 relationship trust。

## 7. Location 与 Mobility

Location 是带层级的实体：

```
location_id
name
type
parent_id
capacity
baseline_activity
semantic_tags
supported_channels
```

必须支持：

```
City
District
Campus
Residential
Workplace
School
Library
Canteen
Community
Retail
Transit
Online
```

每个 Agent 必须拥有：

```
home_location
primary_location
social_location
```

并执行：

```
Home -> Transit -> Work/School -> Transit -> Social -> Home
```

地点容量必须参与分配约束。事件的 source/target location 必须影响 onsite 和空间相关触达。

## 8. Event Injection 与传播

Event 必须保存：

```
event_id
title / description
start_tick / duration_ticks
source_location_id / target_location_ids
channels
audience_filters
intensity / credibility / novelty / valence
belief_signals / value_signals / goal_signals
evidence_refs
```

支持渠道：

```
social_media
news
interpersonal
community
search
onsite
```

触达必须分别记录：

```
cumulative reach
new reach per tick
estimated reached population
channel reach
event awareness per Agent
```

直接投放结束后允许存在衰减尾部和关系传播，不允许事件在 tick 0 默认全员知晓。

触达不得仅保存连续期望值。每个 Agent 的 event awareness 与 channel awareness 必须是离散 `0/1` 状态；hazard 仅用于逐 Agent、逐渠道采样首次触达。首次触达计入 new reach，已触达者只能作为低权重 reinforcement 再次学习，从未触达者的 belief 不得发生事件驱动更新。尚未知晓任何事件的 Agent 只能输出 `ignore`，不得凭空出现 discuss/share/support/oppose/participate。

多路径不确定性必须包含在整条路径上持续生效的 event regime 扰动，不能只使用会随 tick 平均消失的独立噪声。Emotion arousal、stress 和 belief confidence 必须回归各 Agent 的个人 baseline，而不是衰减到全局 0。

## 9. 大人口规模

允许使用加权 Synthetic Prototypes 表示大人口：

```
prototype_count >= 5000
represented_population >= prototype_count
```

例如 5,000 个原型可代表 13,500,000 人。必须同时输出原型数量、代表人口、每个原型权重和数据来源；不得把代表人口描述成系统实际持有的真实人物档案。

Key / Representative / Background 三层均必须参与每个 tick。层级只允许改变推理深度、决策噪声或计算路径，不允许跳过状态转移。

## 10. 输出契约

结果必须包含：

```
population_heatmap
emotion_distribution
belief_distribution
diffusion_curve
segment_difference
location_activity
agent_trace
final_action_distribution
state_transition_order
deterministic_signature
artifacts
limitations
```

必须支持：

```
run result
replay verification
agent search
agent detail
location detail
snapshot download
```

Agent Trace 必须是结构化模拟收据，只输出 state、action、reason_codes 和 evidence refs；同时区分当期 `received_event_ids` 与累计 `aware_event_ids`。不得输出隐藏思维链，不得伪装为真实用户原话。

## 11. 持久化与重放

每次运行必须生成：

```
population.parquet
relationships.parquet
locations.json
trajectory.csv
agent_traces.parquet
snapshots/*.npz
replay.jsonl
result.json
run_manifest.json
```

Replay record 必须保存：

```
path
tick
previous_hash
record_hash
state_hash
personality_signature
stage_order
stage_counts
event_touch_counts
snapshot reference
```

验证器必须检查记录数、哈希链、tick 连续性、人格签名不变、快照状态哈希和全部产物哈希。

## 12. LLM 边界

LLM 只允许用于：

```
自然语言事件 -> 类型化 Event
语义标签/信号的受约束编译
高不确定性 Agent 的可选语言表达
报告摘要
```

LLM 不得：

```
直接给出全人口最终概率
绕过结构化状态转移
修改稳定人格
生成不可验证的随机结果
输出或保存隐藏思维链
```

无 LLM API 时，数值运行时和确定性词汇回退必须仍可完整执行。

## 13. 验收条件

必须通过：

```
Ruff
strict mypy
unit tests
API integration tests
full pytest with branch coverage
JSON Schema export
deterministic replay verification
```

功能验收：

```
默认人格原型 >= 5000
完整人格维度全部存在且有界
六类关系全部存在
地点树无重复、无孤儿、无环
tick 0 事件触达为 0
事件开始后出现差异化触达
event/channel awareness 始终为离散 0/1
从未触达 Agent 的 belief 与基线完全一致且 event action 为 ignore
stress / arousal / belief confidence 回归个人 baseline
p10 / p50 / p90 反映持久路径不确定性
相同 seed 的相同路径逐数组一致
事件前后 personality_signature 不变
七类 UI 数据均能从 API 直接获得
人物与地点均可脱离地图前端独立钻取
```
