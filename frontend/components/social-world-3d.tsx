'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { WorldAgent } from '@/lib/social-world-fixtures';

export type SocialWorldSceneMode = 'campus' | 'district' | 'interior';

type SceneView = {
  rotation: number;
  zoom: number;
  panX: number;
  panY: number;
  selectedAgentId?: string;
};

type SocialWorld3DProps = {
  mode: SocialWorldSceneMode;
  variant?: string;
  building?: string;
  floor?: number;
  rotation: number;
  zoom: number;
  pan?: { x: number; y: number };
  agents?: WorldAgent[];
  anchors?: SceneOverlayAnchor[];
  selectedAgentId?: string;
  onAgentSelect?: (agent: WorldAgent) => void;
  onAnchorSelect?: (anchor: SceneOverlayAnchor) => void;
};

export type SceneOverlayAnchor = {
  id: string;
  label: string;
  position: [number, number, number];
  kind?: 'poi' | 'entrance' | 'room';
  detail?: string;
  actionId?: string;
};

type Block = {
  x: number;
  z: number;
  width: number;
  depth: number;
  height: number;
  color: number;
  roof?: number;
  accent?: number;
};

type PopulationLayer = {
  meshes: THREE.InstancedMesh[];
  baseX: Float32Array;
  baseZ: Float32Array;
  phase: Float32Array;
  speed: Float32Array;
  count: number;
  movingCount: number;
};

type HeroRig = {
  agent: WorldAgent;
  root: THREE.Group;
  leftArm: THREE.Group;
  rightArm: THREE.Group;
  leftLeg: THREE.Group;
  rightLeg: THREE.Group;
  halo: THREE.Mesh;
  phase: number;
  moving: boolean;
  baseX: number;
  baseZ: number;
};

type AtmosphereLayer = THREE.Points & { userData: { speeds?: Float32Array; drift?: number; falling?: boolean } };

type SceneWorld = {
  group: THREE.Group;
  population: PopulationLayer;
  atmosphere: AtmosphereLayer | null;
  heroes: HeroRig[];
  pickables: THREE.Object3D[];
};

const CAMPUS_BLOCKS: Block[] = [
  { x: -11.5, z: -9.3, width: 8.8, depth: 3.7, height: 3.5, color: 0xd8d0c2, roof: 0xb8b6ad, accent: 0x8e6653 },
  { x: -2.3, z: -10.1, width: 6.2, depth: 4.0, height: 5.2, color: 0xd9d9d1, roof: 0xbfc7c2, accent: 0x4f7775 },
  { x: 7.2, z: -9.6, width: 8.0, depth: 3.8, height: 4.5, color: 0xd8dcd7, roof: 0xb8c3be, accent: 0x456f70 },
  { x: 15.4, z: -7.8, width: 4.4, depth: 6.2, height: 5.6, color: 0xd4dad7, roof: 0xb5c0bc, accent: 0x4a7572 },
  { x: -15.9, z: -1.6, width: 5.8, depth: 4.6, height: 3.1, color: 0xded3c4, roof: 0xbdaea0, accent: 0x936650 },
  { x: -7.7, z: -1.6, width: 5.3, depth: 4.2, height: 3.6, color: 0xe0d9ce, roof: 0xc0b7aa, accent: 0x836351 },
  { x: 12.9, z: 0.8, width: 6.8, depth: 4.4, height: 3.7, color: 0xdedbd2, roof: 0xc0c3bd, accent: 0x647f7a },
  { x: -15.4, z: 7.1, width: 6.3, depth: 4.0, height: 3.9, color: 0xd8d1c4, roof: 0xbab2a8, accent: 0x8d6652 },
  { x: -7.1, z: 8.2, width: 5.3, depth: 3.9, height: 3.0, color: 0xe1d9cd, roof: 0xc2b8aa, accent: 0x936a52 },
  { x: 3.1, z: 8.6, width: 7.4, depth: 4.2, height: 4.2, color: 0xd5dbd6, roof: 0xb8c3bd, accent: 0x4d7974 },
  { x: 12.3, z: 9.1, width: 6.4, depth: 4.4, height: 4.8, color: 0xd2d9d6, roof: 0xb3c0bc, accent: 0x47736f },
];

const PERSON_COLORS = [0x295c63, 0xc16d4f, 0xd0a057, 0x6c7d53, 0x6b6f96, 0x8d5c59, 0x2f8278];

function seededRandom(seedText: string) {
  let seed = 2166136261;
  for (let index = 0; index < seedText.length; index += 1) {
    seed ^= seedText.charCodeAt(index);
    seed = Math.imul(seed, 16777619);
  }
  return () => {
    seed += 0x6d2b79f5;
    let value = seed;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function addBox(
  parent: THREE.Object3D,
  size: [number, number, number],
  position: [number, number, number],
  material: THREE.Material,
  rotationY = 0,
  shadows = true,
) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
  mesh.position.set(...position);
  mesh.rotation.y = rotationY;
  mesh.castShadow = shadows;
  mesh.receiveShadow = shadows;
  parent.add(mesh);
  return mesh;
}

function addPlane(
  parent: THREE.Object3D,
  width: number,
  depth: number,
  x: number,
  z: number,
  material: THREE.Material,
  rotationY = 0,
  y = 0.015,
) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.rotation.z = rotationY;
  mesh.position.set(x, y, z);
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function addRibbonPath(
  parent: THREE.Object3D,
  points: Array<[number, number]>,
  width: number,
  material: THREE.Material,
  y = 0.035,
) {
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  points.forEach(([x, z], index) => {
    const previous = points[Math.max(0, index - 1)];
    const next = points[Math.min(points.length - 1, index + 1)];
    const tangentX = next[0] - previous[0];
    const tangentZ = next[1] - previous[1];
    const length = Math.max(0.001, Math.hypot(tangentX, tangentZ));
    const normalX = (-tangentZ / length) * width * 0.5;
    const normalZ = (tangentX / length) * width * 0.5;
    positions.push(x + normalX, y, z + normalZ, x - normalX, y, z - normalZ);
    const progress = index / Math.max(1, points.length - 1);
    uvs.push(0, progress, 1, progress);
    if (index < points.length - 1) {
      const base = index * 2;
      indices.push(base, base + 1, base + 2, base + 1, base + 3, base + 2);
    }
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, material);
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function addDetailedAcademicBuilding(
  parent: THREE.Object3D,
  block: Block,
  options: { rotation?: number; brick?: boolean; atrium?: boolean; setbacks?: number } = {},
) {
  const group = new THREE.Group();
  group.position.set(block.x, 0, block.z);
  group.rotation.y = options.rotation ?? 0;
  parent.add(group);
  const wall = new THREE.MeshStandardMaterial({ color: block.color, roughness: 0.78, metalness: 0.02 });
  const stone = new THREE.MeshStandardMaterial({ color: options.brick ? 0xbca58f : 0xc9cdc7, roughness: 0.84 });
  const roof = new THREE.MeshStandardMaterial({ color: block.roof ?? 0xbac3be, roughness: 0.7, metalness: 0.08 });
  const glass = new THREE.MeshPhysicalMaterial({ color: block.accent ?? 0x4e7775, roughness: 0.16, metalness: 0.12, transparent: true, opacity: 0.8 });
  const shadowGlass = new THREE.MeshStandardMaterial({ color: 0x375e60, roughness: 0.34, metalness: 0.12 });
  const baseHeight = Math.max(2.2, block.height - 0.36);
  addBox(group, [block.width, baseHeight, block.depth], [0, baseHeight / 2 + 0.1, 0], wall);
  addBox(group, [block.width + 0.3, 0.2, block.depth + 0.3], [0, baseHeight + 0.18, 0], roof);
  addBox(group, [block.width * 0.46, 0.35, block.depth * 0.46], [0, baseHeight + 0.43, 0], roof);

  const floors = Math.max(3, Math.round(baseHeight / 0.82));
  for (let floor = 0; floor < floors; floor += 1) {
    const y = 0.62 + floor * ((baseHeight - 0.5) / floors);
    addBox(group, [block.width * 0.82, 0.13, 0.06], [0, y, block.depth / 2 + 0.035], glass, 0, false);
    addBox(group, [block.width * 0.82, 0.1, 0.04], [0, y, -block.depth / 2 - 0.025], shadowGlass, 0, false);
  }
  const bayCount = Math.max(3, Math.round(block.width / 1.25));
  for (let index = 0; index <= bayCount; index += 1) {
    const x = -block.width * 0.42 + (index / bayCount) * block.width * 0.84;
    addBox(group, [0.07, baseHeight * 0.76, 0.11], [x, baseHeight * 0.5, block.depth / 2 + 0.07], stone, 0, false);
  }
  if (options.atrium) {
    addBox(group, [Math.min(2.1, block.width * 0.34), baseHeight * 0.78, block.depth + 0.12], [0, baseHeight * 0.48, 0], glass, 0, false);
    addBox(group, [Math.min(2.45, block.width * 0.39), 0.2, block.depth + 0.28], [0, baseHeight * 0.9, 0], roof, 0, false);
  }
  const setbacks = options.setbacks ?? 0;
  for (let index = 0; index < setbacks; index += 1) {
    const direction = index % 2 ? -1 : 1;
    addBox(group, [block.width * 0.34, 0.38, block.depth + 0.26], [direction * block.width * 0.31, baseHeight + 0.36 + index * 0.08, 0], roof);
  }
  return group;
}

function addCampusLibrary(parent: THREE.Object3D, x: number, z: number) {
  const group = new THREE.Group();
  group.position.set(x, 0, z);
  parent.add(group);
  const paleStone = new THREE.MeshStandardMaterial({ color: 0xd6d0c4, roughness: 0.82 });
  const redStone = new THREE.MeshStandardMaterial({ color: 0xa7775f, roughness: 0.88 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x416f73, roughness: 0.14, metalness: 0.16, transparent: true, opacity: 0.84 });
  const metal = new THREE.MeshStandardMaterial({ color: 0x8f9b98, roughness: 0.52, metalness: 0.28 });
  addBox(group, [7.8, 0.55, 5.5], [0, 0.3, 0], paleStone);
  addBox(group, [6.7, 3.6, 4.45], [0, 2.1, -0.05], redStone);
  addBox(group, [2.8, 3.25, 4.62], [0, 2.05, 0], glass, 0, false);
  addBox(group, [7.25, 0.26, 4.9], [0, 3.98, -0.05], metal);
  addBox(group, [5.5, 0.65, 3.2], [0, 4.42, -0.05], paleStone);
  for (let index = -3; index <= 3; index += 1) {
    addBox(group, [0.1, 2.75, 0.14], [index * 0.82, 2.1, 2.31], paleStone, 0, false);
  }
  for (let step = 0; step < 4; step += 1) {
    addBox(group, [3.8 + step * 0.5, 0.09, 0.42], [0, 0.05 + step * 0.07, 3.05 + step * 0.38], paleStone, 0, false);
  }
}

function addCampusAuditorium(parent: THREE.Object3D, x: number, z: number, rotation = 0) {
  const group = new THREE.Group();
  group.position.set(x, 0, z);
  group.rotation.y = rotation;
  parent.add(group);
  const stone = new THREE.MeshStandardMaterial({ color: 0xd6c9b8, roughness: 0.84 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x557f80, roughness: 0.17, transparent: true, opacity: 0.76 });
  const roof = new THREE.MeshStandardMaterial({ color: 0x9fa9a5, roughness: 0.62, metalness: 0.16 });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(2.7, 3.05, 2.45, 32), stone);
  body.scale.z = 0.72;
  body.position.y = 1.28;
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);
  const crown = new THREE.Mesh(new THREE.CylinderGeometry(2.86, 2.82, 0.24, 32), roof);
  crown.scale.z = 0.76;
  crown.position.y = 2.62;
  crown.castShadow = true;
  group.add(crown);
  addBox(group, [3.5, 1.62, 0.12], [0, 1.22, 2.18], glass, 0, false);
  for (let index = -3; index <= 3; index += 1) addBox(group, [0.08, 1.68, 0.18], [index * 0.48, 1.2, 2.27], roof, 0, false);
}

function addCampusCanteen(parent: THREE.Object3D, x: number, z: number) {
  const wall = new THREE.MeshStandardMaterial({ color: 0xdccfbe, roughness: 0.82 });
  const roof = new THREE.MeshStandardMaterial({ color: 0xa9b4b0, roughness: 0.65, metalness: 0.12 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x5b8580, roughness: 0.15, transparent: true, opacity: 0.78 });
  addBox(parent, [7.2, 2.25, 4.7], [x, 1.18, z], wall);
  addBox(parent, [7.65, 0.22, 5.15], [x, 2.4, z], roof);
  addBox(parent, [6.25, 1.42, 0.1], [x, 1.22, z + 2.38], glass, 0, false);
  for (let index = -3; index <= 3; index += 1) addBox(parent, [0.09, 1.46, 0.16], [x + index * 0.82, 1.22, z + 2.47], roof, 0, false);
  addBox(parent, [2.4, 0.18, 1.25], [x, 2.72, z - 0.15], roof);
}

function addCampusGate(parent: THREE.Object3D, x: number, z: number) {
  const stone = new THREE.MeshStandardMaterial({ color: 0xd6cbbb, roughness: 0.9 });
  const red = new THREE.MeshStandardMaterial({ color: 0x934e43, roughness: 0.78 });
  addBox(parent, [0.62, 2.7, 0.72], [x - 3.1, 1.36, z], stone);
  addBox(parent, [0.62, 2.7, 0.72], [x + 3.1, 1.36, z], stone);
  addBox(parent, [6.85, 0.42, 0.84], [x, 2.55, z], stone);
  addBox(parent, [3.4, 0.16, 0.88], [x, 2.56, z + 0.02], red, 0, false);
}

function addCampusTrack(parent: THREE.Object3D, x: number, z: number) {
  const trackMaterial = new THREE.MeshStandardMaterial({ color: 0xa96152, roughness: 0.94 });
  const fieldMaterial = new THREE.MeshStandardMaterial({ color: 0x62855f, roughness: 1 });
  const lineMaterial = new THREE.MeshBasicMaterial({ color: 0xe2d5c3, transparent: true, opacity: 0.72, side: THREE.DoubleSide });
  const track = new THREE.Mesh(new THREE.RingGeometry(2.25, 3.35, 64), trackMaterial);
  track.rotation.x = -Math.PI / 2;
  track.scale.z = 0.62;
  track.position.set(x, 0.055, z);
  track.receiveShadow = true;
  parent.add(track);
  const field = new THREE.Mesh(new THREE.CircleGeometry(2.17, 64), fieldMaterial);
  field.rotation.x = -Math.PI / 2;
  field.scale.z = 0.62;
  field.position.set(x, 0.06, z);
  field.receiveShadow = true;
  parent.add(field);
  for (let index = 0; index < 4; index += 1) {
    const radius = 2.42 + index * 0.23;
    const lane = new THREE.Mesh(new THREE.RingGeometry(radius, radius + 0.025, 64), lineMaterial);
    lane.rotation.x = -Math.PI / 2;
    lane.scale.z = 0.62;
    lane.position.set(x, 0.065, z);
    parent.add(lane);
  }
}

function addBroadleafTrees(parent: THREE.Object3D, random: () => number, blocks: Block[], count: number) {
  const trunkGeometry = new THREE.CylinderGeometry(0.055, 0.09, 0.72, 7);
  const lowerGeometry = new THREE.IcosahedronGeometry(0.42, 1);
  const upperGeometry = new THREE.IcosahedronGeometry(0.34, 1);
  const trunkMaterial = new THREE.MeshStandardMaterial({ color: 0x66513e, roughness: 1 });
  const foliageMaterial = new THREE.MeshStandardMaterial({ color: 0x4d7654, roughness: 0.98, vertexColors: true });
  const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, count);
  const lower = new THREE.InstancedMesh(lowerGeometry, foliageMaterial, count);
  const upper = new THREE.InstancedMesh(upperGeometry, foliageMaterial, count);
  const dummy = new THREE.Object3D();
  let created = 0;
  let attempts = 0;
  while (created < count && attempts < count * 18) {
    attempts += 1;
    const x = (random() - 0.5) * 45;
    const z = (random() - 0.5) * 32;
    const sports = x < -10.4 && z > 5.1;
    const lake = x > 3 && x < 11 && z > -0.2 && z < 5.2;
    const mainAxis = Math.abs(x) < 2.2 && z > -6 && z < 12;
    if (sports || lake || mainAxis || isNearBlock(x, z, blocks, 0.65)) continue;
    const scale = 0.78 + random() * 0.7;
    dummy.position.set(x, 0.38 * scale, z);
    dummy.scale.set(scale, scale, scale);
    dummy.rotation.y = random() * Math.PI;
    dummy.updateMatrix();
    trunks.setMatrixAt(created, dummy.matrix);
    dummy.position.y = 1.06 * scale;
    dummy.scale.set(scale * 1.05, scale * (0.9 + random() * 0.18), scale);
    dummy.updateMatrix();
    lower.setMatrixAt(created, dummy.matrix);
    dummy.position.set(x + (random() - 0.5) * 0.14, 1.48 * scale, z + (random() - 0.5) * 0.14);
    dummy.scale.set(scale * 0.82, scale * 0.82, scale * 0.82);
    dummy.updateMatrix();
    upper.setMatrixAt(created, dummy.matrix);
    const color = new THREE.Color(random() > 0.62 ? 0x587c54 : random() > 0.42 ? 0x3f6d4d : 0x6d8657);
    lower.setColorAt(created, color);
    upper.setColorAt(created, color.clone().offsetHSL(0, 0.02, 0.035));
    created += 1;
  }
  [trunks, lower, upper].forEach((mesh) => {
    mesh.count = created;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
  });
}

