'use client';

// Copied from OpenFlipbook commit b3e5044 (MIT); import paths only adapted.
import type { CSSProperties, RefObject, TransitionEvent } from 'react';

import type { MorphFx } from '../../hooks/useImageMorph';
import type { ImageFit } from '../../lib/image-click';
import { DIVE_END_SCALE, inkMorphStyle } from '../../lib/morph-style';

interface Props {
  imgRef: RefObject<HTMLImageElement | null>;
  imageDataUrl: string;
  alt: string;
  morphFx: MorphFx | null;
  onError: () => void;
  onMorphTransitionEnd: (e: TransitionEvent<HTMLImageElement>) => void;
  newImageClassName: string;
  imageFit?: ImageFit;
}

export function MorphImagePair({
  imgRef,
  imageDataUrl,
  alt,
  morphFx,
  onError,
  onMorphTransitionEnd,
  newImageClassName,
  imageFit = 'contain',
}: Props) {
  const newImageStyle = inkMorphStyle(morphFx);
  return (
    <>
      {morphFx ? (
        // eslint-disable-next-line @next/next/no-img-element -- exact OpenFlipbook image canvas; static scene URLs need no Next loader hop
        <img
          src={morphFx.prevImg ?? imageDataUrl}
          alt=""
          aria-hidden
          className={
            'absolute inset-0 block h-full w-full select-none ' +
            (morphFx.phase === 'wait' && !morphFx.reduceMotion
              ? morphFx.dive
                ? 'ec-morph-old'
                : 'ec-morph-shimmer'
              : '')
          }
          style={
            {
              opacity: morphFx.phase === 'reveal' ? 0 : 1,
              transition: 'opacity 480ms cubic-bezier(0.22, 0.61, 0.36, 1)',
              transformOrigin:
                typeof morphFx.ox === 'number' && typeof morphFx.oy === 'number'
                  ? `${morphFx.ox}px ${morphFx.oy}px`
                  : 'center',
              '--ec-dive-scale': String(DIVE_END_SCALE),
              objectFit: imageFit,
            } as CSSProperties
          }
          draggable={false}
        />
      ) : null}
      {/* eslint-disable-next-line @next/next/no-img-element -- exact OpenFlipbook image canvas; static scene URLs need no Next loader hop */}
      <img
        ref={imgRef}
        src={morphFx?.nextImg ?? imageDataUrl}
        alt={alt}
        onError={onError}
        className={newImageClassName}
        style={{ ...newImageStyle, objectFit: imageFit }}
        onTransitionEnd={onMorphTransitionEnd}
        draggable={false}
      />
    </>
  );
}
