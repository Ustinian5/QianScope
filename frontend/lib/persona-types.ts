import type { AIExecutionMetadata } from '@/lib/types';

export type PersonaSearchItem = {
  persona_id: string;
  name: string;
  role: string;
  organization: string;
  location_id: string;
  location: string;
  tier: string;
  represented_weight: number;
  mood: string;
  tags: string[];
  bio: string;
};

export type PersonaSearchResult = {
  query: string;
  prototype_matches: number;
  represented_population: number;
  total_prototypes: number;
  total_represented_population: number;
  offset: number;
  limit: number;
  items: PersonaSearchItem[];
  note: string;
};

export type PersonaMapItem = {
  persona_id: string;
  tier: string;
  represented_weight: number;
  route_location_ids: string[];
};

export type PersonaMapSnapshot = {
  total_prototypes: number;
  total_represented_population: number;
  items: PersonaMapItem[];
  note: string;
};

export type PersonaProfile = {
  persona_id: string;
  name: string;
  role: string;
  organization: string;
  age: number;
  age_group: string;
  gender: string;
  education_level: string;
  region_type: string;
  household_type: string;
  tier: string;
  represented_weight: number;
  bio: string;
  traits: Array<{ key: string; label: string; score: number }>;
  values: Array<{ key: string; label: string; score: number }>;
  demographics: Record<string, string>;
  frameworks: Array<{
    framework_id: string;
    label: string;
    reference: string;
    description: string;
    dimensions: Array<{
      key: string;
      field: string;
      label: string;
      description: string;
      score: number;
      scale_min: number;
      scale_max: number;
      low_pole: string;
      high_pole: string;
      interpretation: string;
    }>;
  }>;
  primary_goal: string;
  primary_interest: string;
  primary_channel: string;
  state: {
    mood: string;
    stress: number;
    intention: number;
    confidence: number;
    current_action: string;
    current_location: string;
  };
  memories: string[];
  schedule: Array<{ time: string; activity: string; location: string }>;
  relationships: Array<{
    persona_id: string;
    name: string;
    role: string;
    relation: string;
    trust: number;
    strength: number;
    channel: string;
  }>;
  mobility: {
    home_location_id: string;
    primary_location_id: string;
    social_location_id: string;
    scene_location_id: string;
  };
  model_version: string;
  data_version: string;
  definition_version: string;
  source_id: string;
  field_origins: Record<string, string>;
  profile_completeness: number;
  profile_hash: string;
  profile_origin: 'synthetic';
  disclaimer: string;
};

export type PersonaInterviewResponse = {
  interview_id: string;
  persona_id: string;
  persona_name: string;
  question: string;
  answer: string;
  confidence: number;
  mode: 'deterministic_persona' | 'llm_persona';
  cited_state: string[];
  cross_check_candidates: Array<{
    persona_id: string;
    name: string;
    relation: string;
  }>;
  cognitive_boundary: string;
  ai_execution: AIExecutionMetadata[];
};
