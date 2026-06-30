import type { HitlState } from "../state/runReducer";

export function HitlCard({ hitl, onChoose }: { hitl: HitlState; onChoose: (choiceId: string) => void }) {
  return (
    <div
      className="panel"
      style={{
        borderColor: "color-mix(in srgb, var(--mauve) 40%, var(--hairline))",
        background: "var(--panel-2)",
        padding: "14px 16px",
        marginTop: 12,
      }}
    >
      <div className="label" style={{ color: "var(--mauve)", marginBottom: 8 }}>
        Needs your input
      </div>
      <div style={{ marginBottom: 12 }}>{hitl.prompt}</div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {hitl.choices.map((c) => (
          <button
            key={c.id}
            className={c.kind === "keep" || c.kind === "approve" ? "primary" : "ghost"}
            onClick={() => onChoose(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  );
}
