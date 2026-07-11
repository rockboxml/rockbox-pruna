"""
Run lifecycle, event streaming, and the human-in-the-loop bridge.

A :class:`RunManager` turns a goal into a background :class:`RunSession` that
drives the pipeline (plan → approve → execute) while emitting ordered events the
API streams to the browser over SSE. Human-in-the-loop pauses are bridged with
``asyncio.Future``s: the executor raises a :class:`HitlRequest`, the session emits
``hitl.requested`` and awaits the future, and ``POST /runs/{id}/respond`` resolves
it via :meth:`RunSession.resolve`.
"""

from __future__ import annotations

import asyncio
import uuid
from enum import Enum

from .artifacts import ArtifactStore
from .entities import EntityStore
from .events import Choice, Event, EventType, HitlDecision, HitlRequest
from .models import ExecutionResult, Goal
from .skills.registry import SkillRegistry


class RunStatus(str, Enum):
    PLANNING = "planning"
    AWAITING_PLAN = "awaiting_plan"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class RunSession:
    """One run's event log, subscriber fan-out, and pending HITL futures."""

    def __init__(self, run_id: str, goal: Goal):
        self.run_id = run_id
        self.goal = goal
        self.status = RunStatus.PLANNING
        self.result: ExecutionResult | None = None
        self._seq = 0
        self._buffer: list[Event] = []
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._pending: dict[str, asyncio.Future[HitlDecision]] = {}
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    # -- event fan-out -----------------------------------------------------
    async def emit(self, **kw) -> Event:
        async with self._lock:
            self._seq += 1
            ev = Event(seq=self._seq, run_id=self.run_id, **kw)
            self._buffer.append(ev)
            for q in list(self._subscribers):
                q.put_nowait(ev)
            return ev

    async def subscribe(self, last_seq: int | None) -> tuple[asyncio.Queue[Event], list[Event]]:
        """Register a subscriber and return it plus the backlog after ``last_seq``.

        Registering the queue and snapshotting the backlog happen under the same
        lock as ``emit``, so no event can slip through the gap; the client still
        dedupes by ``seq`` to absorb any reconnect overlap.
        """
        async with self._lock:
            q: asyncio.Queue[Event] = asyncio.Queue()
            self._subscribers.add(q)
            backlog = [e for e in self._buffer if last_seq is None or e.seq > last_seq]
            return q, backlog

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(q)

    # -- HITL bridge -------------------------------------------------------
    async def request_hitl(self, req: HitlRequest) -> HitlDecision:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[HitlDecision] = loop.create_future()
        self._pending[req.request_id] = fut
        prev_status = self.status
        self.status = RunStatus.WAITING
        await self.emit(
            type=EventType.HITL_REQUESTED, step_id=req.step_id, skill_id=req.skill_id,
            request_id=req.request_id, prompt=req.prompt, choices=req.choices,
            artifact=req.artifact, status="waiting", data={"kind": req.kind},
        )
        try:
            decision = await fut
        finally:
            self._pending.pop(req.request_id, None)
        self.status = prev_status if prev_status != RunStatus.AWAITING_PLAN else RunStatus.RUNNING
        await self.emit(
            type=EventType.HITL_RESOLVED, step_id=req.step_id, request_id=req.request_id,
            data={"choice_id": decision.choice_id, "notes": decision.notes},
        )
        return decision

    def resolve(self, request_id: str, choice_id: str, notes: str | None = None) -> bool:
        fut = self._pending.get(request_id)
        if fut is None or fut.done():
            return False
        fut.set_result(HitlDecision(request_id=request_id, choice_id=choice_id, notes=notes))
        return True

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()


class RunManager:
    """Owns active runs and spawns the background driver for each."""

    def __init__(self, registry: SkillRegistry, store: ArtifactStore, entity_store: EntityStore):
        self._registry = registry
        self._store = store
        self._entities = entity_store
        self._runs: dict[str, RunSession] = {}

    def get(self, run_id: str) -> RunSession | None:
        return self._runs.get(run_id)

    def create(self, goal: Goal) -> RunSession:
        run_id = uuid.uuid4().hex
        sess = RunSession(run_id, goal)
        self._runs[run_id] = sess
        sess._task = asyncio.create_task(self._drive(sess))
        return sess

    async def _drive(self, sess: RunSession) -> None:
        # Imported here to avoid an import cycle at module load.
        from .executor import execute
        from .humanize import humanize_plan
        from .service import make_plan

        try:
            await sess.emit(type=EventType.RUN_STARTED, status="running", message="Run started.")

            plan = await make_plan(sess.goal, self._registry, self._store, self._entities)

            # --- approve-then-run: preview the plan, await approval ---
            sess.status = RunStatus.AWAITING_PLAN
            await sess.emit(type=EventType.PLAN_PROPOSED, plan=humanize_plan(plan),
                            status="awaiting_plan", message="Proposed a plan.")
            decision = await sess.request_hitl(HitlRequest(
                request_id=uuid.uuid4().hex, step_id="__plan__", skill_id="plan",
                kind="plan_approval", prompt="Approve this plan?",
                choices=[Choice(id="approve", label="Approve", kind="approve"),
                         Choice(id="cancel", label="Cancel", kind="cancel")],
            ))
            if decision.choice_id == "cancel":
                sess.status = RunStatus.CANCELLED
                await sess.emit(type=EventType.RUN_COMPLETED, status="cancelled",
                                message="Run cancelled before execution.")
                return

            # --- execute with streaming + HITL ---
            sess.status = RunStatus.RUNNING
            policy = sess.goal.constraints.get("hitl", "per_artifact")
            concurrency = 1 if policy == "per_artifact" else 4

            async def on_event(kw: dict) -> None:
                await sess.emit(**kw)

            result = await execute(
                plan, self._registry, self._store, self._entities,
                on_event=on_event, hitl=sess.request_hitl,
                hitl_policy=policy, concurrency=concurrency,
            )
            sess.result = result
            sess.status = RunStatus.COMPLETED
            final = [self._store.payload(a) for a in result.final_artifacts]
            await sess.emit(type=EventType.RUN_COMPLETED, status="done",
                            message="Run complete.",
                            data={"final_artifacts": final, "ok": result.ok})
        except asyncio.CancelledError:
            sess.status = RunStatus.CANCELLED
            await sess.emit(type=EventType.RUN_ERROR, status="cancelled", message="Run cancelled.")
            raise
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            sess.status = RunStatus.ERROR
            await sess.emit(type=EventType.RUN_ERROR, status="error",
                            message=str(exc), data={"error": repr(exc)})
