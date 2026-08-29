'use client';

/**
 * QianScope's Guiyang adapter for OpenFlipbook's /play world-mode surface.
 *
 * Unlike the retired scene adapter, this component is page-graph first: every
 * visible image is a world node with a SceneView, a numeric geometry frame and
 * a parent/scale relation. Pointer routing, projection, morphing, beacons,
 * labels, breadcrumbs and the atlas are sourced from OpenFlipbook b3e5044.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react';

import {
  activeGuiyangPage,
  agentsForPage,
  buildingFromGeo,
  interiorPage,
  locationFromGeo,
  locationPage,
  rootPage,
  type FlipbookInteriorProfile,
  type GuiyangFlipbookPage,
} from '@/lib/openflipbook-world';
import {
  WORLD_LOCATIONS,
  type WorldAgent,
  type WorldLevel,
  type WorldLocation,
} from '@/lib/social-world-fixtures';
import { BlankTapNudge } from '@/vendor/openflipbook/components/PlayPage/BlankTapNudge';
import { BranchBeacons } from '@/vendor/openflipbook/components/PlayPage/BranchBeacons';
import Breadcrumb from '@/vendor/openflipbook/components/PlayPage/Breadcrumb';
import { ClickRipple } from '@/vendor/openflipbook/components/PlayPage/ClickRipple';
import { EnterableMarkers } from '@/vendor/openflipbook/components/PlayPage/EnterableMarkers';
import { EntityHoverOverlay } from '@/vendor/openflipbook/components/PlayPage/EntityHoverOverlay';
import { GeneratingBanner } from '@/vendor/openflipbook/components/PlayPage/GeneratingBanner';
import { HoverCrosshair } from '@/vendor/openflipbook/components/PlayPage/HoverCrosshair';
import { MorphImagePair } from '@/vendor/openflipbook/components/PlayPage/MorphImagePair';
import SpatialPath from '@/vendor/openflipbook/components/PlayPage/SpatialPath';
import { TapHint } from '@/vendor/openflipbook/components/PlayPage/TapHint';
import WorldMap from '@/vendor/openflipbook/components/WorldMap';
import { useContainRect } from '@/vendor/openflipbook/hooks/useContainRect';
import { useImageMorph } from '@/vendor/openflipbook/hooks/useImageMorph';
import { buildBreadcrumb } from '@/vendor/openflipbook/lib/breadcrumb';
import { focusOnMap, routeClick } from '@/vendor/openflipbook/lib/click-route';
import { REGION_FRAC, diveOriginPx } from '@/vendor/openflipbook/lib/image-condition';
import {
  normalizeClickOnImage,
  objectFitRect,
  type NormalizedClick,
} from '@/vendor/openflipbook/lib/image-click';
import { emit as hudEmit, nowMs } from '@/vendor/openflipbook/lib/trace';

type PlayPhase = 'ready' | 'generating';
type HoverState = { xPx: number; yPx: number; enterable: boolean };
type TapFeedback = { xPx: number; yPx: number; key: number };
type RoomFocus = { id: string; label: string; index: number };

type Props = {
  level: WorldLevel;
  location: WorldLocation;
  building: string;
  floor: number;
  selectedAgentId?: string;
  interiorProfile: FlipbookInteriorProfile;
  getInteriorProfile: (building: string, floor: number) => FlipbookInteriorProfile;
  onAgentSelect: (agent: WorldAgent) => void;
  onNavigate: (page: GuiyangFlipbookPage) => void;
  onFloorChange: (floor: number) => void;
};

const IMAGE_FIT = 'cover' as const;
const ROUTING_FRAME = { x: 0, y: 0, w: 100, h: 60 } as const;

function mergePages(...groups: GuiyangFlipbookPage[][]): GuiyangFlipbookPage[] {
  const pages = new Map<string, GuiyangFlipbookPage>();
  for (const page of groups.flat()) pages.set(page.nodeId, page);
  return [...pages.values()];
}

function pointInCanvas(img: HTMLImageElement, click: NormalizedClick) {
  const content = objectFitRect(
    img.clientWidth,
    img.clientHeight,
    img.naturalWidth,
    img.naturalHeight,
    IMAGE_FIT,
  );
  if (!content) {
    return { x: click.x_pct * img.clientWidth, y: click.y_pct * img.clientHeight };
  }
  return {
    x: content.offsetX + click.x_pct * content.width,
    y: content.offsetY + click.y_pct * content.height,
  };
}

export function OpenFlipbookPlayWorld({
  level,
  location,
  building,
  floor,
  selectedAgentId,
  interiorProfile,
  getInteriorProfile,
  onAgentSelect,
  onNavigate,
  onFloorChange,
}: Props) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const timersRef = useRef<number[]>([]);
  const activePage = useMemo(
    () => activeGuiyangPage(level, location, building, floor, interiorProfile),
    [building, floor, interiorProfile, level, location],
  );
  const imageContent = useContainRect(imgRef, IMAGE_FIT);
  const { morphFx, setMorphFx } = useImageMorph(activePage.imageDataUrl);
  const [phase, setPhase] = useState<PlayPhase>('ready');
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [hoverPos, setHoverPos] = useState<HoverState | null>(null);
  const [clickRipple, setClickRipple] = useState<TapFeedback | null>(null);
  const [blankTap, setBlankTap] = useState<TapFeedback | null>(null);
  const [roomFocus, setRoomFocus] = useState<RoomFocus | null>(null);
  const [atlasOpen, setAtlasOpen] = useState(false);
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  const [storedPages, setStoredPages] = useState<GuiyangFlipbookPage[]>(() => [rootPage()]);

  const parentPage = level === 'interior' ? locationPage(location) : null;
  const pages = useMemo(
    () => mergePages([rootPage()], parentPage ? [parentPage] : [], storedPages, [activePage]),
    [activePage, parentPage, storedPages],
  );
  const pagesById = useMemo(() => new Map(pages.map((page) => [page.nodeId, page])), [pages]);
  const crumbs = useMemo(
    () => buildBreadcrumb(activePage.nodeId, pages.map((page) => ({ nodeId: page.nodeId, parentId: page.parentId, title: page.title }))),
    [activePage.nodeId, pages],
  );
  const positionedAgents = useMemo(() => agentsForPage(activePage), [activePage]);
  const sceneViews = useMemo(
    () => Object.fromEntries(pages.map((page) => [page.nodeId, page.sceneView])),
    [pages],
  );
  const roomIndex = roomFocus ? activePage.entities.findIndex((entity) => entity.id === roomFocus.id) : -1;

  useEffect(() => () => {
    for (const timer of timersRef.current) window.clearTimeout(timer);
  }, []);

  const rememberPage = useCallback((page: GuiyangFlipbookPage) => {
    const additions = page.level === 'interior'
      ? [rootPage(), locationPage(WORLD_LOCATIONS.find((item) => item.id === page.locationId) ?? location), page]
      : page.level === 'campus'
        ? [rootPage(), page]
        : [page];
    setStoredPages((current) => mergePages(current, additions));
  }, [location]);

  const clearTimers = useCallback(() => {
    for (const timer of timersRef.current) window.clearTimeout(timer);
    timersRef.current = [];
  }, []);

  const beginTransition = useCallback((
    target: GuiyangFlipbookPage,
    click: NormalizedClick,
    label: string,
  ) => {
    if (phase === 'generating') return;
    const img = imgRef.current;
    if (!img) {
      rememberPage(target);
      onNavigate(target);
      return;
    }
    clearTimers();
    const content = objectFitRect(
      img.clientWidth,
      img.clientHeight,
      img.naturalWidth,
      img.naturalHeight,
      IMAGE_FIT,
    );
    const fallback = pointInCanvas(img, click);
    const origin = content
      ? diveOriginPx(click.x_pct, click.y_pct, REGION_FRAC, content)
      : fallback;
    const startedAt = nowMs();
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setBlankTap(null);
    setRoomFocus(null);
    setClickRipple({ xPx: origin.x, yPx: origin.y, key: Date.now() });
    setStatusMsg(`正在解析 ${label} 的世界坐标…`);
    setPhase('generating');
    setMorphFx({
      ox: origin.x,
      oy: origin.y,
      prevImg: activePage.imageDataUrl,
      nextImg: null,
      phase: 'wait',
      isFinal: false,
      startedAt,
      reduceMotion,
      dive: true,
    });
    hudEmit('morph:start', { t: startedAt, x_pct: click.x_pct, y_pct: click.y_pct });

    timersRef.current.push(window.setTimeout(() => setStatusMsg('正在投影 2.5D 场景与可进入实体…'), 150));
    timersRef.current.push(window.setTimeout(() => {
      rememberPage(target);
      onNavigate(target);
      setStatusMsg(`正在载入 ${target.title} 画页…`);
    }, reduceMotion ? 40 : 360));
    timersRef.current.push(window.setTimeout(() => {
      setMorphFx((previous) => (previous ? { ...previous, isFinal: true } : previous));
    }, reduceMotion ? 80 : 460));
    timersRef.current.push(window.setTimeout(() => {
      setPhase('ready');
      setStatusMsg(null);
      setClickRipple(null);
    }, reduceMotion ? 220 : 1040));
  }, [activePage.imageDataUrl, clearTimers, onNavigate, phase, rememberPage, setMorphFx]);

  const navigateToKnownPage = useCallback((target: GuiyangFlipbookPage) => {
    setAtlasOpen(false);
    setRoomFocus(null);
    rememberPage(target);
    onNavigate(target);
  }, [onNavigate, rememberPage]);

  const activateAt = useCallback((click: NormalizedClick) => {
    const img = imgRef.current;
    if (!img || phase === 'generating') return;
    const point = pointInCanvas(img, click);
    const routingView = {
      node_id: activePage.nodeId,
      level: 'map' as const,
      observer: null,
      map_crop: { ...ROUTING_FRAME },
      focus_id: activePage.sceneView.focus_id ?? null,
      scale_tier: activePage.sceneView.scale_tier,
    };
    const route = routeClick(
      { entities: activePage.entities, bounds: { ...ROUTING_FRAME } },
      routingView,
      click,
      16 / 9,
      { enterDirect: true },
    );
    if (route.kind !== 'scene') {
      setBlankTap({ xPx: point.x, yPx: point.y, key: Date.now() });
      return;
    }

    if (activePage.level === 'city') {
      const nextLocation = locationFromGeo(route.focus_id);
      if (!nextLocation) return;
      beginTransition(locationPage(nextLocation), click, nextLocation.short);
      return;
    }
    if (activePage.level === 'campus') {
      const nextBuilding = buildingFromGeo(location, route.focus_id);
      if (!nextBuilding) return;
      beginTransition(interiorPage(location, nextBuilding, 1, getInteriorProfile(nextBuilding, 1)), click, nextBuilding);
      return;
    }

    const entity = activePage.entities.find((item) => item.id === route.focus_id);
    if (!entity) return;
    const index = activePage.entities.indexOf(entity);
    setClickRipple({ xPx: point.x, yPx: point.y, key: Date.now() });
    setRoomFocus({ id: entity.id, label: entity.label, index });
  }, [activePage, beginTransition, getInteriorProfile, location, phase]);

  function onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const img = imgRef.current;
    if (!img || phase === 'generating') return;
    const click = normalizeClickOnImage(event.nativeEvent, img, IMAGE_FIT);
    if (!click) {
      setHoverPos(null);
      return;
    }
    const point = pointInCanvas(img, click);
    const focus = focusOnMap(activePage.entities, ROUTING_FRAME, click);
    setHoverPos({ xPx: point.x, yPx: point.y, enterable: focus?.kind === 'place' });
    const viewport = viewportRef.current;
    if (viewport) {
      viewport.style.setProperty('--sw-shift-x', `${(0.5 - click.x_pct) * 13}px`);
      viewport.style.setProperty('--sw-shift-y', `${(0.5 - click.y_pct) * 9}px`);
    }
  }

  function onPointerLeave() {
    setHoverPos(null);
    const viewport = viewportRef.current;
    viewport?.style.setProperty('--sw-shift-x', '0px');
    viewport?.style.setProperty('--sw-shift-y', '0px');
  }

  function onCanvasClick(event: ReactPointerEvent<HTMLDivElement>) {
    const img = imgRef.current;
    if (!img) return;
    const click = normalizeClickOnImage(event.nativeEvent, img, IMAGE_FIT);
    if (click) activateAt(click);
  }

  function goBack() {
    if (roomFocus) {
      setRoomFocus(null);
      return;
    }
    const parent = activePage.parentId ? pagesById.get(activePage.parentId) : null;
    if (parent) navigateToKnownPage(parent);
  }

  return (
    <section className="sw-openflipbook-shell sw-ofb-play-root" aria-label="贵阳 OpenFlipbook 世界模式">
      <div className="sw-openflipbook-stage">
        <div className="sw-openflipbook-toolbar">
          <div className="sw-openflipbook-trail">
            <button type="button" aria-label="返回上一层画页" disabled={!activePage.parentId && !roomFocus} onClick={goBack}>←</button>
            <div className="sw-ofb-nav-stack">
              {crumbs.length === 1 ? (
                <div className="sw-ofb-root-path"><strong>{activePage.title}</strong><span>{activePage.subtitle}</span></div>
              ) : (
                <>
                  <Breadcrumb crumbs={crumbs} onJump={(nodeId) => {
                    const page = pagesById.get(nodeId);
                    if (page) navigateToKnownPage(page);
                  }} />
                  <SpatialPath crumbs={crumbs} onNavigate={(nodeId) => {
                    const page = pagesById.get(nodeId);
                    if (page) navigateToKnownPage(page);
                  }} />
                </>
              )}
            </div>
          </div>
          <div className="sw-ofb-toolbar-actions">
            <button type="button" className={atlasOpen ? 'active' : ''} onClick={() => setAtlasOpen((value) => !value)}>画页图谱</button>
            <div className="sw-openflipbook-meta"><span>{activePage.sceneView.scale_tier?.toUpperCase()} · 2.5D</span><strong>{pages.length}</strong></div>
          </div>
        </div>

        <figure className="sw-openflipbook-figure" data-atmosphere={level === 'city' ? 'world-map' : location.scene.atmosphere}>
          <div
            ref={viewportRef}
            className="sw-openflipbook-viewport"
            onPointerMove={onPointerMove}
            onPointerLeave={onPointerLeave}
            onPointerDown={onCanvasClick}
          >
            <div className="sw-openflipbook-scene-plane">
              <div className="sw-openflipbook-scene-drift">
                <MorphImagePair
                  imgRef={imgRef}
                  imageDataUrl={activePage.imageDataUrl}
                  alt={`${activePage.title} OpenFlipbook 画页`}
                  morphFx={morphFx}
                  imageFit={IMAGE_FIT}
                  onError={() => setFailedImageUrl(activePage.imageDataUrl)}
                  newImageClassName={`sw-openflipbook-live-image absolute inset-0 block h-full w-full select-none ${morphFx ? 'ec-morph-new ' : ''}${phase === 'generating' ? 'cursor-wait' : 'cursor-none'}`}
                  onMorphTransitionEnd={(event) => {
                    if (!['mask-size', '-webkit-mask-size', 'opacity'].includes(event.propertyName)) return;
                    setMorphFx((previous) => {
                      if (!previous || previous.phase !== 'reveal') return previous;
                      hudEmit('morph:end', { duration_ms: nowMs() - previous.startedAt, t: nowMs() });
                      return null;
                    });
                  }}
                />
              </div>
            </div>

            <div className="sw-openflipbook-atmosphere" aria-hidden><i /><i /><i /></div>
            <div className="sw-openflipbook-light-sweep" aria-hidden />
            <div className="sw-openflipbook-grain" aria-hidden />

            <EnterableMarkers
              entities={activePage.entities}
              currentView={activePage.level === 'interior' ? null : activePage.sceneView}
              imgRef={imgRef}
              prominent
            />
            <EntityHoverOverlay
              agents={positionedAgents}
              imgRef={imgRef}
              imageFit={IMAGE_FIT}
              selectedAgentId={selectedAgentId}
              onSelect={onAgentSelect}
            />

            {hoverPos && phase === 'ready' ? <HoverCrosshair {...hoverPos} /> : null}
            {clickRipple ? <ClickRipple rippleKey={clickRipple.key} xPx={clickRipple.xPx} yPx={clickRipple.yPx} /> : null}
            {blankTap ? <BlankTapNudge nudgeKey={blankTap.key} xPx={blankTap.xPx} yPx={blankTap.yPx} /> : null}

            {activePage.entities.map((entity, index) => {
              const left = imageContent
                ? imageContent.offsetX + (entity.pos.x / ROUTING_FRAME.w) * imageContent.width
                : (entity.pos.x / ROUTING_FRAME.w) * 100;
              const top = imageContent
                ? imageContent.offsetY + (entity.pos.y / ROUTING_FRAME.h) * imageContent.height
                : (entity.pos.y / ROUTING_FRAME.h) * 100;
              return (
                <button
                  type="button"
                  key={entity.id}
                  className={`sw-ofb-map-label ${index % 2 === 0 ? 'is-cobalt' : 'is-coral'} ${roomFocus?.id === entity.id ? 'is-active' : ''}`}
                  style={imageContent ? { left: `${left}px`, top: `${top}px` } : { left: `${left}%`, top: `${top}%` }}
                  onPointerDown={(event) => {
                    event.stopPropagation();
                    activateAt({ x_pct: entity.pos.x / ROUTING_FRAME.w, y_pct: entity.pos.y / ROUTING_FRAME.h });
                  }}
                >
                  {entity.label}
                </button>
              );
            })}

            {activePage.level !== 'interior' ? (
              <BranchBeacons
                beacons={pages
                  .filter((page) => page.parentId === activePage.nodeId && page.clickInParent)
                  .map((page) => ({ nodeId: page.nodeId, title: page.title, clickInParent: page.clickInParent! }))}
                onSelect={(nodeId) => {
                  const page = pagesById.get(nodeId);
                  if (page) navigateToKnownPage(page);
                }}
              />
            ) : null}

            {phase === 'generating' ? <GeneratingBanner statusMsg={statusMsg} /> : null}
            {failedImageUrl === activePage.imageDataUrl ? <div className="sw-ofb-image-error">画页载入失败，请刷新重试。</div> : null}

            <span className="sw-openflipbook-world-badge pointer-events-none absolute z-20 select-none"><i />WORLD MODE · GUIYANG</span>
            <span className="sw-openflipbook-scene-badge pointer-events-none absolute z-20 select-none"><i />{activePage.sceneView.view?.projection ?? 'oblique'} · {activePage.entities.length} 个空间实体</span>

            {roomFocus ? (
              <aside className="sw-openflipbook-room-card">
                <span>SCENE ENTITY · {String(roomIndex + 1).padStart(2, '0')}</span>
                <strong>{roomFocus.label}</strong>
                <p>{interiorProfile.activity}</p>
                <small>{interiorProfile.count} 人活动中 · {interiorProfile.openHours}</small>
                <button type="button" onClick={() => setRoomFocus(null)}>关闭</button>
              </aside>
            ) : null}

            {phase === 'ready' ? <TapHint text={activePage.level === 'interior' ? '移动鼠标观察空间 · 点击光圈查看场景实体 · 点击人物访谈' : '移动鼠标观察 2.5D 世界 · 点击光圈进入地点'} /> : null}
          </div>
        </figure>

        <footer className="sw-openflipbook-footer">
          <div><span>OPENFLIPBOOK PAGE · {activePage.nodeId}</span><strong>{activePage.title}</strong><small>{activePage.subtitle}</small></div>
          {activePage.level === 'interior' ? <nav aria-label="楼层切换">{[1, 2, 3, 4, 5].map((item) => <button type="button" className={floor === item ? 'active' : ''} key={item} onClick={() => onFloorChange(item)}>{item}F</button>)}</nav> : null}
        </footer>
      </div>

      {atlasOpen ? (
        <div className="sw-ofb-atlas-overlay" role="dialog" aria-modal="true" aria-label="OpenFlipbook 画页图谱">
          <WorldMap
            pages={pages.map((page) => ({
              nodeId: page.nodeId,
              parentId: page.parentId,
              imageDataUrl: page.imageDataUrl,
              title: page.title,
              relation: page.relation,
              scale: page.scale,
              ...(page.clickInParent ? { clickInParent: page.clickInParent } : {}),
            }))}
            activeNodeId={activePage.nodeId}
            sceneViews={sceneViews}
            onSelect={(nodeId) => {
              const page = pagesById.get(nodeId);
              if (page) navigateToKnownPage(page);
            }}
            onClose={() => setAtlasOpen(false)}
          />
        </div>
      ) : null}
    </section>
  );
}
