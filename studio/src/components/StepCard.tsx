import type { StepState, HitlState } from "../state/runReducer";
import { StatusDot } from "./StatusDot";
import { ArtifactView } from "./ArtifactView";
import { HitlCard } from "./HitlCard";

function time(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function StepCard({
  step,
  last,
  hitl,
  onChoose,
}: {
  step: StepState;
  last: boolean;
  hitl?: HitlState;
  onChoose: (choiceId: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 16 }}>
      {/* timeline rail */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 5 }}>
        <StatusDot status={step.status} />
        {!last && <div style={{ width: 1, flex: 1, background: "var(--hairline)", marginTop: 4 }} />}
      </div>

      {/* content */}
      <div style={{ flex: 1, paddingBottom: 26 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ color: step.status === "error" ? "var(--err)" : "var(--cream)" }}>
            {step.message || step.skill_id}
          </span>
          <span className="timestamp">{time(step.ts)}</span>
        </div>
        <div className="label" style={{ marginTop: 3, fontSize: 10 }}>
          {step.skill_id}
        </div>

        {step.artifacts.length > 0 && <ArtifactView artifacts={step.artifacts} />}

        {hitl && hitl.step_id === step.id && <HitlCard hitl={hitl} onChoose={onChoose} />}
      </div>
    </div>
  );
}