function addCampusStreetDetails(parent: THREE.Object3D, random: () => number) {
  const dark = new THREE.MeshStandardMaterial({ color: 0x4b5856, roughness: 0.64, metalness: 0.24 });
  const warm = new THREE.MeshStandardMaterial({ color: 0xe0c17d, emissive: 0x8b672d, emissiveIntensity: 0.38 });
  const wood = new THREE.MeshStandardMaterial({ color: 0x95765c, roughness: 0.9 });
  const bicycle = new THREE.MeshStandardMaterial({ color: 0x335f5e, roughness: 0.64, metalness: 0.2 });
  for (let index = 0; index < 30; index += 1) {
    const side = index % 2 ? -1 : 1;
    const z = -12.5 + Math.floor(index / 2) * 1.75;
    addBox(parent, [0.045, 0.92, 0.045], [side * 2.45, 0.46, z], dark, 0, false);
    addBox(parent, [0.16, 0.11, 0.16], [side * 2.45, 0.94, z], warm, 0, false);
  }
  [[-4.6, 3.8], [4.2, 6.1], [10.4, 5.6], [-9.5, 3.1], [1.8, -5.1]].forEach(([x, z], row) => {
    for (let index = 0; index < 3; index += 1) {
      addBox(parent, [0.86, 0.08, 0.24], [x + index * 1.05, 0.3, z], wood, row % 2 ? Math.PI / 2 : 0, false);
      addBox(parent, [0.06, 0.28, 0.06], [x + index * 1.05 - 0.3, 0.15, z], dark, row % 2 ? Math.PI / 2 : 0, false);
    }
  });
  for (let index = 0; index < 26; index += 1) {
    const x = -8.5 + (index % 13) * 0.46;
    const z = -6.4 + Math.floor(index / 13) * 0.62;
    const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.018, 5, 12), bicycle);
    wheel.position.set(x + (random() - 0.5) * 0.08, 0.13, z);
    wheel.rotation.y = Math.PI / 2;
    parent.add(wheel);
  }
}

function addBuilding(parent: THREE.Object3D, block: Block) {
  const bodyMaterial = new THREE.MeshStandardMaterial({ color: block.color, roughness: 0.82, metalness: 0.04 });
  const roofMaterial = new THREE.MeshStandardMaterial({ color: block.roof ?? 0xc5ccc8, roughness: 0.88 });
  const glassMaterial = new THREE.MeshStandardMaterial({ color: block.accent ?? 0x587f7b, roughness: 0.25, metalness: 0.12 });
  addBox(parent, [block.width, block.height, block.depth], [block.x, block.height / 2 + 0.08, block.z], bodyMaterial);
  addBox(parent, [block.width + 0.18, 0.18, block.depth + 0.18], [block.x, block.height + 0.17, block.z], roofMaterial);

  const floors = Math.max(2, Math.min(6, Math.round(block.height / 0.9)));
  for (let floor = 0; floor < floors; floor += 1) {
    const windowY = 0.62 + floor * ((block.height - 0.55) / floors);
    addBox(parent, [block.width * 0.72, 0.16, 0.055], [block.x, windowY, block.z + block.depth / 2 + 0.032], glassMaterial, 0, false);
    addBox(parent, [0.055, 0.16, block.depth * 0.62], [block.x + block.width / 2 + 0.032, windowY, block.z], glassMaterial, 0, false);
  }
}

function isNearBlock(x: number, z: number, blocks: Block[], margin = 0.7) {
  return blocks.some((block) => Math.abs(x - block.x) < block.width / 2 + margin && Math.abs(z - block.z) < block.depth / 2 + margin);
}

function addTrees(parent: THREE.Object3D, random: () => number, blocks: Block[], count: number) {
  const trunkGeometry = new THREE.CylinderGeometry(0.055, 0.08, 0.58, 5);
  const crownGeometry = new THREE.ConeGeometry(0.3, 0.95, 7);
  const trunkMaterial = new THREE.MeshStandardMaterial({ color: 0x765e43, roughness: 1 });
  const crownMaterial = new THREE.MeshStandardMaterial({ color: 0x3f7154, roughness: 0.96, vertexColors: true });
  const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, count);
  const crowns = new THREE.InstancedMesh(crownGeometry, crownMaterial, count);
  const dummy = new THREE.Object3D();
  let created = 0;
  let attempts = 0;
  while (created < count && attempts < count * 12) {
    attempts += 1;
    const x = (random() - 0.5) * 42;
    const z = (random() - 0.5) * 29;
    if (isNearBlock(x, z, blocks, 0.55) || Math.abs(z) < 1.9 || Math.abs(x - 0.6) < 1.8) continue;
    const scale = 0.72 + random() * 0.58;
    dummy.position.set(x, 0.31 * scale, z);
    dummy.scale.set(scale, scale, scale);
    dummy.rotation.y = random() * Math.PI;
    dummy.updateMatrix();
    trunks.setMatrixAt(created, dummy.matrix);
    dummy.position.y = 0.93 * scale;
    dummy.updateMatrix();
    crowns.setMatrixAt(created, dummy.matrix);
    crowns.setColorAt(created, new THREE.Color(random() > 0.48 ? 0x3f7154 : random() > 0.5 ? 0x527f5f : 0x668767));
    created += 1;
  }
  trunks.count = created;
  crowns.count = created;
  trunks.instanceMatrix.needsUpdate = true;
  crowns.instanceMatrix.needsUpdate = true;
  trunks.castShadow = true;
  crowns.castShadow = true;
  parent.add(trunks, crowns);
}

