'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT); type kept local.
import { useState } from 'react';

export interface Crumb {
  nodeId: string;
  title: string;
}

interface Props {
  crumbs: Crumb[];
  onJump: (nodeId: string) => void;
}

function short(title: string): string {
  return title.length > 28 ? `${title.slice(0, 27)}…` : title;
}

export default function Breadcrumb({ crumbs, onJump }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (crumbs.length < 2) return null;
  const collapsed = !expanded && crumbs.length > 4;
  const visible: (Crumb | 'ellipsis')[] = collapsed
    ? [crumbs[0]!, 'ellipsis', ...crumbs.slice(-2)]
    : crumbs;
  return (
    <nav aria-label="当前位置" className="flex flex-wrap items-center gap-0.5 text-xs">
      {visible.map((crumb, index) => {
        if (crumb === 'ellipsis') {
          return (
            <span key="ellipsis" className="flex items-center gap-0.5">
              <span aria-hidden className="px-0.5 opacity-40">›</span>
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className="rounded px-1 py-0.5 opacity-70 hover:bg-[var(--color-ink)]/10 hover:opacity-100"
              >
                …
              </button>
            </span>
          );
        }
        const isLast = index === visible.length - 1;
        return (
          <span key={crumb.nodeId} className="flex items-center gap-0.5">
            {index > 0 ? <span aria-hidden className="px-0.5 opacity-40">›</span> : null}
            {isLast ? (
              <span aria-current="page" title={crumb.title} className="font-semibold text-[var(--color-ink)]">
                {short(crumb.title)}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => onJump(crumb.nodeId)}
                title={`返回 ${crumb.title}`}
                className="rounded px-1 py-0.5 opacity-70 hover:bg-[var(--color-ink)]/10 hover:opacity-100"
              >
                {short(crumb.title)}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}
