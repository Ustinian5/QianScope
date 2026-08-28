import type { ProbabilityBand } from '@/lib/research-types';

export type WorldQuantileBand = ProbabilityBand & { mean: number };

export type WorldSimulationResult = {
  run_id: string;
  project_id: string;
  world_id: string;
  status: string;
  model_version: string;
  data_version: string;
  population: {
    prototype_count: number;
    represented_population: number;
    tier_counts: Record<string, number>;
    relationship_count: number;
    relationship_types: string[];
    location_count: number;
    immutable_personality_signature: string;
  };
  diffusion_curve: Array<{
    event_id: string;
    tick: number;
    reached_fraction: WorldQuantileBand;
    reached_population: WorldQuantileBand;
    newly_reached_fraction: WorldQuantileBand;
    channel_reach: Record<string, WorldQuantileBand>;
  }>;
  population_heatmap: Array<{
    tick: number;
    location_id: string;
    metrics: Record<string, WorldQuantileBand>;
  }>;
  emotion_distribution: Array<{
    tick: number;
    metrics: Record<string, WorldQuantileBand>;
  }>;
  belief_distribution: Array<{
    tick: number;
    beliefs: Record<string, WorldQuantileBand>;
  }>;
  segment_difference: Array<{
    segment_field: string;
    segment_value: string;
    prototype_count: number;
    represented_population: number;
    reached_fraction: WorldQuantileBand;
    support: WorldQuantileBand;
    leading_action: string;
    leading_action_share: WorldQuantileBand;
  }>;
  location_activity: Array<{
    tick: number;
    location_id: string;
    present_population: number;
    awareness: WorldQuantileBand;
    active_expression: WorldQuantileBand;
    dominant_action: string;
  }>;
  agent_trace: Array<{
    agent_id: string;
    tier: string;
    path: number;
    tick: number;
    location_id: string;
    received_event_ids: string[];
    aware_event_ids: string[];
    received_channels: string[];
    beliefs: Record<string, number>;
    emotion: Record<string, number>;
    goals: Record<string, number>;
    action: string;
    working_memory_salience: number;
    episodic_memory_count: number;
    semantic_memory_strength: number;
    reason_codes: string[];
  }>;
  decision_report: {
    interaction_mode: 'independent';
    event_id: string;
    event_category: string;
    agent_count: number;
    round_count: number;
    total_decisions: number;
    completed_decisions: number;
    rounds: Array<{
      round_index: number;
      question: {
        question_id: string;
        round_index: number;
        prompt: string;
        context: string;
        construct: 'reaction' | 'evidence' | 'action' | 'persistence' | 'recommendation';
        options: Array<{ option_id: string; label: string; position: number }>;
      };
      options: Array<{
        option_id: string;
        label: string;
        agent_count: number;
        represented_population: number;
        share: number;
        ci_low: number;
        ci_high: number;
      }>;
      agent_count: number;
      mean_confidence: number;
      changed_from_previous_share: number | null;
      response_entropy: number;
      representatives: Array<{
        agent_id: string;
        name: string;
        role: string;
        segment: string;
        round_index: number;
        choice: string;
        confidence: number;
        rationale: string;
        reason_codes: string[];
        represented_weight: number;
      }>;
    }>;
    final_leading_choice: string;
    final_leading_share: number;
    changed_mind_share: number;
    mean_confidence: number;
    summary: string[];
    methodology: string[];
    deterministic_signature: string;
  } | null;
  final_action_distribution: Record<string, WorldQuantileBand>;
  state_transition_order: string[];
  deterministic_signature: string;
  limitations: string[];
  disclaimer: string;
};

export type WorldSimulationRequest = {
  project_id: string;
  world: {
    world_id: string;
    name: string;
    represented_population: number;
    prototype_count: number;
    tick_minutes: number;
    start_hour: number;
    population_filters: Record<string, string[]>;
    locations: Array<{
      location_id: string;
      name: string;
      location_type: string;
      parent_id: string | null;
      capacity: number;
      baseline_activity: number;
      semantic_tags: string[];
      supported_channels: string[];
    }>;
  };
  events: Array<{
    event_id: string;
    title: string;
    description: string;
    start_tick: number;
    duration_ticks: number;
    source_location_id: string | null;
    target_location_ids: string[];
    channels: string[];
    audience_filters: Record<string, string[]>;
    intensity: number;
    credibility: number;
    novelty: number;
    valence: number;
    belief_signals: Record<string, number>;
    value_signals: Record<string, number>;
    goal_signals: Record<string, number>;
    evidence_refs: string[];
  }>;
  horizon_ticks: number;
  paths: number;
  seed: number;
  trace_agent_count: number;
  snapshot_interval: number;
  interaction_mode: 'independent';
  decision_rounds: number;
  question_overrides: Array<{
    question_id: string;
    round_index: number;
    prompt: string;
    context: string;
    construct: 'reaction' | 'evidence' | 'action' | 'persistence' | 'recommendation';
    options: Array<{ option_id: string; label: string; position: number }>;
  }>;
};
