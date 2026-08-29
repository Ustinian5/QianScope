'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT).
interface Props {
  rippleKey: string | number;
  xPx: number;
  yPx: number;
}

export function ClickRipple({ rippleKey, xPx, yPx }: Props) {
  return (
    <span
      key={rippleKey}
      aria-hidden
      className="sw-openflipbook-click-ripple pointer-events-none absolute h-10 w-10 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 shadow-lg"
      style={{ left: `${xPx}px`, top: `${yPx}px`, animation: 'ec-ripple 1.2s ease-out infinite' }}
    />
  );
}
