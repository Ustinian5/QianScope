'use client';

import { useEffect, useRef, useState } from 'react';
import type { FeatureCollection, Point } from 'geojson';
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { PersonaMapItem, PersonaMapSnapshot } from '@/lib/persona-types';
import { SOCIAL_WORLD_CITY, stableUnit, type WorldLocation } from '@/lib/social-world-fixtures';

export type SocialMapProvider = 'loading' | 'amap' | 'fallback';

export type SocialMapCamera = {
  center: [number, number];
  zoom: number;
  pitch: number;
  rotation: number;
};

export type SocialMapStatus = {
  provider: SocialMapProvider;
  ready: boolean;
  detail: string;
};

export type SocialWeather = {
  weather: string;
  temperature: string;
  humidity: string;
  windDirection: string;
  windPower: string;
};

export const DEFAULT_SOCIAL_MAP_CAMERA: SocialMapCamera = {
  // Start from a high, near-plan view of Guiyang: the municipal area fills the
  // desktop canvas without dropping the camera into a low building-level angle.
  center: [106.630153, 26.647661],
  zoom: 10.65,
  pitch: 16,
  rotation: 0,
};

type Props = {
  camera: SocialMapCamera;
  locations: WorldLocation[];
  onAgentSelect: (personaId: string) => void;
  onCameraChange: (camera: SocialMapCamera) => void;
  onEnter: (location: WorldLocation) => void;
  onStatusChange: (status: SocialMapStatus) => void;
  onAgentActivityChange?: (status: SocialAgentActivityStatus) => void;
  onWeatherChange?: (weather: SocialWeather) => void;
  populationVisible: boolean;
};

type ProjectedLocation = {
  location: WorldLocation;
  x: number;
  y: number;
};

type MapPoint = { x: number; y: number };

type AgentMotionWaypoint = {
  longitude: number;
  latitude: number;
};

type AgentMotion = {
  item: PersonaMapItem;
  tone: 'cobalt' | 'coral';
  waypoints: AgentMotionWaypoint[];
  durationMs: number;
  phaseMs: number;
  bend: number;
  orbitPhase: number;
  orbitRadius: number;
};

type AgentFramePoint = {
  coordinates: [number, number];
  personaId: string;
  tier: string;
  representedWeight: number;
  moving: boolean;
  tone: 'cobalt' | 'coral';
  style: number;
};

export type SocialAgentActivityStatus = {
  ready: boolean;
  total: number;
  moving: number;
  detail: string;
};

type MapAdapter = {
  destroy: () => void;
  focus: (location: WorldLocation) => void;
  getCamera: () => SocialMapCamera;
  project: (position: [number, number]) => MapPoint;
  reset: () => void;
  setPopulationVisible: (visible: boolean) => void;
  togglePerspective: () => void;
  zoomBy: (delta: number) => void;
};

type AMapLngLat = { getLng: () => number; getLat: () => number };
type AMapPixel = { getX: () => number; getY: () => number };
type AMapMassMarksDatum = {
  lnglat: [number, number];
  style: number;
  personaId: string;
  tier: string;
  representedWeight: number;
  moving: boolean;
};
type AMapMassMarksEvent = { data?: AMapMassMarksDatum };
type AMapMassMarks = {
  on: (event: string, listener: (event: AMapMassMarksEvent) => void) => void;
  setData: (data: AMapMassMarksDatum[]) => void;
  setMap: (map: AMapMap | null) => void;
};
type AMapWeather = {
  getLive: (
    city: string,
    callback: (error: unknown, data: Partial<SocialWeather>) => void,
  ) => void;
};
type AMapMap = {
  addControl: (control: unknown) => void;
  destroy: () => void;
  getCenter: () => AMapLngLat;
  getPitch: () => number;
  getRotation: () => number;
  getZoom: () => number;
  lngLatToContainer: (position: [number, number]) => AMapPixel;
  on: (event: string, listener: () => void) => void;
  setPitch: (pitch: number, immediately?: boolean, duration?: number) => void;
  setRotation: (rotation: number, immediately?: boolean, duration?: number) => void;
  setZoom: (zoom: number, immediately?: boolean, duration?: number) => void;
  setZoomAndCenter: (zoom: number, center: [number, number], immediately?: boolean, duration?: number) => void;
};
type AMapRuntime = {
  Map: new (container: HTMLDivElement, options: Record<string, unknown>) => AMapMap;
  MassMarks: new (
    data: AMapMassMarksDatum[],
    options: Record<string, unknown>,
  ) => AMapMassMarks;
  Pixel: new (x: number, y: number) => unknown;
  Scale?: new (options?: Record<string, unknown>) => unknown;
  Size: new (width: number, height: number) => unknown;
  Weather?: new () => AMapWeather;
};

