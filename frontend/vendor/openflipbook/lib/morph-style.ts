// Copied from OpenFlipbook commit b3e5044 (MIT).
import type { CSSProperties } from 'react';

import type { MorphFx } from '../hooks/useImageMorph';
import { REGION_FRAC } from './image-condition';

export const DIVE_END_SCALE = 1 / REGION_FRAC;

const MASK_GRADIENT = 'radial-gradient(circle, #000 55%, transparent 78%)';
const MASK_TRANSITION =
  'mask-size 320ms cubic-bezier(0.22, 0.61, 0.36, 1), -webkit-mask-size 320ms cubic-bezier(0.22, 0.61, 0.36, 1)';

export function inkMorphStyle(morphFx: MorphFx | null): CSSProperties | undefined {
  if (!morphFx) return undefined;
  if (morphFx.reduceMotion) {
    return { opacity: 1, transition: 'opacity 200ms linear' };
  }
  const size = morphFx.phase === 'reveal' ? '280% 280%' : '0% 0%';
  const position = `${morphFx.ox}px ${morphFx.oy}px`;
  return {
    maskImage: MASK_GRADIENT,
    WebkitMaskImage: MASK_GRADIENT,
    maskRepeat: 'no-repeat',
    WebkitMaskRepeat: 'no-repeat',
    maskPosition: position,
    WebkitMaskPosition: position,
    maskSize: size,
    WebkitMaskSize: size,
    transition: MASK_TRANSITION,
  };
}
