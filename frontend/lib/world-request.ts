import type { WorldSimulationRequest } from '@/lib/world-types';
import { SOCIAL_WORLD_CITY } from '@/lib/social-world-fixtures';

const socialWorldLocations: WorldSimulationRequest['world']['locations'] = [
  {
    location_id: 'guiyang',
    name: '贵阳',
    location_type: 'city',
    parent_id: null,
    capacity: SOCIAL_WORLD_CITY.representedPopulation,
    baseline_activity: 0.72,
    semantic_tags: ['city', 'public', 'mountain_city'],
    supported_channels: ['news', 'social_media'],
  },
  {
    location_id: 'guanshanhu_district',
    name: '观山湖区',
    location_type: 'district',
    parent_id: 'guiyang',
    capacity: 700_000,
    baseline_activity: 0.68,
    semantic_tags: ['exhibition', 'business', 'transit'],
    supported_channels: ['news', 'community', 'onsite'],
  },
  {
    location_id: 'guian_innovation_area',
    name: '贵安科创片区',
    location_type: 'district',
    parent_id: 'guiyang',
    capacity: 760_000,
    baseline_activity: 0.64,
    semantic_tags: ['technology', 'innovation', 'work'],
    supported_channels: ['news', 'community', 'social_media'],
  },
  {
    location_id: 'huaxi_district',
    name: '花溪区',
    location_type: 'district',
    parent_id: 'guiyang',
    capacity: 1_050_000,
    baseline_activity: 0.61,
    semantic_tags: ['education', 'heritage', 'tourism'],
    supported_channels: ['news', 'community', 'interpersonal'],
  },
  {
    location_id: 'nanming_district',
    name: '南明区',
    location_type: 'district',
    parent_id: 'guiyang',
    capacity: 1_100_000,
    baseline_activity: 0.7,
    semantic_tags: ['residential', 'heritage', 'commerce'],
    supported_channels: ['news', 'community', 'social_media'],
  },
  {
    location_id: 'guiyang_convention',
    name: '贵阳国际会议展览中心',
    location_type: 'workplace',
    parent_id: 'guanshanhu_district',
    capacity: 120_000,
    baseline_activity: 0.76,
    semantic_tags: ['exhibition', 'event', 'business', 'public'],
    supported_channels: ['onsite', 'news', 'social_media'],
  },
  {
    location_id: 'guiyang_big_data',
    name: '贵阳大数据科创城',
    location_type: 'workplace',
    parent_id: 'guian_innovation_area',
    capacity: 180_000,
    baseline_activity: 0.7,
    semantic_tags: ['technology', 'data', 'innovation', 'work'],
    supported_channels: ['community', 'social_media', 'interpersonal'],
  },
  {
    location_id: 'guizhou_university',
    name: '贵州大学西校区',
    location_type: 'campus',
    parent_id: 'huaxi_district',
    capacity: 80_000,
    baseline_activity: 0.72,
    semantic_tags: ['campus', 'student', 'research'],
    supported_channels: ['community', 'social_media', 'onsite'],
  },
  {
    location_id: 'jiaxiu_tower',
    name: '甲秀楼·南明河',
    location_type: 'community',
    parent_id: 'nanming_district',
    capacity: 90_000,
    baseline_activity: 0.65,
    semantic_tags: ['heritage', 'public', 'riverfront', 'tourism'],
    supported_channels: ['onsite', 'social_media', 'interpersonal'],
  },
  {
    location_id: 'qingyan_town',
    name: '青岩古镇',
    location_type: 'community',
    parent_id: 'huaxi_district',
    capacity: 75_000,
    baseline_activity: 0.62,
    semantic_tags: ['heritage', 'tourism', 'community', 'retail'],
    supported_channels: ['onsite', 'community', 'social_media'],
  },
  {
    location_id: 'guiyang_north_station',
    name: '贵阳北站',
    location_type: 'transit',
    parent_id: 'guanshanhu_district',
    capacity: 240_000,
    baseline_activity: 0.78,
    semantic_tags: ['transit', 'mobility', 'public'],
    supported_channels: ['onsite', 'news', 'interpersonal'],
  },
  {
    location_id: 'huaguoyuan',
    name: '花果园社区',
    location_type: 'residential',
    parent_id: 'nanming_district',
    capacity: 520_000,
    baseline_activity: 0.66,
    semantic_tags: ['home', 'community', 'commerce', 'high_density'],
    supported_channels: ['community', 'interpersonal', 'social_media'],
  },
  {
    location_id: 'online_public_space',
    name: '贵阳线上公共空间',
    location_type: 'online',
    parent_id: 'guiyang',
    capacity: SOCIAL_WORLD_CITY.representedPopulation,
    baseline_activity: 0.82,
    semantic_tags: ['online', 'public'],
    supported_channels: ['social_media', 'search'],
  },
];

const worldLocationIds = new Set(socialWorldLocations.map((location) => location.location_id));

export function buildWorldRequest(input: {
  projectId: string;
  eventId: string;
  eventTitle: string;
  eventDescription: string;
  populationSize: number;
  filters: Record<string, string[]>;
  channels: string[];
  horizon: number;
  paths: number;
  credibility: number;
  eventImpact: number;
  evidenceNotes: string;
  sourceLocationId?: string | null;
  targetLocationIds?: string[];
  decisionRounds?: number;
  questionOverrides?: WorldSimulationRequest['question_overrides'];
}): WorldSimulationRequest {
  const sourceLocationId = input.sourceLocationId && worldLocationIds.has(input.sourceLocationId)
    ? input.sourceLocationId
    : null;
  const targetLocationIds = Array.from(new Set(input.targetLocationIds || []))
    .filter((locationId) => worldLocationIds.has(locationId));

  return {
    project_id: input.projectId,
    world: {
      world_id: `guiyang_${input.projectId}`,
      name: '贵阳社会世界',
      represented_population: SOCIAL_WORLD_CITY.representedPopulation,
      prototype_count: input.populationSize,
      tick_minutes: 60,
      start_hour: 8,
      population_filters: input.filters,
      locations: socialWorldLocations,
    },
    events: [{
      event_id: input.eventId,
      title: input.eventTitle,
      description: input.eventDescription,
      start_tick: 1,
      duration_ticks: Math.min(24, input.horizon),
      source_location_id: sourceLocationId,
      target_location_ids: targetLocationIds,
      channels: input.channels,
      audience_filters: input.filters,
      intensity: 0.68,
      credibility: input.credibility,
      novelty: 0.65,
      valence: input.eventImpact,
      belief_signals: { social_attitude: input.eventImpact * 0.7 },
      value_signals: {},
      goal_signals: { belonging: 0.2, growth: 0.2 },
      evidence_refs: input.evidenceNotes.trim() ? ['user_background'] : [],
    }],
    horizon_ticks: input.horizon,
    paths: Math.min(input.paths, 3),
    seed: 2026,
    trace_agent_count: 12,
    snapshot_interval: 6,
    interaction_mode: 'independent',
    decision_rounds: input.decisionRounds ?? 4,
    question_overrides: input.questionOverrides ?? [],
  };
}