declare global {
  interface Window {
    _AMapSecurityConfig?: { securityJsCode: string };
  }
}

const AGENT_MOTION_TICK_MS = 320;
const AGENT_DWELL_SHARE = 0.18;
const AMAP_KEY = process.env.NEXT_PUBLIC_AMAP_KEY?.trim() || '';
const AMAP_SECURITY_CODE = process.env.NEXT_PUBLIC_AMAP_SECURITY_JS_CODE?.trim() || '';
const AMAP_STYLE = process.env.NEXT_PUBLIC_AMAP_STYLE?.trim() || 'amap://styles/whitesmoke';

const DEFAULT_MAP_STYLE = {
  version: 8 as const,
  sources: {
    openstreetmap: {
      type: 'raster' as const,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
      maxzoom: 19,
    },
  },
  layers: [{
    id: 'openstreetmap',
    type: 'raster' as const,
    source: 'openstreetmap',
    paint: {
      'raster-saturation': -0.38,
      'raster-contrast': -0.08,
      'raster-brightness-min': 0.16,
      'raster-brightness-max': 0.93,
    },
  }],
};

function buildAgentMotions(items: PersonaMapItem[], locations: WorldLocation[]): AgentMotion[] {
  const locationById = new Map(locations.map((location) => [location.id, location]));
  return items.map((item, itemIndex) => {
    const route = item.route_location_ids
      .map((locationId) => locationById.get(locationId))
      .filter((location): location is WorldLocation => Boolean(location));
    const anchors = route.length ? route : [locations[itemIndex % locations.length]];
    const waypointCount = Math.max(2, anchors.length);
    const waypoints = Array.from({ length: waypointCount }, (_, waypointIndex) => {
      const anchor = anchors[waypointIndex % anchors.length];
      const spread = anchor.featured ? 0.022 : anchor.id === 'huaguoyuan' ? 0.036 : 0.028;
      const longitudeOffset = (
        stableUnit(`${item.persona_id}:waypoint:${waypointIndex}:lng:a`)
        + stableUnit(`${item.persona_id}:waypoint:${waypointIndex}:lng:b`)
        - 1
      ) * spread;
      const latitudeOffset = (
        stableUnit(`${item.persona_id}:waypoint:${waypointIndex}:lat:a`)
        + stableUnit(`${item.persona_id}:waypoint:${waypointIndex}:lat:b`)
        - 1
      ) * spread * 0.64;
      return {
        longitude: anchor.longitude + longitudeOffset,
        latitude: anchor.latitude + latitudeOffset,
      };
    });
    const durationMs = 34_000 + stableUnit(`${item.persona_id}:duration`) * 52_000;
    return {
      item,
      tone: stableUnit(`${item.persona_id}:tone`) < 0.5 ? 'cobalt' : 'coral',
      waypoints,
      durationMs,
      phaseMs: stableUnit(`${item.persona_id}:phase`) * durationMs * waypoints.length,
      bend: (stableUnit(`${item.persona_id}:bend`) - 0.5) * 0.68,
      orbitPhase: stableUnit(`${item.persona_id}:orbit-phase`) * Math.PI * 2,
      orbitRadius: 0.00065 + stableUnit(`${item.persona_id}:orbit-radius`) * 0.0015,
    };
  });
}

function smoothstep(value: number) {
  return value * value * (3 - 2 * value);
}

