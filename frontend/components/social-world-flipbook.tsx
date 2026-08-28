'use client';

import { useEffect, useRef, useState, type CSSProperties, type MouseEvent } from 'react';
import {
  stableUnit,
  WORLD_AGENTS,
  type WorldAgent,
  type WorldLevel,
  type WorldLocation,
} from '@/lib/social-world-fixtures';

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
  zoom: number;
  pan: { x: number; y: number };
  selectedAgentId?: string;
  interiorProfile: FlipbookInteriorProfile;
  onAgentSelect: (agent: WorldAgent) => void;
  onEnterInterior: (building: string) => void;
  onFloorChange: (floor: number) => void;
  onReturnCity: () => void;
  onReturnLocation: () => void;
};

type ScenePalette = {
  sky: string;
  paper: string;
  mountainFar: string;
  mountainNear: string;
  ground: string;
  groundSide: string;
  path: string;
  water: string;
  wall: string;
  wallSide: string;
  roof: string;
  accent: string;
  tree: string;
  ink: string;
};

type Point = { x: number; y: number };

const DEFAULT_PALETTE: ScenePalette = {
  sky: '#dfe8de', paper: '#eee9da', mountainFar: '#a9b9a6', mountainNear: '#718b78',
  ground: '#b8c99c', groundSide: '#819879', path: '#dfd3b7', water: '#85aeb0',
  wall: '#d9d1bd', wallSide: '#aaa590', roof: '#607d72', accent: '#b8714e', tree: '#52795f', ink: '#30453f',
};

const LOCATION_PALETTES: Record<string, ScenePalette> = {
  guiyang_convention: { ...DEFAULT_PALETTE, sky: '#d9e8e4', mountainFar: '#a5bab2', mountainNear: '#6f8f87', ground: '#adc6b1', roof: '#547d7a', accent: '#c27a4e', path: '#ddd4bf' },
  guiyang_big_data: { ...DEFAULT_PALETTE, sky: '#d8e8e7', mountainFar: '#9eb8b5', mountainNear: '#688a88', ground: '#a8c5b4', roof: '#466f72', accent: '#d49a53', water: '#7ba9af' },
  guizhou_university: { ...DEFAULT_PALETTE, sky: '#dee8dc', mountainFar: '#a8bca2', mountainNear: '#688568', ground: '#abc78f', roof: '#546f5b', accent: '#a76447', water: '#74a7a1' },
  jiaxiu_tower: { ...DEFAULT_PALETTE, sky: '#e7e2d2', mountainFar: '#b6b49c', mountainNear: '#777e67', ground: '#b8bd91', roof: '#596a5b', accent: '#ad5d42', water: '#759da0', wall: '#d8c69e' },
  qingyan_town: { ...DEFAULT_PALETTE, sky: '#e6dfce', mountainFar: '#b8af98', mountainNear: '#7f806b', ground: '#b9b68d', roof: '#5b6057', accent: '#9f5a41', path: '#cbbd9f', wall: '#cbbf9e' },
  guiyang_north_station: { ...DEFAULT_PALETTE, sky: '#dce6e7', mountainFar: '#a8b5b5', mountainNear: '#6e8182', ground: '#aebfb3', roof: '#58767c', accent: '#d18a50', path: '#d4d1c4' },
  huaguoyuan: { ...DEFAULT_PALETTE, sky: '#e4e4d5', mountainFar: '#b3b7a2', mountainNear: '#75816c', ground: '#a9bd87', roof: '#5f7770', accent: '#b66d4b', water: '#7fa7a0' },
};

const BUILDING_POINTS = [
  { x: 39, y: 47, svgX: 625, svgY: 540, scale: 1.06 },
  { x: 49, y: 39, svgX: 785, svgY: 445, scale: .94 },
  { x: 59, y: 52, svgX: 945, svgY: 575, scale: .86 },
  { x: 51, y: 69, svgX: 815, svgY: 750, scale: .78 },
];

