'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT); import path only adapted.
import { useEffect, useState, type RefObject } from 'react';

import { objectContainRect, type ContainRect } from '../lib/image-click';

export function useContainRect(
  imgRef?: RefObject<HTMLImageElement | null>,
): ContainRect | null {
  const [rect, setRect] = useState<ContainRect | null>(null);
  useEffect(() => {
    let ro: ResizeObserver | null = null;
    let attached: HTMLImageElement | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;
    const measure = () => {
      if (!attached) return;
      setRect(
        objectContainRect(
          attached.clientWidth,
          attached.clientHeight,
          attached.naturalWidth,
          attached.naturalHeight,
        ),
      );
    };
    const attach = (img: HTMLImageElement) => {
      attached = img;
      measure();
      ro = new ResizeObserver(measure);
      ro.observe(img);
      img.addEventListener('load', measure);
    };
    const img = imgRef?.current;
    if (img) {
      attach(img);
    } else {
      poll = setInterval(() => {
        const found = imgRef?.current;
        if (found) {
          if (poll) clearInterval(poll);
          poll = null;
          attach(found);
        }
      }, 300);
    }
    return () => {
      if (poll) clearInterval(poll);
      ro?.disconnect();
      attached?.removeEventListener('load', measure);
    };
  }, [imgRef]);
  return rect;
}