function addPopulation(
  parent: THREE.Object3D,
  random: () => number,
  count: number,
  interior = false,
  crowdCenters?: Array<[number, number]>,
): PopulationLayer {
  const unit = interior ? 1.12 : 0.88;
  const bodyGeometry = new THREE.BoxGeometry(0.15 * unit, 0.28 * unit, 0.105 * unit);
  bodyGeometry.translate(0, 0.43 * unit, 0);
  const headGeometry = new THREE.SphereGeometry(0.078 * unit, 7, 6);
  headGeometry.translate(0, 0.65 * unit, 0);
  const hairGeometry = new THREE.SphereGeometry(0.081 * unit, 7, 5, 0, Math.PI * 2, 0, Math.PI * 0.48);
  hairGeometry.translate(0, 0.675 * unit, 0);
  const leftArmGeometry = new THREE.CylinderGeometry(0.026 * unit, 0.022 * unit, 0.27 * unit, 6);
  leftArmGeometry.rotateZ(0.1);
  leftArmGeometry.translate(-0.105 * unit, 0.42 * unit, 0);
  const rightArmGeometry = new THREE.CylinderGeometry(0.026 * unit, 0.022 * unit, 0.27 * unit, 6);
  rightArmGeometry.rotateZ(-0.1);
  rightArmGeometry.translate(0.105 * unit, 0.42 * unit, 0);
  const leftLegGeometry = new THREE.CylinderGeometry(0.03 * unit, 0.024 * unit, 0.29 * unit, 6);
  leftLegGeometry.translate(-0.045 * unit, 0.16 * unit, 0);
  const rightLegGeometry = new THREE.CylinderGeometry(0.03 * unit, 0.024 * unit, 0.29 * unit, 6);
  rightLegGeometry.translate(0.045 * unit, 0.16 * unit, 0);
  const leftShoeGeometry = new THREE.BoxGeometry(0.065 * unit, 0.045 * unit, 0.115 * unit);
  leftShoeGeometry.translate(-0.045 * unit, 0.035 * unit, 0.018 * unit);
  const rightShoeGeometry = new THREE.BoxGeometry(0.065 * unit, 0.045 * unit, 0.115 * unit);
  rightShoeGeometry.translate(0.045 * unit, 0.035 * unit, 0.018 * unit);

  const makeMaterial = (color: number) => new THREE.MeshStandardMaterial({ color, roughness: 0.9, vertexColors: true });
  const geometries = [bodyGeometry, headGeometry, hairGeometry, leftArmGeometry, rightArmGeometry, leftLegGeometry, rightLegGeometry, leftShoeGeometry, rightShoeGeometry];
  const materials = [makeMaterial(0xffffff), makeMaterial(0xc9936f), makeMaterial(0x3f3531), makeMaterial(0xffffff), makeMaterial(0xffffff), makeMaterial(0x45565c), makeMaterial(0x45565c), makeMaterial(0x30383a), makeMaterial(0x30383a)];
  const meshes = geometries.map((geometry, index) => new THREE.InstancedMesh(geometry, materials[index], count));
  const baseX = new Float32Array(count);
  const baseZ = new Float32Array(count);
  const phase = new Float32Array(count);
  const speed = new Float32Array(count);
  const dummy = new THREE.Object3D();
  const centers = crowdCenters || (interior
    ? [[-5, -2], [-1, 2.5], [4.3, -1.5], [6, 3]]
    : [[-14, -8.5], [-16.5, 9.5], [-2, -0.8], [6, 1.7], [12, 7], [-7, 5.5], [2, -6]]) as Array<[number, number]>;

  for (let index = 0; index < count; index += 1) {
    const clustered = random() < (interior ? 0.7 : 0.62);
    const center = centers[Math.floor(random() * centers.length)];
    const x = clustered ? center[0] + (random() - 0.5) * (interior ? 3.3 : 4.8) : (random() - 0.5) * (interior ? 19 : 40);
    const z = clustered ? center[1] + (random() - 0.5) * (interior ? 2.3 : 3.8) : (random() - 0.5) * (interior ? 11 : 27);
    baseX[index] = x;
    baseZ[index] = z;
    phase[index] = random() * Math.PI * 2;
    speed[index] = 0.25 + random() * 0.7;
    const scale = 0.82 + random() * 0.32;
    dummy.position.set(x, 0.02, z);
    dummy.scale.set(scale, scale, scale);
    dummy.rotation.y = random() * Math.PI * 2;
    dummy.updateMatrix();
    meshes.forEach((mesh) => mesh.setMatrixAt(index, dummy.matrix));
    const clothing = new THREE.Color(PERSON_COLORS[Math.floor(random() * PERSON_COLORS.length)]);
    const skin = new THREE.Color(random() > 0.4 ? 0xc9916d : random() > 0.45 ? 0x9a674f : 0xe0b08d);
    const hair = new THREE.Color(random() > 0.22 ? 0x352e2c : 0x665046);
    const pants = new THREE.Color(random() > 0.5 ? 0x3d4a50 : 0x665b54);
    meshes[0].setColorAt(index, clothing);
    meshes[1].setColorAt(index, skin);
    meshes[2].setColorAt(index, hair);
    meshes[3].setColorAt(index, clothing);
    meshes[4].setColorAt(index, clothing);
    meshes[5].setColorAt(index, pants);
    meshes[6].setColorAt(index, pants);
    meshes[7].setColorAt(index, new THREE.Color(0x303638));
    meshes[8].setColorAt(index, new THREE.Color(0x303638));
  }
  meshes.forEach((mesh) => {
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.castShadow = false;
    parent.add(mesh);
  });
  return { meshes, baseX, baseZ, phase, speed, count, movingCount: Math.min(count, interior ? 30 : 150) };
}

function createHeroAgent(agent: WorldAgent, position: [number, number], interior: boolean): HeroRig {
  const random = seededRandom(`hero:${agent.id}`);
  const root = new THREE.Group();
  root.position.set(position[0], 0.03, position[1]);
  root.rotation.y = random() * Math.PI * 2;
  const scale = interior ? 0.82 : 0.9;
  root.scale.setScalar(scale);

  const clothingColor = /医生/.test(agent.role)
    ? 0xe7eee9
    : PERSON_COLORS[Math.floor(random() * PERSON_COLORS.length)];
  const accentColor = PERSON_COLORS[Math.floor(random() * PERSON_COLORS.length)];
  const skinColor = random() > 0.45 ? 0xc98f6e : random() > 0.35 ? 0x9b684e : 0xe1b08d;
  const hairColor = random() > 0.2 ? 0x302927 : 0x695044;
  const pantsColor = random() > 0.5 ? 0x34484e : 0x5b514c;
  const clothing = new THREE.MeshStandardMaterial({ color: clothingColor, roughness: 0.78 });
  const accent = new THREE.MeshStandardMaterial({ color: accentColor, roughness: 0.74 });
  const skin = new THREE.MeshStandardMaterial({ color: skinColor, roughness: 0.9 });
  const hair = new THREE.MeshStandardMaterial({ color: hairColor, roughness: 0.96 });
  const pants = new THREE.MeshStandardMaterial({ color: pantsColor, roughness: 0.88 });
  const shoes = new THREE.MeshStandardMaterial({ color: 0x252f31, roughness: 0.78 });

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.265, 0.58, 8), clothing);
  torso.position.y = 1.03;
  torso.castShadow = true;
  root.add(torso);
  const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.17, 0.08, 8), accent);
  collar.position.y = 1.32;
  root.add(collar);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.185, 12, 9), skin);
  head.position.y = 1.55;
  head.castShadow = true;
  root.add(head);
  const hairCap = new THREE.Mesh(new THREE.SphereGeometry(0.192, 12, 7, 0, Math.PI * 2, 0, Math.PI * 0.54), hair);
  hairCap.position.y = 1.6;
  root.add(hairCap);

  const leftArm = new THREE.Group();
  const rightArm = new THREE.Group();
  leftArm.position.set(-0.25, 1.24, 0);
  rightArm.position.set(0.25, 1.24, 0);
  const leftArmMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.061, 0.048, 0.54, 7), clothing);
  const rightArmMesh = leftArmMesh.clone();
  leftArmMesh.position.y = -0.25;
  rightArmMesh.position.y = -0.25;
  const leftHand = new THREE.Mesh(new THREE.SphereGeometry(0.061, 7, 5), skin);
  const rightHand = leftHand.clone();
  leftHand.position.y = -0.53;
  rightHand.position.y = -0.53;
  leftArm.add(leftArmMesh, leftHand);
  rightArm.add(rightArmMesh, rightHand);
  leftArm.rotation.z = -0.08;
  rightArm.rotation.z = 0.08;
  root.add(leftArm, rightArm);

  const leftLeg = new THREE.Group();
  const rightLeg = new THREE.Group();
  leftLeg.position.set(-0.1, 0.72, 0);
  rightLeg.position.set(0.1, 0.72, 0);
  const leftLegMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.058, 0.62, 7), pants);
  const rightLegMesh = leftLegMesh.clone();
  leftLegMesh.position.y = -0.3;
  rightLegMesh.position.y = -0.3;
  const leftShoe = new THREE.Mesh(new THREE.BoxGeometry(0.145, 0.09, 0.27), shoes);
  const rightShoe = leftShoe.clone();
  leftShoe.position.set(0, -0.62, 0.06);
  rightShoe.position.set(0, -0.62, 0.06);
  leftLeg.add(leftLegMesh, leftShoe);
  rightLeg.add(rightLegMesh, rightShoe);
  root.add(leftLeg, rightLeg);

  if (/学生|博士|工程师|产品/.test(agent.role)) {
    const backpack = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.46, 0.16), accent);
    backpack.position.set(0, 1.02, -0.2);
    backpack.rotation.x = -0.08;
    root.add(backpack);
  } else if (/经理|主理人|管理员|馆员|记录者/.test(agent.role)) {
    const satchel = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.34, 0.1), accent);
    satchel.position.set(0.28, 0.82, -0.04);
    satchel.rotation.z = -0.12;
    root.add(satchel);
  }

  const haloMaterial = new THREE.MeshStandardMaterial({ color: 0x62b5a4, emissive: 0x2c776d, emissiveIntensity: 1.15, transparent: true, opacity: 0.82 });
  const halo = new THREE.Mesh(new THREE.TorusGeometry(0.39, 0.026, 6, 32), haloMaterial);
  halo.rotation.x = Math.PI / 2;
  halo.position.y = 0.02;
  root.add(halo);
  root.userData.agentId = agent.id;
  root.traverse((object) => {
    object.userData.agentId = agent.id;
  });

  return {
    agent,
    root,
    leftArm,
    rightArm,
    leftLeg,
    rightLeg,
    halo,
    phase: random() * Math.PI * 2,
    moving: /赶往|前往|沿河|巡查|穿过|采集|赶|巡/.test(agent.action),
    baseX: position[0],
    baseZ: position[1],
  };
}

