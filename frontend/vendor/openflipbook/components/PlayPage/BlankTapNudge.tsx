'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT); copy localized for this app.
interface Props {
  nudgeKey: string | number;
  xPx: number;
  yPx: number;
  text?: string;
}

export function BlankTapNudge({ nudgeKey, xPx, yPx, text = '这里还没有可进入的画页' }: Props) {
  return (
    <span
      key={nudgeKey}
      aria-hidden
      className="pointer-events-none absolute -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full bg-black/70 px-2.5 py-1 text-xs font-medium text-white/95 shadow-lg backdrop-blur"
      style={{ left: `${xPx}px`, top: `${yPx - 12}px`, animation: 'ec-nudge 1.6s ease-out forwards' }}
    >
      {text}
    </span>
  );
}
