'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT).
import { useEffect, useState } from 'react';

import { emit as hudEmit, nowMs } from '../lib/trace';

export interface MorphFx {
  ox: number;
  oy: number;
  prevImg: string | null;
  nextImg: string | null;
  phase: 'wait' | 'reveal';
  isFinal: boolean;
  startedAt: number;
  reduceMotion: boolean;
  dive?: boolean;
}

export function useImageMorph(currentImageDataUrl: string | null | undefined) {
  const [morphFx, setMorphFx] = useState<MorphFx | null>(null);

  useEffect(() => {
    if (!morphFx || morphFx.phase !== 'wait') return;
    if (!morphFx.isFinal || !currentImageDataUrl) return;
    if (currentImageDataUrl === morphFx.prevImg) return;
    let cancelled = false;
    const url = currentImageDataUrl;
    const im = new Image();
    im.decoding = 'async';
    im.src = url;
    const decodeStart = nowMs();
    const finish = () => {
      if (cancelled) return;
      hudEmit('image:decode', { ms: nowMs() - decodeStart, t0: decodeStart });
      setMorphFx((prev) =>
        prev && prev.phase === 'wait' ? { ...prev, nextImg: url, phase: 'reveal' } : prev,
      );
    };
    im.decode().then(finish).catch(finish);
    return () => {
      cancelled = true;
    };
  }, [currentImageDataUrl, morphFx]);

  return { morphFx, setMorphFx } as const;
}