function addHeroAgents(
  parent: THREE.Object3D,
  agents: WorldAgent[],
  interior = false,
  positions?: Array<[number, number]>,
) {
  const defaults: Array<[number, number]> = interior
    ? [[-7.2, -4.8], [-1.4, -1.4], [5.8, -4.6], [3.2, 4.8], [-5.8, 4.6]]
    : [[-7.4, -3.6], [2.8, 1.2], [9.2, 5.3], [-12.2, 6.4], [13.1, -4.6], [-1.5, 7.4]];
  const anchors = positions?.length ? positions : defaults;
  const heroes = agents.slice(0, anchors.length).map((agent, index) => createHeroAgent(agent, anchors[index % anchors.length], interior));
  const pickables: THREE.Object3D[] = [];
  heroes.forEach((hero) => {
    parent.add(hero.root);
    hero.root.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.Sprite) pickables.push(object);
    });
  });
  return { heroes, pickables };
}

function addAtmosphere(
  parent: THREE.Object3D,
  random: () => number,
  options: { color?: number; count?: number; opacity?: number; falling?: boolean; drift?: number; size?: number } = {},
): AtmosphereLayer {
  const count = options.count ?? 520;
  const positions = new Float32Array(count * 3);
  const speeds = new Float32Array(count);
  for (let index = 0; index < count; index += 1) {
    positions[index * 3] = (random() - 0.5) * 48;
    positions[index * 3 + 1] = random() * 16 + 1;
    positions[index * 3 + 2] = (random() - 0.5) * 35;
    speeds[index] = (options.falling === false ? 0.12 : 2.2) + random() * (options.falling === false ? 0.4 : 3.6);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({ color: options.color ?? 0xdde8e6, size: options.size ?? 0.04, transparent: true, opacity: options.opacity ?? 0.32, depthWrite: false });
  const atmosphere = new THREE.Points(geometry, material) as AtmosphereLayer;
  atmosphere.userData.speeds = speeds;
  atmosphere.userData.drift = options.drift ?? 0.16;
  atmosphere.userData.falling = options.falling !== false;
  parent.add(atmosphere);
  return atmosphere;
}

function completeScene(
  group: THREE.Group,
  population: PopulationLayer,
  atmosphere: AtmosphereLayer | null,
  agents: WorldAgent[],
  interior = false,
  heroPositions?: Array<[number, number]>,
): SceneWorld {
  const { heroes, pickables } = addHeroAgents(group, agents, interior, heroPositions);
  return { group, population, atmosphere, heroes, pickables };
}

function addTower(
  parent: THREE.Object3D,
  x: number,
  z: number,
  height: number,
  width: number,
  depth: number,
  bodyColor = 0xd8dcda,
  glassColor = 0x5c8583,
  rotation = 0,
) {
  const body = new THREE.MeshStandardMaterial({ color: bodyColor, roughness: 0.52, metalness: 0.08 });
  const glass = new THREE.MeshPhysicalMaterial({ color: glassColor, roughness: 0.18, metalness: 0.16, transparent: true, opacity: 0.78 });
  const metal = new THREE.MeshStandardMaterial({ color: 0x8d9b98, roughness: 0.48, metalness: 0.34 });
  addBox(parent, [width, height, depth], [x, height / 2 + 0.05, z], body, rotation);
  addBox(parent, [width * 0.78, height * 0.88, depth + 0.06], [x, height * 0.48, z], glass, rotation, false);
  for (let index = -1; index <= 1; index += 1) {
    addBox(parent, [0.055, height * 0.86, depth + 0.11], [x + index * width * 0.28, height * 0.48, z], metal, rotation, false);
  }
  addBox(parent, [width + 0.18, 0.16, depth + 0.18], [x, height + 0.12, z], metal, rotation);
}

function addHistoricHouse(parent: THREE.Object3D, x: number, z: number, width: number, depth: number, rotation = 0) {
  const whiteWall = new THREE.MeshStandardMaterial({ color: 0xe9e4da, roughness: 0.96 });
  const darkWood = new THREE.MeshStandardMaterial({ color: 0x3d4543, roughness: 0.88 });
  const tile = new THREE.MeshStandardMaterial({ color: 0x505956, roughness: 0.98 });
  addBox(parent, [width, 1.45, depth], [x, 0.75, z], whiteWall, rotation);
  const roof = new THREE.Mesh(new THREE.CylinderGeometry(0, 1, 0.62, 4), tile);
  roof.scale.set(width * 0.72, 1, depth * 0.72);
  roof.position.set(x, 1.72, z);
  roof.rotation.y = rotation + Math.PI / 4;
  roof.castShadow = true;
  parent.add(roof);
  for (let offset = -0.3; offset <= 0.3; offset += 0.3) {
    addBox(parent, [0.055, 0.82, 0.055], [x + offset * width, 0.74, z + depth / 2 + 0.035], darkWood, rotation, false);
  }
}

function addBridge(parent: THREE.Object3D, z: number) {
  const stone = new THREE.MeshStandardMaterial({ color: 0xc9c4b9, roughness: 0.98 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x66706d, roughness: 0.9 });
  addBox(parent, [6.1, 0.28, 1.5], [0, 0.42, z], stone, 0, true);
  [-2.7, 2.7].forEach((x) => addBox(parent, [0.12, 0.55, 1.65], [x, 0.7, z], dark, 0, false));
  for (let index = -2; index <= 2; index += 1) {
    addBox(parent, [0.08, 0.42, 0.08], [index * 1.1, 0.68, z - 0.72], dark, 0, false);
    addBox(parent, [0.08, 0.42, 0.08], [index * 1.1, 0.68, z + 0.72], dark, 0, false);
  }
}

function buildNjuCampus(scene: THREE.Scene, random: () => number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const earth = new THREE.MeshStandardMaterial({ color: 0x788774, roughness: 1 });
  const lawn = new THREE.MeshStandardMaterial({ color: 0x91a889, roughness: 1 });
  const road = new THREE.MeshStandardMaterial({ color: 0x727c79, roughness: 0.98 });
  const path = new THREE.MeshStandardMaterial({ color: 0xc9c4b7, roughness: 0.96 });
  const plaza = new THREE.MeshStandardMaterial({ color: 0xd3cec2, roughness: 0.94 });
  const lane = new THREE.MeshBasicMaterial({ color: 0xd8d2c4, transparent: true, opacity: 0.62 });
  const water = new THREE.MeshPhysicalMaterial({ color: 0x5f9499, roughness: 0.13, metalness: 0.04, transparent: true, opacity: 0.86 });
  const waterEdge = new THREE.MeshStandardMaterial({ color: 0xbebbac, roughness: 0.92 });

  addBox(group, [50, 0.48, 36.5], [0, -0.25, 0], earth, 0, false);
  addPlane(group, 49.2, 35.7, 0, 0, lawn, 0, 0.01);
  addRibbonPath(group, [[-23, -14], [-15, -15], [-5, -14.4], [6, -14.7], [16, -14], [23, -11]], 2.05, road);
  addRibbonPath(group, [[-22, 13.6], [-13, 14.8], [-2, 14.5], [9, 14.8], [21.8, 12.2]], 2.15, road);
  addRibbonPath(group, [[-21.8, -13.8], [-22.4, -5], [-21.4, 4.2], [-20.6, 13.5]], 1.9, road);
  addRibbonPath(group, [[22.2, -11], [21.2, -3.5], [22.1, 5.6], [21.8, 12.2]], 1.9, road);
  addRibbonPath(group, [[0.1, 15.2], [0.15, 9.6], [-0.25, 4.8], [0.15, -1], [-0.1, -6.2], [-0.1, -14.4]], 2.55, road);
  addRibbonPath(group, [[-19.6, 1.9], [-12, 1.4], [-5.4, 2.1], [0, 1.8], [6.2, 2.2], [13.8, 1.4], [21.3, 0.5]], 1.8, road);
  addRibbonPath(group, [[-18, -5.8], [-11, -5.2], [-4, -5.8], [3.5, -5.1], [11.2, -5.7], [20.7, -5.1]], 1.05, path, 0.055);
  addRibbonPath(group, [[-17.5, 6.5], [-9, 6.2], [-2.2, 6.8], [5.5, 6.1], [12.7, 6.5], [20.3, 7.2]], 1.05, path, 0.055);
  addRibbonPath(group, [[0, 14.8], [0.1, 10.4], [0.2, 6.5], [0, 2]], 0.07, lane, 0.075);
  addPlane(group, 13.2, 8.4, -0.4, 1.7, plaza, -0.015, 0.05);
  addPlane(group, 8.7, 5.2, -0.2, 9.9, plaza, 0.015, 0.05);

  const lakeEdge = new THREE.Mesh(new THREE.CircleGeometry(3.55, 64), waterEdge);
  lakeEdge.rotation.x = -Math.PI / 2;
  lakeEdge.scale.y = 0.6;
  lakeEdge.position.set(8.6, 0.045, 2.7);
  lakeEdge.receiveShadow = true;
  group.add(lakeEdge);
  const lake = new THREE.Mesh(new THREE.CircleGeometry(3.25, 64), water);
  lake.rotation.x = -Math.PI / 2;
  lake.scale.y = 0.58;
  lake.position.set(8.6, 0.07, 2.7);
  lake.receiveShadow = true;
  group.add(lake);
  addRibbonPath(group, [[5.3, 2.5], [6.8, 2.7], [8.6, 2.85], [10.4, 2.7], [11.9, 2.45]], 0.56, path, 0.11);

  addCampusTrack(group, -15.6, 9.2);
  addCampusLibrary(group, -0.4, -0.2);
  addCampusAuditorium(group, -15.1, -1.4, -0.04);
  addCampusCanteen(group, 13.5, 0.4);
  addCampusGate(group, 0, 15.3);
  CAMPUS_BLOCKS.slice(0, 4).forEach((block, index) => addDetailedAcademicBuilding(group, block, { rotation: index % 2 ? 0.035 : -0.025, atrium: index === 1 || index === 2, setbacks: index % 3, brick: index === 0 }));
  addDetailedAcademicBuilding(group, CAMPUS_BLOCKS[5], { rotation: 0.025, brick: true, atrium: true });
  addDetailedAcademicBuilding(group, CAMPUS_BLOCKS[7], { rotation: -0.035, brick: true, setbacks: 1 });
  addDetailedAcademicBuilding(group, CAMPUS_BLOCKS[8], { rotation: 0.025, brick: true });
  addDetailedAcademicBuilding(group, CAMPUS_BLOCKS[9], { rotation: -0.02, atrium: true, setbacks: 2 });
  addDetailedAcademicBuilding(group, CAMPUS_BLOCKS[10], { rotation: 0.03, atrium: true, setbacks: 1 });

  const sculptureMaterial = new THREE.MeshStandardMaterial({ color: 0x8d6c52, roughness: 0.52, metalness: 0.32 });
  const sculpture = new THREE.Mesh(new THREE.TorusKnotGeometry(0.48, 0.12, 72, 10), sculptureMaterial);
  sculpture.position.set(-0.3, 1.0, 8.9);
  sculpture.scale.set(0.72, 1.25, 0.72);
  sculpture.castShadow = true;
  group.add(sculpture);
  addBox(group, [1.4, 0.28, 1.4], [-0.3, 0.15, 8.9], new THREE.MeshStandardMaterial({ color: 0xc9c2b4, roughness: 0.9 }));

  addBroadleafTrees(group, random, CAMPUS_BLOCKS, 286);
  addCampusStreetDetails(group, random);
  const population = addPopulation(group, random, 720, false, [[-0.5, 7.5], [-0.3, 2.8], [-9.2, -4.8], [7.4, -5], [13.5, 4.8], [-14.8, 3.2], [1.4, -7.2]]);
  const atmosphere = addAtmosphere(group, random, { color: 0xdce9e2, count: 420, falling: true, opacity: 0.18, drift: 0.11, size: 0.032 });
  return completeScene(group, population, atmosphere, agents, false, [[-4.8, 3.2], [1.2, 7.1], [6.3, -4.8], [-11.8, 3.6], [13.2, -3.8], [-1.4, -6.4]]);
}

function buildScienceCity(scene: THREE.Scene, random: () => number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const ground = new THREE.MeshStandardMaterial({ color: 0xb7c3b8, roughness: 1 });
  const plaza = new THREE.MeshStandardMaterial({ color: 0xd7d8d1, roughness: 0.92 });
  const road = new THREE.MeshStandardMaterial({ color: 0x8d9997, roughness: 1 });
  addPlane(group, 50, 36, 0, 0, ground, 0, 0);
  addPlane(group, 50, 3.4, 0, 1.5, road);
  addPlane(group, 3.2, 36, -10.4, 0, road);
  addPlane(group, 18, 12, 6.2, -3.6, plaza, -0.05, 0.03);
  addTower(group, -16, -8, 8.6, 4.6, 4.1, 0xd7dfdc, 0x4c7f80, -0.08);
  addTower(group, -6.8, -8.8, 6.7, 5.3, 3.8, 0xdde1dc, 0x567f7d, 0.04);
  addTower(group, 5.2, -9.1, 10.2, 4.4, 4.2, 0xd2dcda, 0x487a7d, -0.03);
  addTower(group, 15.5, -7.4, 7.4, 5.2, 4.5, 0xd9dfda, 0x648d89, 0.06);
  addTower(group, 16.4, 7.2, 5.8, 6.2, 4.7, 0xdde0d8, 0x5f8580, -0.05);
  addBuilding(group, { x: -17, z: 8.5, width: 7.4, depth: 4.5, height: 3.2, color: 0xe2ddd2, roof: 0xc6c8c0, accent: 0x8b705c });
  const pole = new THREE.MeshStandardMaterial({ color: 0x5d716f, roughness: 0.62, metalness: 0.3 });
  const solar = new THREE.MeshStandardMaterial({ color: 0x355f6c, roughness: 0.2, metalness: 0.42 });
  for (let index = 0; index < 8; index += 1) {
    const x = -6 + index * 1.7;
    addBox(group, [0.08, 1.55, 0.08], [x, 0.78, 7.3], pole, 0, false);
    addBox(group, [1.45, 0.08, 1.9], [x, 1.6, 7.3], solar, -0.12, false);
  }
  addBox(group, [1.35, 0.42, 0.58], [-2.8, 0.27, 1.4], new THREE.MeshStandardMaterial({ color: 0xe1e5df, roughness: 0.45 }), 0, true);
  addBox(group, [0.62, 0.18, 0.5], [-2.8, 0.54, 1.4], new THREE.MeshPhysicalMaterial({ color: 0x4c7b7e, roughness: 0.16, transparent: true, opacity: 0.72 }), 0, false);
  const blocks: Block[] = [{ x: -16, z: -8, width: 4.6, depth: 4.1, height: 8.6, color: 0xd7dfdc }, { x: -6.8, z: -8.8, width: 5.3, depth: 3.8, height: 6.7, color: 0xdde1dc }, { x: 5.2, z: -9.1, width: 4.4, depth: 4.2, height: 10.2, color: 0xd2dcda }, { x: 15.5, z: -7.4, width: 5.2, depth: 4.5, height: 7.4, color: 0xd9dfda }];
  addTrees(group, random, blocks, 96);
  const population = addPopulation(group, random, 286, false, [[6, -3], [-4, 6.5], [-3, 1], [14, 6]]);
  const atmosphere = addAtmosphere(group, random, { color: 0x8fd5ca, count: 360, opacity: 0.34, falling: false, drift: 0.06, size: 0.055 });
  return completeScene(group, population, atmosphere, agents, false, [[-4.5, 5.9], [6.1, -1.2], [11.8, 5.2], [-13.6, 6.8]]);
}

function buildShishan(scene: THREE.Scene, random: () => number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const ground = new THREE.MeshStandardMaterial({ color: 0xaeb6b0, roughness: 1 });
  const road = new THREE.MeshStandardMaterial({ color: 0x747f80, roughness: 1 });
  const pavement = new THREE.MeshStandardMaterial({ color: 0xc8c7c1, roughness: 0.93 });
  addPlane(group, 50, 36, 0, 0, ground, 0, 0);
  addPlane(group, 50, 4.8, 0, 2.2, road);
  addPlane(group, 5.1, 36, -1.8, 0, road);
  addPlane(group, 18, 9, 8.8, 7.7, pavement, -0.04, 0.03);
  [[-18, -10, 11.5, 5.2, 4.3], [-10, -9, 7.8, 4.5, 4], [7, -9.5, 13.2, 5.1, 4.4], [16.5, -7.5, 9.6, 4.6, 4.5], [-16.5, 9, 6.7, 5, 4.2], [7.2, 9, 8.9, 5.3, 4.4], [16.8, 8.4, 7.4, 4.8, 4.5]].forEach(([x, z, height, width, depth], index) => addTower(group, x, z, height, width, depth, index % 2 ? 0xd4d7d3 : 0xcfd8d6, index % 3 ? 0x496f76 : 0x6a7d80, index % 2 ? 0.04 : -0.06));
  const podium = new THREE.MeshStandardMaterial({ color: 0xd9cec0, roughness: 0.8 });
  const screen = new THREE.MeshStandardMaterial({ color: 0x4d817b, emissive: 0x397469, emissiveIntensity: 0.9, roughness: 0.26 });
  addBox(group, [13.5, 1.45, 4.1], [8.7, 0.76, 7.6], podium, -0.04);
  addBox(group, [5.2, 0.92, 0.08], [8.7, 1.14, 5.52], screen, -0.04, false);
  addBox(group, [5.8, 0.5, 2.1], [-2, 0.28, 2.2], new THREE.MeshStandardMaterial({ color: 0xb8c3be, roughness: 0.68 }));
  for (let index = -8; index <= 8; index += 2) addBox(group, [0.05, 0.04, 3.8], [index, 0.06, 2.2], new THREE.MeshBasicMaterial({ color: 0xe5ded0 }), 0, false);
  const population = addPopulation(group, random, 418, false, [[-2, 2], [9, 7], [-8, -2], [15, 1], [-14, 7]]);
  const atmosphere = addAtmosphere(group, random, { color: 0xe0b975, count: 290, opacity: 0.22, falling: false, drift: 0.04, size: 0.045 });
  return completeScene(group, population, atmosphere, agents, false, [[-7.4, 1.1], [7.6, 6.5], [13.4, 0.4], [-13.1, 6.8]]);
}

function buildPingjiang(scene: THREE.Scene, random: () => number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const stone = new THREE.MeshStandardMaterial({ color: 0xc8c3b7, roughness: 1 });
  const water = new THREE.MeshPhysicalMaterial({ color: 0x6c9898, roughness: 0.22, transparent: true, opacity: 0.86 });
  addPlane(group, 50, 36, 0, 0, stone, 0, 0);
  addPlane(group, 5.8, 36, 0, 0, water, 0.02, 0.045);
  addPlane(group, 4.1, 36, -5.1, 0, new THREE.MeshStandardMaterial({ color: 0xb8b4aa, roughness: 1 }), 0, 0.03);
  addPlane(group, 4.1, 36, 5.1, 0, new THREE.MeshStandardMaterial({ color: 0xb8b4aa, roughness: 1 }), 0, 0.03);
  for (let row = 0; row < 6; row += 1) {
    const z = -14 + row * 5.5;
    addHistoricHouse(group, -10.2 - (row % 2) * 1.1, z, 6.2, 3.8, row % 2 ? 0.04 : -0.03);
    addHistoricHouse(group, 10.4 + (row % 2) * 0.9, z + 0.7, 6.5, 3.7, row % 2 ? -0.04 : 0.03);
  }
  [-8, 3.2, 11.3].forEach((z) => addBridge(group, z));
  const boatMaterial = new THREE.MeshStandardMaterial({ color: 0x6e4d3c, roughness: 0.92 });
  const canopy = new THREE.MeshStandardMaterial({ color: 0x4b5552, roughness: 0.88 });
  [-3.6, 7.2].forEach((z, index) => {
    addBox(group, [1.9, 0.18, 0.55], [index ? 0.8 : -0.6, 0.16, z], boatMaterial, 0.04, true);
    addBox(group, [1.05, 0.58, 0.48], [index ? 0.8 : -0.6, 0.51, z], canopy, 0.04, false);
  });
  const lantern = new THREE.MeshStandardMaterial({ color: 0xb95f46, emissive: 0x7b2d1d, emissiveIntensity: 0.72 });
  for (let index = 0; index < 20; index += 1) {
    const side = index % 2 ? -1 : 1;
    addBox(group, [0.12, 0.2, 0.12], [side * 4.1, 1.15, -15 + index * 1.55], lantern, 0, false);
  }
  const population = addPopulation(group, random, 236, false, [[-5.3, -5], [5.1, 5], [-5, 9], [5, -10]]);
  const atmosphere = addAtmosphere(group, random, { color: 0xe5ece6, count: 680, opacity: 0.3, falling: false, drift: 0.03, size: 0.07 });
  return completeScene(group, population, atmosphere, agents, false, [[-5.4, -2.6], [5.2, 4.8], [-5.5, 8.7], [5.2, -9.2]]);
}

function buildJinjiLake(scene: THREE.Scene, random: () => number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const cityGround = new THREE.MeshStandardMaterial({ color: 0xbcc2b9, roughness: 1 });
  const water = new THREE.MeshPhysicalMaterial({ color: 0x5e99aa, roughness: 0.14, metalness: 0.05, transparent: true, opacity: 0.86 });
  const boardwalk = new THREE.MeshStandardMaterial({ color: 0xc9b69d, roughness: 0.9 });
  addPlane(group, 50, 36, 0, 0, cityGround, 0, 0);
  addPlane(group, 50, 15, 0, 10.6, water, -0.02, 0.045);
  addPlane(group, 48, 2.4, 0, 2.6, boardwalk, -0.01, 0.055);
  addTower(group, -16.8, -9.4, 8.5, 4.1, 4.2, 0xd8ddda, 0x4e7880, -0.05);
  addTower(group, -9.7, -10.2, 11.2, 4.3, 4.1, 0xd2dad9, 0x436e78, 0.03);
  addTower(group, 14.9, -9.2, 9.1, 4.6, 4.2, 0xd6dcda, 0x547b80, 0.04);
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x4a737b, roughness: 0.16, metalness: 0.18, transparent: true, opacity: 0.84 });
  addBox(group, [3.2, 10.8, 3.2], [1.2, 5.45, -9], glass, -0.06);
  addBox(group, [3.2, 10.8, 3.2], [6.1, 5.45, -9], glass, 0.06);
  addBox(group, [6.2, 2.4, 3.25], [3.65, 9.7, -9], glass, 0, true);
  const stage = new THREE.MeshStandardMaterial({ color: 0xe1d7c7, roughness: 0.82 });
  addBox(group, [7.8, 0.42, 4.3], [-8.2, 0.24, -0.2], stage, -0.03);
  const shell = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 3.2, 2.1, 24, 1, true, 0, Math.PI), new THREE.MeshStandardMaterial({ color: 0xd8ded8, side: THREE.DoubleSide, roughness: 0.7 }));
  shell.position.set(-8.2, 1.2, -0.8);
  shell.rotation.z = Math.PI / 2;
  group.add(shell);
  for (let index = -10; index <= 10; index += 2) addBox(group, [0.05, 0.65, 0.05], [index, 0.35, 2.5], new THREE.MeshStandardMaterial({ color: 0x667673, roughness: 0.8 }), 0, false);
  const population = addPopulation(group, random, 452, false, [[-8, 0], [4, -2], [11, 1], [-4, 2.4], [13, -5]]);
  const atmosphere = addAtmosphere(group, random, { color: 0xc8eef0, count: 420, opacity: 0.25, falling: false, drift: 0.12, size: 0.055 });
  return completeScene(group, population, atmosphere, agents, false, [[-7.4, 0.2], [4.5, 1.2], [11.4, -2.8], [-1.8, 2.2]]);
}