const AGENT_POINTS = [
  { x: 44, y: 61 }, { x: 56, y: 60 }, { x: 49, y: 74 }, { x: 61, y: 70 },
  { x: 35, y: 68 }, { x: 66, y: 62 },
];

const ROOM_POINTS = [
  { x: 40, y: 52, svgX: 640, svgY: 575 },
  { x: 50, y: 43, svgX: 800, svgY: 485 },
  { x: 60, y: 54, svgX: 960, svgY: 595 },
  { x: 45, y: 70, svgX: 720, svgY: 760 },
  { x: 56, y: 71, svgX: 895, svgY: 770 },
];

const INTERIOR_AGENT_POINTS = [
  { x: 43, y: 58 }, { x: 54, y: 52 }, { x: 48, y: 75 }, { x: 59, y: 69 },
  { x: 36, y: 66 }, { x: 65, y: 62 },
];

function IsoBlock({ palette, width = 170, depth = 82, height = 105, storeys = 3 }: { palette: ScenePalette; width?: number; depth?: number; height?: number; storeys?: number }) {
  const half = width / 2;
  const halfDepth = depth / 2;
  return (
    <g className="sw-ink-stroke">
      <polygon points={`0,${-height - depth} ${half},${-height - halfDepth} 0,${-height} ${-half},${-height - halfDepth}`} fill={palette.roof} />
      <polygon points={`${-half},${-height - halfDepth} 0,${-height} 0,0 ${-half},${-halfDepth}`} fill={palette.wallSide} />
      <polygon points={`0,${-height} ${half},${-height - halfDepth} ${half},${-halfDepth} 0,0`} fill={palette.wall} />
      {Array.from({ length: storeys }, (_, index) => {
        const y = -height + 18 + index * Math.max(20, (height - 28) / storeys);
        return <path key={index} d={`M 13 ${y} L ${half - 12} ${y - halfDepth + 13}`} className="sw-iso-window-line" />;
      })}
      <path d={`M ${-half + 12} ${-halfDepth + 4} L ${-half + 12} ${-height - halfDepth + 15}`} className="sw-iso-detail" />
      <rect x="12" y="-35" width="25" height="31" rx="2" fill={palette.accent} opacity=".82" />
    </g>
  );
}

function HeritageHouse({ palette, tower = false }: { palette: ScenePalette; tower?: boolean }) {
  if (tower) {
    return (
      <g className="sw-ink-stroke">
        {[0, 1, 2].map((level) => {
          const y = -level * 68;
          const width = 150 - level * 30;
          return (
            <g key={level} transform={`translate(0 ${y})`}>
              <polygon points={`0,-78 ${width / 2},-38 0,-4 ${-width / 2},-38`} fill={level === 2 ? palette.accent : palette.roof} />
              <polygon points={`0,-4 ${width / 2 - 14},-34 ${width / 2 - 14},5 0,34`} fill={palette.wall} />
              <polygon points={`0,-4 ${-width / 2 + 14},-34 ${-width / 2 + 14},5 0,34`} fill={palette.wallSide} />
            </g>
          );
        })}
        <path d="M-96 -42 L0 8 L96 -42" fill="none" stroke={palette.ink} strokeWidth="5" />
      </g>
    );
  }
  return (
    <g className="sw-ink-stroke">
      <IsoBlock palette={palette} width={170} depth={74} height={72} storeys={2} />
      <polygon points="0,-174 112,-116 0,-66 -112,-116" fill={palette.roof} stroke={palette.ink} strokeWidth="3" />
      <path d="M-125 -112 L0 -55 L125 -112" fill="none" stroke={palette.accent} strokeWidth="5" strokeLinecap="round" />
    </g>
  );
}

