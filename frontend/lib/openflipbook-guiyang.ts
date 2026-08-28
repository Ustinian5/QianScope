import type { WorldLocation } from '@/lib/social-world-fixtures';

export type FlipbookHotspot = {
  id: string;
  label: string;
  xPct: number;
  yPct: number;
};

type SceneAsset = {
  exterior: string;
  interior: string;
  exteriorAnchors: Array<{ xPct: number; yPct: number }>;
};

const ROOT = '/openflipbook/guiyang';

const SCENE_ASSETS: Record<string, SceneAsset> = {
  guiyang_convention: {
    exterior: `${ROOT}/guiyang-convention-exterior.jpg`,
    interior: `${ROOT}/guiyang-convention-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.34 },
      { xPct: 0.74, yPct: 0.34 },
      { xPct: 0.27, yPct: 0.69 },
      { xPct: 0.73, yPct: 0.69 },
    ],
  },
  guiyang_big_data: {
    exterior: `${ROOT}/guiyang-big-data-exterior.jpg`,
    interior: `${ROOT}/guiyang-big-data-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.30 },
      { xPct: 0.73, yPct: 0.29 },
      { xPct: 0.27, yPct: 0.68 },
      { xPct: 0.73, yPct: 0.68 },
    ],
  },
  guizhou_university: {
    exterior: `${ROOT}/guizhou-university-exterior.jpg`,
    interior: `${ROOT}/guizhou-university-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.30 },
      { xPct: 0.74, yPct: 0.30 },
      { xPct: 0.25, yPct: 0.66 },
      { xPct: 0.74, yPct: 0.67 },
    ],
  },
  jiaxiu_tower: {
    exterior: `${ROOT}/jiaxiu-tower-exterior.jpg`,
    interior: `${ROOT}/jiaxiu-tower-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.30 },
      { xPct: 0.73, yPct: 0.30 },
      { xPct: 0.25, yPct: 0.71 },
      { xPct: 0.75, yPct: 0.71 },
    ],
  },
  qingyan_town: {
    exterior: `${ROOT}/qingyan-town-exterior.jpg`,
    interior: `${ROOT}/qingyan-town-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.27 },
      { xPct: 0.73, yPct: 0.27 },
      { xPct: 0.28, yPct: 0.68 },
      { xPct: 0.72, yPct: 0.69 },
    ],
  },
  guiyang_north_station: {
    exterior: `${ROOT}/guiyang-north-station-exterior.jpg`,
    interior: `${ROOT}/guiyang-north-station-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.24, yPct: 0.29 },
      { xPct: 0.70, yPct: 0.29 },
      { xPct: 0.25, yPct: 0.69 },
      { xPct: 0.72, yPct: 0.71 },
    ],
  },
  huaguoyuan: {
    exterior: `${ROOT}/huaguoyuan-exterior.jpg`,
    interior: `${ROOT}/huaguoyuan-interior.jpg`,
    exteriorAnchors: [
      { xPct: 0.23, yPct: 0.28 },
      { xPct: 0.72, yPct: 0.27 },
      { xPct: 0.23, yPct: 0.70 },
      { xPct: 0.72, yPct: 0.70 },
    ],
  },
};

export const INTERIOR_ANCHORS = [
  { xPct: 0.23, yPct: 0.27 },
  { xPct: 0.73, yPct: 0.27 },
  { xPct: 0.50, yPct: 0.51 },
  { xPct: 0.24, yPct: 0.72 },
  { xPct: 0.75, yPct: 0.72 },
] as const;

export const AGENT_ANCHORS = [
  { xPct: 0.43, yPct: 0.62 },
  { xPct: 0.57, yPct: 0.63 },
  { xPct: 0.50, yPct: 0.78 },
  { xPct: 0.62, yPct: 0.54 },
] as const;

function assetFor(locationId: string): SceneAsset {
  return SCENE_ASSETS[locationId] ?? SCENE_ASSETS.guiyang_convention!;
}

export function sceneImageUrl(
  locationId: string,
  level: 'campus' | 'interior',
  floor: number,
): string {
  const asset = assetFor(locationId);
  const source = level === 'campus' ? asset.exterior : asset.interior;
  // OpenFlipbook's morph hook keys on the arrival URL. Floors share one stable
  // venue illustration but remain distinct pages in the navigation trail.
  return level === 'interior' ? `${source}?floor=${floor}` : source;
}

export function exteriorHotspots(location: WorldLocation): FlipbookHotspot[] {
  const asset = assetFor(location.id);
  const buildings = location.buildings ?? [];
  return asset.exteriorAnchors.map((anchor, index) => ({
    id: `${location.id}:building:${index}`,
    label: buildings[index] ?? `地点 ${index + 1}`,
    ...anchor,
  }));
}

export function interiorHotspots(roomNames: string[]): FlipbookHotspot[] {
  return INTERIOR_ANCHORS.map((anchor, index) => ({
    id: `room:${index}`,
    label: roomNames[index] ?? `空间 ${index + 1}`,
    ...anchor,
  }));
}

export function allGuiyangSceneUrls(): string[] {
  return Object.values(SCENE_ASSETS).flatMap((asset) => [asset.exterior, asset.interior]);
}