function buildTaihuNeighborhood(scene: THREE.Scene, random: () => number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const lawn = new THREE.MeshStandardMaterial({ color: 0xa9bf9f, roughness: 1 });
  const path = new THREE.MeshStandardMaterial({ color: 0xd2c9b9, roughness: 0.96 });
  const water = new THREE.MeshPhysicalMaterial({ color: 0x70a9ad, roughness: 0.2, transparent: true, opacity: 0.82 });
  addPlane(group, 50, 36, 0, 0, lawn, 0, 0);
  addPlane(group, 50, 7.4, 0, 14.1, water, 0, 0.04);
  addPlane(group, 46, 1.6, 0, 8.6, path, 0, 0.04);
  addPlane(group, 1.7, 28, 0, -1.5, path, 0, 0.04);
  const residentialBlocks: Block[] = [];
  [-16, -9, 9, 16].forEach((x, column) => {
    [-8, 1.8].forEach((z, row) => {
      const block: Block = { x, z, width: 4.5, depth: 4.2, height: 5.8 + ((column + row) % 3) * 1.2, color: column % 2 ? 0xded8ce : 0xd7ddd7, roof: 0xbfc8c0, accent: 0x6b887f };
      residentialBlocks.push(block);
      addBuilding(group, block);
      for (let floor = 1; floor <= 4; floor += 1) addBox(group, [block.width + 0.14, 0.08, 0.62], [x, floor * 1.05, z + block.depth / 2 + 0.27], new THREE.MeshStandardMaterial({ color: 0xb4b8ae, roughness: 0.8 }), 0, false);
    });
  });
  addBuilding(group, { x: 5.5, z: -5.3, width: 8.2, depth: 4.8, height: 2.4, color: 0xe0d6c7, roof: 0xc6b9a8, accent: 0x7d927e });
  const playground = new THREE.MeshStandardMaterial({ color: 0xb97962, roughness: 0.9 });
  const playAccent = new THREE.MeshStandardMaterial({ color: 0xe2b65f, roughness: 0.82 });
  addPlane(group, 7.4, 5.2, -4.8, 3.8, playground, -0.06, 0.055);
  addBox(group, [0.18, 1.8, 0.18], [-6, 0.9, 3.8], playAccent);
  addBox(group, [0.18, 1.8, 0.18], [-3.7, 0.9, 3.8], playAccent);
  addBox(group, [2.5, 0.16, 0.2], [-4.85, 1.72, 3.8], playAccent);
  addTrees(group, random, residentialBlocks, 210);
  const population = addPopulation(group, random, 328, false, [[-4.5, 3.6], [5.5, -4.7], [0, 8], [-12, 5], [12, 5]]);
  const atmosphere = addAtmosphere(group, random, { color: 0xf2ddb1, count: 260, opacity: 0.2, falling: false, drift: 0.05, size: 0.05 });
  return completeScene(group, population, atmosphere, agents, false, [[-4.7, 3.8], [5.3, -4.4], [0.5, 7.4], [11.5, 4.8]]);
}

