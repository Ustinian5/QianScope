# OpenFlipbook 场景转场

黔镜保留高德地图作为贵阳城市入口，场景链路固定为：

1. 高德地图选择一级地点；
2. 地点总览画页选择一个具体场景；
3. 镜头锁定实际点击热点，连续推近该建筑并穿过入口；
4. 视频尾帧无跳变进入该场景的独立交互画页。

7 个一级地点各有 4 个独立场景，共 28 条边。图片与视频的唯一映射维护在
`frontend/lib/openflipbook-guiyang.ts`，运行时不请求视频生成服务。

## 视频生成与空间时序

- 模型：Lightricks `ltxv-2b-0.9.8-distilled`（LTX-Video 2B）。
- 本地推理适配：`baisampayans/ltx-mlx` commit
  `0d884df6c5f086915e4ffdab950d914757c306f2`，本地增加首帧、中间帧和尾帧条件入口。
- 第 0 帧：一级地点完整室外总览。
- 第 24 帧：以该场景真实 `xPct / yPct` 热点为中心，从同一室外图裁出的 3.6 倍光学聚焦帧。
- 第 48 帧：该场景自己的独立室内画页。
- 时序约束：单镜头向前推进、建筑保持刚性、稳定地平线；明确排除纸张、书页、折叠、树叶、花瓣、分屏和翻页。
- 模型尺寸：512×288；输出尺寸：1024×576。
- 时序：49 帧、24 fps、4 个去噪步骤，成片 2.041667 秒。
- 固定种子：`42642 + crc32(输出文件名) % 100000`。
- 编码：H.264 High、`yuv420p`、CRF 27、`faststart`，无音轨。

35 张场景条件图以 WebP `drawing` preset、quality 82 交付；这只改变网页传输编码，
不改变模型生成内容、像素尺寸或各场景的独立映射。

首帧、热点聚焦帧和尾帧在模型输出后再次锁定到条件图，相邻帧只做短距离稳定处理，
避免进入和离开视频时发生视觉跳变；其余帧来自 LTX-Video 扩散推理，不是 CSS 模糊或
静态淡入淡出。28 条路线由 `scripts/generate_focus_transitions.py` 维护，地点、热点坐标、
目标图和固定种子均可复现。

生成命令必须使用项目约定的 conda 环境：

```bash
conda run -p /Users/ustinian/.cache/qianscope-ltx-env \
  python scripts/generate_focus_transitions.py \
  --output-dir /tmp/qianscope-focus-transitions
```

模型说明：<https://huggingface.co/Lightricks/LTX-Video>

MLX 适配：<https://github.com/baisampayans/ltx-mlx>

## 前端播放与降级

`frontend/vendor/openflipbook/components/PlayPage/DescentVideoTransition.tsx`
沿用 OpenFlipbook `/play` 下钻视频的播放时序，并接收当前热点的 `focusX / focusY`。
浏览器会预加载目标图，视频自然结束后才切换交互状态。只有媒体加载或自动播放失败时
才启用同坐标的 CSS 推近与圆形阈值展开降级，不存在折页路径；系统开启
`prefers-reduced-motion` 时直接进入目标场景。

运行以下命令可验证 28 条视频的引用、编码、尺寸、帧率、帧数和文件唯一性：

```bash
./scripts/verify_scene_transitions.sh
```
