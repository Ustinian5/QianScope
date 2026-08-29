import type { WorldLocation } from '@/lib/social-world-fixtures';

export type FlipbookHotspot = {
  id: string;
  label: string;
  xPct: number;
  yPct: number;
};

type SceneAsset = {
  exterior: string;
  pages: Record<string, FlipbookScenePage>;
  exteriorAnchors: Array<{ xPct: number; yPct: number }>;
};

export type FlipbookScenePage = {
  image: string;
  video: string;
};

const ROOT = '/openflipbook/guiyang';
const TRANSITIONS = `${ROOT}/transitions`;

const SCENE_ASSETS: Record<string, SceneAsset> = {
  guiyang_convention: {
    exterior: `${ROOT}/guiyang-convention-exterior.jpg`,
    pages: {
      国际会议中心: {
        image: `${ROOT}/guiyang-convention-interior.jpg`,
        video: `${TRANSITIONS}/guiyang-convention-conference-center.mp4`,
      },
      展览中心登录厅: {
        image: `${ROOT}/guiyang-convention-exhibition-login-hall.png`,
        video: `${TRANSITIONS}/guiyang-convention-exhibition-login-hall.mp4`,
      },
      数博发布厅: {
        image: `${ROOT}/guiyang-convention-big-data-release-hall.png`,
        video: `${TRANSITIONS}/guiyang-convention-big-data-release-hall.mp4`,
      },
      城市会客厅: {
        image: `${ROOT}/guiyang-convention-city-reception-hall.png`,
        video: `${TRANSITIONS}/guiyang-convention-city-reception-hall.mp4`,
      },
    },
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.34 },
      { xPct: 0.74, yPct: 0.34 },
      { xPct: 0.27, yPct: 0.69 },
      { xPct: 0.73, yPct: 0.69 },
    ],
  },
  guiyang_big_data: {
    exterior: `${ROOT}/guiyang-big-data-exterior.jpg`,
    pages: {
      科创城展示中心: {
        image: `${ROOT}/guiyang-big-data-interior.jpg`,
        video: `${TRANSITIONS}/guiyang-big-data-showcase-center.mp4`,
      },
      数据要素路演厅: {
        image: `${ROOT}/guiyang-big-data-roadshow-hall.png`,
        video: `${TRANSITIONS}/guiyang-big-data-roadshow-hall.mp4`,
      },
      算力协同实验室: {
        image: `${ROOT}/guiyang-big-data-compute-lab.png`,
        video: `${TRANSITIONS}/guiyang-big-data-compute-lab.mp4`,
      },
      青年人才社区: {
        image: `${ROOT}/guiyang-big-data-youth-community.png`,
        video: `${TRANSITIONS}/guiyang-big-data-youth-community.mp4`,
      },
    },
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.30 },
      { xPct: 0.73, yPct: 0.29 },
      { xPct: 0.27, yPct: 0.68 },
      { xPct: 0.73, yPct: 0.68 },
    ],
  },
  guizhou_university: {
    exterior: `${ROOT}/guizhou-university-exterior.jpg`,
    pages: {
      西区图书馆: {
        image: `${ROOT}/guizhou-university-interior.jpg`,
        video: `${TRANSITIONS}/guizhou-university-library.mp4`,
      },
      工程训练中心: {
        image: `${ROOT}/guizhou-university-engineering-center.png`,
        video: `${TRANSITIONS}/guizhou-university-engineering-center.mp4`,
      },
      大学生活动中心: {
        image: `${ROOT}/guizhou-university-student-activity-center.png`,
        video: `${TRANSITIONS}/guizhou-university-student-activity-center.mp4`,
      },
      学生食堂: {
        image: `${ROOT}/guizhou-university-cafeteria.png`,
        video: `${TRANSITIONS}/guizhou-university-cafeteria.mp4`,
      },
    },
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.30 },
      { xPct: 0.74, yPct: 0.30 },
      { xPct: 0.25, yPct: 0.66 },
      { xPct: 0.74, yPct: 0.67 },
    ],
  },
  jiaxiu_tower: {
    exterior: `${ROOT}/jiaxiu-tower-exterior.jpg`,
    pages: {
      甲秀楼文化展厅: {
        image: `${ROOT}/jiaxiu-tower-interior.jpg`,
        video: `${TRANSITIONS}/jiaxiu-tower-culture-hall.mp4`,
      },
      翠微园: {
        image: `${ROOT}/jiaxiu-tower-cuiwei-garden.png`,
        video: `${TRANSITIONS}/jiaxiu-tower-cuiwei-garden.mp4`,
      },
      南明河公共驿站: {
        image: `${ROOT}/jiaxiu-tower-riverside-outpost.png`,
        video: `${TRANSITIONS}/jiaxiu-tower-riverside-outpost.mp4`,
      },
      河滨书屋: {
        image: `${ROOT}/jiaxiu-tower-riverside-library.png`,
        video: `${TRANSITIONS}/jiaxiu-tower-riverside-library.mp4`,
      },
    },
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.30 },
      { xPct: 0.73, yPct: 0.30 },
      { xPct: 0.25, yPct: 0.71 },
      { xPct: 0.75, yPct: 0.71 },
    ],
  },
  qingyan_town: {
    exterior: `${ROOT}/qingyan-town-exterior.jpg`,
    pages: {
      古镇游客中心: {
        image: `${ROOT}/qingyan-town-interior.jpg`,
        video: `${TRANSITIONS}/qingyan-town-visitor-center.mp4`,
      },
      非遗工坊: {
        image: `${ROOT}/qingyan-town-heritage-workshop.png`,
        video: `${TRANSITIONS}/qingyan-town-heritage-workshop.mp4`,
      },
      背街社区议事厅: {
        image: `${ROOT}/qingyan-town-community-council.png`,
        video: `${TRANSITIONS}/qingyan-town-community-council.mp4`,
      },
      状元文化书屋: {
        image: `${ROOT}/qingyan-town-zhuangyuan-library.png`,
        video: `${TRANSITIONS}/qingyan-town-zhuangyuan-library.mp4`,
      },
    },
    exteriorAnchors: [
      { xPct: 0.27, yPct: 0.27 },
      { xPct: 0.73, yPct: 0.27 },
      { xPct: 0.28, yPct: 0.68 },
      { xPct: 0.72, yPct: 0.69 },
    ],
  },
  guiyang_north_station: {
    exterior: `${ROOT}/guiyang-north-station-exterior.jpg`,
    pages: {
      综合换乘大厅: {
        image: `${ROOT}/guiyang-north-station-interior.jpg`,
        video: `${TRANSITIONS}/guiyang-north-station-interchange-hall.mp4`,
      },
      高铁候车厅: {
        image: `${ROOT}/guiyang-north-station-waiting-hall.png`,
        video: `${TRANSITIONS}/guiyang-north-station-waiting-hall.mp4`,
      },
      公交调度中心: {
        image: `${ROOT}/guiyang-north-station-bus-control.png`,
        video: `${TRANSITIONS}/guiyang-north-station-bus-control.mp4`,
      },
      旅客服务中心: {
        image: `${ROOT}/guiyang-north-station-passenger-service.png`,
        video: `${TRANSITIONS}/guiyang-north-station-passenger-service.mp4`,
      },
    },
    exteriorAnchors: [
      { xPct: 0.24, yPct: 0.29 },
      { xPct: 0.70, yPct: 0.29 },
      { xPct: 0.25, yPct: 0.69 },
      { xPct: 0.72, yPct: 0.71 },
    ],
  },
  huaguoyuan: {
    exterior: `${ROOT}/huaguoyuan-exterior.jpg`,
    pages: {
      社区服务中心: {
        image: `${ROOT}/huaguoyuan-interior.jpg`,
        video: `${TRANSITIONS}/huaguoyuan-community-service.mp4`,
      },
      湿地公园驿站: {
        image: `${ROOT}/huaguoyuan-wetland-outpost.png`,
        video: `${TRANSITIONS}/huaguoyuan-wetland-outpost.mp4`,
      },
      托育活动站: {
        image: `${ROOT}/huaguoyuan-childcare-center.png`,
        video: `${TRANSITIONS}/huaguoyuan-childcare-center.mp4`,
      },
      健康管理中心: {
        image: `${ROOT}/huaguoyuan-health-center.png`,
        video: `${TRANSITIONS}/huaguoyuan-health-center.mp4`,
      },
    },
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
  building: string,
): string {
  const asset = assetFor(locationId);
  if (level === 'campus') return asset.exterior;
  return scenePage(locationId, building).image;
}

export function scenePage(locationId: string, building: string): FlipbookScenePage {
  const asset = assetFor(locationId);
  return asset.pages[building] ?? Object.values(asset.pages)[0]!;
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
  return Object.values(SCENE_ASSETS).flatMap((asset) => [
    asset.exterior,
    ...Object.values(asset.pages).flatMap((page) => [page.image, page.video]),
  ]);
}
