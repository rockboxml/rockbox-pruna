"""Executor streaming + HITL hooks (default-off behavior covered by test_executor)."""

from __future__ import annotations

from orchestrator.events import HitlDecision, HitlRequest
from orchestrator.executor import execute
from orchestrator.models import Goal, MediaType, Plan, WorkflowStep
from orchestrator.skills.base import Skill
from orchestrator.skills.generate_image import _spec


class _CountingImageSkill(Skill):
    spec = _spec()

    def __init__(self):
        self.calls = 0

    async def run(self, inputs, params, entities, store):
        self.calls += 1
        # vary bytes by call so the carousel has distinct content-addressed ids
        return {"image": store.put_bytes(f"img-{self.calls}".encode(), MediaType.IMAGE)}


def _image_plan():
    goal = Goal(text="a cat")
    return goal, Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"})],
        final_step="s1",
    )


async def test_streams_step_events(store):
    from orchestrator.skills.registry import SkillRegistry

    reg = SkillRegistry()
    reg.register(_CountingImageSkill())
    _, plan = _image_plan()

    events: list[dict] = []

    async def on_event(kw):
        events.append(kw)

    result = await execute(plan, reg, store, on_event=on_event)
    types = [e["type"].value for e in events]
    assert "step.started" in types
    assert "step.artifact" in types
    assert "step.completed" in types
    assert result.ok


async def test_regenerate_then_keep(store):
    from orchestrator.skills.registry import SkillRegistry

    reg = SkillRegistry()
    skill = _CountingImageSkill()
    reg.register(skill)
    _, plan = _image_plan()

    artifact_events: list[dict] = []

    async def on_event(kw):
        if kw["type"].value == "step.artifact":
            artifact_events.append(kw)

    decisions = iter(["regenerate", "keep"])

    async def hitl(req: HitlRequest) -> HitlDecision:
        return HitlDecision(request_id=req.request_id, choice_id=next(decisions))

    result = await execute(plan, reg, store, on_event=on_event, hitl=hitl, hitl_policy="per_artifact")

    assert skill.calls == 2  # one initial + one regenerate
    # last artifact event carries the full attempt history -> carousel of 2
    assert len(artifact_events[-1]["data"]["attempts"]) == 2
    assert result.ok


async def test_hitl_off_when_no_callbacks(store):
    """With hitl=None the run never pauses even if a policy is set."""
    from orchestrator.skills.registry import SkillRegistry

    reg = SkillRegistry()
    skill = _CountingImageSkill()
    reg.register(skill)
    _, plan = _image_plan()

    result = await execute(plan, reg, store, hitl_policy="per_artifact")  # no hitl bridge
    assert skill.calls == 1
    assert result.ok
