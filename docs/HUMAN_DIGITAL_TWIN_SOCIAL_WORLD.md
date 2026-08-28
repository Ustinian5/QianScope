# Human Digital Twin 与 Social World 后端实现

> 本文描述与“城市/校园社会模拟 demo”对齐的非 UI 后端。地图底图、三维建筑、镜头、动画和高德联动不在本实现范围内；前端需要的数据契约、事件推演、人格状态、地点钻取和重放能力均在范围内。

## 1. 可执行主链路

```text
WorldSpec + Event Injection
  -> 5,000+ 加权合成人格原型（默认代表贵阳 666.89 万人口）
  -> family / friend / coworker / follower / authority / community 多层关系图
  -> home / work / social / transit 的逐 tick 地点移动
  -> 多渠道直接触达 + 关系传播 + 地点接触
  -> Belief -> Emotion -> Goal -> Intention -> Action
  -> Working / Episodic / Semantic Memory
  -> 关系信任更新
  -> 人口、地点、群体和 Agent 级聚合
  -> 快照、哈希链、Parquet/JSON/CSV 产物与确定性重放
```

入口实现：

- 人格与动态状态契约：`src/echo_swm/contracts/person.py`
- 完整人格人口生成：`src/echo_swm/research/population.py`
- 地点、事件与结果契约：`src/echo_swm/world/contracts.py`
- 加权人口、移动与六类关系图：`src/echo_swm/world/population.py`
- 状态转移运行时：`src/echo_swm/world/runtime.py`
- 聚合、持久化和重放：`src/echo_swm/world/engine.py`
- HTTP API：`src/echo_swm/serving/api.py`

## 2. Human Digital Twin 人格架构

每个 Agent 是类型化状态，而不是一段 `You are ...` Persona Prompt：

\[
H_i(t)=(I_i,P_i,V_i,B_i(t),G_i(t),M_i(t),R_i(t),C_i(t))
\]

### 2.1 状态分区与不变量

| 分区 | 内容 | 事件能否直接修改 |
|---|---|---|
| Identity | 年龄、教育、角色、家庭、区域、人口分群 | 否 |
| Personality | Big Five、风险、认知风格 | 否 |
| Values | Schwartz、Moral Foundations | 否 |
| Beliefs | 技术、经济、品牌、机构、社会态度及置信度 | 是，仅在触达后 |
| Goals | 安全、成就、地位、归属、成长、意义、生存的激活度 | 是 |
| Memory | 工作、情节、语义记忆 | 是 |
| Relationships | 强度、信任、相似性、影响、频率 | 是，慢更新 |
| Current State | 注意、情绪、压力、信心、兴趣、意图、知晓 | 是 |

所有慢变量均进入 `profile_hash` 和 `personality_signature`。每个 replay record 保存同一人格签名；重放验证会拒绝事件过程中人格被改写的运行。

### 2.2 完整结构化人格向量

当前人口表具备以下显式数值列：

- Big Five：`openness / conscientiousness / extraversion / agreeableness / neuroticism`
- Schwartz：`self_direction / stimulation / achievement / power / security / conformity / tradition / benevolence / universalism / hedonism`
- Moral Foundations：`care / fairness / loyalty / authority / purity / liberty`
- Risk：`financial / social / technology / health`
- Cognitive Style：`analytical_intuitive / independent_social / long_short_term / evidence_experience`
- Goals：`security / achievement / status / belonging / growth / meaning / survival`
- Beliefs：`technology / economic_outlook / brand_trust / institutional_trust / social_attitude`

其中认知风格为双极轴：`+1` 偏向字段左侧，`-1` 偏向字段右侧；其他人格维度为 `[0, 1]`。各维度不是独立均匀随机数，而是由相关潜变量和有界噪声生成，例如开放性同时影响自我导向、刺激偏好、技术风险接受和成长目标。所有内置值均标记为 `synthetic_correlated_vector`，不会伪装成真实测量。

