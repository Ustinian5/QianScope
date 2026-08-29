#!/usr/bin/env python3
"""Generate Guiyang scene transitions as spatial focus dives.

This script is intentionally run from the dedicated LTX conda environment::

    conda run -p /Users/ustinian/.cache/qianscope-ltx-env \
      python scripts/generate_focus_transitions.py --output-dir /tmp/qianscope-focus

Each clip is conditioned on three independent frames:

1. the full location overview;
2. a real crop centred on the hotspot that the user clicked;
3. the destination interior.

The middle condition is a camera crop, never a folded or composited image.  It
therefore gives the video model one unambiguous motion path: push toward the
selected point, cross the threshold, and settle in the destination.
"""

from __future__ import annotations

import argparse
import gc
import shutil
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image


MODEL_PROMPT = (
    "One continuous forward dolly shot. The camera locks onto the selected "
    "building, pushes straight toward its entrance with natural spatial "
    "parallax, passes through the doorway, and arrives inside the destination. "
    "Stable horizon and rigid architecture. No paper, pages, folding, "
    "unfolding, leaves, petals, panels, split screen, wipes, or page turns."
)

MODEL_HEIGHT = 288
MODEL_WIDTH = 512
OUTPUT_HEIGHT = 576
OUTPUT_WIDTH = 1024
FRAME_COUNT = 49
FPS = 24
BASE_SEED = 42642


@dataclass(frozen=True)
class TransitionSpec:
    output: str
    exterior: str
    destination: str
    x_pct: float
    y_pct: float


