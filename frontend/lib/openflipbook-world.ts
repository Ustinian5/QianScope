import {
  AGENT_ANCHORS,
  INTERIOR_ANCHORS,
  exteriorHotspots,
  sceneImageUrl,
} from '@/lib/openflipbook-guiyang';
import {
  SOCIAL_WORLD_CITY,
  WORLD_AGENTS,
  WORLD_LOCATIONS,
  type WorldAgent,
  type WorldLevel,
  type WorldLocation,
} from '@/lib/social-world-fixtures';
import type {
  NodeRelation,
  SceneView,
  ScaleKind,
  WorldEntityGeo,
} from '@/vendor/openflipbook/config/world';

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

export type GuiyangFlipbookPage = {
  nodeId: string;
  parentId: string | null;
  relation: NodeRelation;
  scale: ScaleKind;
  title: string;
  subtitle: string;
  imageDataUrl: string;
  level: WorldLevel;
  locationId: string | null;
  building: string | null;
  floor: number | null;
  sceneView: SceneView;
  entities: WorldEntityGeo[];
  clickInParent?: { xPct: number; yPct: number };
};

export const GUIYANG_WORLD_IMAGE = '/openflipbook/guiyang/guiyang-world-map.png';
export const OPENFLIPBOOK_FRAME = { x: 0, y: 0, w: 100, h: 60 } as const;

const UPDATED_AT = '2026-08-29T00:00:00.000Z';

const CITY_ANCHORS: Record<string, { xPct: number; yPct: number; w: number; d: number }> = {
  guiyang_convention: { xPct: 0.245, yPct: 0.315, w: 21, d: 11 },
  guiyang_big_data: { xPct: 0.54, yPct: 0.27, w: 17, d: 10 },
  guizhou_university: { xPct: 0.28, yPct: 0.50, w: 20, d: 11 },
  jiaxiu_tower: { xPct: 0.55, yPct: 0.655, w: 15, d: 9 },
  qingyan_town: { xPct: 0.17, yPct: 0.745, w: 20, d: 14 },
  guiyang_north_station: { xPct: 0.82, yPct: 0.22, w: 20, d: 10 },
  huaguoyuan: { xPct: 0.765, yPct: 0.49, w: 21, d: 16 },
};

function geoEntity({
  id,
  label,
  xPct,
  yPct,
  footprint,
  height,
  visual,
  parentId = null,
  scaleTier,
}: {
  id: string;
  label: string;
  xPct: number;
  yPct: number;
  footprint: { w: number; d: number };
  height: number;
  visual: string;
  parentId?: string | null;
  scaleTier: WorldEntityGeo['scale_tier'];
}): WorldEntityGeo {
  return {
    id,
    entity_id: id,
    parent_id: parentId,
    kind: 'place',
    label,
    pos: { x: xPct * OPENFLIPBOOK_FRAME.w, y: yPct * OPENFLIPBOOK_FRAME.h },
    height,
    footprint,
    scale_tier: scaleTier,
    visual,
    state: { status: 'active', city: '贵阳' },
    confidence: 1,
    source: 'user',
    updated_at: UPDATED_AT,
  };
}

export function locationGeoId(locationId: string): string {
  return `geo:guiyang:${locationId}`;
}

export function buildingGeoId(locationId: string, index: number): string {
  return `geo:guiyang:${locationId}:building:${index}`;
}

export function roomGeoId(locationId: string, buildingIndex: number, floor: number, index: number): string {
  return `geo:guiyang:${locationId}:building:${buildingIndex}:floor:${floor}:room:${index}`;
}

export function cityFrameEntities(): WorldEntityGeo[] {
  return WORLD_LOCATIONS.map((location) => {
    const anchor = CITY_ANCHORS[location.id]!;
    return geoEntity({
      id: locationGeoId(location.id),
      label: location.short,
      xPct: anchor.xPct,
      yPct: anchor.yPct,
      footprint: { w: anchor.w, d: anchor.d },
      height: location.id === 'huaguoyuan' ? 18 : location.id === 'jiaxiu_tower' ? 12 : 15,
      visual: `${location.scene.architecture}；${location.scene.signature}`,
      scaleTier: 'place',
    });
  });
}

export function locationFrameEntities(location: WorldLocation): WorldEntityGeo[] {
  return exteriorHotspots(location).map((hotspot, index) =>
    geoEntity({
      id: buildingGeoId(location.id, index),
      label: hotspot.label,
      xPct: hotspot.xPct,
      yPct: hotspot.yPct,
      footprint: { w: 20, d: 12 },
      height: 13 + index * 1.6,
      visual: `${location.scene.architecture}中的${hotspot.label}`,
      scaleTier: 'room',
    }),
  );
}

export function interiorFrameEntities(
  location: WorldLocation,
  building: string,
  floor: number,
  profile: FlipbookInteriorProfile,
): WorldEntityGeo[] {
  const buildingIndex = Math.max(0, location.buildings?.indexOf(building) ?? 0);
  return INTERIOR_ANCHORS.map((anchor, index) =>
    geoEntity({
      id: roomGeoId(location.id, buildingIndex, floor, index),
      label: profile.rooms[index] ?? `空间 ${index + 1}`,
      xPct: anchor.xPct,
      yPct: anchor.yPct,
      footprint: { w: 18, d: 10 },
      height: 4,
      visual: `${profile.kind}内的${profile.rooms[index] ?? `空间 ${index + 1}`}`,
      scaleTier: 'object',
    }),
  );
}