### 2.3 状态转移

事件不直接覆盖人格或行动。对已触达 Agent，运行时执行：

```text
Exposure(event, channel, relation, location)
  -> Bayesian-like bounded belief adjustment
  -> goal-congruence emotion appraisal
  -> goal activation / decay-to-baseline
  -> intention and action distribution
  -> memory encoding / consolidation / decay
  -> private stance / confidence update
```

简化形式为：

\[
B_i^{t+1}=clip(B_i^t+\alpha_i X_i^t(\hat B_E-B_i^t),-1,1)
\]

\[
C_i^{t+1}=Appraise(B_i^{t+1},G_i^t,P_i,E,X_i^t)
\]

\[
G_i^{t+1}=clip(G_i^t+\beta X_i^t g_E+\rho(G_i^0-G_i^t),0,1)
\]

其中 `X` 同时包含渠道匹配、地点相关度、受众匹配、来源可信度和路径扰动，不包含其他 Agent 的状态或关系传播。未触达 Agent 不会因为“全局注入事件”而瞬间改变信念。

### 2.4 行为策略

运行时输出八类互斥行为的概率采样：

```text
ignore / consume / discuss / share / support / oppose / participate / exit
```

核心决策共同使用身份、人格、价值、信念、目标、记忆和该 Agent 自己的当前状态，**不读取关系邻域、其他 Agent 的答案或聚合比例**。关键、代表、背景三层都会完成全部问题；层级只用于人口说明与代表选择，不给予答案特权。

单轮问卷为一次实际分类选择；事件推演为 1—8 轮（前端默认 3—6 轮）的连续选择。每轮只能更新该 Agent 的私有立场与置信度，全部个体作答结束后才能聚合。

### 2.5 三层记忆

- Working Memory：连续显著度；每 tick 衰减，新触达、情绪唤醒和互动提高显著度。
- Episodic Memory：重要性超过个人阈值时写入事件次数，阈值受开放性影响。
- Semantic Memory：每三次有效情节记忆触发一次巩固，形成长期强度并缓慢衰减。

为了让 5,000—250,000 个原型可在单机批量运行，主状态使用向量化数值表；被抽样用于钻取的 Agent 会输出逐 tick 的结构化记忆收据，不生成或泄露隐藏思维链。

## 3. Social World 底层架构

世界状态定义为：

\[
W_t=(H_t,G_t,L_t,E_t,Q_t)
\]

- `H_t`：Human Digital Twin 批量状态
- `G_t`：动态多层社会关系图
- `L_t`：地点层级、容量、语义和当前人口
- `E_t`：事件队列和各 Agent/渠道触达状态
- `Q_t`：仿真时钟、路径、随机流和快照元数据

### 3.1 地点是一等实体

内置无地图依赖的语义地点树覆盖：

```text
贵阳
├── 贵阳国际会议展览中心
├── 贵阳大数据科创城
├── 贵州大学西校区
├── 甲秀楼·南明河
├── 青岩古镇
├── 贵阳北站
├── 花果园社区
└── 线上公共空间
```

`LocationSpec` 保存类型、父节点、容量、基础活跃度、语义标签和可用渠道。自定义世界可以完全替换这棵树；后端不依赖 AMap、OpenStreetMap 或三维资产。

### 3.2 移动模型

每个 Agent 固定保存 `home_location / primary_location / social_location`。运行时根据本地小时和工作日执行：

```text
Home -> Transit -> Work/School -> Transit -> Social -> Home
```

校园容量用于限制被分配到校园的加权学生原型，因此校园钻取是全城人口的真实子集，而不是把所有学生都塞入一个建筑。

### 3.3 关系层与核心决策隔离

每条有向边保存：

```text
source / target / relationship_type
strength / trust / similarity / influence / frequency / channel
```

关系类型完整覆盖：

