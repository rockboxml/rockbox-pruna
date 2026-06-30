// Mirrors of the orchestrator's pydantic shapes (orchestrator/events.py, models.py).

export type MediaType = "image" | "video" | "audio" | "text";

export interface MediaArtifact {
  id: string;
  media_type: MediaType;
  uri: string;
  mime?: string | null;
  meta?: Record<string, unknown>;
  produced_by?: string | null;
  entity_id?: string | null;
  url?: string; // added by the backend payload() helper
}

export interface Choice {
  id: string;
  label: string;
  kind: string; // keep | regenerate | approve | cancel | generic
}

export type EventType =
  | "run.started"
  | "plan.proposed"
  | "step.started"
  | "step.message"
  | "step.artifact"
  | "step.completed"
  | "hitl.requested"
  | "hitl.resolved"
  | "run.completed"
  | "run.error";

export interface RunEvent {
  seq: number;
  run_id: string;
  type: EventType;
  ts: number;
  step_id?: string | null;
  skill_id?: string | null;
  message?: string | null;
  status?: string | null;
  artifact?: MediaArtifact | null;
  request_id?: string | null;
  prompt?: string | null;
  choices: Choice[];
  plan?: HumanPlan | null;
  data: Record<string, any>;
}

export interface HumanPlanStep {
  id: string;
  skill_id: string;
  title: string;
  rationale: string;
  entity_refs: string[];
}

export interface HumanPlan {
  goal: string;
  final_step: string;
  steps: HumanPlanStep[];
}

export interface Goal {
  text: string;
  cast: { entity_id: string }[];
  constraints: Record<string, unknown>;
  seed_inputs?: MediaArtifact[];
}

export interface CastMember {
  entity_id: string;
  name: string;
  type: "character" | "location";
  referenceUrl?: string;
}