function StationHall({ palette }: { palette: ScenePalette }) {
  return (
    <g className="sw-ink-stroke">
      <path d="M-145 -70 Q0 -180 145 -70 L145 -10 L0 60 L-145 -10Z" fill={palette.wall} />
      <path d="M-151 -75 Q0 -195 151 -75 L112 -49 Q0 -132 -112 -49Z" fill={palette.roof} />
      <path d="M-102 -35 L0 18 L103 -35" fill="none" stroke={palette.accent} strokeWidth="8" />
      {[-68, -34, 0, 34, 68].map((x) => <path key={x} d={`M${x} -72 L${x * .75} 8`} className="sw-iso-window-line" />)}
    </g>
  );
}

function ConventionHall({ palette }: { palette: ScenePalette }) {
  return (
    <g className="sw-ink-stroke">
      <IsoBlock palette={palette} width={255} depth={112} height={76} storeys={2} />
      <path d="M-135 -127 Q0 -205 135 -127 L95 -103 Q0 -154 -95 -103Z" fill={palette.roof} stroke={palette.ink} strokeWidth="3" />
      <path d="M-98 -52 L99 -150" stroke={palette.accent} strokeWidth="7" opacity=".8" />
    </g>
  );
}

function ResidentialCluster({ palette, index }: { palette: ScenePalette; index: number }) {
  const tall = index % 2 === 0;
  return (
    <g>
      <g transform="translate(-48 10) scale(.72)"><IsoBlock palette={palette} width={105} depth={58} height={tall ? 215 : 165} storeys={6} /></g>
      <g transform="translate(38 -6) scale(.84)"><IsoBlock palette={palette} width={112} depth={62} height={tall ? 250 : 195} storeys={7} /></g>
      <path d="M-110 22 Q0 -18 112 10" fill="none" stroke={palette.accent} strokeWidth="5" strokeDasharray="7 8" />
    </g>
  );
}

function IllustratedBuilding({ locationId, palette, index, active }: { locationId: string; palette: ScenePalette; index: number; active: boolean }) {
  const point = BUILDING_POINTS[index];
  let content = <IsoBlock palette={palette} height={96 + index * 13} storeys={3 + (index % 2)} />;
  if (locationId === 'guiyang_convention' && index === 0) content = <ConventionHall palette={palette} />;
  if (locationId === 'guiyang_big_data') content = <IsoBlock palette={palette} width={150 + index * 10} height={140 + index * 22} storeys={5} />;
  if (locationId === 'guizhou_university') content = <IsoBlock palette={palette} width={200 - index * 8} height={75 + index * 13} storeys={3} />;
  if (locationId === 'jiaxiu_tower' || locationId === 'qingyan_town') content = <HeritageHouse palette={palette} tower={index === 0} />;
  if (locationId === 'guiyang_north_station' && index === 0) content = <StationHall palette={palette} />;
  if (locationId === 'huaguoyuan') content = <ResidentialCluster palette={palette} index={index} />;
  return (
    <g transform={`translate(${point.svgX} ${point.svgY}) scale(${point.scale})`}>
      <ellipse cx="0" cy="18" rx="118" ry="39" fill="#243c35" opacity=".14" />
      <g className={`sw-illustrated-building ${active ? 'is-active' : ''}`}>{content}</g>
    </g>
  );
}

function Tree({ x, y, scale, palette }: { x: number; y: number; scale: number; palette: ScenePalette }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} className="sw-illustrated-tree">
      <ellipse cx="0" cy="13" rx="24" ry="9" fill="#314d3e" opacity=".16" />
      <path d="M-3 7 L2 -45 L8 8Z" fill="#765c43" stroke={palette.ink} strokeWidth="2" />
      <circle cx="-13" cy="-45" r="25" fill={palette.tree} /><circle cx="14" cy="-53" r="28" fill={palette.mountainNear} /><circle cx="3" cy="-72" r="25" fill={palette.tree} />
    </g>
  );
}

