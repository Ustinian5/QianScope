# 黔镜 QianScope Web

默认入口是面向电脑端展示与推演的全屏社会世界，不是传统仪表盘：用户可在贵阳真实底图上进入 7 个代表性场所和建筑，通过 2.5D 交互画页继续下钻，检索 5,000 个稳定合成人格，查看档案、关系和日程，并通过统一任务界面运行问卷、事件及九类洞察工具。

## 页面

- `/`：L1 贵阳全景、L2 场所、L3 建筑/楼层、人物搜索与访谈、12 个研究工具。
- `/predict`：适合严肃研究项目的五步问卷与事件预测流程。
- `/runs`：历史预测项目。
- `/demo`：无需后端的明确标注演示报告。
- `/cities/suzhou`：仅兼容历史链接的旧版苏州页面；`/governance`：贵阳现行模型治理与可追溯信息。

所有真实运行均通过同源 `/api/qianscope/*` 网关访问 FastAPI。工具创建后台任务后显示任务 ID、真实阶段、已处理 Agent 数和最新轨迹；支持终止，并能按任务 ID 恢复持久化结果。后端不可用时，界面只会显示明确标注为“合成演示 · 未校准”的回退内容。

## 本地开发

先从仓库根目录启动 Conda 后端：

```bash
conda create -p ./.conda-env python=3.11 -y
conda run -p ./.conda-env pip install -e '.[dev]'
conda run -p ./.conda-env qianscope serve --host 127.0.0.1 --port 8000
```

再启动前端：

```bash
cd frontend
npm ci
npm run dev
```

打开 `http://localhost:3000`。

## 环境变量

| 名称 | 用途 | 本地默认值 |
| --- | --- | --- |
| `QIANSCOPE_API_URL` | 服务端网关访问的 FastAPI 地址；兼容旧 `ECHO_API_URL` | `http://127.0.0.1:8000` |
| `SITE_URL` | 分享元数据的规范域名 | `http://localhost:3000` |
| `NEXT_PUBLIC_AMAP_KEY` | 高德 Web JS API Key | 未设置时进入明确标注的演示模式 |
| `NEXT_PUBLIC_AMAP_SECURITY_JS_CODE` | 与 Key 配套的高德安全密钥 | 未设置时进入明确标注的演示模式 |
| `NEXT_PUBLIC_AMAP_STYLE` | 高德地图样式 | `amap://styles/whitesmoke` |
| `NEXT_PUBLIC_MAP_STYLE_URL` | 仅供降级模式使用的 MapLibre 样式地址 | 未设置时使用 OSM 公共瓦片 |

正式发布必须在高德开放平台创建 Web 端（JS API）应用，并把 Key、安全密钥配置到部署环境；前端通过官方 Loader 在线加载 JS API 2.0。OpenStreetMap 公共瓦片只用于无高德凭证时的本地开发降级，不作为正式发布底图。

## 质量检查

```bash
npm run lint
npm run typecheck
npm run build
# 或一次运行全部：
npm run check
```

## 前端设计原则

- 城市、场所、建筑和人物保持空间连续性；城市镜头会在 L1 → L2 → L1 下钻和返回时保留。
- L1 高德地图支持拖拽、滚轮/双指缩放、双击缩放、键盘平移、旋转、俯仰、活动层开关和地点镜头锁定。
- L2/L3 使用“整幅插画即界面”的 2.5D 画页：地点热点、人物、房间、楼层路径、点击涟漪和径向揭幕共同构成连续探索体验，不再加载 Three.js。
- 暖灰绿、低对比玻璃层和编辑型衬线标题构成克制的视觉系统；小字号使用专门的标签与数字字体层级。
- 输入/运行阶段采用模态交互；结果完成后在桌面端停靠右侧，地图仍可探索。
- 5,000 原型、666.89 万加权代表人口、真实数据、校准状态和演示回退始终使用不同措辞。
- 键盘焦点、Escape 关闭、模态焦点约束、减少动画偏好和手机布局均属于验收项。