function buildCampus(scene: THREE.Scene, random: () => number, variant: string, agents: WorldAgent[]) {
  if (variant === 'guizhou_university') return buildNjuCampus(scene, random, agents);
  throw new Error(`未知贵阳校园场景：${variant}`);
}

function buildDistrict(scene: THREE.Scene, random: () => number, variant: string, agents: WorldAgent[]) {
  if (variant === 'guiyang_convention') return buildJinjiLake(scene, random, agents);
  if (variant === 'guiyang_big_data') return buildScienceCity(scene, random, agents);
  if (variant === 'jiaxiu_tower' || variant === 'qingyan_town') return buildPingjiang(scene, random, agents);
  if (variant === 'guiyang_north_station') return buildShishan(scene, random, agents);
  if (variant === 'huaguoyuan') return buildTaihuNeighborhood(scene, random, agents);
  throw new Error(`未知贵阳城市场景：${variant}`);
}

function addDesk(parent: THREE.Object3D, x: number, z: number, rotation = 0) {
  const wood = new THREE.MeshStandardMaterial({ color: 0xb99571, roughness: 0.83 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x4f5d5b, roughness: 0.72 });
  addBox(parent, [1.05, 0.08, 0.48], [x, 0.54, z], wood, rotation);
  addBox(parent, [0.06, 0.5, 0.06], [x - 0.42, 0.27, z - 0.16], dark, rotation, false);
  addBox(parent, [0.06, 0.5, 0.06], [x + 0.42, 0.27, z + 0.16], dark, rotation, false);
  addBox(parent, [0.46, 0.42, 0.42], [x, 0.25, z + 0.63], dark, rotation, false);
}

type InteriorKind = 'library' | 'canteen' | 'auditorium' | 'lab' | 'community';

function resolveInteriorKind(building: string): InteriorKind {
  if (/食堂|餐厅|茶馆/.test(building)) return 'canteen';
  if (/礼堂|交流|路演|展演|会客厅|会议|发布|候车|大厅|展览/.test(building)) return 'auditorium';
  if (/科创|科研|实验|制造|创新/.test(building)) return 'lab';
  if (/图书|南雍|书店|资料/.test(building)) return 'library';
  return 'community';
}

function addInteriorShell(parent: THREE.Object3D, kind: InteriorKind, floor: number) {
  const floorColors: Record<InteriorKind, number> = { library: 0xd6cbbb, canteen: 0xcfc1ad, auditorium: 0xbbb8b1, lab: 0xc9d5d1, community: 0xd3d5c8 };
  const floorMaterial = new THREE.MeshStandardMaterial({ color: floorColors[kind] + (floor % 2 ? 0x020100 : 0), roughness: 0.9 });
  const wallMaterial = new THREE.MeshStandardMaterial({ color: 0xe9e4db, roughness: 0.9, transparent: true, opacity: 0.94 });
  const glassMaterial = new THREE.MeshPhysicalMaterial({ color: kind === 'lab' ? 0x6e9b9d : 0x86a49f, roughness: 0.16, transparent: true, opacity: 0.46 });
  addPlane(parent, 24, 16, 0, 0, floorMaterial, 0, 0);
  addBox(parent, [24, 2.9, 0.18], [0, 1.45, -8], wallMaterial);
  addBox(parent, [0.18, 2.9, 16], [-12, 1.45, 0], wallMaterial);
  addBox(parent, [0.18, 2.9, 16], [12, 1.45, 0], wallMaterial);
  for (let index = 0; index < 8; index += 1) addBox(parent, [1.9, 1.12, 0.055], [-9.6 + index * 2.75, 1.5, -7.88], glassMaterial, 0, false);
}

function addInteriorPlants(parent: THREE.Object3D) {
  const plantPot = new THREE.MeshStandardMaterial({ color: 0x9d7a5c, roughness: 1 });
  const plant = new THREE.MeshStandardMaterial({ color: 0x4a7655, roughness: 1 });
  [[-11, -7], [-10.8, 6.8], [10.8, 6.7], [11, -7]].forEach(([x, z]) => {
    const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.24, 0.35, 7), plantPot);
    pot.position.set(x, 0.18, z);
    parent.add(pot);
    const crown = new THREE.Mesh(new THREE.ConeGeometry(0.38, 1.05, 7), plant);
    crown.position.set(x, 0.82, z);
    crown.castShadow = true;
    parent.add(crown);
  });
}

function addLibraryInterior(parent: THREE.Object3D) {
  const shelf = new THREE.MeshStandardMaterial({ color: 0x826c57, roughness: 0.9 });
  const bookColors = [0x486f6b, 0xa26550, 0xc1a35f, 0x626b85];
  for (let row = 0; row < 3; row += 1) {
    for (let column = 0; column < 7; column += 1) {
      const x = -9.8 + column * 1.35;
      const z = 4.5 + row * 1.35;
      addBox(parent, [0.92, 1.65, 0.34], [x, 0.83, z], shelf, 0, true);
      addBox(parent, [0.72, 0.22, 0.05], [x, 1.15, z - 0.2], new THREE.MeshStandardMaterial({ color: bookColors[(row + column) % bookColors.length], roughness: 0.82 }), 0, false);
    }
  }
  for (let row = 0; row < 3; row += 1) for (let column = 0; column < 5; column += 1) addDesk(parent, -7.8 + column * 3.6, -5.5 + row * 2.05);
  addBox(parent, [4.8, 0.12, 1.8], [5.9, 0.5, 5.7], new THREE.MeshStandardMaterial({ color: 0xb28f69, roughness: 0.82 }));
}

function addCanteenInterior(parent: THREE.Object3D) {
  const counter = new THREE.MeshStandardMaterial({ color: 0x9d7659, roughness: 0.82 });
  const metal = new THREE.MeshStandardMaterial({ color: 0x7e8d8a, roughness: 0.4, metalness: 0.34 });
  addBox(parent, [21, 0.88, 1.3], [0, 0.45, -6.7], counter);
  for (let index = 0; index < 6; index += 1) addBox(parent, [2.6, 0.8, 0.08], [-8.2 + index * 3.25, 1.48, -6.02], new THREE.MeshStandardMaterial({ color: index % 2 ? 0xc9915f : 0x547d76, emissive: index % 2 ? 0x4d2610 : 0x153f39, emissiveIntensity: 0.35 }), 0, false);
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 5; column += 1) {
      const x = -8.2 + column * 4.1;
      const z = -3.6 + row * 2.55;
      addBox(parent, [2.4, 0.1, 0.82], [x, 0.72, z], new THREE.MeshStandardMaterial({ color: 0xc0a581, roughness: 0.82 }));
      addBox(parent, [2.6, 0.38, 0.28], [x, 0.23, z - 0.78], metal);
      addBox(parent, [2.6, 0.38, 0.28], [x, 0.23, z + 0.78], metal);
    }
  }
}

function addAuditoriumInterior(parent: THREE.Object3D) {
  const stage = new THREE.MeshStandardMaterial({ color: 0x8d715e, roughness: 0.88 });
  const screen = new THREE.MeshStandardMaterial({ color: 0xe8eee8, emissive: 0xa5c6bf, emissiveIntensity: 0.42, roughness: 0.52 });
  const seat = new THREE.MeshStandardMaterial({ color: 0x536f6c, roughness: 0.9 });
  addBox(parent, [18, 0.42, 3.1], [0, 0.23, -5.8], stage);
  addBox(parent, [9.8, 2.35, 0.08], [0, 1.65, -7.72], screen, 0, false);
  for (let row = 0; row < 6; row += 1) {
    for (let column = 0; column < 10; column += 1) {
      const x = -8.1 + column * 1.8;
      const z = -2.7 + row * 1.65;
      addBox(parent, [0.68, 0.72, 0.62], [x, 0.38 + row * 0.045, z], seat, 0, false);
    }
  }
  addBox(parent, [1.8, 1.05, 0.78], [-7.2, 0.55, -4.8], new THREE.MeshStandardMaterial({ color: 0xb49a73, roughness: 0.82 }));
}

