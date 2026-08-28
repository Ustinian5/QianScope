'use client';

// Adapted directly from OpenFlipbook commit b3e5044 EntityHoverOverlay (MIT).
import { useState, type RefObject } from 'react';

import type { WorldAgent } from '@/lib/social-world-fixtures';
import { useContainRect } from '../../hooks/useContainRect';
import type { ContainRect } from '../../lib/image-click';

export interface PositionedAgent {
  agent: WorldAgent;
  xPct: number;
  yPct: number;
}

interface Props {
  agents: PositionedAgent[];
  imgRef?: RefObject<HTMLImageElement | null>;
  selectedAgentId?: string;
  onSelect: (agent: WorldAgent) => void;
}

export function EntityHoverOverlay({ agents, imgRef, selectedAgentId, onSelect }: Props) {
  const content = useContainRect(imgRef);
  if (agents.length === 0) return null;
  return (
    <div role="group" aria-label="画页人物" className="pointer-events-none absolute inset-0 z-20">
      {agents.map((item) => (
        <ChipMarker
          key={item.agent.id}
          item={item}
          content={content}
          selected={selectedAgentId === item.agent.id}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

function ChipMarker({
  item,
  content,
  selected,
  onSelect,
}: {
  item: PositionedAgent;
  content: ContainRect | null;
  selected: boolean;
  onSelect: (agent: WorldAgent) => void;
}) {
  const [hover, setHover] = useState(false);
  const left = content
    ? `${content.offsetX + item.xPct * content.width}px`
    : `${item.xPct * 100}%`;
  const top = content
    ? `${content.offsetY + item.yPct * content.height}px`
    : `${item.yPct * 100}%`;
  const placeAbove = item.yPct > 0.65;
  const shown = hover || selected;
  return (
    <div className="pointer-events-auto absolute" style={{ left, top, transform: 'translate(-50%, -50%)' }}>
      <button
        type="button"
        aria-label={`人物：${item.agent.name}`}
        aria-pressed={selected}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(item.agent);
        }}
        className={
          'block h-3 w-3 rounded-full border border-white/80 shadow transition-transform ' +
          (shown ? 'scale-125 bg-white' : 'bg-white/70 hover:scale-110 hover:bg-white')
        }
      />
      {shown ? (
        <div
          className={
            'pointer-events-none absolute left-1/2 z-10 w-48 -translate-x-1/2 rounded-md border border-white/15 bg-black/80 px-2 py-1.5 text-[11px] text-white shadow-lg backdrop-blur-sm ' +
            (placeAbove ? 'bottom-full mb-2' : 'top-full mt-2')
          }
        >
          <div className="font-medium leading-tight">{item.agent.name}</div>
          <div className="text-[10px] uppercase tracking-wider opacity-60">{item.agent.role}</div>
          <p className="mt-1 line-clamp-2 opacity-85">{item.agent.action}</p>
          <div className="mt-1 flex flex-wrap gap-1">
            <span className="rounded bg-white/10 px-1 font-mono text-[10px]">情绪：{item.agent.mood}</span>
            <span className="rounded bg-white/10 px-1 font-mono text-[10px]">意向：{item.agent.intention}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