function motionPointAt(motion: AgentMotion, timestamp: number): AgentFramePoint {
  const legTime = (timestamp + motion.phaseMs) / motion.durationMs;
  const absoluteLeg = Math.floor(legTime);
  const legProgress = legTime - absoluteLeg;
  const waypointIndex = absoluteLeg % motion.waypoints.length;
  const start = motion.waypoints[waypointIndex];
  const end = motion.waypoints[(waypointIndex + 1) % motion.waypoints.length];
  const moving = legProgress >= AGENT_DWELL_SHARE && legProgress <= 1 - AGENT_DWELL_SHARE;
  let longitude: number;
  let latitude: number;

  if (moving) {
    const normalized = (legProgress - AGENT_DWELL_SHARE) / (1 - AGENT_DWELL_SHARE * 2);
    const progress = smoothstep(normalized);
    const inverse = 1 - progress;
    const deltaLongitude = end.longitude - start.longitude;
    const deltaLatitude = end.latitude - start.latitude;
    const distance = Math.hypot(deltaLongitude, deltaLatitude) || 1;
    const controlLongitude = (start.longitude + end.longitude) / 2 - (deltaLatitude / distance) * distance * motion.bend;
    const controlLatitude = (start.latitude + end.latitude) / 2 + (deltaLongitude / distance) * distance * motion.bend;
    longitude = inverse * inverse * start.longitude + 2 * inverse * progress * controlLongitude + progress * progress * end.longitude;
    latitude = inverse * inverse * start.latitude + 2 * inverse * progress * controlLatitude + progress * progress * end.latitude;
  } else {
    const base = legProgress < AGENT_DWELL_SHARE ? start : end;
    const direction = absoluteLeg % 2 === 0 ? 1 : -1;
    const angle = motion.orbitPhase + direction * timestamp / 7_800;
    longitude = base.longitude + Math.cos(angle) * motion.orbitRadius;
    latitude = base.latitude + Math.sin(angle) * motion.orbitRadius * 0.66;
  }

  const tierOffset = motion.item.tier === 'key' ? 4 : motion.item.tier === 'representative' ? 2 : 0;
  return {
    coordinates: [longitude, latitude],
    personaId: motion.item.persona_id,
    tier: motion.item.tier,
    representedWeight: motion.item.represented_weight,
    moving,
    tone: motion.tone,
    style: (tierOffset + (moving ? 1 : 0)) * 2 + (motion.tone === 'coral' ? 1 : 0),
  };
}

function agentFrame(motions: AgentMotion[], timestamp: number) {
  return motions.map((motion) => motionPointAt(motion, timestamp));
}

function agentGeoJson(points: AgentFramePoint[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: points.map((point) => ({
      type: 'Feature' as const,
      geometry: { type: 'Point' as const, coordinates: point.coordinates },
      properties: {
        personaId: point.personaId,
        tier: point.tier,
        tone: point.tone,
        moving: point.moving ? 1 : 0,
        representedWeight: point.representedWeight,
      },
    })),
  };
}

function normalizeRotation(value: number) {
  const normalized = ((value + 180) % 360 + 360) % 360 - 180;
  return Math.round(normalized * 10) / 10;
}

function clampZoom(value: number) {
  return Math.min(18, Math.max(8, value));
}

const GCJ_EARTH_RADIUS = 6_378_245;
const GCJ_ECCENTRICITY = 0.006693421622965943;

function isOutsideChina([longitude, latitude]: [number, number]) {
  return longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271;
}

function transformLatitude(longitude: number, latitude: number) {
  let result = -100 + 2 * longitude + 3 * latitude + 0.2 * latitude * latitude
    + 0.1 * longitude * latitude + 0.2 * Math.sqrt(Math.abs(longitude));
  result += (20 * Math.sin(6 * longitude * Math.PI) + 20 * Math.sin(2 * longitude * Math.PI)) * 2 / 3;
  result += (20 * Math.sin(latitude * Math.PI) + 40 * Math.sin(latitude / 3 * Math.PI)) * 2 / 3;
  result += (160 * Math.sin(latitude / 12 * Math.PI) + 320 * Math.sin(latitude * Math.PI / 30)) * 2 / 3;
  return result;
}

function transformLongitude(longitude: number, latitude: number) {
  let result = 300 + longitude + 2 * latitude + 0.1 * longitude * longitude
    + 0.1 * longitude * latitude + 0.1 * Math.sqrt(Math.abs(longitude));
  result += (20 * Math.sin(6 * longitude * Math.PI) + 20 * Math.sin(2 * longitude * Math.PI)) * 2 / 3;
  result += (20 * Math.sin(longitude * Math.PI) + 40 * Math.sin(longitude / 3 * Math.PI)) * 2 / 3;
  result += (150 * Math.sin(longitude / 12 * Math.PI) + 300 * Math.sin(longitude / 30 * Math.PI)) * 2 / 3;
  return result;
}

function wgs84ToGcj02(position: [number, number]): [number, number] {
  if (isOutsideChina(position)) return position;
  const [longitude, latitude] = position;
  let latitudeDelta = transformLatitude(longitude - 105, latitude - 35);
  let longitudeDelta = transformLongitude(longitude - 105, latitude - 35);
  const latitudeRadians = latitude / 180 * Math.PI;
  const latitudeSine = Math.sin(latitudeRadians);
  const magic = 1 - GCJ_ECCENTRICITY * latitudeSine * latitudeSine;
  const magicRoot = Math.sqrt(magic);
  latitudeDelta = latitudeDelta * 180
    / ((GCJ_EARTH_RADIUS * (1 - GCJ_ECCENTRICITY)) / (magic * magicRoot) * Math.PI);
  longitudeDelta = longitudeDelta * 180
    / (GCJ_EARTH_RADIUS / magicRoot * Math.cos(latitudeRadians) * Math.PI);
  return [longitude + longitudeDelta, latitude + latitudeDelta];
}

