'use client';

/**
 * First/last-frame descent playback adapted from OpenFlipbook commit b3e5044
 * (MIT), apps/web/app/play/page.tsx. QianScope pre-generates and stores one
 * clip per location edge, so entering a place never waits for inference.
 */
import { useEffect, useRef, useState, type CSSProperties } from 'react';

type DescentVideoTransitionProps = {
  videoUrl: string;
  posterUrl: string;
  destinationUrl: string;
  destinationLabel: string;
  onFinish: () => void;
};

export function DescentVideoTransition({
  videoUrl,
  posterUrl,
  destinationUrl,
  destinationLabel,
  onFinish,
}: DescentVideoTransitionProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const finishedRef = useRef(false);
  const onFinishRef = useRef(onFinish);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    onFinishRef.current = onFinish;
  }, [onFinish]);

  useEffect(() => {
    const target = new Image();
    target.decoding = 'async';
    target.src = destinationUrl;
  }, [destinationUrl]);

  useEffect(() => {
    if (!failed) return;
    const timeout = window.setTimeout(() => {
      if (finishedRef.current) return;
      finishedRef.current = true;
      onFinishRef.current();
    }, 1180);
    return () => window.clearTimeout(timeout);
  }, [failed]);

  function finish() {
    if (finishedRef.current) return;
    finishedRef.current = true;
    onFinishRef.current();
  }

  return (
    <div
      className={`of-descent-transition ${ready ? 'is-playing' : 'is-loading'} ${failed ? 'is-fallback' : ''}`}
      role="status"
      aria-label={`正在通过折叠画页进入${destinationLabel}`}
      style={{ '--of-video-progress': `${progress * 100}%` } as CSSProperties}
    >
      {failed ? (
        <div className="of-descent-fold-fallback" aria-hidden>
          {/* eslint-disable-next-line @next/next/no-img-element -- OpenFlipbook image canvas */}
          <img src={posterUrl} alt="" />
          {/* eslint-disable-next-line @next/next/no-img-element -- OpenFlipbook image canvas */}
          <img src={destinationUrl} alt="" />
        </div>
      ) : (
        <video
          ref={videoRef}
          className="of-descent-video"
          src={videoUrl}
          poster={posterUrl}
          muted
          playsInline
          preload="auto"
          onLoadedData={() => {
            setReady(true);
            void videoRef.current?.play().catch(() => setFailed(true));
          }}
          onTimeUpdate={(event) => {
            const video = event.currentTarget;
            setProgress(video.duration > 0 ? Math.min(1, video.currentTime / video.duration) : 0);
          }}
          onEnded={finish}
          onError={() => setFailed(true)}
        />
      )}

      <div className="of-descent-caption" aria-hidden>
        <span>OPENFLIPBOOK DESCENT</span>
        <strong>{destinationLabel}</strong>
      </div>
      <div className="of-descent-progress" aria-hidden><i /></div>
    </div>
  );
}
