"""RunManager/RunSession: event ordering, seq, replay, and HITL resolution."""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.artifacts import ArtifactStore
from orchestrator.models import EntityRef, Goal
from orchestrator.runtime import RunManager


@pytest.fixture
def manager(registry, store, entities):
    return RunManager(registry, store, entities)


async def _drive_run(sess, *, regenerate_once=True):
    """Subscribe, auto-approve the plan, optionally regenerate one artifact, collect events."""
    q, _ = await sess.subscribe(None)
    seen = []
    regenerated = False

    async def pump():
        nonlocal regenerated
        while True:
            ev = await q.get()
            seen.append(ev)
            if ev.type.value == "hitl.requested":
                kind = ev.data.get("kind")
                if kind == "plan_approval":
                    sess.resolve(ev.request_id, "approve")
                elif kind == "artifact_approval":
                    if regenerate_once and not regenerated:
                        regenerated = True
                        sess.resolve(ev.request_id, "regenerate")
                    else:
                        sess.resolve(ev.request_id, "keep")
            if ev.type.value in ("run.completed", "run.error"):
                break

    await asyncio.wait_for(pump(), timeout=10)
    await sess._task
    return seen


async def test_event_order_and_monotonic_seq(manager, entities):
    goal = Goal(text="a portrait of Maya", cast=[EntityRef(entity_id="maya")],
                constraints={"hitl": "per_artifact"})
    sess = manager.create(goal)
    seen = await _drive_run(sess)

    seqs = [e.seq for e in seen]
    assert seqs == sorted(seqs)  # monotonic
    types = [e.type.value for e in seen]
    assert types[:2] == ["run.started", "plan.proposed"]
    assert types[2] == "hitl.requested"  # plan approval gate
    assert "step.started" in types
    assert types[-1] == "run.completed"


async def test_regenerate_builds_carousel(manager):
    goal = Goal(text="a portrait of Maya", constraints={"hitl": "per_artifact"})
    sess = manager.create(goal)
    seen = await _drive_run(sess, regenerate_once=True)
    art = [e for e in seen if e.type.value == "step.artifact"]
    assert max(len(e.data["attempts"]) for e in art) == 2


async def test_cancel_via_plan_choice(manager):
    goal = Goal(text="a portrait", constraints={"hitl": "per_artifact"})
    sess = manager.create(goal)
    q, _ = await sess.subscribe(None)
    seen = []

    async def pump():
        while True:
            ev = await q.get()
            seen.append(ev)
            if ev.type.value == "hitl.requested" and ev.data.get("kind") == "plan_approval":
                sess.resolve(ev.request_id, "cancel")
            if ev.type.value in ("run.completed", "run.error"):
                break

    await asyncio.wait_for(pump(), timeout=10)
    await sess._task
    done = [e for e in seen if e.type.value == "run.completed"][0]
    assert done.status == "cancelled"
    assert not any(e.type.value == "step.started" for e in seen)


async def test_subscribe_replays_only_newer(manager):
    goal = Goal(text="a portrait", constraints={"hitl": "per_artifact"})
    sess = manager.create(goal)
    await _drive_run(sess)
    _q, backlog = await sess.subscribe(3)
    assert backlog and all(e.seq > 3 for e in backlog)


async def test_double_resolve_returns_false(manager):
    goal = Goal(text="a portrait", constraints={"hitl": "per_artifact"})
    sess = manager.create(goal)
    await _drive_run(sess)
    assert sess.resolve("does-not-exist", "approve") is False
