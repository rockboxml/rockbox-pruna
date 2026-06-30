import type { Choice, HumanPlan, MediaArtifact, RunEvent } from "../api/types";

export type StepStatus = "pending" | "running" | "done" | "waiting" | "error" | "skipped";

export interface StepState {
  id: string;
  skill_id: string;
  status: StepStatus;
  message: string;
  ts: number;
  artifacts: MediaArtifact[]; // attempt history -> carousel when length > 1
}

export interface HitlState {
  request_id: string;
  step_id: string;
  kind: string;
  prompt: string;
  choices: Choice[];
  artifact?: MediaArtifact | null;
}

export interface RunState {
  status: string;
  plan?: HumanPlan;
  planHitl?: HitlState; // the plan-approval gate
  steps: Record<string, StepState>;
  order: string[];
  hitl?: HitlState; // an inline artifact/elicitation gate
  finalArtifacts: MediaArtifact[];
  error?: string;
}

export const initialRunState: RunState = {
  status: "planning",
  steps: {},
  order: [],
  finalArtifacts: [],
};

function upsertStep(s: RunState, id: string, skill_id: string, patch: Partial<StepState>): RunState {
  const existing = s.steps[id];
  const order = existing ? s.order : [...s.order, id];
  const base: StepState = existing ?? {
    id,
    skill_id,
    status: "pending",
    message: "",
    ts: Date.now(),
    artifacts: [],
  };
  const step: StepState = { ...base, ...patch, id, skill_id: skill_id || base.skill_id };
  return { ...s, order, steps: { ...s.steps, [id]: step } };
}

export function runReducer(state: RunState, action: { type: "event"; event: RunEvent }): RunState {
  const ev = action.event;
  switch (ev.type) {
    case "run.started":
      return { ...state, status: "running" };

    case "plan.proposed":
      return { ...state, plan: ev.plan ?? undefined, status: "awaiting_plan" };

    case "hitl.requested": {
      const hitl: HitlState = {
        request_id: ev.request_id!,
        step_id: ev.step_id ?? "",
        kind: ev.data?.kind ?? "elicitation",
        prompt: ev.prompt ?? "",
        choices: ev.choices ?? [],
        artifact: ev.artifact ?? undefined,
      };
      if (hitl.kind === "plan_approval") return { ...state, planHitl: hitl, status: "awaiting_plan" };
      let s: RunState = { ...state, hitl, status: "waiting" };
      if (hitl.step_id && s.steps[hitl.step_id]) {
        s = upsertStep(s, hitl.step_id, s.steps[hitl.step_id].skill_id, { status: "waiting" });
      }
      return s;
    }

    case "hitl.resolved": {
      let s: RunState = { ...state };
      if (state.planHitl?.request_id === ev.request_id) s.planHitl = undefined;
      if (state.hitl?.request_id === ev.request_id) s.hitl = undefined;
      if (ev.step_id && s.steps[ev.step_id] && s.steps[ev.step_id].status === "waiting") {
        s = upsertStep(s, ev.step_id, s.steps[ev.step_id].skill_id, { status: "running" });
      }
      if (s.status === "waiting" || s.status === "awaiting_plan") s.status = "running";
      return s;
    }

    case "step.started":
      return upsertStep(state, ev.step_id!, ev.skill_id ?? "", {
        status: "running",
        message: ev.message ?? "",
        ts: ev.ts * 1000,
      });

    case "step.artifact": {
      const attempts: MediaArtifact[] = ev.data?.attempts ?? (ev.artifact ? [ev.artifact] : []);
      return upsertStep(state, ev.step_id!, ev.skill_id ?? "", { artifacts: attempts });
    }

    case "step.completed":
      return upsertStep(state, ev.step_id!, ev.skill_id ?? "", {
        status: (ev.status as StepStatus) ?? "done",
        message: ev.message ?? state.steps[ev.step_id!]?.message ?? "",
      });

    case "run.completed":
      return {
        ...state,
        status: ev.status ?? "completed",
        finalArtifacts: ev.data?.final_artifacts ?? [],
      };

    case "run.error":
      return { ...state, status: "error", error: ev.message ?? "Run failed." };

    default:
      return state;
  }
}
