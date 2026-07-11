import type { RunState } from "../state/runReducer";
import { StepCard } from "../components/StepCard";
import { ArtifactView } from "../components/ArtifactView";

export function ExecutionTimeline({
  state,
  onChoose,
  onRestart,
}: {
  state: RunState;
  onChoose: (choiceId: string) => void;
  onRestart: () => void;
}) {
  const steps = state.order.map((id) => state.steps[id]);
  const terminal = ["completed", "done", "cancelled", "error"].includes(state.status);

  return (
    <div className="app-shell">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div className="label" style={{ color: "var(--amber)" }}>
          ∂ &nbsp;Execution
        </div>
        <div className="label">{state.status}</div>
      </div>

      <div style={{ marginTop: 28 }}>
        {steps.map((s, i) => (
          <StepCard
            key={s.id}
            step={s}
            last={i === steps.length - 1}
            hitl={state.hitl}
            onChoose={onChoose}
          />
        ))}
        {steps.length === 0 && <div className="label">Waiting for the first step…</div>}
      </div>

      {state.error && (
        <div className="panel" style={{ padding: 16, borderColor: "var(--err)", color: "var(--err)", marginTop: 12 }}>
          {state.error}
        </div>
      )}

      {state.finalArtifacts.length > 0 && (
        <div style={{ marginTop: 36 }}>
          <div className="label" style={{ color: "var(--teal)", marginBottom: 12 }}>
            ✓ Deliverable
          </div>
          <ArtifactView artifacts={state.finalArtifacts} />
        </div>
      )}

      {terminal && (
        <div style={{ marginTop: 36 }}>
          <button className="ghost" onClick={onRestart}>
            ← New goal
          </button>
        </div>
      )}
    </div>
  );
}
