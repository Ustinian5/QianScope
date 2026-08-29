# OpenFlipbook 场景转场

黔镜保留高德地图作为贵阳城市入口，场景链路固定为：

1. 高德地图选择一级地点；
2. 地点总览画页选择一个具体场景；
3. 播放对应的折叠展开视频；
4. 视频尾帧无跳变进入该场景的独立交互画页。

7 个一级地点各有 4 个独立场景，共 28 条边。图片与视频的唯一映射维护在
`frontend/lib/openflipbook-guiyang.ts`，运行时不请求视频生成服务。

## 视频生成

- 模型：Lightricks `ltxv-2b-0.9.8-distilled`（LTX-Video 2B）。
- 本地推理适配：`baisampayans/ltx-mlx` commit
  `0d884df6c5f086915e4ffdab950d914757c306f2`，增加首帧、中间帧和尾帧条件入口。
- 第 0 帧：一级地点室外总览。
- 第 24 帧：由室外画页左右透视折起、目标场景从中央显露的折叠关键帧。
- 第 48 帧：具体场景画页。
- 提示词：`architectural paper world folds open and reveals the destination, continuous camera motion`
- 模型尺寸：512×288；输出尺寸：1024×576。
- 时序：49 帧、24 fps、4 个去噪步骤，成片 2.041667 秒。
- 固定种子：`42642 + crc32(输出文件名) % 100000`。
- 编码：H.264 High、`yuv420p`、CRF 24、`faststart`，无音轨。

35 张场景条件图以 WebP `drawing` preset、quality 82 交付；这只改变网页传输编码，
不改变模型生成内容、像素尺寸或各场景的独立映射。

首帧、折叠关键帧和尾帧在模型输出后再次锁定到高清条件图，避免进入和离开
视频时发生视觉跳变；其余帧来自 LTX-Video 扩散推理，不是 CSS 模糊或静态淡入淡出。

模型说明：<https://huggingface.co/Lightricks/LTX-Video>

MLX 适配：<https://github.com/baisampayans/ltx-mlx>

## 前端播放与降级

`frontend/vendor/openflipbook/components/PlayPage/DescentVideoTransition.tsx`
沿用 OpenFlipbook `/play` 下钻视频的播放时序。浏览器会预加载目标图，视频自然结束后
才切换交互状态。只有媒体加载或自动播放失败时才启用 CSS 折页降级；系统开启
`prefers-reduced-motion` 时直接进入目标场景。

运行以下命令可验证 28 条视频的引用、编码、尺寸、帧率、帧数和文件唯一性：

```bash
./scripts/verify_scene_transitions.sh
```
