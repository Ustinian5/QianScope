/**
 * World and scene contracts copied from OpenFlipbook commit b3e5044 (MIT).
 *
 * QianScope keeps this bounded copy beside the upstream play primitives so the
 * deployed frontend does not depend on a parent-directory workspace package.
 */

export type ScaleKind = 'component' | 'peer' | 'container';

export const SCALE_LADDER = [
  'universe',
  'galaxy',
  'star_system',
  'planet',
  'world',
  'region',
  'city',
  'district',
  'place',
  'room',
  'object',
] as const;

export type ScaleTier = (typeof SCALE_LADDER)[number];

export function tierIndex(tier: ScaleTier): number {
  return SCALE_LADDER.indexOf(tier);
}

export function finerTier(tier: ScaleTier): ScaleTier {
  const index = tierIndex(tier);
  return SCALE_LADDER[Math.min(index + 1, SCALE_LADDER.length - 1)] ?? tier;
}

export type NodeRelation = 'descend' | 'expand' | 'ascend' | 'edit';
export type EntityKind = 'person' | 'place' | 'item' | 'creature';
export type EntityState = Record<string, string | number | boolean>;

export interface EntityBBox {
  x_pct: number;
  y_pct: number;
  w_pct: number;
  h_pct: number;
}

export interface Entity {
  id: string;
  kind: EntityKind;
  name: string;
  aliases: string[];
  appearance: string;
  reference_image_url: string | null;
  facts: string[];
  state: EntityState;
  first_seen_node_id: string;
  last_seen_node_id: string;
  appears_on_node_ids: string[];
  appearance_bboxes: Record<string, EntityBBox>;
  appearance_borders?: Record<string, [number, number][]>;
  pinned_by_user: boolean;
  confidence: number;
  updated_at: string;
}

export interface WorldVec2 {
  x: number;
  y: number;
}

export interface WorldEntityGeo {
  id: string;
  entity_id: string | null;
  parent_id?: string | null;
  kind: EntityKind;
  label: string;
  pos: WorldVec2;
  height: number;
  elevation?: number;
  footprint: { w: number; d: number };
  scale?: number;
  scale_tier?: ScaleTier;
  heading?: number;
  visual: string;
  state: EntityState;
  confidence: number;
  source: 'extracted' | 'user' | 'derived';
  updated_at: string;
  border?: WorldVec2[];
  height_m?: number;
}

export interface ObserverPose {
  pos: WorldVec2;
  eye_height: number;
  gaze: number;
  pitch?: number;
  fov: number;
}

export interface MapCrop {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type ViewLevel = 'map' | 'building' | 'street' | 'eye';
export type ViewSpecProjection = 'top_down' | 'oblique' | 'isometric' | 'eye_level';

export interface ViewSpec {
  projection: ViewSpecProjection;
  pitch_deg?: number;
  azimuth_deg?: number;
  camera_height?: 'ground' | 'eye' | 'rooftop' | 'aerial' | number;
  fov_deg?: number;
  source: 'policy' | 'user' | 'estimated';
}

export interface SceneView {
  node_id: string;
  level: ViewLevel;
  observer: ObserverPose | null;
  map_crop: MapCrop | null;
  closeup?: boolean;
  focus_id?: string | null;
  scale_tier?: ScaleTier;
  view?: ViewSpec | null;
  enter_index?: number | null;
  place_form?: string;
}

export interface ProjectedEntity {
  id: string;
  label: string;
  x_pct: number;
  y_pct: number;
  w_pct: number;
  h_pct: number;
  depth: number;
  h_pos: string;
  v_pos: string;
  size: string;
}

export type ViewProjection = 'top_down' | 'oblique' | 'perspective';

export interface WorldMapSnapshot {
  session_id: string;
  entities: WorldEntityGeo[];
  bounds: MapCrop;
  schema_version: number;
  updated_at: string;
}
