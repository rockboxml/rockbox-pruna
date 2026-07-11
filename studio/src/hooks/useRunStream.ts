import { useEffect, useReducer, useRef } from "react";
import type { RunEvent, EventType } from "../api/types";
import { initialRunState, runReducer, type RunState } from "../state/runReducer";

const EVENT_TYPES: EventType[] = [
  "run.started",
  "plan.proposed",
  "step.started",
  "step.message",
  "step.artifact",
  "step.completed",
  "hitl.requested",
  "hitl.resolved",
  "run.completed",
  "run.error",
];

/**
 * Subscribe to a run's SSE stream and reduce events into timeline state.
 * Reconnects on error, passing ?lastEventId= so the server replays missed
 * events; dedupes by seq to absorb any overlap.
 */
export function useRunStream(runId: string | null): RunState {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!runId) return;
    seen.current = new Set();
    let es: EventSource | null = null;
    let closed = false;

    const lastSeq = () => (seen.current.size ? Math.max(...seen.current) : 0);

    const open = () => {
      es = new EventSource(`/runs/${runId}/events?lastEventId=${lastSeq()}`);
      const onMsg = (e: MessageEvent) => {
        const ev = JSON.parse(e.data) as RunEvent;
        if (seen.current.has(ev.seq)) return;
        seen.current.add(ev.seq);
        dispatch({ type: "event", event: ev });
        if (ev.type === "run.completed" || ev.type === "run.error") {
          closed = true;
          es?.close();
        }
      };
      EVENT_TYPES.forEach((t) => es!.addEventListener(t, onMsg as EventListener));
      es.onerror = () => {
        es?.close();
        if (!closed) setTimeout(open, 1000);
      };
    };

    open();
    return () => {
      closed = true;
      es?.close();
    };
  }, [runId]);

  return state;
}
