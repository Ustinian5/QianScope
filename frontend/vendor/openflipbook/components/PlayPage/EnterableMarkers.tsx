"use client";

import { useMemo, type RefObject } from "react";
import type { MapCrop, SceneView, WorldEntityGeo } from "../../config/world";

import { useContainRect } from "../../hooks/useContainRect";
import { MAP_IMAGE_FRAME } from "../../lib/geo-tap";
import { cropEntities, toAbsoluteEntities } from "../../lib/world-geometry";

interface Props {
  /** The geo world map's entities (all of them; this component scopes). */
  entities: WorldEntityGeo[];
  /** The frame the page shows. Markers render only on map frames
   *  (null = the top-level map; a submap carries its crop). */
  currentView: SceneView | null;
  /** The rendered <img>; markers track the object-contain content rect. */
  imgRef?: RefObject<HTMLImageElement | null>;
  /** Flag-gated (NEXT_PUBLIC_ENTER_COACH): a louder, ping-animated ring. The
   *  default subtle ring is lost next to the bold DOM labels — the blind UX
   *  bench saw labels but not the rings the coach copy points at. */
  prominent?: boolean;
}

/**
 * Idle-state enter affordance (W3). A soft pulsing ring on every ENTERABLE
 * place of the current map frame, so "tap = enter a place" is discoverable
 * before the first click — previously only revealed by ⌘-tap. Pure
 * decoration: pointer events pass through to the image's own tap handler,
 * and world OFF never mounts it (the parent gates), so classic exploration
 * is pixel-identical.
 */
export function EnterableMarkers({
  entities,
  currentView,
  imgRef,
  prominent = false,
}: Props) {
  const content = useContainRect(imgRef);
  const markers = useMemo(() => {
    // Inside an entered place the frame is a scene, not the map — no rings.
    if (currentView && currentView.level !== "map") return [];
    const frame: MapCrop = currentView?.map_crop ?? MAP_IMAGE_FRAME;
    // Nested places resolve through their parent chain to the absolute map
    // frame (after an OUTWARD ascend every former root is nested — the old
    // top-level-only filter blanked the whole map); the crop culls whatever
    // resolves outside the displayed window.
    const places = toAbsoluteEntities(
      entities.filter((e) => e.kind === "place"),
      entities,
    );
    return cropEntities(places, frame).map((e) => ({
      id: e.id,
      label: e.label,
      xPct: (e.pos.x - frame.x) / frame.w,
      yPct: (e.pos.y - frame.y) / frame.h,
    }));
  }, [entities, currentView]);

  if (markers.length === 0) return null;

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-10">
      {markers.map((m, index) => {
        const left = content
          ? `${content.offsetX + m.xPct * content.width}px`
          : `${m.xPct * 100}%`;
        const top = content
          ? `${content.offsetY + m.yPct * content.height}px`
          : `${m.yPct * 100}%`;
        return (
          <span
            key={m.id}
            data-entity-id={m.id}
            data-prominent={prominent ? "1" : undefined}
            title={m.label}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left, top }}
          >
            {prominent ? (
              // Louder affordance: an expanding ping ring + a solid glowing
              // core so "tap a glowing place" has something that visibly glows.
              <span className={`sw-ofb-enter-marker ${index % 2 === 0 ? "is-cobalt" : "is-coral"} relative flex h-7 w-7`}>
                <span className="sw-ofb-enter-ping absolute inline-flex h-full w-full rounded-full" />
                <span className="sw-ofb-enter-core relative inline-flex h-7 w-7 rounded-full border-2" />
              </span>
            ) : (
              <span className={`sw-ofb-enter-marker ${index % 2 === 0 ? "is-cobalt" : "is-coral"} block h-5 w-5 rounded-full border-2`} />
            )}
          </span>
        );
      })}
    </div>
  );
}
