'use client';

// Adapted directly from OpenFlipbook commit b3e5044 EnterableMarkers (MIT).
import type { RefObject } from 'react';

import { useContainRect } from '../../hooks/useContainRect';

export interface EnterableMarker {
  id: string;
  label: string;
  xPct: number;
  yPct: number;
}

interface Props {
  markers: EnterableMarker[];
  imgRef?: RefObject<HTMLImageElement | null>;
}

export function EnterableMarkers({ markers, imgRef }: Props) {
  const content = useContainRect(imgRef);
  if (markers.length === 0) return null;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-10">
      {markers.map((marker) => {
        const left = content
          ? `${content.offsetX + marker.xPct * content.width}px`
          : `${marker.xPct * 100}%`;
        const top = content
          ? `${content.offsetY + marker.yPct * content.height}px`
          : `${marker.yPct * 100}%`;
        return (
          <span
            key={marker.id}
            data-entity-id={marker.id}
            title={marker.label}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left, top }}
          >
            <span className="relative flex h-7 w-7">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/45" />
              <span className="relative inline-flex h-7 w-7 rounded-full border-2 border-emerald-500 bg-emerald-400/20 shadow-[0_0_14px_rgba(16,185,129,0.8)]" />
            </span>
          </span>
        );
      })}
    </div>
  );
}