function PersonGlyph({ x, y, color, scale = 1 }: { x: number; y: number; color: string; scale?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} className="sw-illustrated-person">
      <ellipse cx="0" cy="8" rx="10" ry="4" fill="#203932" opacity=".18" />
      <circle cx="0" cy="-15" r="5" fill="#b98263" stroke="#344942" strokeWidth="1.4" />
      <path d="M-5 -9 Q0 -14 5 -9 L7 3 L0 8 L-7 3Z" fill={color} stroke="#344942" strokeWidth="1.4" />
      <path d="M-2 6 L-5 15 M3 6 L6 15" stroke="#344942" strokeWidth="2.2" strokeLinecap="round" />
    </g>
  );
}

function SceneDefs({ id, palette }: { id: string; palette: ScenePalette }) {
  return (
    <defs>
      <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1"><stop stopColor={palette.sky} /><stop offset="1" stopColor={palette.paper} /></linearGradient>
      <linearGradient id={`${id}-water`} x1="0" y1="0" x2="1" y2="1"><stop stopColor={palette.water} stopOpacity=".9" /><stop offset=".55" stopColor="#dbe1d0" stopOpacity=".68" /><stop offset="1" stopColor={palette.water} /></linearGradient>
      <filter id={`${id}-paper`} x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency=".55" numOctaves="3" seed="7" result="noise" />
        <feColorMatrix in="noise" type="saturate" values="0" result="grain" />
        <feComponentTransfer in="grain"><feFuncA type="table" tableValues="0 .13" /></feComponentTransfer>
      </filter>
    </defs>
  );
}

function LocationIllustration({ location, buildings, hoveredBuilding }: { location: WorldLocation; buildings: string[]; hoveredBuilding: number | null }) {
  const palette = LOCATION_PALETTES[location.id] || DEFAULT_PALETTE;
  const waterScene = ['jiaxiu_tower', 'guizhou_university', 'huaguoyuan'].includes(location.id);
  const people = Array.from({ length: 38 }, (_, index) => ({
    x: 435 + stableUnit(`${location.id}:person-x:${index}`) * 730,
    y: 555 + stableUnit(`${location.id}:person-y:${index}`) * 265,
    scale: .6 + stableUnit(`${location.id}:person-s:${index}`) * .45,
    color: [palette.accent, palette.roof, '#d2a453', '#557b68'][index % 4],
  }));
  const trees = Array.from({ length: 18 }, (_, index) => ({
    x: 365 + stableUnit(`${location.id}:tree-x:${index}`) * 860,
    y: 500 + stableUnit(`${location.id}:tree-y:${index}`) * 335,
    scale: .45 + stableUnit(`${location.id}:tree-s:${index}`) * .42,
  }));
  return (
    <svg className="sw-flipbook-svg" viewBox="0 0 1600 1000" preserveAspectRatio="none" aria-hidden="true">
      <SceneDefs id={location.id} palette={palette} />
      <rect width="1600" height="1000" fill={`url(#${location.id}-sky)`} />
      <circle cx="1200" cy="164" r="86" fill="#f3d99b" opacity=".55" />
      <path d="M0 420 Q180 210 340 390 Q510 130 720 376 Q930 110 1115 360 Q1340 185 1600 410 L1600 610 L0 610Z" fill={palette.mountainFar} opacity=".62" />
      <path d="M0 510 Q210 310 410 493 Q595 245 790 478 Q1005 275 1180 470 Q1360 320 1600 520 L1600 650 L0 650Z" fill={palette.mountainNear} opacity=".78" />
      <path d="M175 720 L760 382 L1450 682 L855 985Z" fill={palette.groundSide} stroke={palette.ink} strokeWidth="4" />
      <path d="M175 684 L760 346 L1450 646 L855 949Z" fill={palette.ground} stroke={palette.ink} strokeWidth="4" />
      <path d="M330 682 C570 565 635 502 770 445 C900 390 1032 515 1274 626" fill="none" stroke={palette.path} strokeWidth="64" strokeLinecap="round" opacity=".9" />
      <path d="M482 818 C620 688 730 670 842 596 C934 535 1005 600 1125 740" fill="none" stroke={palette.path} strokeWidth="38" strokeLinecap="round" opacity=".84" />
      <path d="M330 682 C570 565 635 502 770 445 C900 390 1032 515 1274 626" fill="none" stroke={palette.ink} strokeWidth="3" strokeDasharray="10 18" opacity=".28" />
      {waterScene ? <path d="M225 783 C470 668 588 760 790 698 C977 641 1105 665 1388 764 L1215 866 C1037 797 930 801 766 846 C593 895 436 822 316 838Z" fill={`url(#${location.id}-water)`} stroke={palette.ink} strokeWidth="3" /> : null}
      {trees.map((tree, index) => <Tree key={index} {...tree} palette={palette} />)}
      {buildings.slice(0, 4).map((_, index) => <IllustratedBuilding key={index} locationId={location.id} palette={palette} index={index} active={hoveredBuilding === index} />)}
      {people.map((person, index) => <PersonGlyph key={index} {...person} />)}
      <g opacity=".72">
        <path d="M370 850 C600 730 930 760 1220 685" fill="none" stroke={palette.accent} strokeWidth="4" strokeDasharray="4 16" />
        <path d="M730 404 C712 457 684 493 635 527" fill="none" stroke={palette.accent} strokeWidth="4" strokeDasharray="4 14" />
      </g>
      <rect width="1600" height="1000" fill="#6b5742" opacity=".18" filter={`url(#${location.id}-paper)`} />
      <path d="M18 18 H1582 V982 H18Z" fill="none" stroke={palette.ink} strokeWidth="2" opacity=".2" />
    </svg>
  );
}

