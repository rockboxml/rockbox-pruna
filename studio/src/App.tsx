import { useCallback, useState } from "react";
import type { Goal } from "./api/types";
import { createRun, respond } from "./api/client";
import { useRunStream } from "./hooks/useRunStream";
import { GoalEntry } from "./screens/GoalEntry";
import { PlanPreview } from "./screens/PlanPreview";
import { ExecutionTimeline } from "./screens/ExecutionTimeline";

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const state = useRunStream(runId);

  const begin = useCallback(async (goal: Goal) => {
    const { run_id } = await createRun(goal);
    setRunId(run_id);
  }, []);

  const choose = useCallback(
    (requestId: string, choiceId: string) => {
      if (!runId) return;
      void respond(runId, { request_id: requestId, choice_id: choiceId });
    },
    [runId],
  );

  const restart = useCallback(() => setRunId(null), []);

  if (!runId) return <GoalEntry onBegin={begin} />;

  // Plan-approval gate: show the read-only preview until the plan is approved.
  const started = state.order.length > 0 || ["running", "completed", "done", "error", "cancelled"].includes(state.status);
  if (state.plan && !started && state.status === "awaiting_plan") {
    return (
      <PlanPreview
        plan={state.plan}
        hitl={state.planHitl}
        onChoose={(c) => state.planHitl && choose(state.planHitl.request_id, c)}
      />
    );
  }

  return (
    <ExecutionTimeline
      state={state}
      onChoose={(c) => state.hitl && choose(state.hitl.request_id, c)}
      onRestart={restart}
    />
  );
}