function addLabInterior(parent: THREE.Object3D) {
  const bench = new THREE.MeshStandardMaterial({ color: 0xd7ddd8, roughness: 0.58, metalness: 0.12 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x4f6462, roughness: 0.65 });
  const screen = new THREE.MeshStandardMaterial({ color: 0x4f9290, emissive: 0x286b66, emissiveIntensity: 0.82, roughness: 0.22 });
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      const x = -7.8 + column * 5.1;
      const z = -5.5 + row * 3.3;
      addBox(parent, [3.4, 0.12, 1.15], [x, 0.76, z], bench);
      addBox(parent, [0.72, 0.55, 0.08], [x, 1.12, z - 0.2], screen, 0, false);
      addBox(parent, [0.08, 0.7, 0.08], [x - 1.35, 0.38, z], dark, 0, false);
      addBox(parent, [0.08, 0.7, 0.08], [x + 1.35, 0.38, z], dark, 0, false);
    }
  }
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x73a5a3, roughness: 0.12, transparent: true, opacity: 0.36 });
  addBox(parent, [0.08, 2.4, 14], [0, 1.2, 0], glass, 0, false);
}

function addCommunityInterior(parent: THREE.Object3D) {
  const reception = new THREE.MeshStandardMaterial({ color: 0xb39370, roughness: 0.84 });
  const lounge = new THREE.MeshStandardMaterial({ color: 0x688b80, roughness: 0.94 });
  const play = new THREE.MeshStandardMaterial({ color: 0xd7aa59, roughness: 0.88 });
  addBox(parent, [7.8, 0.92, 1.25], [0, 0.48, -5.9], reception);
  addBox(parent, [4.1, 0.54, 1.1], [-7.3, 0.28, 2.8], lounge);
  addBox(parent, [1.1, 0.54, 3.4], [-9.1, 0.28, 4.5], lounge);
  addBox(parent, [4.1, 0.54, 1.1], [7.3, 0.28, 2.8], lounge);
  addBox(parent, [1.1, 0.54, 3.4], [9.1, 0.28, 4.5], lounge);
  addPlane(parent, 5.4, 4.2, 0, 4.3, new THREE.MeshStandardMaterial({ color: 0xb77b67, roughness: 0.94 }), -0.04, 0.04);
  addBox(parent, [0.14, 1.4, 0.14], [-1.2, 0.7, 4.3], play);
  addBox(parent, [0.14, 1.4, 0.14], [1.2, 0.7, 4.3], play);
  addBox(parent, [2.6, 0.12, 0.18], [0, 1.35, 4.3], play);
}

function addFloorIdentityZone(parent: THREE.Object3D, kind: InteriorKind, floor: number) {
  const accentColors: Record<InteriorKind, number> = {
    library: 0x517d75,
    canteen: 0xb97955,
    auditorium: 0x756b7f,
    lab: 0x4c8d8d,
    community: 0x7b9165,
  };
  const accent = new THREE.MeshStandardMaterial({
    color: accentColors[kind],
    emissive: accentColors[kind],
    emissiveIntensity: 0.16,
    roughness: 0.66,
  });
  const pale = new THREE.MeshStandardMaterial({ color: 0xdfe3db, roughness: 0.84 });
  const wood = new THREE.MeshStandardMaterial({ color: 0xb79570, roughness: 0.88 });
  const glass = new THREE.MeshPhysicalMaterial({
    color: 0x77a49d,
    roughness: 0.12,
    transparent: true,
    opacity: 0.34,
  });

  // Every floor has a physically different circulation and furniture signature,
  // so switching floors changes more than a label or random seed.
  if (floor === 1) {
    addBox(parent, [7.2, 0.9, 1.2], [0, 0.46, 5.9], accent);
    addBox(parent, [2.7, 1.95, 0.08], [0, 1.35, 6.56], glass, 0, false);
    for (let index = -3; index <= 3; index += 1) addBox(parent, [0.62, 0.42, 0.62], [index * 1.25, 0.22, 3.9], pale, Math.PI / 4, false);
    return;
  }
  if (floor === 2) {
    for (let index = -4; index <= 4; index += 1) {
      addBox(parent, [1.35, 1.28, 0.08], [index * 2.35, 0.66, 5.9], index % 2 ? accent : pale, 0, false);
      addBox(parent, [1.2, 0.08, 0.55], [index * 2.35, 0.72, 4.95], wood, 0, false);
    }
    return;
  }
  if (floor === 3) {
    const center = new THREE.Mesh(new THREE.CylinderGeometry(2.3, 2.3, 0.15, 32), wood);
    center.position.set(0, 0.09, 4.3);
    center.receiveShadow = true;
    parent.add(center);
    for (let index = 0; index < 8; index += 1) {
      const angle = (index / 8) * Math.PI * 2;
      addBox(parent, [0.85, 0.52, 0.52], [Math.cos(angle) * 3.25, 0.28, 4.3 + Math.sin(angle) * 2.25], accent, -angle, false);
    }
    return;
  }
  if (floor === 4) {
    for (let index = 0; index < 5; index += 1) {
      addBox(parent, [3.1, 2.25, 0.08], [-7.6 + index * 3.8, 1.13, 4.6], glass, 0, false);
      addBox(parent, [2.7, 0.8, 0.72], [-7.6 + index * 3.8, 0.42, 5.25], index % 2 ? accent : pale, 0, false);
    }
    return;
  }
  addPlane(parent, 19.5, 5.4, 0, 4.8, new THREE.MeshStandardMaterial({ color: 0xc8d6ca, roughness: 0.95 }), 0, 0.025);
  for (let index = -3; index <= 3; index += 1) {
    addBox(parent, [1.65, 0.1, 0.62], [index * 2.65, 0.6, 4.8 + (index % 2) * 1.35], wood, index % 2 ? 0.12 : -0.12);
    addBox(parent, [0.08, 2.3, 0.08], [index * 2.65, 1.15, 6.9], accent, 0, false);
  }
  addBox(parent, [19.5, 0.1, 0.12], [0, 2.3, 6.9], accent, 0, false);
}

function buildInterior(scene: THREE.Scene, random: () => number, building: string, floor: number, agents: WorldAgent[]) {
  const group = new THREE.Group();
  scene.add(group);
  const kind = resolveInteriorKind(building);
  addInteriorShell(group, kind, floor);
  if (kind === 'library') addLibraryInterior(group);
  if (kind === 'canteen') addCanteenInterior(group);
  if (kind === 'auditorium') addAuditoriumInterior(group);
  if (kind === 'lab') addLabInterior(group);
  if (kind === 'community') addCommunityInterior(group);
  addFloorIdentityZone(group, kind, floor);
  addInteriorPlants(group);
  const counts: Record<InteriorKind, number> = { library: 78, canteen: 104, auditorium: 116, lab: 64, community: 82 };
  const floorCount = Math.max(18, counts[kind] + [14, 4, -8, -18, -26][Math.max(0, Math.min(4, floor - 1))]);
  const centers: Record<InteriorKind, Array<[number, number]>> = {
    library: [[-6, -4], [1, -2], [6, 4]],
    canteen: [[-7, -2], [0, 0], [7, 3], [4, -4]],
    auditorium: [[-5, 1], [0, 2], [5, 3]],
    lab: [[-7, -4], [5, -3], [-3, 4], [7, 4]],
    community: [[0, -4], [-7, 3], [7, 3], [0, 5]],
  };
  const population = addPopulation(group, random, floorCount, true, centers[kind]);
  return completeScene(group, population, null, agents, true, [[-6.5, -4.2], [-1.4, -1.2], [5.9, -4.2], [3.3, 4.4]]);
}

function disposeScene(scene: THREE.Scene) {
  scene.traverse((object) => {
    if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.InstancedMesh || object instanceof THREE.Sprite) {
      object.geometry?.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => {
        const texturedMaterial = material as THREE.Material & { map?: THREE.Texture | null };
        texturedMaterial.map?.dispose();
        material?.dispose();
      });
    }
  });
}