function Furniture({ kind, index, palette }: { kind: string; index: number; palette: ScenePalette }) {
  const isReading = /阅读|学习/.test(kind);
  const isLab = /实验|协作/.test(kind);
  const isDining = /餐饮/.test(kind);
  const isAuditorium = /演讲|展演/.test(kind);
  if (isReading) return <g>{[-42, -12, 18, 48].map((x) => <rect key={x} x={x} y={-58 + (x % 2) * 2} width="15" height="76" rx="2" fill={index % 2 ? palette.wallSide : palette.roof} stroke={palette.ink} strokeWidth="2" />)}</g>;
  if (isLab) return <g><path d="M-58 -22 L0 -52 L58 -22 L0 10Z" fill={palette.wall} stroke={palette.ink} strokeWidth="2" />{[-35, 0, 35].map((x) => <circle key={x} cx={x} cy={-20 - Math.abs(x) * .25} r="8" fill={palette.accent} />)}</g>;
  if (isAuditorium) return <g>{[0, 1, 2].map((row) => <path key={row} d={`M${-58 + row * 8} ${-42 + row * 24} L0 ${-12 + row * 24} L${58 - row * 8} ${-42 + row * 24}`} fill="none" stroke={row === 0 ? palette.accent : palette.roof} strokeWidth="9" strokeLinecap="round" />)}</g>;
  if (isDining) return <g>{[-34, 28].map((x) => <g key={x}><ellipse cx={x} cy="-20" rx="27" ry="14" fill={palette.wall} stroke={palette.ink} strokeWidth="2" /><path d={`M${x} -8 V22`} stroke={palette.ink} strokeWidth="4" /></g>)}</g>;
  return <g><path d="M-58 -15 L-18 -36 L20 -16 L-21 7Z" fill={palette.wall} stroke={palette.ink} strokeWidth="3" /><path d="M5 -6 L43 -25 L63 -13 L23 8Z" fill={palette.accent} opacity=".75" /></g>;
}