```text
family / friend / coworker / follower / authority / community
```

这些边保留给地图展示、人物档案、搜索和历史兼容产物。当前 `interaction_mode=independent` 是唯一有效的核心推演模式；关系边及关系信任不会进入问题生成、选项生成、个体选择或私有状态更新。修改或清空关系图不会改变 `decision_report`。

### 3.4 渠道与触达

支持 `social_media / news / interpersonal / community / search / onsite`。兼容地图状态会根据事件声明渠道、Agent 渠道偏好、来源位置、目标地点、受众条件、可信度和新颖度计算个体触达；不再计算 Agent 到 Agent 的社交 hazard。

hazard 只定义触达概率；运行时会按 Agent、渠道实际采样。事件知晓和渠道知晓均为离散 `0/1` 状态，`newly_reached_fraction` 只统计本 tick 首次触达者。已触达者可以被低权重重复强化；从未触达者不会收到信念证据。每条路径还会在事件开始前抽取一个持续生效的传播环境因子，使 p10/p50/p90 表达路径级不确定性，而不是被逐 tick 独立噪声平均掉。

每个事件独立保存：

- 累计触达率与估算触达人口
- 当期新增触达率
- 分渠道累计触达
- 触达 Agent 的 belief/goal appraisal 信号

事件停止直接投放后仍有衰减尾部，但不会沿社会关系传播。

### 3.5 固定 tick 顺序

每个 tick 严格执行：

1. `mobility_and_context`
2. `event_and_individual_exposure`
3. `belief_update`
4. `emotion_appraisal`
5. `goal_activation`
6. `intention_and_action`
7. `memory_consolidation`
8. `private_state_update`

阶段名和处理数量写入 replay。相同请求、人口、种子和版本得到相同 `deterministic_signature`。

## 4. Demo 能力与后端输出映射

| Demo 语义 | 后端输出/API |
|---|---|
| “事件触达 N 人” | `diffusion_curve[].reached_population` |
| 地图人口点/热区 | `population_heatmap` |
| 情绪颜色变化 | `emotion_distribution` 与 heatmap 的 `emotion_valence` |
| 传播随时间扩散 | `diffusion_curve` + `channel_reach` |
| 群体差异 | `segment_difference` |
| 地点/校园钻取 | `location_activity`、location API |
| 人物画像搜索 | agents search/detail API |
| 单人行为与原因 | `agent_trace`，含当期 `received_event_ids` 与累计 `aware_event_ids` |
| 问卷调查 | `/v1/jobs/world` + 1 个 `question_overrides`，每 Agent 实际选择一次 |
| 事件推演 | 自动生成问题和不定长选项 + 多轮独立决策 + 私有状态更新 |
| 可重现性 | replay API、NPZ 快照、manifest 和产物哈希 |

`WorldSimulationResult.decision_report` 是问卷和事件报告的唯一核心事实源，包含逐轮问题、选项、实际计数、加权占比、置信区间、改变判断比例和真实作答代表。其余七组字段用于地图与历史兼容：

```text
population_heatmap
emotion_distribution
belief_distribution
diffusion_curve
segment_difference
location_activity
agent_trace
```

## 5. API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/v1/social-world/preset` | 获取默认城市/校园世界和示例事件 |
| POST | `/v1/social-world/simulations` | 注入事件并执行多路径推演 |
| GET | `/v1/social-world/simulations/{run_id}` | 获取全部聚合结果 |
| GET | `/v1/social-world/simulations/{run_id}/replay` | 验证哈希链、人格不变量和产物 |
| GET | `/v1/social-world/simulations/{run_id}/agents` | 搜索加权人格原型 |
| GET | `/v1/social-world/simulations/{run_id}/agents/{agent_id}` | 获取完整人格、关系和轨迹 |
| GET | `/v1/social-world/simulations/{run_id}/locations/{location_id}` | 获取地点、人数和时间序列 |
| GET | `/v1/social-world/simulations/{run_id}/snapshots/{path}/{tick}` | 下载可校验状态快照 |

