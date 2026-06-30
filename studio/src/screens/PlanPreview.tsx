import type { HumanPlan } from "../api/types";
import type { HitlState } from "../state/runReducer";

/** Read-only humanized preview of the proposed workflow with Approve / Cancel. */
export function PlanPreview({
  plan,
  hitl,
  onChoose,
}: {
  plan: HumanPlan;
  hitl?: HitlState;
  onChoose: (choiceId: string) => void;
}) {
  return (
    <div className="app-shell">
      <div className="label" style={{ color: "var(--amber)", marginBottom: 16 }}>
        ∂ &nbsp;Proposed workflow
      </div>
      <h1 style={{ marginTop: 0 }}>{plan.goal}</h1>

      <div style={{ marginTop: 28 }}>
        {plan.steps.map((s, i) => (
          <div key={s.id} style={{ display: "flex", gap: 16, paddingBottom: 22 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <span className="mono" style={stepNum}>
                {i + 1}
              </span>
              {i < plan.steps.length - 1 && (
                <div style={{ width: 1, flex: 1, background: "var(--hairline)", marginTop: 4 }} />
              )}
            </div>
            <div>
              <div>{s.title}</div>
              <div className="label" style={{ marginTop: 3, fontSize: 10 }}>
                {s.skill_id}
                {s.entity_refs.length > 0 && ` · ${s.entity_refs.join(", ")}`}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 24 }}>
        {hitl ? (
          hitl.choices.map((c) => (
            <button
              key={c.id}
              className={c.kind === "approve" ? "primary" : "ghost"}
              onClick={() => onChoose(c.id)}
              style={{ padding: "11px 26px" }}
            >
              {c.label}
            </button>
          ))
        ) : (
          <span className="label">Preparing…</span>
        )}
      </div>
    </div>
  );
}

const stepNum: React.CSSProperties = {
  width: 26,
  height: 26,
  borderRadius: "50%",
  border: "1px solid var(--hairline-strong)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 12,
  color: "var(--amber)",
  flex: "0 0 auto",
};
