'use client';

/**
 * Product adapter of OpenFlipbook's QueryToolbar.
 *
 * The upstream rounded query form, flexible input and pill control group come
 * directly from OpenFlipbook commit b3e5044 (MIT). QianScope replaces the
 * generator-specific model/theme controls with the fixed Guiyang world scope
 * and exposes the result slot for its stable-persona search.
 */
import type { ChangeEvent, FormEvent, KeyboardEvent, ReactNode } from 'react';

type WorldQueryToolbarProps = {
  value: string;
  placeholder: string;
  open: boolean;
  controlsId: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onFocus: () => void;
  onToggle: () => void;
  onEscape: () => void;
  children?: ReactNode;
};

export function WorldQueryToolbar({
  value,
  placeholder,
  open,
  controlsId,
  onChange,
  onFocus,
  onToggle,
  onEscape,
  children,
}: WorldQueryToolbarProps) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
  }

  function keyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') onEscape();
  }

  return (
    <form
      role="search"
      onSubmit={submit}
      className={`sw-search sw-openflipbook-query flex items-center gap-2 rounded-full border border-[var(--color-edge)] bg-[var(--color-canvas)]/80 px-2 py-2 shadow-sm ${open ? 'open' : ''}`}
    >
      <button
        type="button"
        aria-label="搜索稳定人格"
        aria-expanded={open}
        aria-controls={controlsId}
        onClick={onToggle}
        title="搜索稳定人格"
        className="grid shrink-0 place-items-center rounded-full border border-[var(--color-edge)] hover:bg-[var(--color-ink)]/5"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.8" cy="10.8" r="5.8" />
          <path d="m15.2 15.2 4.1 4.1" />
        </svg>
      </button>
      <input
        className="min-w-[8rem] flex-1 bg-transparent outline-none placeholder:opacity-60"
        aria-label="搜索稳定人格"
        aria-controls={controlsId}
        aria-autocomplete="list"
        value={value}
        placeholder={placeholder}
        onChange={onChange}
        onFocus={onFocus}
        onKeyDown={keyDown}
      />
      <div
        role="group"
        aria-label="世界范围"
        className="sw-query-scope flex shrink-0 items-center overflow-hidden rounded-full border border-[var(--color-edge)] text-xs"
        title="当前世界范围"
      >
        <span>WORLD</span>
        <strong>贵阳</strong>
      </div>
      {children}
    </form>
  );
}
