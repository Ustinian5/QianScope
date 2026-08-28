# 历史发布环境与第三方服务清单（苏州）

状态：2026-08-25 苏州版归档基线，不是当前贵州发布配置。贵州新项目必须以 [`DEPLOYMENT.md`](DEPLOYMENT.md) 和 [`GUIYANG_SOCIAL_WORLD.md`](GUIYANG_SOCIAL_WORLD.md) 为准，不得复用本清单中的苏州服务、凭证或数据卷。凭证只能写入本地或部署平台的环境变量，不得提交到 Git，也不应粘贴到 Issue 或聊天中。

## 已满足的必需项

| 服务 | 用途 | 当前状态 | 环境变量 |
| --- | --- | --- | --- |
| 高德 Web JS API 2.0 | 苏州 3D 底图、交互、实时天气 | 已配置并接入 | `NEXT_PUBLIC_AMAP_KEY`、`NEXT_PUBLIC_AMAP_SECURITY_JS_CODE`、`NEXT_PUBLIC_AMAP_STYLE` |
| 前后端公网域名与 HTTPS | 浏览器访问、Cookie 与邮件回调 | 生产部署时必须提供 | `SITE_URL`、`QIANSCOPE_API_URL` |

实时天气使用同一个高德 Web 端应用，当前不需要新 Key。

## 达到目标产品完整发布形态前必须补全

| 优先级 | 服务 | 建议方案 | 需要提供的信息 |
| --- | --- | --- | --- |
| P0 | 邮箱一次性登录 | Postmark 或 Resend，由项目自己发送 Magic Link | 发件域名、API Key、From 地址 |
| P0 | 用户/会话/项目持久化 | PostgreSQL | `DATABASE_URL`，并完成备份策略 |
| P0 | 仿真产物持久化 | S3 兼容对象存储（Cloudflare R2、AWS S3 或 MinIO） | endpoint、bucket、access key、secret key |
| P1 | 分布式任务与进度 | Redis | `REDIS_URL`；单实例开源演示可暂不接 |
| P1 | 事件语义编译/人物对话增强 | OpenAI 兼容模型服务 | `QIANSCOPE_LLM_API_KEY`、`QIANSCOPE_LLM_BASE_URL`、`QIANSCOPE_LLM_MODEL` |
| P1 | 服务端地理编码、路线或批量 POI | 高德 Web 服务 API | 独立的 Web 服务 Key；只做当前前端地图时不需要 |

## 可选发布项

- Sentry 或 OpenTelemetry：生产错误、性能和任务链路；不得采集问卷原文、人物访谈或凭证。
- CDN/WAF：静态资源加速、限流与基础防护。
- 授权的苏州人口边际和历史结果数据：这不是 API Key，但是从“未校准合成预测”升级为可验证现实预测的必要条件。

## 历史结论

归档时的高德凭证足够运行苏州地图、拖动/缩放/旋转、地点下钻和实时天气，但不得复制到贵州新项目。目标站的邮件一次性登录尚不能在生产环境完成，直到团队选定邮件服务、提供发件域名与 API Key，并提供 PostgreSQL。