def specs() -> list[TransitionSpec]:
    groups = [
        (
            "guiyang-convention-exterior.webp",
            [
                ("guiyang-convention-conference-center.mp4", "guiyang-convention-interior.webp", .27, .34),
                ("guiyang-convention-exhibition-login-hall.mp4", "guiyang-convention-exhibition-login-hall.webp", .74, .34),
                ("guiyang-convention-big-data-release-hall.mp4", "guiyang-convention-big-data-release-hall.webp", .27, .69),
                ("guiyang-convention-city-reception-hall.mp4", "guiyang-convention-city-reception-hall.webp", .73, .69),
            ],
        ),
        (
            "guiyang-big-data-exterior.webp",
            [
                ("guiyang-big-data-showcase-center.mp4", "guiyang-big-data-interior.webp", .27, .30),
                ("guiyang-big-data-roadshow-hall.mp4", "guiyang-big-data-roadshow-hall.webp", .73, .29),
                ("guiyang-big-data-compute-lab.mp4", "guiyang-big-data-compute-lab.webp", .27, .68),
                ("guiyang-big-data-youth-community.mp4", "guiyang-big-data-youth-community.webp", .73, .68),
            ],
        ),
        (
            "guizhou-university-exterior.webp",
            [
                ("guizhou-university-library.mp4", "guizhou-university-interior.webp", .27, .30),
                ("guizhou-university-engineering-center.mp4", "guizhou-university-engineering-center.webp", .74, .30),
                ("guizhou-university-student-activity-center.mp4", "guizhou-university-student-activity-center.webp", .25, .66),
                ("guizhou-university-cafeteria.mp4", "guizhou-university-cafeteria.webp", .74, .67),
            ],
        ),
        (
            "jiaxiu-tower-exterior.webp",
            [
                ("jiaxiu-tower-culture-hall.mp4", "jiaxiu-tower-interior.webp", .27, .30),
                ("jiaxiu-tower-cuiwei-garden.mp4", "jiaxiu-tower-cuiwei-garden.webp", .73, .30),
                ("jiaxiu-tower-riverside-outpost.mp4", "jiaxiu-tower-riverside-outpost.webp", .25, .71),
                ("jiaxiu-tower-riverside-library.mp4", "jiaxiu-tower-riverside-library.webp", .75, .71),
            ],
        ),
        (
            "qingyan-town-exterior.webp",
            [
                ("qingyan-town-visitor-center.mp4", "qingyan-town-interior.webp", .27, .27),
                ("qingyan-town-heritage-workshop.mp4", "qingyan-town-heritage-workshop.webp", .73, .27),
                ("qingyan-town-community-council.mp4", "qingyan-town-community-council.webp", .28, .68),
                ("qingyan-town-zhuangyuan-library.mp4", "qingyan-town-zhuangyuan-library.webp", .72, .69),
            ],
        ),
        (
            "guiyang-north-station-exterior.webp",
            [
                ("guiyang-north-station-interchange-hall.mp4", "guiyang-north-station-interior.webp", .24, .29),
                ("guiyang-north-station-waiting-hall.mp4", "guiyang-north-station-waiting-hall.webp", .70, .29),
                ("guiyang-north-station-bus-control.mp4", "guiyang-north-station-bus-control.webp", .25, .69),
                ("guiyang-north-station-passenger-service.mp4", "guiyang-north-station-passenger-service.webp", .72, .71),
            ],
        ),
        (
            "huaguoyuan-exterior.webp",
            [
                ("huaguoyuan-community-service.mp4", "huaguoyuan-interior.webp", .23, .28),
                ("huaguoyuan-wetland-outpost.mp4", "huaguoyuan-wetland-outpost.webp", .72, .27),
                ("huaguoyuan-childcare-center.mp4", "huaguoyuan-childcare-center.webp", .23, .70),
                ("huaguoyuan-health-center.mp4", "huaguoyuan-health-center.webp", .72, .70),
            ],
        ),
    ]
    return [
        TransitionSpec(output, exterior, destination, x_pct, y_pct)
        for exterior, entries in groups
        for output, destination, x_pct, y_pct in entries
    ]


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    source = image.convert("RGB")
    scale = max(width / source.width, height / source.height)
    resized = source.resize(
        (round(source.width * scale), round(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def focus_crop(
    image: Image.Image,
    x_pct: float,
    y_pct: float,
    zoom: float,
    width: int,
    height: int,
) -> Image.Image:
    """Create a real optical crop centred on the selected exterior hotspot."""

    source = image.convert("RGB")
    target_ratio = width / height
    crop_width = source.width / zoom
    crop_height = crop_width / target_ratio
    if crop_height > source.height:
        crop_height = source.height / zoom
        crop_width = crop_height * target_ratio

    centre_x = x_pct * source.width
    centre_y = y_pct * source.height
    left = min(max(centre_x - crop_width / 2, 0), source.width - crop_width)
    top = min(max(centre_y - crop_height / 2, 0), source.height - crop_height)
    crop = source.crop((round(left), round(top), round(left + crop_width), round(top + crop_height)))
    return crop.resize((width, height), Image.Resampling.LANCZOS)


def load_conditions(
    asset_dir: Path,
    spec: TransitionSpec,
    focus_zoom: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with Image.open(asset_dir / spec.exterior) as source_image:
        start = cover(source_image, MODEL_WIDTH, MODEL_HEIGHT)
        focus = focus_crop(
            source_image,
            spec.x_pct,
            spec.y_pct,
            focus_zoom,
            MODEL_WIDTH,
            MODEL_HEIGHT,
        )
    with Image.open(asset_dir / spec.destination) as destination_image:
        end = cover(destination_image, MODEL_WIDTH, MODEL_HEIGHT)
    return np.asarray(start), np.asarray(focus), np.asarray(end)


def lock_endpoints(
    frames: np.ndarray,
    start: np.ndarray,
    focus: np.ndarray,
    end: np.ndarray,
) -> np.ndarray:
    """Keep exact route anchors while softly settling adjacent model frames."""

    result = frames.copy()
    result[0] = start
    result[FRAME_COUNT // 2] = focus
    result[-1] = end
    for index, weight in ((1, .70), (2, .38), (FRAME_COUNT - 3, .32), (FRAME_COUNT - 2, .68)):
        anchor = start if index < FRAME_COUNT // 2 else end
        blended = result[index].astype(np.float32) * (1 - weight) + anchor.astype(np.float32) * weight
        result[index] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


def encode_video(frames: np.ndarray, output: Path, ffmpeg: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="qianscope-focus-") as temp_dir:
        raw_path = Path(temp_dir) / "model.mp4"
        imageio.mimwrite(
            raw_path,
            frames,
            fps=FPS,
            codec="libx264",
            pixelformat="yuv420p",
            macro_block_size=None,
            ffmpeg_log_level="error",
        )
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(raw_path),
                "-vf",
                f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos",
                "-frames:v",
                str(FRAME_COUNT),
                "-r",
                str(FPS),
                "-an",
                "-c:v",
                "libx264",
                "-profile:v",
                "high",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "medium",
                "-crf",
                "27",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--asset-dir",
        type=Path,
        default=repo_root / "frontend/public/openflipbook/guiyang",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("/Users/ustinian/.cache/qianscope-ltx2b-model"),
    )
    parser.add_argument(
        "--ffmpeg",
        default=shutil.which("ffmpeg") or "/Users/ustinian/.cache/qianscope-ltx-env/bin/ffmpeg",
    )
    parser.add_argument("--only", action="append", default=[], help="Output filename to generate")
    parser.add_argument("--focus-zoom", type=float, default=3.6)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--keyframes-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = [spec for spec in specs() if not args.only or spec.output in set(args.only)]
    if not selected:
        raise SystemExit("No transition matched --only")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prepared: list[tuple[TransitionSpec, np.ndarray, np.ndarray, np.ndarray]] = []
    for spec in selected:
        start, focus, end = load_conditions(args.asset_dir, spec, args.focus_zoom)
        prepared.append((spec, start, focus, end))
        if args.keyframes_only:
            preview = Image.new("RGB", (MODEL_WIDTH * 3, MODEL_HEIGHT))
            preview.paste(Image.fromarray(start), (0, 0))
            preview.paste(Image.fromarray(focus), (MODEL_WIDTH, 0))
            preview.paste(Image.fromarray(end), (MODEL_WIDTH * 2, 0))
            preview.save(args.output_dir / f"{Path(spec.output).stem}-route.jpg", quality=92)

    if args.keyframes_only:
        print(f"Wrote {len(prepared)} focus-route previews to {args.output_dir}")
        return

    from ltx_mlx.pipeline import LTXPipeline

    pipeline = LTXPipeline(str(args.model_dir), load_text_encoder=False)
    for index, (spec, start, focus, end) in enumerate(prepared, start=1):
        seed = BASE_SEED + zlib.crc32(spec.output.encode("utf-8")) % 100_000
        print(f"\n[{index}/{len(prepared)}] {spec.output} · hotspot=({spec.x_pct:.2f}, {spec.y_pct:.2f}) · seed={seed}")
        frames = pipeline.generate(
            prompt=MODEL_PROMPT,
            num_frames=FRAME_COUNT,
            height=MODEL_HEIGHT,
            width=MODEL_WIDTH,
            num_steps=args.steps,
            seed=seed,
            image=start,
            middle_image=focus,
            end_image=end,
        )
        if len(frames) != FRAME_COUNT:
            raise RuntimeError(f"{spec.output}: expected {FRAME_COUNT} frames, got {len(frames)}")
        frames = lock_endpoints(frames, start, focus, end)
        encode_video(frames, args.output_dir / spec.output, args.ffmpeg)
        del frames
        gc.collect()

    print(f"Generated {len(prepared)} spatial focus transitions in {args.output_dir}")


if __name__ == "__main__":
    main()