function gcj02ToWgs84(position: [number, number]): [number, number] {
  if (isOutsideChina(position)) return position;
  const converted = wgs84ToGcj02(position);
  return [position[0] * 2 - converted[0], position[1] * 2 - converted[1]];
}

function overviewMarkerOffset(location: WorldLocation, zoom: number): [number, number] {
  const offset = location.labelOffset;
  if (!offset) return [0, 0];
  const strength = Math.min(1, Math.max(0, (13 - zoom) / 1.7));
  return [offset[0] * strength, offset[1] * strength];
}

function agentDataUrl(fill: string, glow: string, moving: boolean) {
  const motionLine = moving ? `<path d="M2 17h4" stroke="${fill}" stroke-width="1.2" stroke-linecap="round" opacity=".58"/>` : '';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="20" viewBox="0 0 16 20"><ellipse cx="8" cy="17" rx="6" ry="2.5" fill="${glow}"/>${motionLine}<circle cx="8" cy="6" r="2.7" fill="${fill}" stroke="rgba(255,255,255,.88)" stroke-width="1"/><path d="M4.5 15c.2-4.2 1.3-6.2 3.5-6.2s3.3 2 3.5 6.2z" fill="${fill}" stroke="rgba(255,255,255,.8)" stroke-width=".8"/></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function SocialWorldMap({
  camera,
  locations,
  onAgentSelect,
  onCameraChange,
  onEnter,
  onStatusChange,
  onAgentActivityChange,
  onWeatherChange,
  populationVisible,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const adapterRef = useRef<MapAdapter | null>(null);
  const initialCameraRef = useRef(camera);
  const populationVisibleRef = useRef(populationVisible);
  const callbacksRef = useRef({ onAgentSelect, onCameraChange, onEnter, onStatusChange, onAgentActivityChange, onWeatherChange });
  const enterTimerRef = useRef<number | null>(null);
  const [cameraSnapshot, setCameraSnapshot] = useState(camera);
  const [enteringId, setEnteringId] = useState('');
  const [projectedLocations, setProjectedLocations] = useState<ProjectedLocation[]>([]);
  const [status, setStatus] = useState<SocialMapStatus>({
    provider: 'loading',
    ready: false,
    detail: '正在连接高德城市空间…',
  });
  const [agentActivity, setAgentActivity] = useState<SocialAgentActivityStatus>({
    ready: false,
    total: 0,
    moving: 0,
    detail: '正在同步稳定数字人格…',
  });

  useEffect(() => {
    callbacksRef.current = { onAgentSelect, onCameraChange, onEnter, onStatusChange, onAgentActivityChange, onWeatherChange };
  }, [onAgentActivityChange, onAgentSelect, onCameraChange, onEnter, onStatusChange, onWeatherChange]);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    let disposed = false;
    let projectionFrame = 0;
    let agentMotionTimer: number | null = null;
    let agentMotionWriter: ((points: AgentFramePoint[]) => void) | null = null;
    let agentMotionTick = 0;
    let activeMotions: AgentMotion[] = [];
    const snapshotController = new AbortController();
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const emitAgentActivity = (next: SocialAgentActivityStatus) => {
      if (disposed) return;
      setAgentActivity(next);
      callbacksRef.current.onAgentActivityChange?.(next);
    };

    const updateAgentLayer = (forceActivity = false) => {
      if (disposed || !agentMotionWriter || !activeMotions.length) return;
      const points = agentFrame(activeMotions, window.performance.now());
      agentMotionWriter(points);
      agentMotionTick += 1;
      if (forceActivity || agentMotionTick % 6 === 0) {
        const moving = points.reduce((total, point) => total + (point.moving ? 1 : 0), 0);
        emitAgentActivity({
          ready: true,
          total: points.length,
          moving,
          detail: '点击任意活动体查看稳定人格档案',
        });
      }
    };

    const startAgentMotion = (writer: (points: AgentFramePoint[]) => void) => {
      if (agentMotionTimer !== null) window.clearInterval(agentMotionTimer);
      agentMotionWriter = writer;
      updateAgentLayer(true);
      if (!prefersReducedMotion) agentMotionTimer = window.setInterval(updateAgentLayer, AGENT_MOTION_TICK_MS);
    };

    async function loadAgentPopulation(attempt = 0): Promise<void> {
      try {
        const response = await fetch('/api/qianscope/v1/personas/map', {
          cache: 'no-store',
          signal: snapshotController.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const snapshot = await response.json() as PersonaMapSnapshot;
        if (disposed) return;
        activeMotions = buildAgentMotions(snapshot.items, locations);
        emitAgentActivity({
          ready: true,
          total: snapshot.total_prototypes,
          moving: 0,
          detail: snapshot.note,
        });
        updateAgentLayer(true);
      } catch (reason) {
        if (disposed || (reason instanceof DOMException && reason.name === 'AbortError')) return;
        if (attempt < 2) {
          emitAgentActivity({
            ready: false,
            total: 0,
            moving: 0,
            detail: `数字人格活动层正在重新同步（${attempt + 2}/3）`,
          });
          await new Promise<void>((resolve) => window.setTimeout(resolve, 900 * (attempt + 1)));
          if (disposed || snapshotController.signal.aborted) return;
          await loadAgentPopulation(attempt + 1);
          return;
        }
        emitAgentActivity({
          ready: false,
          total: 0,
          moving: 0,
          detail: '数字人格活动层同步失败；请确认后端服务后刷新',
        });
      }
    }

    const emitStatus = (next: SocialMapStatus) => {
      if (disposed) return;
      setStatus(next);
      callbacksRef.current.onStatusChange(next);
    };

    const projectLocations = () => {
      window.cancelAnimationFrame(projectionFrame);
      projectionFrame = window.requestAnimationFrame(() => {
        const adapter = adapterRef.current;
        if (!adapter || disposed) return;
        setProjectedLocations(locations.map((location) => {
          const point = adapter.project([location.longitude, location.latitude]);
          return { location, x: point.x, y: point.y };
        }).filter(({ x, y }) => Number.isFinite(x) && Number.isFinite(y)));
      });
    };

    const updateCamera = (persist: boolean) => {
      const adapter = adapterRef.current;
      if (!adapter || disposed) return;
      const next = adapter.getCamera();
      setCameraSnapshot(next);
      if (persist) callbacksRef.current.onCameraChange(next);
    };

    async function createFallbackMap(reason: string) {
      const maplibregl = await import('maplibre-gl');
      if (disposed) return;
      container.replaceChildren();
      const initial = initialCameraRef.current;
      const map: MapLibreMap = new maplibregl.Map({
        container,
        style: process.env.NEXT_PUBLIC_MAP_STYLE_URL || DEFAULT_MAP_STYLE,
        center: gcj02ToWgs84(initial.center),
        zoom: initial.zoom,
        minZoom: 8,
        maxZoom: 18,
        pitch: initial.pitch,
        bearing: initial.rotation,
        attributionControl: false,
        cooperativeGestures: false,
      });
      map.addControl(new maplibregl.ScaleControl({ maxWidth: 92, unit: 'metric' }), 'bottom-right');

      const adapter: MapAdapter = {
        destroy: () => map.remove(),
        focus: (location) => map.easeTo({
          center: gcj02ToWgs84([location.longitude, location.latitude]),
          zoom: Math.max(13.6, map.getZoom()),
          pitch: 44,
          bearing: location.focusRotation ?? -7,
          duration: 520,
          essential: true,
        }),
        getCamera: () => {
          const center = map.getCenter();
          return {
            center: wgs84ToGcj02([center.lng, center.lat]),
            zoom: map.getZoom(),
            pitch: map.getPitch(),
            rotation: normalizeRotation(map.getBearing()),
          };
        },
        project: (position) => map.project(gcj02ToWgs84(position)),
        reset: () => map.easeTo({
          center: gcj02ToWgs84(DEFAULT_SOCIAL_MAP_CAMERA.center),
          zoom: DEFAULT_SOCIAL_MAP_CAMERA.zoom,
          pitch: DEFAULT_SOCIAL_MAP_CAMERA.pitch,
          bearing: DEFAULT_SOCIAL_MAP_CAMERA.rotation,
          duration: 480,
          essential: true,
        }),
        setPopulationVisible: (visible) => {
          ['sw-agent-halo', 'sw-agent-points'].forEach((layerId) => {
            if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
          });
        },
        togglePerspective: () => map.easeTo({ pitch: map.getPitch() > 12 ? 0 : 44, duration: 320, essential: true }),
        zoomBy: (delta) => map.easeTo({ zoom: clampZoom(map.getZoom() + delta), duration: 240, essential: true }),
      };
      adapterRef.current = adapter;

      map.on('move', () => {
        projectLocations();
        updateCamera(false);
      });
      map.on('moveend', () => updateCamera(true));
      map.once('load', () => {
        if (disposed) return;
        map.addSource('sw-agents', { type: 'geojson', data: agentGeoJson([]) });
        map.addLayer({
          id: 'sw-agent-halo',
          type: 'circle',
          source: 'sw-agents',
          filter: ['==', ['get', 'moving'], 1],
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 2.2, 14, 7.5],
            'circle-color': ['match', ['get', 'tone'], 'coral', '#f1664c', '#3159dc'],
            'circle-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.1, 14, 0.28],
            'circle-blur': 0.44,
          },
        });
        map.addLayer({
          id: 'sw-agent-points',
          type: 'circle',
          source: 'sw-agents',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, ['match', ['get', 'tier'], 'key', 2.5, 'representative', 1.6, 0.9], 14, ['match', ['get', 'tier'], 'key', 7.5, 'representative', 5.5, 3.3]],
            'circle-color': ['match', ['get', 'tone'], 'coral', '#f1664c', '#3159dc'],
            'circle-opacity': ['interpolate', ['linear'], ['zoom'], 8, ['case', ['==', ['get', 'moving'], 1], 0.56, 0.34], 14, ['case', ['==', ['get', 'moving'], 1], 0.9, 0.72]],
            'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 8, 0, 14, 1],
            'circle-stroke-color': 'rgba(255,255,252,.9)',
          },
        });
        map.on('click', 'sw-agent-points', (event) => {
          const personaId = String(event.features?.[0]?.properties?.personaId || '');
          if (personaId) callbacksRef.current.onAgentSelect(personaId);
        });
        map.on('mouseenter', 'sw-agent-points', () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', 'sw-agent-points', () => { map.getCanvas().style.cursor = ''; });
        startAgentMotion((points) => {
          const source = map.getSource('sw-agents') as GeoJSONSource | undefined;
          source?.setData(agentGeoJson(points.map((point) => ({
            ...point,
            coordinates: gcj02ToWgs84(point.coordinates),
          }))));
        });
        adapter.setPopulationVisible(populationVisibleRef.current);
        projectLocations();
        updateCamera(true);
        emitStatus({ provider: 'fallback', ready: true, detail: reason });
      });
      map.on('error', () => {
        if (!map.loaded() && !disposed) {
          emitStatus({ provider: 'fallback', ready: false, detail: '演示底图网络不可用，保留本地空间层。' });
        }
      });
    }

    async function createAMap() {
      window._AMapSecurityConfig = { securityJsCode: AMAP_SECURITY_CODE };
      const { load } = await import('@amap/amap-jsapi-loader');
      const api = await load({
        key: AMAP_KEY,
        version: '2.0',
        plugins: ['AMap.Scale', 'AMap.Weather'],
      }) as AMapRuntime;
      if (disposed) return;

      const initial = initialCameraRef.current;
      const map = new api.Map(container, {
        animateEnable: true,
        center: initial.center,
        defaultCursor: 'grab',
        doubleClickZoom: true,
        dragEnable: true,
        features: ['bg', 'road', 'point', 'building'],
        isHotspot: true,
        jogEnable: true,
        keyboardEnable: true,
        mapStyle: AMAP_STYLE,
        pitch: initial.pitch,
        pitchEnable: true,
        resizeEnable: true,
        rotateEnable: true,
        rotation: initial.rotation,
        scrollWheel: true,
        showBuildingBlock: true,
        showIndoorMap: false,
        showLabel: true,
        touchZoom: true,
        touchZoomCenter: 0,
        viewMode: '3D',
        zoom: initial.zoom,
        zoomEnable: true,
        zooms: [8, 18],
      });

      if (api.Scale) map.addControl(new api.Scale({ position: 'RB' }));
      if (api.Weather) {
        new api.Weather().getLive('贵阳市', (error, data) => {
          if (disposed || error || !data.weather || !data.temperature) return;
          callbacksRef.current.onWeatherChange?.({
            weather: data.weather,
            temperature: data.temperature,
            humidity: data.humidity || '--',
            windDirection: data.windDirection || '--',
            windPower: data.windPower || '--',
          });
        });
      }
      const massMarkTones = [
        { color: '#3159dc', glow: 'rgba(49,89,220,.2)' },
        { color: '#f1664c', glow: 'rgba(241,102,76,.2)' },
      ] as const;
      const massMarkShapes = [
        { anchor: [3, 7], size: [6, 8], moving: false, zIndex: 1 },
        { anchor: [4, 8], size: [7, 10], moving: true, zIndex: 2 },
        { anchor: [5, 10], size: [9, 12], moving: false, zIndex: 3 },
        { anchor: [5, 11], size: [10, 14], moving: true, zIndex: 4 },
        { anchor: [6, 13], size: [11, 15], moving: false, zIndex: 5 },
        { anchor: [7, 15], size: [13, 17], moving: true, zIndex: 6 },
      ] as const;
      const massMarks = new api.MassMarks(
        [],
        {
          alwaysRender: true,
          cursor: 'pointer',
          opacity: 0.84,
          style: massMarkShapes.flatMap((shape) =>
            massMarkTones.map((tone) => ({
              anchor: new api.Pixel(shape.anchor[0], shape.anchor[1]),
              rotation: 0,
              size: new api.Size(shape.size[0], shape.size[1]),
              url: agentDataUrl(tone.color, tone.glow, shape.moving),
              zIndex: shape.zIndex,
            })),
          ),
          zIndex: 115,
          zooms: [8, 18],
        },
      );
      massMarks.setMap(populationVisibleRef.current ? map : null);
      massMarks.on('click', (event) => {
        const personaId = event.data?.personaId;
        if (personaId) callbacksRef.current.onAgentSelect(personaId);
      });

      const adapter: MapAdapter = {
        destroy: () => {
          massMarks.setMap(null);
          map.destroy();
        },
        focus: (location) => {
          map.setZoomAndCenter(Math.max(13.6, map.getZoom()), [location.longitude, location.latitude], false, 520);
          map.setPitch(44, false, 520);
          map.setRotation(location.focusRotation ?? -7, false, 520);
        },
        getCamera: () => {
          const center = map.getCenter();
          return {
            center: [center.getLng(), center.getLat()],
            zoom: map.getZoom(),
            pitch: map.getPitch(),
            rotation: normalizeRotation(map.getRotation()),
          };
        },
        project: (position) => {
          const point = map.lngLatToContainer(position);
          return { x: point.getX(), y: point.getY() };
        },
        reset: () => {
          map.setZoomAndCenter(DEFAULT_SOCIAL_MAP_CAMERA.zoom, DEFAULT_SOCIAL_MAP_CAMERA.center, false, 480);
          map.setPitch(DEFAULT_SOCIAL_MAP_CAMERA.pitch, false, 480);
          map.setRotation(DEFAULT_SOCIAL_MAP_CAMERA.rotation, false, 480);
        },
        setPopulationVisible: (visible) => massMarks.setMap(visible ? map : null),
        togglePerspective: () => map.setPitch(map.getPitch() > 12 ? 0 : 44, false, 320),
        zoomBy: (delta) => map.setZoom(clampZoom(map.getZoom() + delta), false, 240),
      };
      adapterRef.current = adapter;

      const updateView = () => {
        projectLocations();
        updateCamera(false);
      };
      const persistView = () => updateCamera(true);
      ['mapmove', 'zoomchange', 'rotatechange', 'pitchchange'].forEach((event) => map.on(event, updateView));
      ['moveend', 'zoomend'].forEach((event) => map.on(event, persistView));
      map.on('click', () => setEnteringId(''));
      map.on('complete', () => {
        startAgentMotion((points) => {
          massMarks.setData(points.map((point) => ({
            lnglat: point.coordinates,
            style: point.style,
            personaId: point.personaId,
            tier: point.tier,
            representedWeight: point.representedWeight,
            moving: point.moving,
          })));
        });
        projectLocations();
        updateCamera(true);
        emitStatus({ provider: 'amap', ready: true, detail: '高德贵阳 3D 空间已连接。' });
      });
    }

    async function initialize() {
      try {
        if (!AMAP_KEY || !AMAP_SECURITY_CODE) {
          emitStatus({ provider: 'loading', ready: false, detail: '正在装载贵阳空间演示底图…' });
          await createFallbackMap('未配置高德 Web JS API 凭证，当前为本地演示底图。');
          return;
        }
        emitStatus({ provider: 'loading', ready: false, detail: '正在连接高德贵阳 3D 空间…' });
        try {
          await createAMap();
        } catch {
          if (adapterRef.current) adapterRef.current.destroy();
          adapterRef.current = null;
          await createFallbackMap('高德底图连接失败，已自动切换本地演示底图。');
        }
      } catch (reason) {
        const detail = reason instanceof Error ? reason.message : '地图初始化失败';
        emitStatus({ provider: 'fallback', ready: false, detail });
      }
    }

    void initialize();
    void loadAgentPopulation();
    return () => {
      disposed = true;
      snapshotController.abort();
      window.cancelAnimationFrame(projectionFrame);
      if (agentMotionTimer !== null) window.clearInterval(agentMotionTimer);
      agentMotionTimer = null;
      agentMotionWriter = null;
      if (enterTimerRef.current !== null) window.clearTimeout(enterTimerRef.current);
      enterTimerRef.current = null;
      adapterRef.current?.destroy();
      adapterRef.current = null;
    };
  }, [locations]);

  useEffect(() => {
    populationVisibleRef.current = populationVisible;
    adapterRef.current?.setPopulationVisible(populationVisible);
  }, [populationVisible]);

  function enterLocation(location: WorldLocation) {
    if (enteringId) return;
    setEnteringId(location.id);
    adapterRef.current?.focus(location);
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    enterTimerRef.current = window.setTimeout(() => {
      callbacksRef.current.onCameraChange(adapterRef.current?.getCamera() || cameraSnapshot);
      callbacksRef.current.onEnter(location);
    }, reduceMotion ? 60 : 560);
  }

  function runMapAction(action: 'zoom-in' | 'zoom-out' | 'perspective' | 'reset') {
    const adapter = adapterRef.current;
    if (!adapter) return;
    if (action === 'zoom-in') adapter.zoomBy(1);
    if (action === 'zoom-out') adapter.zoomBy(-1);
    if (action === 'perspective') adapter.togglePerspective();
    if (action === 'reset') adapter.reset();
  }

  const providerLabel = status.provider === 'amap' ? '高德地图 · 3D' : status.provider === 'fallback' ? '本地演示底图' : '地图连接中';

  return (
    <>
      <div className={`sw-geospatial-map provider-${status.provider} ${status.ready ? 'ready' : ''}`} role="region" aria-label="可拖拽、缩放和旋转的贵阳社会世界地图">
        <div ref={containerRef} className="sw-geospatial-container" tabIndex={0} />
        <div className="sw-map-status" role="status" aria-live="polite">
          <i />
          <span>{status.detail}</span>
        </div>
        <div className={`sw-agent-activity ${agentActivity.ready ? 'ready' : ''} ${populationVisible ? '' : 'hidden'}`} role="status" aria-live="polite" title={agentActivity.detail}>
          <span><i /> {agentActivity.ready ? `${agentActivity.total.toLocaleString('zh-CN')} 人格在线` : '同步数字人格'}</span>
          <small>{populationVisible ? agentActivity.ready ? `${agentActivity.moving.toLocaleString('zh-CN')} 正在移动 · 点击人物查看档案` : agentActivity.detail : '数字人格活动层已隐藏'}</small>
        </div>
        <div className="sw-map-provider-badge"><i /> {providerLabel}</div>
      </div>

      <div className="sw-geospatial-markers" aria-label="可进入的社会地点">
        <svg className="sw-geo-marker-leaders" aria-hidden="true">
          {projectedLocations.map(({ location, x, y }) => {
            const [offsetX, offsetY] = overviewMarkerOffset(location, cameraSnapshot.zoom);
            return offsetX || offsetY ? <line key={location.id} x1={x} y1={y} x2={x + offsetX} y2={y + offsetY} /> : null;
          })}
        </svg>
        {projectedLocations.map(({ location, x, y }) => {
          const [offsetX, offsetY] = overviewMarkerOffset(location, cameraSnapshot.zoom);
          return (
            <button
              key={location.id}
              type="button"
              className={`sw-geo-marker ${location.featured ? 'hero' : ''} ${enteringId === location.id ? 'is-entering' : ''}`}
              aria-label={`聚焦并进入${location.short}`}
              disabled={Boolean(enteringId)}
              style={{ left: `${x + offsetX}px`, top: `${y + offsetY}px` }}
              onClick={() => enterLocation(location)}
            >
              <i />
              <span>{location.short}</span>
              <small>{enteringId === location.id ? '正在进入…' : `${location.population} 活跃`}</small>
            </button>
          );
        })}
      </div>

      <nav className="sw-map-controls sw-glass" aria-label="地图视角控制">
        <button type="button" aria-label="地图放大" onClick={() => runMapAction('zoom-in')}>＋</button>
        <button type="button" aria-label="地图缩小" onClick={() => runMapAction('zoom-out')}>−</button>
        <button type="button" aria-label="切换俯视和三维视角" aria-pressed={cameraSnapshot.pitch > 12} onClick={() => runMapAction('perspective')}>◇</button>
        <button type="button" aria-label={`复位${SOCIAL_WORLD_CITY.name}全景`} onClick={() => runMapAction('reset')}><i style={{ transform: `rotate(${cameraSnapshot.rotation}deg)` }}>↑</i></button>
      </nav>
      <p className="sw-map-gesture"><span>拖动平移</span><span>滚轮 / 双指缩放</span><span>Ctrl + 拖动旋转</span></p>
      {enteringId ? <div className="sw-map-transition" role="status">镜头已锁定 · 正在进入社会现场</div> : null}
    </>
  );
}
