'use client';

/**
 * Guiyang content adapter for OpenFlipbook's image-is-the-UI play surface.
 *
 * The canvas structure, object-fit click math, descent-video playback, hover
 * crosshair, enterable markers, entity chips and feedback overlays come from
 * OpenFlipbook commit b3e5044 (MIT) via `frontend/vendor/openflipbook`. This
 * file only maps Guiyang locations, independent scene pages and stable agents
 * onto those upstream primitives.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react';

import {
  AGENT_ANCHORS,
  exteriorHotspots,
  interiorHotspots,
  sceneImageUrl,
  scenePage,
  type FlipbookHotspot,
} from '@/lib/openflipbook-guiyang';
import {
  WORLD_AGENTS,
  type WorldAgent,
  type WorldLevel,
  type WorldLocation,
} from '@/lib/social-world-fixtures';
import { BlankTapNudge } from '@/vendor/openflipbook/components/PlayPage/BlankTapNudge';
import Breadcrumb, {
  type Crumb,
} from '@/vendor/openflipbook/components/PlayPage/Breadcrumb';
import { ClickRipple } from '@/vendor/openflipbook/components/PlayPage/ClickRipple';
import { DescentVideoTransition } from '@/vendor/openflipbook/components/PlayPage/DescentVideoTransition';
import { EnterableMarkers } from '@/vendor/openflipbook/components/PlayPage/EnterableMarkers';
import { EntityHoverOverlay } from '@/vendor/openflipbook/components/PlayPage/EntityHoverOverlay';
import { HoverCrosshair } from '@/vendor/openflipbook/components/PlayPage/HoverCrosshair';
import { MorphImagePair } from '@/vendor/openflipbook/components/PlayPage/MorphImagePair';
import { TapHint } from '@/vendor/openflipbook/components/PlayPage/TapHint';
import { useContainRect } from '@/vendor/openflipbook/hooks/useContainRect';
import {
  normalizeClickOnImage,
  objectFitRect,
  type NormalizedClick,
} from '@/vendor/openflipbook/lib/image-click';

export type FlipbookInteriorProfile = {
  kind: string;
  floorName: string;
  activity: string;
  count: number;
  capacity: number;
  openHours: string;
  transition: string;
  rooms: string[];
};

type SocialWorldFlipbookProps = {
  level: Exclude<WorldLevel, 'city'>;
  location: WorldLocation;
  building: string;
  selectedAgentId?: string;
  interiorProfile: FlipbookInteriorProfile;
  onAgentSelect: (agent: WorldAgent) => void;
  onEnterInterior: (building: string) => void;
  onReturnCity: () => void;
  onReturnLocation: () => void;
};

type HoverState = { xPx: number; yPx: number; enterable: boolean };
type TapFeedback = { xPx: number; yPx: number; key: number };
type RoomFocus = { pageKey: string; index: number };
type PendingTransition = {
  building: string;
  destinationUrl: string;
  videoUrl: string;
};

const HIT_RADIUS = 0.115;
const IMAGE_FIT = 'cover' as const;

function nearestHotspot(
  click: NormalizedClick,
  hotspots: FlipbookHotspot[],
): { hotspot: FlipbookHotspot; index: number } | null {
  let best: { hotspot: FlipbookHotspot; index: number; distance: number } | undefined;
  for (const [index, hotspot] of hotspots.entries()) {
    const distance = Math.hypot(click.x_pct - hotspot.xPct, click.y_pct - hotspot.yPct);
    if (distance <= HIT_RADIUS && (!best || distance < best.distance)) {
      best = { hotspot, index, distance };
    }
  }
  return best ? { hotspot: best.hotspot, index: best.index } : null;
}

function pointInCanvas(
  img: HTMLImageElement,
  xPct: number,
  yPct: number,
): { xPx: number; yPx: number } {
  const content = objectFitRect(
    img.clientWidth,
    img.clientHeight,
    img.naturalWidth,
    img.naturalHeight,
    IMAGE_FIT,
  );
  if (!content) {
    return { xPx: xPct * img.clientWidth, yPx: yPct * img.clientHeight };
  }
  return {
    xPx: content.offsetX + xPct * content.width,
    yPx: content.offsetY + yPct * content.height,
  };
}

export function SocialWorldFlipbook({
  level,
  location,
  building,
  selectedAgentId,
  interiorProfile,
  onAgentSelect,
  onEnterInterior,
  onReturnCity,
  onReturnLocation,
}: SocialWorldFlipbookProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const motionFrameRef = useRef<number | null>(null);
  const imageContent = useContainRect(imgRef, IMAGE_FIT);
  const imageUrl = sceneImageUrl(location.id, level, building);
  const pageKey = `${location.id}:${level}:${building}`;
  const [phase, setPhase] = useState<'ready' | 'transition'>('ready');
  const [pendingTransition, setPendingTransition] = useState<PendingTransition | null>(null);
  const [hoverPos, setHoverPos] = useState<HoverState | null>(null);
  const [clickRipple, setClickRipple] = useState<TapFeedback | null>(null);
  const [blankTap, setBlankTap] = useState<TapFeedback | null>(null);
  const [roomFocus, setRoomFocus] = useState<RoomFocus | null>(null);
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);

  useEffect(
    () => () => {
      if (motionFrameRef.current !== null) {
        window.cancelAnimationFrame(motionFrameRef.current);
      }
    },
    [],
  );

  const hotspots = useMemo(
    () =>
      level === 'campus'
        ? exteriorHotspots(location)
        : interiorHotspots(interiorProfile.rooms),
    [interiorProfile.rooms, level, location],
  );
  const activeRoom = roomFocus?.pageKey === pageKey ? roomFocus.index : null;
  const localAgents = useMemo(
    () => WORLD_AGENTS.filter((agent) => agent.locationId === location.id),
    [location.id],
  );
  const positionedAgents = useMemo(
    () =>
      localAgents.map((agent, index) => ({
        agent,
        ...AGENT_ANCHORS[index % AGENT_ANCHORS.length]!,
      })),
    [localAgents],
  );

  const crumbs = useMemo<Crumb[]>(() => {
    const items: Crumb[] = [
      { nodeId: 'city', title: '贵阳全景' },
      { nodeId: 'location', title: location.short },
    ];
    if (level === 'interior') {
      items.push({ nodeId: 'interior', title: building });
    }
    return items;
  }, [building, level, location.short]);

  const beginDescent = useCallback(
    (xPct: number, yPct: number, nextBuilding: string) => {
      if (phase === 'transition') return;
      const img = imgRef.current;
      if (!img) {
        onEnterInterior(nextBuilding);
        return;
      }
      const origin = pointInCanvas(img, xPct, yPct);
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      setBlankTap(null);
      setClickRipple({ xPx: origin.xPx, yPx: origin.yPx, key: Date.now() });
      if (reduceMotion) {
        onEnterInterior(nextBuilding);
        return;
      }
      const target = scenePage(location.id, nextBuilding);
      setPendingTransition({
        building: nextBuilding,
        destinationUrl: target.image,
        videoUrl: target.video,
      });
      setPhase('transition');
    },
    [location.id, onEnterInterior, phase],
  );

  const completeDescent = useCallback(() => {
    if (!pendingTransition) return;
    const nextBuilding = pendingTransition.building;
    setPendingTransition(null);
    setClickRipple(null);
    setPhase('ready');
    onEnterInterior(nextBuilding);
  }, [onEnterInterior, pendingTransition]);

  const chooseHotspot = useCallback(
    (hotspot: FlipbookHotspot, index: number) => {
      if (level === 'campus') {
        beginDescent(hotspot.xPct, hotspot.yPct, hotspot.label);
        return;
      }
      const img = imgRef.current;
      const point = img
        ? pointInCanvas(img, hotspot.xPct, hotspot.yPct)
        : { xPx: 0, yPx: 0 };
      setClickRipple({ ...point, key: Date.now() });
      setRoomFocus((current) =>
        current?.pageKey === pageKey && current.index === index
          ? null
          : { pageKey, index },
      );
      window.setTimeout(() => setClickRipple(null), 520);
    },
    [beginDescent, level, pageKey],
  );

  const clickCanvas = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (phase !== 'ready' || !imgRef.current) return;
      if ((event.target as HTMLElement).closest('button')) return;
      const click = normalizeClickOnImage(event.nativeEvent, imgRef.current, IMAGE_FIT);
      if (!click) return;
      const hit = nearestHotspot(click, hotspots);
      if (hit) {
        chooseHotspot(hit.hotspot, hit.index);
        return;
      }
      const point = pointInCanvas(imgRef.current, click.x_pct, click.y_pct);
      setBlankTap({ ...point, key: Date.now() });
    },
    [chooseHotspot, hotspots, phase],
  );

  const updateParallax = useCallback((clientX: number, clientY: number) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, ((clientX - rect.left) / rect.width - 0.5) * 2));
    const y = Math.max(-1, Math.min(1, ((clientY - rect.top) / rect.height - 0.5) * 2));
    if (motionFrameRef.current !== null) {
      window.cancelAnimationFrame(motionFrameRef.current);
    }
    motionFrameRef.current = window.requestAnimationFrame(() => {
      viewport.style.setProperty('--sw-shift-x', `${(-x * 12).toFixed(2)}px`);
      viewport.style.setProperty('--sw-shift-y', `${(-y * 8).toFixed(2)}px`);
      motionFrameRef.current = null;
    });
  }, []);

  const resetParallax = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.style.setProperty('--sw-shift-x', '0px');
    viewport.style.setProperty('--sw-shift-y', '0px');
    setHoverPos(null);
  }, []);

  const movePointer = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      updateParallax(event.clientX, event.clientY);
      if (phase !== 'ready' || !imgRef.current) return;
      const click = normalizeClickOnImage(event.nativeEvent, imgRef.current, IMAGE_FIT);
      if (!click) {
        setHoverPos(null);
        return;
      }
      const point = pointInCanvas(imgRef.current, click.x_pct, click.y_pct);
      setHoverPos({ ...point, enterable: nearestHotspot(click, hotspots) !== null });
    },
    [hotspots, phase, updateParallax],
  );

  const jumpBreadcrumb = useCallback(
    (nodeId: string) => {
      if (nodeId === 'city') {
        onReturnCity();
      } else if (nodeId === 'location' && level === 'interior') {
        onReturnLocation();
      }
    },
    [level, onReturnCity, onReturnLocation],
  );

  return (
    <section className="sw-openflipbook-shell" aria-label={`${location.name} OpenFlipbook 交互画页`}>
      <div className="sw-openflipbook-stage">
        <div className="sw-openflipbook-toolbar">
          <div className="sw-openflipbook-trail">
            <button
              type="button"
              aria-label={level === 'interior' ? '返回地点画页' : '返回贵阳地图'}
              onClick={level === 'interior' ? onReturnLocation : onReturnCity}
            >
              ←
            </button>
            <Breadcrumb crumbs={crumbs} onJump={jumpBreadcrumb} />
          </div>
          <div className="sw-openflipbook-meta">
            <span>IMAGE IS THE UI</span>
            <strong>{level === 'campus' ? '01' : '02'}</strong>
          </div>
        </div>

        <figure className="sw-openflipbook-figure" data-atmosphere={location.scene.atmosphere}>
          <div
            ref={viewportRef}
            className="sw-openflipbook-viewport"
            onClick={clickCanvas}
            onPointerMove={movePointer}
            onPointerLeave={resetParallax}
          >
            <div className="sw-openflipbook-scene-plane">
              <div className="sw-openflipbook-scene-drift">
                <MorphImagePair
                  imgRef={imgRef}
                  imageDataUrl={imageUrl}
                  imageFit={IMAGE_FIT}
                  alt={`${location.name}${level === 'interior' ? ` ${building}` : ''}手绘交互画页`}
                  morphFx={null}
                  onError={() => setFailedImageUrl(imageUrl)}
                  newImageClassName={
                    'sw-openflipbook-live-image absolute inset-0 block h-full w-full select-none ' +
                    (phase === 'transition' ? 'cursor-wait' : 'cursor-none')
                  }
                  onMorphTransitionEnd={() => {}}
                />

                <EnterableMarkers markers={hotspots} imgRef={imgRef} imageFit={IMAGE_FIT} />
                <div className="pointer-events-none absolute inset-0 z-10">
                  {hotspots.map((hotspot, index) => {
                    const left = imageContent
                      ? `${imageContent.offsetX + hotspot.xPct * imageContent.width}px`
                      : `${hotspot.xPct * 100}%`;
                    const top = imageContent
                      ? `${imageContent.offsetY + hotspot.yPct * imageContent.height}px`
                      : `${hotspot.yPct * 100}%`;
                    return (
                      <button
                        key={hotspot.id}
                        type="button"
                        className={`sw-openflipbook-hotspot ${index % 3 === 0 || index === 4 ? 'is-coral' : 'is-cobalt'} ${activeRoom === index ? 'is-active' : ''}`}
                        style={{ left, top }}
                        onClick={(event) => {
                          event.stopPropagation();
                          chooseHotspot(hotspot, index);
                        }}
                        aria-label={`${level === 'campus' ? '进入' : '查看'} ${hotspot.label}`}
                        aria-pressed={level === 'interior' ? activeRoom === index : undefined}
                      >
                        <span>{hotspot.label}</span>
                      </button>
                    );
                  })}
                </div>

                <EntityHoverOverlay
                  agents={positionedAgents}
                  imgRef={imgRef}
                  imageFit={IMAGE_FIT}
                  selectedAgentId={selectedAgentId}
                  onSelect={onAgentSelect}
                />
                {hoverPos && phase === 'ready' ? <HoverCrosshair {...hoverPos} /> : null}
                {clickRipple ? (
                  <ClickRipple
                    rippleKey={clickRipple.key}
                    xPx={clickRipple.xPx}
                    yPx={clickRipple.yPx}
                  />
                ) : null}
                {blankTap ? <BlankTapNudge nudgeKey={blankTap.key} xPx={blankTap.xPx} yPx={blankTap.yPx} /> : null}
              </div>
            </div>

            <div className="sw-openflipbook-atmosphere" aria-hidden>
              <i />
              <i />
              <i />
            </div>
            <div className="sw-openflipbook-light-sweep" aria-hidden />
            <div className="sw-openflipbook-grain" aria-hidden />

            <span className="sw-openflipbook-world-badge pointer-events-none absolute z-20 select-none">
              <i aria-hidden />
              <span>贵阳世界 · 动态画页</span>
            </span>
            <span className="sw-openflipbook-scene-badge pointer-events-none absolute z-20 select-none">
              <i aria-hidden />
              <span>OpenFlipbook 场景引擎</span>
            </span>

            {failedImageUrl === imageUrl ? (
              <div className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center bg-black/70 p-6 text-center text-sm text-white">
                贵阳画页加载失败，请刷新后重试。
              </div>
            ) : null}
            {activeRoom !== null ? (
              <aside className="sw-openflipbook-room-card">
                <span>当前空间</span>
                <strong>{interiorProfile.rooms[activeRoom]}</strong>
                <p>{interiorProfile.activity}</p>
                <small>{interiorProfile.count} 个活动体 · 承载 {interiorProfile.capacity} 人</small>
              </aside>
            ) : null}
            {phase === 'ready' ? (
              <TapHint text="移动鼠标探索景深 · 点击光圈进入下一页 · 点击人物查看状态" />
            ) : null}

            {pendingTransition ? (
              <DescentVideoTransition
                videoUrl={pendingTransition.videoUrl}
                posterUrl={imageUrl}
                destinationUrl={pendingTransition.destinationUrl}
                destinationLabel={pendingTransition.building}
                onFinish={completeDescent}
              />
            ) : null}
          </div>
        </figure>

        <footer className="sw-openflipbook-footer">
          <div>
            <span>{level === 'campus' ? '地点画页' : '具体场景 · 独立画页'}</span>
            <strong>{level === 'campus' ? location.scene.architecture : building}</strong>
            <small>{level === 'campus' ? location.scene.signature : interiorProfile.activity}</small>
          </div>
          <small>{level === 'interior' ? `${interiorProfile.openHours} · ${interiorProfile.transition}` : location.description}</small>
        </footer>
      </div>
    </section>
  );
}
