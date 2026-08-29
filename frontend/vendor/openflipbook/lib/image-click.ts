// Copied from OpenFlipbook commit b3e5044 (MIT).
import { clamp01 } from './clamp';

export interface NormalizedClick {
  x_pct: number;
  y_pct: number;
}

export type ImageFit = 'contain' | 'cover';

/** The on-screen rectangle occupied by an object-contain image. */
export interface ContainRect {
  offsetX: number;
  offsetY: number;
  width: number;
  height: number;
}

export function objectContainRect(
  boxWidth: number,
  boxHeight: number,
  naturalWidth: number,
  naturalHeight: number,
): ContainRect | null {
  if (boxWidth <= 0 || boxHeight <= 0 || naturalWidth <= 0 || naturalHeight <= 0) {
    return null;
  }
  const naturalAspect = naturalWidth / naturalHeight;
  const boxAspect = boxWidth / boxHeight;
  let width = boxWidth;
  let height = boxHeight;
  let offsetX = 0;
  let offsetY = 0;
  if (naturalAspect > boxAspect) {
    height = boxWidth / naturalAspect;
    offsetY = (boxHeight - height) / 2;
  } else {
    width = boxHeight * naturalAspect;
    offsetX = (boxWidth - width) / 2;
  }
  return { offsetX, offsetY, width, height };
}

/** The on-screen rectangle occupied by an object-cover image. */
export function objectCoverRect(
  boxWidth: number,
  boxHeight: number,
  naturalWidth: number,
  naturalHeight: number,
): ContainRect | null {
  if (boxWidth <= 0 || boxHeight <= 0 || naturalWidth <= 0 || naturalHeight <= 0) {
    return null;
  }
  const scale = Math.max(boxWidth / naturalWidth, boxHeight / naturalHeight);
  const width = naturalWidth * scale;
  const height = naturalHeight * scale;
  return {
    offsetX: (boxWidth - width) / 2,
    offsetY: (boxHeight - height) / 2,
    width,
    height,
  };
}

export function objectFitRect(
  boxWidth: number,
  boxHeight: number,
  naturalWidth: number,
  naturalHeight: number,
  imageFit: ImageFit = 'contain',
): ContainRect | null {
  return imageFit === 'cover'
    ? objectCoverRect(boxWidth, boxHeight, naturalWidth, naturalHeight)
    : objectContainRect(boxWidth, boxHeight, naturalWidth, naturalHeight);
}

/** Convert a raw mouse event into the intrinsic image's normalized grid. */
export function normalizeClickOnImage(
  event: MouseEvent,
  img: HTMLImageElement,
  imageFit: ImageFit = 'contain',
): NormalizedClick | null {
  const rect = img.getBoundingClientRect();
  const content = objectFitRect(
    rect.width,
    rect.height,
    img.naturalWidth,
    img.naturalHeight,
    imageFit,
  );
  if (!content) return null;
  const localX = event.clientX - rect.left - content.offsetX;
  const localY = event.clientY - rect.top - content.offsetY;
  if (localX < 0 || localY < 0 || localX > content.width || localY > content.height) {
    return null;
  }
  return {
    x_pct: clamp01(localX / content.width),
    y_pct: clamp01(localY / content.height),
  };
}
