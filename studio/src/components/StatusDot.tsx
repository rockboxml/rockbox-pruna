import type { StepStatus } from "../state/runReducer";

const COLOR: Record<string, string> = {
  pending: "var(--faint)",
  running: "var(--amber)",
  waiting: "var(--mauve)",
  done: "var(--teal)",
  error: "var(--err)",
  skipped: "var(--faint)",
};

export function StatusDot({ status }: { status: StepStatus }) {
  const color = COLOR[status] ?? "var(--faint)";
  const pulse = status === "running" || status === "waiting";
  return (
    <span
      aria-label={status}
      style={{
        width: 9,
        height: 9,
        borderRadius: "50%",
        background: color,
        boxShadow: pulse ? `0 0 0 4px color-mix(in srgb, ${color} 22%, transparent)` : "none",
        display: "inline-block",
        flex: "0 0 auto",
      }}
    />
  );
}
