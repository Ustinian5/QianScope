# 黔镜 QianScope：可交互社会世界与通用事件预测

> 在贵阳社会世界中搜索人物、进入场所、访谈稳定人格，或让 5,000 个合成人格原型独立回答单轮问卷、完成多轮事件决策并形成可复现的条件预测。

本仓库是基于公开产品形态与公开研究路线进行的 clean-room 自主实现，不包含、也不声称掌握任何第三方公司的私有代码、模型权重或内部数据。

项目正式名称为 **黔镜（QianScope）**。Python 发行包与命令统一为 `qianscope`；内部实现
命名空间 `echo_swm`、旧命令 `echo-swm`、`ECHO_*` 环境变量和 `/api/echo/*` 网关仅作为
向后兼容别名保留。新代码与文档统一使用 `qianscope`、`QIANSCOPE_*` 和
`/api/qianscope/*`。

## 在线访问（Zeabur）

访问 QianScope 主站：[https://qianscope.zeabur.app](https://qianscope.zeabur.app)

## 技术栈与技术选型

QianScope 采用前后端分离的单仓库架构：Next.js 提供产品界面与同源 API 网关，FastAPI
提供独立计算 API，数值模拟与模型产物以可校验文件保存。大模型是可选的语义增强层，
不负责直接生成最终概率。

| 层次 | 技术与版本 | 技术选型及用途 |
| --- | --- | --- |
| 前端运行时 | Node.js `>=22.13.0`、Next.js `16.3.2`、React `19.2.8` | 使用 App Router 组织页面、服务端路由和同源 `/api/qianscope/*` 网关；生产环境输出 Next.js standalone 镜像。 |
| 前端语言与样式 | TypeScript `5.9.3`、Tailwind CSS `4.2.1`、PostCSS | TypeScript 负责组件与接口类型约束；Tailwind CSS 与项目自定义 CSS 变量共同实现响应式界面和统一视觉系统。 |
| 地理空间 | 高德 JS API `2.0`、`@amap/amap-jsapi-loader 1.0.1`、MapLibre GL `5.24.0` | 正式环境使用高德 3D 城市底图；未配置高德凭证时使用 MapLibre 演示底图，保证本地开发可运行。 |
| 场景交互 | OpenFlipbook（MIT，上游提交 `b3e5044`） | 以“图像即界面”的热点、人物覆盖层和首尾帧视频完成地点与室内场景下钻；运行源码固定在 `frontend/vendor/openflipbook/`。 |
| 后端 API | Python `>=3.11`、FastAPI `>=0.116,<1`、Uvicorn `>=0.35,<1` | 提供 REST API、OpenAPI 文档、后台任务、健康检查和版本化结果接口。 |
| 数据契约 | Pydantic `>=2.11,<3` | 对人口、问卷、事件、预测、社会世界和校准数据执行强类型校验，并生成稳定的 JSON Schema。 |
| 数值与机器学习 | NumPy `>=2.1,<2.3`、scikit-learn `>=1.6,<2`、Joblib `>=1.5,<2` | 执行人格向量计算、概率模型、校准、指标评估和模型持久化；核心数值运行不依赖大模型。 |
| 数据与产物 | PyArrow `>=19,<24`、Parquet、JSON/JSONL、SHA-256 | 保存逐 Agent 决策、人口与关系表、运行清单和回放链；本地运行不强制依赖外部数据库。 |
| CLI 与外部调用 | Typer `>=0.16,<1`、HTTPX `>=0.28,<1`、python-dotenv `>=1.1,<2` | `qianscope` CLI 统一管理演示、训练、预测和服务启动；HTTPX 在服务端接入 DeepSeek V4 Flash 的 OpenAI-compatible Chat Completions API。 |
| 构建与部署 | Hatchling、npm lockfile、Docker、Docker Compose、Zeabur | 后端使用 `python:3.11-slim`，前端使用 `node:22-alpine` 多阶段镜像；Zeabur 分别运行 Web 与 API 服务。 |
| 质量与 CI | GitHub Actions、Ruff、Mypy strict、Pytest、Hypothesis、pytest-cov、ESLint、TypeScript | 每次推送和拉取请求检查格式、静态类型、后端测试、覆盖率以及前端生产构建。 |

```text
浏览器
  └─ Next.js 16 / React 19
       ├─ 高德 JS API 2.0（生产）/ MapLibre GL（本地回退）
       ├─ OpenFlipbook 场景交互
       └─ /api/qianscope/* 同源网关
            └─ FastAPI / Uvicorn
                 ├─ Pydantic 数据契约
                 ├─ NumPy / scikit-learn 数值运行时
                 └─ PyArrow / Parquet / JSON 可复现产物
```

## 现在已经能做什么

- 生成并持久化 **5,000—20,000 个稳定人格 Agent**；同一个人口 ID 与种子会得到相同的身份和稳定属性。
- 默认 5,000 人按 **50 个关键 Agent、450 个代表 Agent、4,500 个背景 Agent** 分层。
- 每个 Agent 都有稳定 ID、来源、人口属性、社会角色，以及完整的 Big Five、Schwartz、Moral Foundations、四类风险、四条认知风格、七类目标、五类信念、动态心理状态和三层记忆。
- 每人至少连接家庭、熟人、同事、社区和线上五类关系；默认 5,000 人形成 25,000 条带强度与信任的关系。
- 所有层级都实际执行相同的 `observe → decide → act → remember` 循环；不会只抽取少数 Agent 后把其余人当作展示数字。
- 支持单选、多选、量表、排序、数值和开放题；保存每个 Agent 的选项概率，并输出总体、分组和不确定范围。
- 同时计算事件前基线问卷与事件后问卷，比较支持、反对、知晓、信任、传播、讨论、沉默、参与和退出变化。
- 任意事件均会比较“未发生”“按描述发生”和可选替代情景，正式运行不少于 30 步，并用多条路径给出常见范围。
- 采用受约束 L2 协议：运行前锁定核心/辅助指标、期望方向、最小有效变化和预测时点；A/B/C 方案共享随机路径，输出配对差值、COD 反事实敏感性与方案排序。
- Agent 只有在被所选渠道直接触达、或从关系邻居收到传播后才会更新事件相关状态；预测时点之后才可获得的证据会被自动隔离并记入审计日志。
- 可导入有权使用的聚合人口边际，通过 IPF/raking 约束 Agent 代表权重，并报告收敛误差、有效样本量、设计效应和极端权重警告。
- 可导入历史问卷预测/实测占比与已揭晓事件结果，按预测时间做后段留出；只有 Brier 与 Log Loss 都未变差的版本才会用于新预测。
- 支持真实问卷/事件结果回填并自动沉淀校准记录，以及 CSV/JSON 导出、逐路径回放与 SHA-256 产物校验。
- 无大模型 API 也能运行；提供兼容 API 后会自动增强任意事件描述的语义结构化，大模型不直接编造最终概率。
- 新增统一 Social World 后端：地点与事件是一等实体，支持 666.89 万代表人口、城市/校园移动、人物/地点钻取和确定性重放；关系仅用于世界展示与人物档案，不进入核心决策。
- 全屏社会世界前端以高德 JS API 2.0 提供贵阳 3D 城市底图；点击一级地点后，直接使用 OpenFlipbook MIT 源码的图像即界面、首尾帧下钻视频、光标、热点与人物覆盖层进入 28 个独立二级场景，并承载 5,000 人格活动层、人物检索、关系跳转和受认知边界约束的访谈。
- 问卷统一为 1 轮独立决策，事件统一为 3—6 轮独立决策；问题与不定长选项按事件自动生成，每个 Agent 只读取事件、稳定人格和自己的上一轮状态。
- 问卷、事件、营销、趋势、品牌、产品、需求、定价、竞品、漏斗、流失和传播节点共 12 个工具均接入后端运行；统一支持任务 ID、真实决策进度、滚动 Agent 回答、主动终止、任务中心和结果恢复。
- 报告使用与社会世界一致的视觉系统，支持情景切换、运行口径与质量门、交叉表、合成代表回答、CSV/JSON、打印/PDF 和可恢复分享路由。

贵阳社会世界已成为本仓库的默认产品叙事；原苏州城市适配器和旧价格实验仅作为兼容性底层示例保留，不参与贵阳默认首页与部署。

OpenFlipbook 的运行源码镜像位于 `frontend/vendor/openflipbook/`，固定到上游提交 `b3e5044`；贵阳内容映射位于 `frontend/lib/openflipbook-guiyang.ts`，7 张地点总览与 28 张互不重复的具体场景画页位于 `frontend/public/openflipbook/guiyang/`，对应的 28 段“全景锁定热点 → 连续推近 → 穿入独立室内”LTX-Video 过渡位于其 `transitions/` 子目录。视频生成参数、固定种子和验收方法见 `docs/OPENFLIPBOOK_SCENE_TRANSITIONS.md`。仓库根目录的 `openflipbook/` 仅作为上游参考副本并被忽略，运行与部署不依赖它。许可证全文见 `frontend/THIRD_PARTY_NOTICES.md`。

## 两种产品入口

默认首页是可探索的社会世界：

```text
贵阳全景 → 场所 → 建筑/楼层 → 人物档案/关系/访谈
        ↘ 12 个问卷、事件与洞察工具 → 后台任务 → 停靠结果
```

`/predict` 仍保留适合严肃研究项目的五步流程：

```text
1. 描述预测目标
2. 选择目标人群
3. 创建或导入问卷
4. 确认时间与比较情景
5. 运行并查看结果
```

结果固定按下面的顺序展示：

```text
一句话结论
  → 受约束 L2 方案排序、配对差值与 COD
  → 问卷前后预测
  → 群体差异
  → 未来反应与情景比较
  → 关键影响因素
  → 不确定性与限制
  → CSV / JSON 导出与真实结果回填
```

模型版本、哈希、回放记录和分层明细放在“高级信息”中，不占据普通用户的主阅读路径。

## 本地直接体验

要求 Conda、Python 3.11+ 和 Node.js 22.13+。

### 1. 安装并验证 Python 环境

```bash
conda create -p ./.conda-env python=3.11 -y
conda run -p ./.conda-env pip install -e '.[dev]'
conda run -p ./.conda-env python --version
```

运行默认 5,000 人、10 题、30 步通用演示：

```bash
conda run -p ./.conda-env qianscope predict demo --paths 8
```

快速验证可使用 3 条路径：

```bash
conda run -p ./.conda-env qianscope predict demo --paths 3
```

### 2. 启动后端

```bash
conda run -p ./.conda-env qianscope serve --host 127.0.0.1 --port 8000
```

API 文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

无需前端即可运行与目标 demo 对齐的社会世界后端：

```bash
conda run -p ./.conda-env qianscope world demo --horizon-ticks 72 --paths 3
```

也可以直接运行 JSON 场景，或通过 HTTP 取得默认世界：

```bash
conda run -p ./.conda-env qianscope world run scenarios/guiyang_guikesong_peak_flow.json
curl http://127.0.0.1:8000/v1/social-world/preset
```

HTTP 事件注入入口为 `POST /v1/social-world/simulations`。

结果直接包含逐轮生成的问题、不定长选项、5,000 个 Agent 的实际选择、改变判断比例、置信区间、动态代表 Agent，以及兼容地图所需的人口热区、地点活动和回放轨迹。每次运行另存 `agent_decisions.parquet`；任何 Agent 的答案或比例都不会成为另一个 Agent 的输入。完整设计、请求示例与验收边界见 [`docs/HUMAN_DIGITAL_TWIN_SOCIAL_WORLD.md`](docs/HUMAN_DIGITAL_TWIN_SOCIAL_WORLD.md)。
贵阳场景 ID、地图锚点和前后端约束见 [`docs/GUIYANG_SOCIAL_WORLD.md`](docs/GUIYANG_SOCIAL_WORLD.md)。原苏州适配器的历史说明保留在 [`docs/SUZHOU_SOCIAL_WORLD.md`](docs/SUZHOU_SOCIAL_WORLD.md)。

### 3. 启动前端

另开一个终端：

```bash
cd frontend
npm ci
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000) 即可进入贵阳社会世界。正式地图需要在 `frontend/.env.local` 配置同一高德 Web 端应用的 `NEXT_PUBLIC_AMAP_KEY` 与 `NEXT_PUBLIC_AMAP_SECURITY_JS_CODE`；未配置时页面会明确进入本地演示底图，不会伪装成高德生产接入。

进入 `/predict` 可使用覆盖六种题型的通用 10 题模板，也可以逐题修改或导入 JSON。

## 提供大模型 API 后直接使用

复制 `.env.example` 为 `.env`，在**后端**配置 DeepSeek V4 Flash：

```dotenv
QIANSCOPE_LLM_API_KEY=your-key
QIANSCOPE_LLM_BASE_URL=https://api.deepseek.com
QIANSCOPE_LLM_MODEL=deepseek-v4-flash
QIANSCOPE_LLM_TIMEOUT_SECONDS=90
QIANSCOPE_LLM_MAX_CALLS=100
QIANSCOPE_LLM_REQUIRED=true
```

然后重启后端。用户在页面中仍只需描述事件；系统会自动选择：

```text
事件预测：编译自然语言或刷新模板中的不确定先验
城市模拟：编译情景或刷新事件与干预假设
社会世界/剧本：生成本次专属的语义信号与多轮独立决策脚本
问卷预测：解释事件，并基于数值结果生成结论与合成人格代表回答
人物与洞察：实时生成人物访谈、解释、限制说明和代表性叙述

所有概率、传播路径、反事实和区间仍由同一个数值运行时计算，不让大模型自由编造数字。
```

API 密钥只从环境变量读取，不会进入浏览器、人格、结果、回放或运行清单。线上生成调用关闭内容缓存，使用非零温度和每次唯一的变化 ID；结果只保存安全调用回执（模型、供应商调用 ID、token 用量与变化 ID）。启用 `QIANSCOPE_LLM_REQUIRED=true` 后，缺少模型配置会阻止服务启动，模型调用失败也会明确失败，不会静默伪装成本地生成成功。完整审计见 [`docs/AI_INTEGRATION_AUDIT.md`](docs/AI_INTEGRATION_AUDIT.md)。

贵州版前后端的独立部署、环境变量、数据卷与发布验收步骤见 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。
邮件登录、数据库和对象存储等通用生产依赖可参考历史清单 [`docs/PRODUCTION_SERVICE_REQUIREMENTS.md`](docs/PRODUCTION_SERVICE_REQUIREMENTS.md)，其中苏州地图配置不适用于贵州新项目。

## 底层模型如何工作

```text
事件描述 + 问卷 + 人群范围
              │
              ▼
 DeepSeek 语义/剧本/叙事编排（服务端实时调用）
              │
              ▼
稳定人格池 + 授权人口边际（可选 IPF）+ 多层关系与地点网络
              │
              ▼
每一时间步：观察 → 判断 → 行动 → 记忆 → 关系信任更新
              │
              ▼
 基线 / 事件 / 替代情景 × K 条可复现路径
              │
              ▼
共享随机数配对反事实 → 方案排序 / COD / P10-P50-P90
              │
              ▼
逐 Agent 问卷/事件概率 → 人口加权 → 历史时间校准（可选）
              │
              ▼
  结论、时间线、后续反应、驱动因素、限制、回放与导出
```

### 1. 稳定人格池

人格生成器位于 `src/echo_swm/research/population.py`。人口表使用 Parquet 持久化，并为每个人格保存 `profile_hash`。人格是相关结构化向量而不是 Persona Prompt；事件只能更新信念、情绪、目标激活、意图、记忆和关系信任，不能直接修改人格与价值。字段来源逐类标记为 `observed`、`inferred` 或 `synthetic`；当前内置人口全部明确标记为 `synthetic`，不冒充真实个人。

人格详情按 `echo-persona-definition-v3` 公开 9 组 54 个维度，包括大五人格、施瓦茨价值观、道德基础、风险、认知风格、目标、信念、信息行动倾向与渠道偏好；每个维度都携带定义、量尺、两端含义、来源和版本。完整口径见 [docs/PERSONA_DEFINITION.md](docs/PERSONA_DEFINITION.md)。

扩展到 20,000 人时仍只创建批量数组，不为每个 Agent 启动独立进程，因此本地电脑也能运行。关键/代表/背景分层影响推理深度、决策噪声和传播放大，但三层均进入每一个时间步。

### 2. 关系传播与事件状态

运行时位于 `src/echo_swm/research/runtime.py`。事件通过媒体偏好逐 Agent 采样首次暴露，随后只沿家庭、熟人、同事、社区和线上关系传播。未直接或间接触达的 Agent 不接收事件证据。关系强度、信任、同质性、关键 Agent 放大和阻断共同决定传播；互动后的立场一致性还会更新关系信任。

每一步都预测 `support / oppose / share / discuss / silence / participate / exit` 七类行动，并更新知晓、信念、态度、情绪、信任、风险、工作记忆和事件记忆。回放日志逐步证明全部 5,000 人完成四阶段。

### 3. 问卷预测

问卷映射位于 `src/echo_swm/research/survey.py`。每道结构化题先得到逐 Agent 选项概率，再按人口权重聚合；事件前状态生成基线答案，事件后每条路径生成后测答案。分组结果默认覆盖年龄、性别、社会角色、单位类型、教育背景和主要信息渠道，并输出完整回答分布、原型数与加权规模。

开放题不伪造“真实原话”：关键与代表 Agent 根据结构化状态形成模拟主题和明确标记的代表回答，再输出主题占比。

每份正式结果还包含模型/数据版本、种子、路径数、成功/失败 Agent 数、有效样本量、区间定义和自动质量门；概率守恒、行动人数、交叉表覆盖、未来信息隔离等检查不会只停留在前端文案。

### 4. 不确定性、复现与校准

- 相同人口 ID、输入、种子与配置产生相同 `deterministic_signature`。
- 每个情景运行 K 条路径，界面显示中位结果和 p10—p90 常见范围。
- 相同路径编号在全部情景中共享外生随机数；结果额外输出相对无事件基线的配对差值、方向一致率、COD 与综合排序。
- `replay.jsonl` 为每个情景、路径、时间步保存状态哈希、前序哈希、阶段人数、实际触达/未触达人数和分层人数。
- `run_manifest.json` 保存请求、人口签名、版本与所有输出文件哈希。
- 授权人口边际通过 raking 改写调查权重；问卷总量、分组、事件时间线、行动占比和驱动因素使用同一套权重。
- 历史校准使用严格的 `forecast_as_of` / `outcome_available_at` 时间边界，避免把预测时尚未知的结果泄漏到训练集。
- 校准按“同题选项 → 同测量构念 → 问卷类型全局”和“同事件结果 → 事件类型全局”逐级回退；未通过时间留出门槛的候选版本会保存但不会应用。
- `POST /v1/predictions/{run_id}/outcomes` 接收真实结果、立即计算误差；若回填方案指标，还会报告方向正确率、Top-1、Spearman、Kendall、区间覆盖率、宽度与 WIS。

## 接入授权人口与历史结果

五步页面中的两项数据导入都是可选项，不会增加必填步骤：第 2 步可导入人口边际，第 3 步可导入历史校准记录。系统只接受已确认授权、且已经去标识化或为聚合统计的数据；内置示例仅说明格式，不代表真实人口或真实准确率。

人口边际最小格式：

```json
{
  "dataset_id": "population_margins_2026q2",
  "name": "目标人群授权聚合边际",
  "source": "your_authorized_source",
  "observed_at": "2026-06-30T00:00:00+08:00",
  "available_at": "2026-07-15T00:00:00+08:00",
  "authorization_confirmed": true,
  "deidentified_or_aggregate": true,
  "scale": "proportion",
  "target_population": 100000,
  "margins": {
    "age_group": {"18-24": 0.12, "25-34": 0.24, "35-44": 0.23, "45-59": 0.25, "60+": 0.16}
  }
}
```

支持的人口边际字段为 `age_group`、`education_level`、`gender`、`primary_channel`、`region_type` 和 `social_role`。比例边际每个字段必须合计为 1；计数边际必须合计为 `target_population`。目标类别在合成人格池中没有支持时会拒绝运行，而不是静默外推。

历史校准数据最少包含 10 条记录。问卷记录使用 `target_type=question_option` 以及题目、选项和测量构念；事件记录使用 `target_type=event_outcome` 以及固定结果 ID：

```json
{
  "dataset_id": "history_2024_2026",
  "name": "授权历史问卷与事件结果",
  "source": "your_authorized_archive",
  "authorization_confirmed": true,
  "deidentified_or_aggregate": true,
  "observations": [{
    "observation_id": "obs_001",
    "target_type": "question_option",
    "question_id": "q_support",
    "option_id": "support",
    "construct": "support",
    "forecast_as_of": "2025-01-01T00:00:00+08:00",
    "outcome_available_at": "2025-01-20T00:00:00+08:00",
    "predicted_probability": 0.42,
    "observed_share": 0.47,
    "sample_size": 800,
    "horizon_ticks": 30,
    "source": "survey_wave_01"
  }]
}
```

完整契约可从 `/v1/examples/population-margin`、`/v1/examples/calibration-dataset` 或 `data_contracts/research-*.schema.json` 获取。`dataset_id` 是不可变版本键：同 ID、同内容可安全重试，同 ID、不同内容返回冲突，更新数据时必须使用新 ID。API 工作流是：登记人口边际 → 登记历史数据 → 拟合校准版本 → 在 `POST /v1/predictions` 中传入 `population_margin_id` 和 `calibration_id`。

更完整的机制说明见 [`docs/RESEARCH_PREDICTION.md`](docs/RESEARCH_PREDICTION.md)，产品验收标准见 [`docs/PRODUCT_REQUIREMENTS.md`](docs/PRODUCT_REQUIREMENTS.md)。

## 主产品 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/v1/populations/generate` | 生成并验证 5,000—20,000 人稳定人格池 |
| `GET` | `/v1/populations/{population_id}` | 获取人口清单与验证结果 |
| `POST` | `/v1/questionnaires` | 保存六类题型的问卷 |
| `GET` | `/v1/questionnaires/{questionnaire_id}` | 获取已保存问卷 |
| `POST` | `/v1/population-margins` | 登记授权聚合人口边际 |
| `GET` | `/v1/population-margins/{dataset_id}` | 读取人口边际及来源 |
| `POST` | `/v1/calibration-datasets` | 登记历史问卷预测和真实事件结果 |
| `POST` | `/v1/calibrations` | 执行时间留出拟合并生成不可变校准版本 |
| `GET` | `/v1/calibrations/{calibration_id}` | 查看校准参数、留出指标与是否可应用 |
| `POST` | `/v1/predictions` | 用人口、问卷、事件与时间范围运行完整预测 |
| `GET` | `/v1/predictions` | 列出最近项目 |
| `GET` | `/v1/predictions/{run_id}` | 获取按产品顺序组织的结果 |
| `GET` | `/v1/predictions/{run_id}/replay` | 验证逐步参与和文件哈希 |
| `GET` | `/v1/predictions/{run_id}/export?format=csv` | 导出问卷结果；也支持 `json` |
| `POST` | `/v1/predictions/{run_id}/outcomes` | 回填真实问卷与事件结果 |
| `GET` | `/v1/personas` | 检索 5,000 个稳定人格原型 |
| `GET` | `/v1/personas/{persona_id}` | 读取人格、状态、记忆、日程与关系 |
| `POST` | `/v1/personas/{persona_id}/interview` | 受认知边界约束的人物访谈 |
| `POST` | `/v1/insights` | 运行 9 类通用洞察工具 |
| `GET` | `/v1/insights/{run_id}` | 恢复洞察结果 |
| `POST` | `/v1/jobs/{insight\|prediction\|world}` | 创建统一后台任务 |
| `GET` | `/v1/jobs/{job_id}` | 读取轮次、实际决策数、处理人数和最新 Agent 回答 |
| `GET` | `/v1/jobs/{job_id}/result` | 恢复已完成任务结果 |
| `POST` | `/v1/jobs/{job_id}/cancel` | 请求在安全计算边界终止任务 |

机器可读 Schema 位于 `data_contracts/research-*.schema.json`。

## 运行产物

```text
artifacts/research/
  populations/{population_id}/
    agents.parquet
    relationships.parquet
    manifest.json
  questionnaires/{questionnaire_id}.json
  grounding/population_margins/{dataset_id}.json
  calibration/
    datasets/{dataset_id}.json
    profiles/{calibration_id}.json
    backfill_observations.jsonl    # 回填真实结果后出现
  predictions/runs/{run_id}/
    request.json
    result.json
    questionnaire_forecast.csv
    individual_predictions.parquet
    timeline.csv
    replay.jsonl
    run_manifest.json
    outcomes.jsonl                 # 回填真实结果后出现
```

## 项目结构

```text
src/echo_swm/research/             人格、人口约束、语义、传播、问卷、校准、结果与回放
src/echo_swm/personas/             稳定人格目录、搜索、详情、关系与访谈
src/echo_swm/insights/             九类通用洞察聚合引擎
src/echo_swm/jobs/                 后台任务、进度、终止、持久化和恢复
src/echo_swm/serving/              FastAPI 与版本化接口
frontend/components/social-world*  默认社会世界体验、高德贵阳地图与开发降级适配层
frontend/app/predict/              五步式严肃研究流程
frontend/components/               问卷编辑器、结果视图与共享组件
data_contracts/research-*.json     主产品机器契约
tests/unit/test_research_*         人格、运行时、问卷和复现测试
tests/integration/test_research_*  完整 API 流程测试
src/echo_swm/event_forecasting/    旧候选事件危险率引擎（高级底层能力）
src/echo_swm/city/                 苏州 World Adapter 示例（非主产品）
```

## 完整质量检查

```bash
conda run -p ./.conda-env ruff check .
conda run -p ./.conda-env ruff format --check .
conda run -p ./.conda-env mypy src
conda run -p ./.conda-env pytest

cd frontend
npm run check
```

## 当前边界

- 仓库不附带真实人口或历史结果；内置人口和两份格式示例均为合成数据。5,000 个 Agent 不等于 5,000 名真实受访者。
- 已实现授权人口边际和历史结果的接入、诊断与版本化校准，但只有用户实际提供合规数据且留出验证通过后，对应运行才会标记为“已加权”或“已校准”。
- 人口边际只约束已提供的聚合维度，无法自动修复抽样框缺失、未响应偏差、关系网络偏差或分布漂移；真实使用仍需要数据卡、外部盲测与持续监控。
- 事件文本语义若不明确且未配置大模型，结果会标记为低置信/分布外，界面提示谨慎解释。
- 系统输出的是条件概率和情景差异，不是因果结论，也不是对未来的保证。
- 禁止用于重新识别、针对具体个人的高风险决策、歧视、隐性操纵或绕过人工与合规审查。

本结果为概率模拟与条件预测，不构成对现实结果的保证。

## 参与贡献与许可证

提交代码前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 与 [`SECURITY.md`](SECURITY.md)。项目采用 [Apache License 2.0](LICENSE)。clean-room 对照边界与逐项验收见 [`docs/REN_LAB_REPLICATION_SPEC.md`](docs/REN_LAB_REPLICATION_SPEC.md)。