export function SocialWorld3D({
  mode,
  variant = 'guiyang_convention',
  building = '',
  floor = 3,
  rotation,
  zoom,
  pan = { x: 0, y: 0 },
  agents = [],
  anchors = [],
  selectedAgentId,
  onAgentSelect,
  onAnchorSelect,
}: SocialWorld3DProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const canvasHostRef = useRef<HTMLDivElement | null>(null);
  const anchorElementsRef = useRef(new Map<string, HTMLElement>());
  const agentElementsRef = useRef(new Map<string, HTMLElement>());
  const thoughtRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<SceneView>({ rotation, zoom, panX: pan.x, panY: pan.y, selectedAgentId });
  const onAgentSelectRef = useRef(onAgentSelect);
  const agentsRef = useRef(agents);
  const anchorsRef = useRef(anchors);
  const agentSignature = agents.map((agent) => agent.id).join('|');
  const anchorSignature = anchors.map((anchor) => `${anchor.id}:${anchor.position.join(',')}`).join('|');
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId);

  useEffect(() => {
    viewRef.current = { rotation, zoom, panX: pan.x, panY: pan.y, selectedAgentId };
  }, [rotation, zoom, pan.x, pan.y, selectedAgentId]);

  useEffect(() => {
    onAgentSelectRef.current = onAgentSelect;
  }, [onAgentSelect]);

  useEffect(() => {
    agentsRef.current = agents;
  }, [agents]);

  useEffect(() => {
    anchorsRef.current = anchors;
  }, [anchors]);

  useEffect(() => {
    const host = hostRef.current;
    const canvasHost = canvasHostRef.current;
    if (!host || !canvasHost) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    } catch {
      host.dataset.failed = 'true';
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(mode === 'interior' ? 0xc7d0ca : mode === 'campus' ? 0xc6d1ca : 0xd3dcd6);
    scene.fog = new THREE.FogExp2(mode === 'interior' ? 0xd1d7d2 : mode === 'campus' ? 0xcbd5cf : 0xd7dfda, mode === 'interior' ? 0.019 : mode === 'campus' ? 0.0105 : 0.014);
    const camera = new THREE.OrthographicCamera(-20, 20, 12, -12, 0.1, 160);
    const random = seededRandom(`${mode}:${variant}:${building}:${floor}`);
    const sceneAgents = agentsRef.current;
    const world = mode === 'campus'
      ? buildCampus(scene, random, variant, sceneAgents)
      : mode === 'district'
        ? buildDistrict(scene, random, variant, sceneAgents)
        : buildInterior(scene, random, building, floor, sceneAgents);

    scene.add(new THREE.HemisphereLight(0xeaf1ed, 0x56655c, mode === 'interior' ? 2.35 : 1.82));
    const sun = new THREE.DirectionalLight(0xffedcf, mode === 'interior' ? 2.45 : 2.55);
    sun.position.set(-18, 28, 14);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1536, 1536);
    sun.shadow.camera.left = -28;
    sun.shadow.camera.right = 28;
    sun.shadow.camera.top = 22;
    sun.shadow.camera.bottom = -22;
    sun.shadow.bias = -0.0005;
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0x88bcb5, 0.75);
    fill.position.set(16, 9, -12);
    scene.add(fill);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.55));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = mode === 'interior' ? 1.02 : 0.96;
    renderer.domElement.className = 'sw-three-canvas';
    renderer.domElement.setAttribute('aria-hidden', 'true');
    canvasHost.replaceChildren(renderer.domElement);

    const resize = () => {
      const width = Math.max(1, host.clientWidth);
      const height = Math.max(1, host.clientHeight);
      renderer.setSize(width, height, false);
      const aspect = width / height;
      const span = mode === 'interior' ? 22 : 34;
      camera.left = -(span * aspect) / 2;
      camera.right = (span * aspect) / 2;
      camera.top = span / 2;
      camera.bottom = -span / 2;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerStart: { x: number; y: number; id: number } | null = null;
    const findAgent = (clientX: number, clientY: number) => {
      if (!world.pickables.length) return null;
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((clientX - bounds.left) / bounds.width) * 2 - 1,
        -((clientY - bounds.top) / bounds.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(world.pickables, false)[0];
      const agentId = hit?.object.userData.agentId as string | undefined;
      return agentId ? world.heroes.find((hero) => hero.agent.id === agentId)?.agent ?? null : null;
    };
    const handlePointerDown = (event: PointerEvent) => {
      pointerStart = { x: event.clientX, y: event.clientY, id: event.pointerId };
    };
    const handlePointerMove = (event: PointerEvent) => {
      const hovered = findAgent(event.clientX, event.clientY);
      if (hovered) host.dataset.agentHover = 'true';
      else delete host.dataset.agentHover;
    };
    const handlePointerUp = (event: PointerEvent) => {
      if (!pointerStart || pointerStart.id !== event.pointerId) return;
      const distance = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y);
      pointerStart = null;
      if (distance > 6) return;
      const agent = findAgent(event.clientX, event.clientY);
      if (agent) onAgentSelectRef.current?.(agent);
    };
    const handlePointerLeave = () => {
      pointerStart = null;
      delete host.dataset.agentHover;
    };
    renderer.domElement.addEventListener('pointerdown', handlePointerDown);
    renderer.domElement.addEventListener('pointermove', handlePointerMove);
    renderer.domElement.addEventListener('pointerup', handlePointerUp);
    renderer.domElement.addEventListener('pointercancel', handlePointerLeave);
    renderer.domElement.addEventListener('pointerleave', handlePointerLeave);

    const dummy = new THREE.Object3D();
    const projected = new THREE.Vector3();
    const placeOverlay = (element: HTMLElement | null | undefined, position: THREE.Vector3) => {
      if (!element) return;
      projected.copy(position).project(camera);
      const width = host.clientWidth;
      const height = host.clientHeight;
      const x = (projected.x * 0.5 + 0.5) * width;
      const y = (-projected.y * 0.5 + 0.5) * height;
      const visible = projected.z > -1 && projected.z < 1 && x > -80 && x < width + 80 && y > -80 && y < height + 80;
      element.dataset.visible = visible ? 'true' : 'false';
      if (visible) {
        element.style.left = `${x.toFixed(1)}px`;
        element.style.top = `${y.toFixed(1)}px`;
      }
    };
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let animationFrame = 0;
    let previous = performance.now();
    const render = (timestamp: number) => {
      const delta = Math.min(0.05, (timestamp - previous) / 1000);
      previous = timestamp;
      const view = viewRef.current;
      const angle = THREE.MathUtils.degToRad(43 + view.rotation * 0.72);
      const radius = mode === 'interior' ? 24 : 38;
      const focusX = -view.panX * (mode === 'interior' ? 0.018 : 0.024);
      const focusZ = -view.panY * (mode === 'interior' ? 0.018 : 0.024) + (mode === 'interior' ? -0.3 : 0.5);
      camera.position.set(focusX + Math.cos(angle) * radius, mode === 'interior' ? 18 : 25, focusZ + Math.sin(angle) * radius);
      camera.zoom = Math.max(0.62, Math.min(1.75, view.zoom));
      camera.lookAt(focusX, mode === 'interior' ? 0.1 : 0, focusZ);
      camera.updateProjectionMatrix();

      if (!reduceMotion) {
        const elapsed = timestamp / 1000;
        const { population } = world;
        for (let index = 0; index < population.movingCount; index += 1) {
          const direction = index % 3 === 0 ? 1 : -1;
          const travel = Math.sin(elapsed * population.speed[index] + population.phase[index]) * (mode === 'interior' ? 0.38 : 0.8);
          const x = population.baseX[index] + travel;
          const z = population.baseZ[index] + Math.cos(elapsed * population.speed[index] * 0.72 + population.phase[index]) * (mode === 'interior' ? 0.12 : 0.26) * direction;
          const scale = 0.9 + (index % 5) * 0.035;
          dummy.position.set(x, mode === 'interior' ? 0.2 : 0.17, z);
          dummy.scale.set(scale, scale, scale);
          dummy.rotation.y = direction > 0 ? Math.PI / 2 : -Math.PI / 2;
          dummy.updateMatrix();
          population.meshes.forEach((mesh) => mesh.setMatrixAt(index, dummy.matrix));
        }
        population.meshes.forEach((mesh) => {
          mesh.instanceMatrix.needsUpdate = true;
        });
        world.heroes.forEach((hero) => {
          const gait = elapsed * (hero.moving ? 2.15 : 0.72) + hero.phase;
          const stride = hero.moving ? Math.sin(gait) * 0.38 : Math.sin(gait) * 0.035;
          hero.leftArm.rotation.x = stride;
          hero.rightArm.rotation.x = -stride;
          hero.leftLeg.rotation.x = -stride * 0.82;
          hero.rightLeg.rotation.x = stride * 0.82;
          hero.root.position.x = hero.baseX + (hero.moving ? Math.sin(gait * 0.42) * 0.34 : 0);
          hero.root.position.z = hero.baseZ + (hero.moving ? Math.cos(gait * 0.42) * 0.18 : 0);
          hero.root.position.y = 0.03 + Math.abs(Math.sin(gait)) * (hero.moving ? 0.035 : 0.012);
          const selected = view.selectedAgentId === hero.agent.id;
          const haloMaterial = hero.halo.material as THREE.MeshStandardMaterial;
          haloMaterial.opacity = selected ? 0.98 : 0.62 + Math.sin(elapsed * 2.2 + hero.phase) * 0.12;
          haloMaterial.emissiveIntensity = selected ? 2.1 : 1.05;
          const haloScale = selected ? 1.15 + Math.sin(elapsed * 3.2) * 0.045 : 1;
          hero.halo.scale.setScalar(haloScale);
        });
        if (world.atmosphere) {
          const position = world.atmosphere.geometry.getAttribute('position') as THREE.BufferAttribute;
          const speeds = world.atmosphere.userData.speeds as Float32Array;
          const drift = world.atmosphere.userData.drift ?? 0.08;
          const falling = world.atmosphere.userData.falling !== false;
          for (let index = 0; index < position.count; index += 1) {
            if (falling) {
              let y = position.getY(index) - speeds[index] * delta;
              if (y < 0.1) y = 13 + (index % 17) * 0.34;
              position.setY(index, y);
            } else {
              const floatingY = position.getY(index) + Math.sin(elapsed * speeds[index] + index) * delta * 0.025;
              position.setY(index, floatingY);
            }
            let x = position.getX(index) - delta * drift;
            if (x < -24) x = 24;
            position.setX(index, x);
          }
          position.needsUpdate = true;
        }
      }
      anchorsRef.current.forEach((anchor) => {
        placeOverlay(anchorElementsRef.current.get(anchor.id), new THREE.Vector3(...anchor.position));
      });
      world.heroes.forEach((hero) => {
        const position = hero.root.position.clone();
        position.y += mode === 'interior' ? 1.72 : 1.95;
        placeOverlay(agentElementsRef.current.get(hero.agent.id), position);
      });
      const activeHero = world.heroes.find((hero) => hero.agent.id === view.selectedAgentId);
      if (activeHero && thoughtRef.current) {
        const thoughtPosition = activeHero.root.position.clone();
        thoughtPosition.y += mode === 'interior' ? 2.62 : 2.88;
        placeOverlay(thoughtRef.current, thoughtPosition);
      } else if (thoughtRef.current) {
        thoughtRef.current.dataset.visible = 'false';
      }
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(render);
    };
    animationFrame = window.requestAnimationFrame(render);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      renderer.domElement.removeEventListener('pointermove', handlePointerMove);
      renderer.domElement.removeEventListener('pointerup', handlePointerUp);
      renderer.domElement.removeEventListener('pointercancel', handlePointerLeave);
      renderer.domElement.removeEventListener('pointerleave', handlePointerLeave);
      disposeScene(scene);
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentElement === canvasHost) canvasHost.removeChild(renderer.domElement);
    };
  }, [mode, variant, building, floor, agentSignature, anchorSignature]);

  const sceneNames: Record<string, string> = {
    guiyang_convention: '贵阳国际会议展览中心',
    guiyang_big_data: '贵阳大数据科创城',
    guizhou_university: '贵州大学西校区',
    jiaxiu_tower: '甲秀楼·南明河',
    qingyan_town: '青岩古镇',
    guiyang_north_station: '贵阳北站',
    huaguoyuan: '花果园社区',
  };
  const sceneName = sceneNames[variant] || '贵阳城市节点';
  const label = mode === 'interior'
    ? `${building} ${floor} 层三维内部场景`
    : mode === 'campus'
      ? `${sceneName}三维校园场景`
      : `${sceneName}三维微观场景`;

  return (
    <div ref={hostRef} className="sw-three-host" role="region" aria-label={label}>
      <div ref={canvasHostRef} className="sw-three-renderer" aria-hidden="true" />
      <span className="sw-three-fallback">当前设备无法加载实时三维场景。</span>
      <div className="sw-three-overlay">
        {anchors.map((anchor) => anchor.actionId ? (
          <button
            ref={(element) => { if (element) anchorElementsRef.current.set(anchor.id, element); else anchorElementsRef.current.delete(anchor.id); }}
            className={`sw-three-anchor kind-${anchor.kind || 'poi'}`}
            data-visible="false"
            type="button"
            key={anchor.id}
            onClick={() => onAnchorSelect?.(anchor)}
          >
            <i />{anchor.label}{anchor.detail ? <small>{anchor.detail}</small> : null}
          </button>
        ) : (
          <span
            ref={(element) => { if (element) anchorElementsRef.current.set(anchor.id, element); else anchorElementsRef.current.delete(anchor.id); }}
            className={`sw-three-anchor kind-${anchor.kind || 'poi'}`}
            data-visible="false"
            key={anchor.id}
          >
            {anchor.label}{anchor.detail ? <small>{anchor.detail}</small> : null}
          </span>
        ))}
        {agents.map((agent) => (
          <button
            ref={(element) => { if (element) agentElementsRef.current.set(agent.id, element); else agentElementsRef.current.delete(agent.id); }}
            className={`sw-three-agent-anchor ${selectedAgentId === agent.id ? 'selected' : ''}`}
            data-visible="false"
            type="button"
            key={agent.id}
            onClick={() => onAgentSelect?.(agent)}
          >
            <i /><span>{agent.name}</span><small>{agent.action}</small>
          </button>
        ))}
        {selectedAgent ? (
          <div ref={thoughtRef} className="sw-three-thought" data-visible="false">
            <span>当前行动</span><strong>{selectedAgent.action}</strong>
          </div>
        ) : null}
      </div>
    </div>
  );
}
