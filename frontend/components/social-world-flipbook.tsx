'use client';

/**
 * Guiyang content adapter for OpenFlipbook's image-is-the-UI play surface.
 *
 * The canvas structure, object-contain click math, two-image morph, focus dive,
 * radial ink reveal, hover crosshair, enterable markers, entity chips and
 * feedback overlays come directly from OpenFlipbook commit b3e5044 (MIT) via
 * `frontend/vendor/openflipbook`. This file only maps the existing Guiyang
 * locations, rooms and stable agents onto those upstream primitives.
 */
import {
  useCallback,
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
import { EnterableMarkers } from '@/vendor/openflipbook/components/PlayPage/EnterableMarkers';
import { EntityHoverOverlay } from '@/vendor/openflipbook/components/PlayPage/EntityHoverOverlay';
import { GeneratingBanner } from '@/vendor/openflipbook/components/PlayPage/GeneratingBanner';
import { HoverCrosshair } from '@/vendor/openflipbook/components/PlayPage/HoverCrosshair';
import { MorphImagePair } from '@/vendor/openflipbook/components/PlayPage/MorphImagePair';
import { TapHint } from '@/vendor/openflipbook/components/PlayPage/TapHint';
import { useImageMorph } from '@/vendor/openflipbook/hooks/useImageMorph';
import { REGION_FRAC, diveOriginPx } from '@/vendor/openflipbook/lib/image-condition';
import {
  normalizeClickOnImage,
  objectContainRect,
  type NormalizedClick,
} from '@/vendor/openflipbook/lib/image-click';
import { emit as hudEmit, nowMs } from '@/vendor/openflipbook/lib/trace';

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
  floor: number;
  selectedAgentId?: string;
  interiorProfile: FlipbookInteriorProfile;
  onAgentSelect: (agent: WorldAgent) => void;
  onEnterInterior: (building: string) => void;
  onFloorChange: (floor: number) => void;
  onReturnCity: () => void;
  onReturnLocation: () => void;
};

type HoverState = { xPx: number; yPx: number; enterable: boolean };
type TapFeedback = { xPx: number; yPx: number; key: number };
type RoomFocus = { pageKey: string; index: number };

