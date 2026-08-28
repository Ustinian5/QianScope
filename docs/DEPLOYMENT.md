# 黔镜 QianScope Zeabur 独立发布链路

状态：2026-08-29 已部署。Web、同源 API 网关和独立 API 健康检查均已通过。

项目只允许发布到 Zeabur。发布源必须是干净的本地 `main` 提交；配置 GitHub `origin` 后，
其地址固定为 `https://github.com/Ustinian5/QianScope.git`，尚未配置远端时允许直接发布
本地提交快照。贵州版使用独立 Zeabur 项目、环境、服务、域名和数据目录，不复用或修改
原苏州 SWM 的服务与数据。

## 隔离边界

- 产品名称：`黔镜 QianScope`
- Zeabur 项目：`swm-guizhou`（为避免迁移中断而保留的基础设施技术名）
- Project ID：`6a91407ccb6b9b31c9e67dda`
- Environment ID：`6a91407c3bf3ef23ef4d4b8a`
- 运行服务器：`server-6a8eee0bb11fb81fb4aaca05`（`Aliyun California 4C 8GB`），按项目负责人
  2026-08-28 的明确决定与原苏州项目共用；这是项目、服务和数据级隔离，不是物理资源隔离。
- 同机运行必须保留独立服务和数据目录；如需持久化只能新建贵州专用卷。同时监控 CPU、
  内存和磁盘，避免资源竞争影响两个项目。
- API 服务目标名：`swm-guizhou-api`
- API Service ID：`6a914f1bcb6b9b31c9e68450`
- Web 服务目标名：`swm-guizhou-web`
- Web Service ID：`6a915044cb6b9b31c9e684f5`
- Web 主域名：`https://qianscope.zeabur.app`
- API 主域名：`https://qianscope-api.zeabur.app`
- 兼容域名：`https://swm-guizhou.zeabur.app`、`https://swm-api-guizhou.zeabur.app`
- API 数据：当前写入贵州 API 容器自己的 `/app/artifacts`，未挂载或导入苏州卷；容器重建会
  丢失任务产物。需要保留线上任务时，在 Zeabur Dashboard 新建贵州专用卷并挂载该路径。

当前贵州环境和两个服务 ID 已作为发布脚本默认值；也可通过本地 shell 环境变量显式覆盖。
脚本没有任何可执行的旧项目目标，并会拒绝旧 SWM 的项目、环境或服务 ID。

```text
GitHub QianScope main
  → scripts/deploy_zeabur.sh
     ├─ swm-guizhou-api（Zeabur，仓库根目录，隔离数据目录）
     └─ swm-guizhou-web（Zeabur，frontend/）

浏览器
  → https://qianscope.zeabur.app
  → /api/qianscope/* 同源网关（兼容旧 /api/echo/*）
  → https://qianscope-api.zeabur.app
```

## 后端服务

- 构建上下文：仓库根目录
- 构建文件：根目录 `Dockerfile`
- 健康检查：`GET /health`
- API 文档：`GET /docs`
- 必需环境变量：`QIANSCOPE_ARTIFACT_DIR=/app/artifacts`
- 生产数据目录：`/app/artifacts`；当前使用隔离的容器文件系统，长期保留前需新建贵州专用卷

根镜像会复制 `src/`、`configs/` 和 `scenarios/`，城市锚点及默认场景必须随同一提交发布。
Zeabur 注入的 `PORT` 会被容器入口直接使用，不要手工固定生产端口。

可选的大模型变量必须使用贵州项目自己的凭证和额度：

```dotenv
QIANSCOPE_LLM_API_KEY=...
QIANSCOPE_LLM_BASE_URL=https://api.openai.com/v1
QIANSCOPE_LLM_MODEL=...
QIANSCOPE_LLM_TIMEOUT_SECONDS=45
QIANSCOPE_LLM_MAX_CALLS=100
```

## 前端服务

- 构建上下文：`frontend/`
- 构建文件：`frontend/Dockerfile`
- 框架：Next.js standalone
- 公网地址：`https://qianscope.zeabur.app`

必需环境变量：

```dotenv
SITE_URL=https://qianscope.zeabur.app
NEXT_PUBLIC_SITE_URL=https://qianscope.zeabur.app
QIANSCOPE_API_URL=https://qianscope-api.zeabur.app
```

