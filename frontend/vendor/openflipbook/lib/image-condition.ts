// Copied from OpenFlipbook commit b3e5044 (MIT), image-navigation subset.
import { clamp } from './clamp';

/** Default region-crop fraction; the dive ends at its reciprocal scale. */
export const REGION_FRAC = 0.42;

export function cropBox(
  xPct: number,
  yPct: number,
  frac: number,
): { x: number; y: number; w: number; h: number } {
  const w = clamp(frac, 0, 1);
  const h = clamp(frac, 0, 1);
  const x = clamp(xPct - w / 2, 0, 1 - w);
  const y = clamp(yPct - h / 2, 0, 1 - h);
  return { x, y, w, h };
}

export function diveOriginPx(
  xPct: number,
  yPct: number,
  frac: number,
  content: { offsetX: number; offsetY: number; width: number; height: number },
): { x: number; y: number } {
  const box = cropBox(xPct, yPct, frac);
  return {
    x: content.offsetX + (box.x + box.w / 2) * content.width,
    y: content.offsetY + (box.y + box.h / 2) * content.height,
  };
}