const HIT_RADIUS = 0.115;

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
  const content = objectContainRect(
    img.clientWidth,
    img.clientHeight,
    img.naturalWidth,
    img.naturalHeight,
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
  floor,
  selectedAgentId,
  interiorProfile,
  onAgentSelect,
  onEnterInterior,
  onFloorChange,
  onReturnCity,
  onReturnLocation,
}: SocialWorldFlipbookProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const imageUrl = sceneImageUrl(location.id, level, floor);
  const pageKey = `${location.id}:${level}:${building}:${floor}`;
  const { morphFx, setMorphFx } = useImageMorph(imageUrl);
  const [phase, setPhase] = useState<'ready' | 'generating'>('ready');
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [hoverPos, setHoverPos] = useState<HoverState | null>(null);
  const [clickRipple, setClickRipple] = useState<TapFeedback | null>(null);
  const [blankTap, setBlankTap] = useState<TapFeedback | null>(null);
  const [roomFocus, setRoomFocus] = useState<RoomFocus | null>(null);
  const [imgFailed, setImgFailed] = useState(false);

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
      items.push({ nodeId: 'interior', title: `${building} · ${floor}F` });
    }
    return items;
  }, [building, floor, level, location.short]);

  const beginMorph = useCallback(
    (xPct: number, yPct: number, nextLabel: string, navigate: () => void) => {
      if (phase === 'generating') return;
      const img = imgRef.current;
      if (!img) {
        navigate();
        return;
      }
      const content = objectContainRect(
        img.clientWidth,
        img.clientHeight,
        img.naturalWidth,
        img.naturalHeight,
      );
      const fallbackOrigin = pointInCanvas(img, xPct, yPct);
      const origin = content
        ? diveOriginPx(xPct, yPct, REGION_FRAC, content)
        : { x: fallbackOrigin.xPx, y: fallbackOrigin.yPx };
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const startedAt = nowMs();
      setBlankTap(null);
      setClickRipple({ xPx: origin.x, yPx: origin.y, key: Date.now() });
      setStatusMsg(`正在进入 ${nextLabel}…`);
      setPhase('generating');
      setMorphFx({
        ox: origin.x,
        oy: origin.y,
        prevImg: imageUrl,
        nextImg: null,
        phase: 'wait',
        isFinal: false,
        startedAt,
        reduceMotion,
        dive: true,
      });
      hudEmit('morph:start', { t: startedAt, x_pct: xPct, y_pct: yPct });
      navigate();
      window.setTimeout(() => {
        setMorphFx((previous) => (previous ? { ...previous, isFinal: true } : previous));
      }, 90);
    },
    [imageUrl, phase, setMorphFx],
  );

  const chooseHotspot = useCallback(
    (hotspot: FlipbookHotspot, index: number) => {
      if (level === 'campus') {
        beginMorph(hotspot.xPct, hotspot.yPct, hotspot.label, () =>
          onEnterInterior(hotspot.label),
        );
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
    [beginMorph, level, onEnterInterior, pageKey],
  );

  const clickCanvas = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (phase === 'generating' || !imgRef.current) return;
      if ((event.target as HTMLElement).closest('button')) return;
      const click = normalizeClickOnImage(event.nativeEvent, imgRef.current);
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

  const movePointer = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (phase === 'generating' || !imgRef.current) return;
      const click = normalizeClickOnImage(event.nativeEvent, imgRef.current);
      if (!click) {
        setHoverPos(null);
        return;
      }
      const point = pointInCanvas(imgRef.current, click.x_pct, click.y_pct);
      setHoverPos({ ...point, enterable: nearestHotspot(click, hotspots) !== null });
    },
    [hotspots, phase],
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

  const changeFloor = useCallback(
    (nextFloor: number) => {
      if (nextFloor === floor) return;
      beginMorph(0.5, 0.5, `${nextFloor}F`, () => onFloorChange(nextFloor));
    },
    [beginMorph, floor, onFloorChange],
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
            <strong>{level === 'campus' ? '01' : String(floor + 1).padStart(2, '0')}</strong>
          </div>
        </div>

        <figure className="sw-openflipbook-figure">
          <div
            className="relative aspect-[16/9] h-full w-full"
            onClick={clickCanvas}
            onPointerMove={movePointer}
            onPointerLeave={() => setHoverPos(null)}
          >
            <MorphImagePair
              imgRef={imgRef}
              imageDataUrl={imageUrl}
              alt={`${location.name}${level === 'interior' ? ` ${building} ${floor}层` : ''}手绘交互画页`}
              morphFx={morphFx}
              onError={() => setImgFailed(true)}
              newImageClassName={
                'absolute inset-0 block h-full w-full object-contain select-none ' +
                (morphFx ? 'ec-morph-new ' : '') +
                (phase === 'generating' ? 'cursor-wait' : 'cursor-none')
              }
              onMorphTransitionEnd={(event) => {
                if (!['mask-size', '-webkit-mask-size', 'opacity'].includes(event.propertyName)) {
                  return;
                }
                setMorphFx((previous) => {
                  if (!previous || previous.phase !== 'reveal') return previous;
                  hudEmit('morph:end', { duration_ms: nowMs() - previous.startedAt, t: nowMs() });
                  return null;
                });
                setPhase('ready');
                setStatusMsg(null);
                setClickRipple(null);
              }}
            />

            <span className="pointer-events-none absolute start-3 top-3 z-20 flex select-none items-center gap-1 rounded-full border border-emerald-700/40 bg-emerald-50/85 px-2.5 py-1 text-xs font-medium text-emerald-900 backdrop-blur">
              <span aria-hidden>🌍</span>
              <span>贵阳世界 · 点击进入地点</span>
            </span>
            <span className="pointer-events-none absolute bottom-3 start-3 z-20 flex select-none items-center gap-1 rounded-full border border-amber-400/70 bg-amber-100/80 px-2.5 py-1 text-xs font-medium text-amber-900 backdrop-blur">
              <span aria-hidden>📌</span>
              <span>贵阳手绘风格已锁定</span>
            </span>

            <EnterableMarkers markers={hotspots} imgRef={imgRef} />
            <div className="pointer-events-none absolute inset-0 z-10">
              {hotspots.map((hotspot, index) => (
                <button
                  key={hotspot.id}
                  type="button"
                  className={`sw-openflipbook-hotspot ${activeRoom === index ? 'is-active' : ''}`}
                  style={{ left: `${hotspot.xPct * 100}%`, top: `${hotspot.yPct * 100}%` }}
                  onClick={(event) => {
                    event.stopPropagation();
                    chooseHotspot(hotspot, index);
                  }}
                  aria-label={`${level === 'campus' ? '进入' : '查看'} ${hotspot.label}`}
                  aria-pressed={level === 'interior' ? activeRoom === index : undefined}
                >
                  <span>{hotspot.label}</span>
                </button>
              ))}
            </div>

            <EntityHoverOverlay
              agents={positionedAgents}
              imgRef={imgRef}
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
            {imgFailed ? (
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
            {phase === 'generating' ? <GeneratingBanner statusMsg={statusMsg} /> : null}
            {phase === 'ready' ? (
              <TapHint text="点击画面中的光圈进入下一页 · 点击白点查看人物" />
            ) : null}
          </div>
        </figure>

        <footer className="sw-openflipbook-footer">
          <div>
            <span>{level === 'campus' ? '地点画页' : `${floor}F · ${interiorProfile.floorName}`}</span>
            <strong>{level === 'campus' ? location.scene.architecture : building}</strong>
            <small>{level === 'campus' ? location.scene.signature : interiorProfile.activity}</small>
          </div>
          {level === 'interior' ? (
            <nav aria-label="楼层画页">
              {[1, 2, 3, 4, 5].map((item) => (
                <button
                  key={item}
                  type="button"
                  className={floor === item ? 'active' : ''}
                  aria-current={floor === item ? 'page' : undefined}
                  onClick={() => changeFloor(item)}
                  disabled={phase === 'generating'}
                >
                  {item}F
                </button>
              ))}
            </nav>
          ) : (
            <small>{location.description}</small>
          )}
        </footer>
      </div>
    </section>
  );
}