接入高德正式底图时再配置贵州站独立凭证：

```dotenv
NEXT_PUBLIC_AMAP_KEY=...
NEXT_PUBLIC_AMAP_SECURITY_JS_CODE=...
NEXT_PUBLIC_AMAP_STYLE=amap://styles/whitesmoke
```

`QIANSCOPE_API_URL` 只能指向贵州新 API；不得复制苏州后端地址。高德 Web Key 与安全密钥应为
贵州域名创建独立应用并配置域名白名单。`NEXT_PUBLIC_*` 会在构建期进入前端产物，修改后
必须重新部署 Web 服务。未配置高德凭证时会明确进入演示底图，不复用苏州站凭证或额度。

## 发布脚本保护与参数

`scripts/deploy_zeabur.sh` 在上传源码前会依次检查：

1. 当前分支必须是已提交且工作区干净的 `main`。
2. 若已配置 `origin`，其地址必须精确等于 `https://github.com/Ustinian5/QianScope.git`；
   未配置远端时直接发布当前本地提交，不读取或修改其他仓库。
3. 项目、环境和目标服务 ID 必须是有效的 Zeabur Object ID，且不属于旧 SWM。
4. 通过 Zeabur API 读取的项目 ID 和名称必须分别为
   `6a91407ccb6b9b31c9e67dda`、`swm-guizhou`。
5. API 与 Web 必须使用不同服务 ID，且两个服务都必须属于已验证的贵州项目。
6. 本机启用 HTTP 代理时，仅将 Zeabur 的 S3 源码上传链路设为直连；命令执行后必须生成
   新的部署记录，否则脚本直接报错，不会误报发布成功。

默认资源无需额外设置。只有在贵州项目内重建了资源时，才在当前 shell 中覆盖：

```bash
export QIANSCOPE_ENVIRONMENT_ID=<黔镜项目环境ID>
export QIANSCOPE_API_SERVICE_ID=<黔镜API服务ID>
export QIANSCOPE_WEB_SERVICE_ID=<黔镜Web服务ID>
```

若项目属于 Zeabur 团队工作区，再明确设置工作区名称或 ID：

```bash
export ZEABUR_WORKSPACE=<工作区名称或ID>
```

这些资源 ID 不是应用密钥，但仍不得写回旧项目脚本或与苏州服务混用。应用密钥只能保存在
Zeabur 服务环境变量中，不得提交到 Git、文档、Issue 或聊天。

## 唯一发布流程

1. 在本地完成后端与前端质量检查。
2. 将同一份源码提交到本地 `main`；已配置 GitHub 时可一并推送，未配置时无需远端。
3. 在仓库根目录执行 `./scripts/deploy_zeabur.sh all`。
4. 等待两个新服务均变为运行状态后完成公网和隔离验收。

仅修改单侧代码时可执行：

```bash
./scripts/deploy_zeabur.sh api
./scripts/deploy_zeabur.sh web
```

两种方式仍会执行相同的仓库、项目名称和旧 ID 拒绝检查。环境或对应服务 ID 未设置时，
脚本会在任何部署操作前终止。

## 发布前检查

```bash
conda run -p ./.conda-env ruff check .
conda run -p ./.conda-env ruff format --check .
conda run -p ./.conda-env mypy src
conda run -p ./.conda-env pytest

cd frontend
npm ci
npm run check
```

## 公网与隔离验收

1. `https://qianscope.zeabur.app/` 返回 `200`。
2. `https://qianscope-api.zeabur.app/health` 返回 `200`。
3. `https://qianscope.zeabur.app/api/qianscope/health` 返回 `200`。
4. 贵阳地图、可点击地点、5,000 人格活动层、人物档案和地点 2.5D 交互画页正常加载。
5. 在贵州站提交一次 world job，最终状态为 `complete`，结果只写入贵州专用卷。
6. 使用该贵州任务 ID 查询旧苏州 API 时必须返回 `404`，证明任务存储未串线。
7. 原苏州站域名、服务、变量和持久卷保持不变；不得向旧站发送发布或写入请求。

任何新增发布平台或跨项目资源共享都必须先修改本文件并获得项目负责人明确批准。
