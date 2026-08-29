'use client';

/**
 * First/last-frame descent playback adapted from OpenFlipbook commit b3e5044
 * (MIT), apps/web/app/play/page.tsx. QianScope adds a per-hotspot optical focus
 * origin and pre-generates one spatial push-in clip per location edge, so
 * entering a place never waits for inference.
 */
import { useEffect, useRef, useState, type CSSProperties } from 'react';

type DescentVideoTransitionProps = {
  videoUrl: string;
  posterUrl: string;
  destinationUrl: string;
  destinationLabel: string;
  focusX: number;
  focusY: number;
  onFinish: () => void;
};

export function DescentVideoTransition({
  videoUrl,
  posterUrl,
  destinationUrl,
  destinationLabel,
  focusX,
  focusY,
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
      aria-label={`镜头正在聚焦并进入${destinationLabel}`}
      style={{
        '--of-video-progress': `${progress * 100}%`,
        '--of-focus-x': `${focusX * 100}%`,
        '--of-focus-y': `${focusY * 100}%`,
      } as CSSProperties}
    >
      {failed ? (
        <div className="of-descent-focus-fallback" aria-hidden>
          {/* eslint-disable-next-line @next/next/no-img-element -- OpenFlipbook image canvas */}
          <img className="of-descent-focus-source" src={posterUrl} alt="" />
          {/* eslint-disable-next-line @next/next/no-img-element -- OpenFlipbook image canvas */}
          <img className="of-descent-focus-destination" src={destinationUrl} alt="" />
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
        <span>OPENFLIPBOOK · FOCUS DIVE</span>
        <strong>{destinationLabel}</strong>
      </div>
      <div className="of-descent-progress" aria-hidden><i /></div>
    </div>
  );
}