function InteriorIllustration({ location, profile, activeRoom }: { location: WorldLocation; profile: FlipbookInteriorProfile; activeRoom: number | null }) {
  const palette = LOCATION_PALETTES[location.id] || DEFAULT_PALETTE;
  return (
    <svg className="sw-flipbook-svg" viewBox="0 0 1600 1000" preserveAspectRatio="none" aria-hidden="true">
      <SceneDefs id={`${location.id}-inside`} palette={palette} />
      <rect width="1600" height="1000" fill={palette.paper} />
      <path d="M0 385 Q230 210 420 372 Q645 178 835 367 Q1095 185 1290 370 Q1450 270 1600 390 V610 H0Z" fill={palette.mountainFar} opacity=".48" />
      <polygon points="300,718 790,420 1320,690 820,968" fill={palette.groundSide} stroke={palette.ink} strokeWidth="5" />
      <polygon points="300,682 790,385 1320,655 820,930" fill="#d8cfb9" stroke={palette.ink} strokeWidth="5" />
      <polygon points="300,682 790,385 790,208 300,505" fill="#c8c6ad" stroke={palette.ink} strokeWidth="4" />
      <polygon points="790,385 1320,655 1320,476 790,208" fill="#ddd5c1" stroke={palette.ink} strokeWidth="4" />
      <path d="M345 561 L752 315 M836 292 L1256 505" stroke={palette.accent} strokeWidth="8" opacity=".7" />
      <path d="M790 385 L790 906 M548 535 L1050 792 M548 812 L1049 516" fill="none" stroke={palette.ink} strokeWidth="3" strokeDasharray="11 12" opacity=".35" />
      {ROOM_POINTS.map((point, index) => (
        <g key={index} transform={`translate(${point.svgX} ${point.svgY})`} className={`sw-illustrated-room ${activeRoom === index ? 'is-active' : activeRoom !== null ? 'is-muted' : ''}`}>
          <ellipse cx="0" cy="24" rx="112" ry="41" fill="#294239" opacity=".12" />
          <polygon points="-105,-22 0,-78 108,-25 0,35" fill={index % 2 ? '#c7c7ad' : '#d7ceb5'} stroke={palette.ink} strokeWidth="3" />
          <Furniture kind={profile.kind} index={index} palette={palette} />
          <PersonGlyph x={-68} y={16} color={palette.accent} scale={.8} />
          <PersonGlyph x={67} y={4} color={palette.roof} scale={.72} />
        </g>
      ))}
      <rect width="1600" height="1000" fill="#765b3f" opacity=".16" filter={`url(#${location.id}-inside-paper)`} />
      <path d="M18 18 H1582 V982 H18Z" fill="none" stroke={palette.ink} strokeWidth="2" opacity=".2" />
    </svg>
  );
}

function AgentHotspot({ agent, point, selected, indoor, onSelect }: { agent: WorldAgent; point: Point; selected: boolean; indoor: boolean; onSelect: (agent: WorldAgent) => void }) {
  return (
    <button
      className={`sw-flipbook-agent ${selected ? 'selected' : ''}`}
      style={{ left: `${point.x}%`, top: `${point.y}%` }}
      type="button"
      aria-label={`查看人物 ${agent.name}，${agent.role}`}
      onClick={() => onSelect(agent)}
    >
      <span className="sw-flipbook-agent-figure" aria-hidden="true"><i /><b /></span>
      <strong>{agent.name}</strong>
      <small>{indoor ? agent.action : agent.role}</small>
    </button>
  );
}

function getOrigin(event: MouseEvent<HTMLElement>, root: HTMLDivElement | null): Point {
  const rect = root?.getBoundingClientRect();
  if (!rect) return { x: 50, y: 50 };
  if (event.detail === 0) return { x: 50, y: 50 };
  return {
    x: Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100)),
    y: Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100)),
  };
}

