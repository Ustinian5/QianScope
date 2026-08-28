'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT).
export function GeneratingBanner({ statusMsg }: { statusMsg: string | null }) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-end bg-black/35">
      <div className="m-4 flex items-center gap-3 rounded-full bg-black/80 px-4 py-2 text-sm text-white shadow-lg">
        <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-white/90" />
        <span>{statusMsg ?? '正在生成画页…'}</span>
      </div>
    </div>
  );
}
