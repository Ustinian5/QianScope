'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT).
export function TapHint({ text }: { text: string }) {
  return (
    <figcaption className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center text-sm text-white">
      <span className="max-w-[70%] truncate rounded-full bg-black/55 px-3 py-1 backdrop-blur">
        {text}
      </span>
    </figcaption>
  );
}
