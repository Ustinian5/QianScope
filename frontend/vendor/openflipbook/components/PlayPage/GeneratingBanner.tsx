'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT).
export function GeneratingBanner({ statusMsg }: { statusMsg: string | null }) {
  return (
    <div className="sw-openflipbook-generating pointer-events-none absolute inset-0 flex items-end">
      <div className="sw-openflipbook-generating-status m-4 flex items-center gap-3 rounded-full px-4 py-2 text-sm shadow-lg">
        <span className="inline-block h-3 w-3 animate-pulse rounded-full" />
        <span>{statusMsg ?? '正在生成画页…'}</span>
      </div>
    </div>
  );
}