export function rootPage(): GuiyangFlipbookPage {
  return {
    nodeId: 'ofb:guiyang',
    parentId: null,
    relation: 'descend',
    scale: 'container',
    title: '贵阳社会世界',
    subtitle: `${SOCIAL_WORLD_CITY.prototypeCount.toLocaleString('zh-CN')} 个稳定人格 · 七个可进入地点`,
    imageDataUrl: GUIYANG_WORLD_IMAGE,
    level: 'city',
    locationId: null,
    building: null,
    floor: null,
    sceneView: {
      node_id: 'ofb:guiyang',
      level: 'map',
      observer: null,
      map_crop: { ...OPENFLIPBOOK_FRAME },
      scale_tier: 'city',
      view: { projection: 'oblique', pitch_deg: -54, azimuth_deg: 18, camera_height: 'aerial', source: 'policy' },
    },
    entities: cityFrameEntities(),
  };
}

export function locationPage(location: WorldLocation): GuiyangFlipbookPage {
  const cityAnchor = CITY_ANCHORS[location.id]!;
  return {
    nodeId: `ofb:${location.id}`,
    parentId: 'ofb:guiyang',
    relation: 'descend',
    scale: 'component',
    title: location.name,
    subtitle: `${location.population} 个在地活动体 · ${location.scene.status}`,
    imageDataUrl: sceneImageUrl(location.id, 'campus', 1),
    level: 'campus',
    locationId: location.id,
    building: null,
    floor: null,
    sceneView: {
      node_id: `ofb:${location.id}`,
      level: 'map',
      observer: null,
      map_crop: { ...OPENFLIPBOOK_FRAME },
      focus_id: locationGeoId(location.id),
      scale_tier: 'place',
      view: { projection: 'oblique', pitch_deg: -48, camera_height: 'aerial', source: 'policy' },
    },
    entities: locationFrameEntities(location),
    clickInParent: { xPct: cityAnchor.xPct, yPct: cityAnchor.yPct },
  };
}

export function interiorPage(
  location: WorldLocation,
  building: string,
  floor: number,
  profile: FlipbookInteriorProfile,
): GuiyangFlipbookPage {
  const buildingIndex = Math.max(0, location.buildings?.indexOf(building) ?? 0);
  const anchor = exteriorHotspots(location)[buildingIndex] ?? exteriorHotspots(location)[0]!;
  const nodeId = `ofb:${location.id}:building:${buildingIndex}:floor:${floor}`;
  return {
    nodeId,
    parentId: `ofb:${location.id}`,
    relation: 'descend',
    scale: 'component',
    title: `${building} · ${floor}F`,
    subtitle: `${profile.floorName} · ${profile.activity}`,
    imageDataUrl: sceneImageUrl(location.id, 'interior', floor),
    level: 'interior',
    locationId: location.id,
    building,
    floor,
    sceneView: {
      node_id: nodeId,
      level: 'eye',
      observer: { pos: { x: 50, y: 57 }, eye_height: 1.7, gaze: -Math.PI / 2, pitch: -0.08, fov: Math.PI / 2 },
      map_crop: null,
      focus_id: buildingGeoId(location.id, buildingIndex),
      scale_tier: 'room',
      place_form: 'interior',
      view: { projection: 'eye_level', pitch_deg: -5, camera_height: 'eye', source: 'policy' },
    },
    entities: interiorFrameEntities(location, building, floor, profile),
    clickInParent: { xPct: anchor.xPct, yPct: anchor.yPct },
  };
}

export function activeGuiyangPage(
  level: WorldLevel,
  location: WorldLocation,
  building: string,
  floor: number,
  profile: FlipbookInteriorProfile,
): GuiyangFlipbookPage {
  if (level === 'city') return rootPage();
  if (level === 'campus') return locationPage(location);
  return interiorPage(location, building, floor, profile);
}

export function locationFromGeo(geoId: string): WorldLocation | null {
  return WORLD_LOCATIONS.find((location) => locationGeoId(location.id) === geoId) ?? null;
}

export function buildingFromGeo(location: WorldLocation, geoId: string): string | null {
  const index = (location.buildings ?? []).findIndex((_, itemIndex) => buildingGeoId(location.id, itemIndex) === geoId);
  return index >= 0 ? location.buildings?.[index] ?? null : null;
}

export function agentsForPage(page: GuiyangFlipbookPage): Array<{ agent: WorldAgent; xPct: number; yPct: number }> {
  if (page.level === 'city') {
    return WORLD_AGENTS.map((agent, index) => {
      const anchor = CITY_ANCHORS[agent.locationId] ?? { xPct: 0.5, yPct: 0.5 };
      const jitter = AGENT_ANCHORS[index % AGENT_ANCHORS.length]!;
      return {
        agent,
        xPct: Math.min(0.96, Math.max(0.04, anchor.xPct + (jitter.xPct - 0.5) * 0.12)),
        yPct: Math.min(0.94, Math.max(0.05, anchor.yPct + (jitter.yPct - 0.5) * 0.10)),
      };
    });
  }
  const local = WORLD_AGENTS.filter((agent) => agent.locationId === page.locationId);
  return local.map((agent, index) => ({ agent, ...AGENT_ANCHORS[index % AGENT_ANCHORS.length]! }));
}