最小请求：

```json
{
  "project_id": "campus_brand_launch",
  "events": [{
    "event_id": "launch",
    "title": "某品牌发布新品",
    "description": "新品在校园首发并提供限时优惠。",
    "source_location_id": "guiyang_convention_center",
    "target_location_ids": ["guiyang_convention_center"],
    "channels": ["social_media", "interpersonal", "onsite"],
    "intensity": 0.8,
    "credibility": 0.75,
    "novelty": 0.8,
    "valence": 0.4
  }],
  "horizon_ticks": 72,
  "paths": 3,
  "seed": 2026
}
```

## 6. 运行产物与重放

每次运行保存：

- `population.parquet`：全部人格原型、代表权重和地点分配
- `relationships.parquet`：六类展示关系；不作为独立决策输入
- `agent_decisions.parquet`：每个 Agent、每一轮的实际选项、置信度、私有状态前后值与解释因子
- `locations.json`：地点树和渠道语义
- `trajectory.csv`：逐路径、逐 tick 宏观状态
- `agent_traces.parquet`：抽样 Agent 的可解释轨迹
- `snapshots/path_x/tick_x.npz`：兼容地图状态；关系信任保持只读
- `replay.jsonl`：前序哈希、状态哈希、阶段人数、人格签名
- `result.json`：UI 无关的完整结果契约
- `run_manifest.json`：版本、输入/配置/输出哈希和全部产物哈希

`verify_world_replay` 同时验证：记录数、路径数、逐路径哈希链、完整 tick 范围、人格签名不变、快照状态哈希和全部物理产物哈希；运行目录、快照引用和产物引用均执行路径边界检查。

## 7. 验收标准

实现必须同时满足：

1. 默认 5,000 原型精确分为 50 key、450 representative、4,500 background。
2. 默认代表人口为 6,668,900，但结果明确标记为加权合成原型。
3. 全部人格、价值、道德、风险、认知、目标和信念维度存在且有界。
4. 六类关系均存在，默认共 30,000 条边。
5. 每轮恰有 5,000 次实际选择，选项占比之和为 1，全部原始选择持久化。
6. 相同 seed 的同一路径逐数组一致。
7. replay 明确证明人格签名全程不变。
8. 修改关系图不会改变独立决策签名；七类地图兼容数据仍可通过结果 API 获取。
9. 人物和地点可以独立搜索/钻取，不依赖前端地图。
10. Ruff、strict mypy、单元测试、API 集成测试和全量 pytest 全部通过。

### 7.1 历史苏州基线记录

- 以下数值来自迁移前的苏州基线，仅用于回归参考，不是贵阳版的现实预测或当前验收结果。
- 该历史验收运行使用 13,500,000 人口口径；贵阳默认世界现为 6,668,900。
- tick 72 平均累计触达率为 `71.25%`，路径 p10—p90 为 `65.50%—75.86%`，平均估算触达人口为 9,619,200。
- 生成 876 条抽样 Agent 轨迹和 236 个地点热区时间单元。
- 219 条 replay 记录全部通过记录数、路径数、哈希链、tick 连续性、人格不变、快照状态和产物哈希校验。
- 当前全量 55 个测试通过，总覆盖率 87.82%；Ruff 及 strict mypy（90 个源文件）通过。

这些数值用于证明机制可执行、结果不退化和不确定性链路有效，不代表未经真实历史数据校准的现实预测精度。

## 8. 现实使用边界

本实现复刻的是 demo 的**后端交互与计算语义**，不是第三方私有算法，也不声称内置合成人口能准确预测现实。上线或对外宣称预测有效前，仍需：授权人口边际、历史事件/问卷结果、时间留出校准、子群体误差与漂移评估、外部盲测、访问控制和隐私治理。