export function SocialWorldFlipbook({
  level,
  location,
  building,
  floor,
  zoom,
  pan,
  selectedAgentId,
  interiorProfile,
  onAgentSelect,
  onEnterInterior,
  onFloorChange,
  onReturnCity,
  onReturnLocation,
}: SocialWorldFlipbookProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const timerRef = useRef<number | null>(null);
  const [origin, setOrigin] = useState<Point>({ x: 50, y: 52 });
  const [departing, setDeparting] = useState(false);
  const [rippleKey, setRippleKey] = useState(0);
  const [hoveredBuilding, setHoveredBuilding] = useState<number | null>(null);
  const [roomFocus, setRoomFocus] = useState<{ pageKey: string; index: number } | null>(null);

  const buildings = location.buildings || ['公共服务中心', '共享工作站', '社区活动厅', '生活服务站'];
  const localAgents = WORLD_AGENT_CACHE(location.id)
    .sort((left, right) => stableUnit(`${left.id}:${building}:${floor}`) - stableUnit(`${right.id}:${building}:${floor}`))
    .slice(0, location.featured ? 6 : 4);
  const pageKey = level === 'campus' ? `place:${location.id}` : `inside:${location.id}:${building}:${floor}`;
  const activeRoom = roomFocus?.pageKey === pageKey ? roomFocus.index : null;
  const agentPoints = level === 'interior' ? INTERIOR_AGENT_POINTS : AGENT_POINTS;
  const pageNumber = level === 'campus' ? '01' : String(floor + 1).padStart(2, '0');

  useEffect(() => () => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
  }, []);

  function navigate(event: MouseEvent<HTMLElement>, action: () => void) {
    if (departing) return;
    const nextOrigin = getOrigin(event, rootRef.current);
    setOrigin(nextOrigin);
    setRippleKey((value) => value + 1);
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      action();
      return;
    }
    setDeparting(true);
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      setDeparting(false);
      timerRef.current = null;
      action();
    }, 360);
  }

  const sceneStyle = {
    '--sw-flip-origin-x': `${origin.x}%`,
    '--sw-flip-origin-y': `${origin.y}%`,
    '--sw-flip-zoom': String(zoom),
    '--sw-flip-pan-x': `${pan.x}px`,
    '--sw-flip-pan-y': `${pan.y}px`,
  } as CSSProperties;

  return (
    <div
      ref={rootRef}
      className={`sw-flipbook-shell sw-${level}-scene scene-${location.id} ${departing ? 'is-departing' : ''}`}
      style={sceneStyle}
      aria-label={`${location.name}${level === 'interior' ? `${building}${floor}层` : ''} 2.5D 交互画页`}
    >
      <div key={pageKey} className="sw-flipbook-frame">
        <div className="sw-flipbook-artboard">
          <div className="sw-flipbook-sheet">
            {level === 'campus'
              ? <LocationIllustration location={location} buildings={[...buildings]} hoveredBuilding={hoveredBuilding} />
              : <InteriorIllustration location={location} profile={interiorProfile} activeRoom={activeRoom} />}
            <div className="sw-flipbook-hotspots">
              {level === 'campus' ? buildings.slice(0, 4).map((item, index) => {
                const point = BUILDING_POINTS[index];
                return (
                  <button
                    key={item}
                    className="sw-flipbook-enter"
                    style={{ left: `${point.x}%`, top: `${point.y}%` }}
                    type="button"
                    aria-label={`进入 ${item}`}
                    onMouseEnter={() => setHoveredBuilding(index)}
                    onMouseLeave={() => setHoveredBuilding(null)}
                    onFocus={() => setHoveredBuilding(index)}
                    onBlur={() => setHoveredBuilding(null)}
                    onClick={(event) => navigate(event, () => onEnterInterior(item))}
                  >
                    <span aria-hidden="true"><i /></span>
                    <strong>{item}</strong>
                    <small>{index === 0 ? '点击进入 · 可探索室内' : '进入画页'}</small>
                  </button>
                );
              }) : interiorProfile.rooms.map((room, index) => {
                const point = ROOM_POINTS[index];
                const selected = activeRoom === index;
                return (
                  <button
                    key={room}
                    className={`sw-flipbook-room ${selected ? 'selected' : ''}`}
                    style={{ left: `${point.x}%`, top: `${point.y}%` }}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setRoomFocus(selected ? null : { pageKey, index })}
                  >
                    <span aria-hidden="true"><i /></span>
                    <strong>{room}</strong>
                  </button>
                );
              })}
              {localAgents.map((agent, index) => (
                <AgentHotspot
                  key={agent.id}
                  agent={agent}
                  point={agentPoints[index % agentPoints.length]}
                  selected={selectedAgentId === agent.id}
                  indoor={level === 'interior'}
                  onSelect={onAgentSelect}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {departing ? <span key={rippleKey} className="sw-flipbook-ripple" style={{ left: `${origin.x}%`, top: `${origin.y}%` }} aria-hidden="true" /> : null}
      <div className="sw-flipbook-grain" aria-hidden="true" />
      <div className="sw-flipbook-page-curl" aria-hidden="true" />

      <nav className="sw-flipbook-breadcrumb" aria-label="画页路径">
        <button type="button" onClick={(event) => navigate(event, onReturnCity)}>贵阳全景</button>
        <span aria-hidden="true">›</span>
        {level === 'interior' ? <button type="button" onClick={(event) => navigate(event, onReturnLocation)}>{location.short}</button> : <strong aria-current="page">{location.short}</strong>}
        {level === 'interior' ? <><span aria-hidden="true">›</span><strong aria-current={activeRoom === null ? 'page' : undefined}>{building} · {floor}F</strong></> : null}
        {activeRoom !== null ? <><span aria-hidden="true">›</span><button type="button" aria-current="page" onClick={() => setRoomFocus(null)}>{interiorProfile.rooms[activeRoom]}</button></> : null}
      </nav>

      <div className="sw-flipbook-caption" aria-hidden="true">
        <span>GUIYANG SOCIAL ATLAS</span>
        <strong>{level === 'campus' ? location.scene.architecture : `${building} · ${interiorProfile.floorName}`}</strong>
        <small>{level === 'campus' ? location.scene.signature : interiorProfile.activity}</small>
      </div>

      <div className="sw-flipbook-pagination" aria-label="画页进度">
        <span>PAGE</span><strong>{pageNumber}</strong><i />
        <small>{level === 'campus' ? '地点画页' : `${floor}F 室内画页`}</small>
      </div>

      {level === 'interior' ? (
        <>
          <aside className="sw-floor-profile sw-glass">
            <span>楼层运行画像</span>
            <strong>{interiorProfile.kind}</strong>
            <p>{interiorProfile.activity}</p>
            <div><small>承载 {interiorProfile.capacity} 人</small><small>{interiorProfile.openHours}</small></div>
            <footer>{interiorProfile.transition}</footer>
          </aside>
          <nav className="sw-floor-nav" aria-label="楼层画页">
            <span>画页</span>
            {[5, 4, 3, 2, 1].map((item) => (
              <button
                className={floor === item ? 'active' : ''}
                aria-current={floor === item ? 'page' : undefined}
                type="button"
                key={item}
                onClick={(event) => floor !== item && navigate(event, () => onFloorChange(item))}
              >{item}F</button>
            ))}
          </nav>
        </>
      ) : (
        <section className="sw-scene-overview sw-glass">
          <span>可探索地点画页</span><strong>{location.name}</strong><p>{location.description}</p><small>点击发光入口进入下一幅画页 · 点击人物查看稳定人格档案</small>
        </section>
      )}

      <div className={`sw-scene-atmosphere atmosphere-${location.scene.atmosphere}`} aria-hidden="true" />
      <div className="sw-scene-sim-status"><i /><span>{level === 'campus' ? location.scene.status : `${interiorProfile.count} 个室内活动体 · ${interiorProfile.activity}`}</span><b>2.5D</b></div>
    </div>
  );
}

// Kept as a function so new/remote personas can be mapped in one place later.
function WORLD_AGENT_CACHE(locationId: string) {
  return WORLD_AGENTS.filter((agent) => agent.locationId === locationId);
}
