import pytest

from orchestrator.artifacts import ArtifactStore
from orchestrator.executor import execute
from orchestrator.models import (
    Goal,
    InputBinding,
    MediaType,
    Plan,
    PortSpec,
    SkillSpec,
    StepStatus,
    WorkflowStep,
)
from orchestrator.skills.base import Skill
from orchestrator.service import run_goal


async def test_branched_dag_runs_and_threads_artifacts(registry, store, entities, cast_goal):
    result = await run_goal(cast_goal, registry, store, entities)
    assert result.ok
    assert all(r.status == StepStatus.OK for r in result.step_results.values())
    assert result.final_artifacts[0].media_type == MediaType.VIDEO
    # stitch consumed the upstream video + audio ids
    stitch = result.step_results["s4"]
    assert stitch.outputs["video"].meta["video"] == result.step_results["s2"].outputs["video"].id
    assert stitch.outputs["video"].meta["audio"] == result.step_results["s3"].outputs["audio"].id


class _FlakySkill(Skill):
    spec = SkillSpec(
        id="generate_image",
        description="flaky",
        outputs=[PortSpec(name="image", media_type=MediaType.IMAGE)],
        params_schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "additionalProperties": False},
    )

    def __init__(self):
        self.calls = 0

    async def run(self, inputs, params, entities, store):
        self.calls += 1
        if self.calls < 2:
            raise RuntimeError("transient")
        return {"image": store.put_bytes(b"ok", MediaType.IMAGE)}


async def test_retry_on_flaky_skill(registry, store):
    flaky = _FlakySkill()
    registry.register(flaky)
    goal = Goal(text="a cat")
    plan = Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"})],
        final_step="s1",
    )
    result = await execute(plan, registry, store)
    assert result.ok
    assert result.step_results["s1"].attempts == 2
    assert flaky.calls == 2


class _AlwaysFail(Skill):
    spec = SkillSpec(
        id="generate_image",
        description="fail",
        outputs=[PortSpec(name="image", media_type=MediaType.IMAGE)],
        params_schema={"type": "object", "properties": {"prompt": {"type": "string"}}, "additionalProperties": False},
    )

    async def run(self, inputs, params, entities, store):
        raise RuntimeError("nope")


async def test_failure_skips_downstream_only(registry, store):
    # s1 (image) fails -> s2 (video, depends on s1) skipped; independent s3 (audio) ok.
    registry.register(_AlwaysFail())
    goal = Goal(text="a video with narration")
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"}),
            WorkflowStep(
                id="s2",
                skill_id="generate_video",
                input_bindings={"image": InputBinding(from_step="s1", port="image")},
            ),
            WorkflowStep(id="s3", skill_id="generate_audio", params={"text": "hi"}),
        ],
        final_step="s2",
    )
    result = await execute(plan, registry, store)
    assert result.step_results["s1"].status == StepStatus.ERROR
    assert result.step_results["s2"].status == StepStatus.SKIPPED
    assert result.step_results["s3"].status == StepStatus.OK  # independent branch ran
    assert not result.ok  # final step did not produce output


async def test_continuity_same_baseline_across_goals(registry, store, entities):
    """Two goals referencing the same character cite the same resolved baseline."""
    from orchestrator.models import EntityRef

    g1 = Goal(text="a portrait of Maya", cast=[EntityRef(entity_id="maya")])
    await run_goal(g1, registry, store, entities)
    baseline_1 = [r.id for r in entities.get("maya").references]

    g2 = Goal(text="a video clip of Maya walking", cast=[EntityRef(entity_id="maya")])
    await run_goal(g2, registry, store, entities)
    baseline_2 = [r.id for r in entities.get("maya").references]

    assert baseline_1 == baseline_2  # baseline reused, not regenerated
    assert baseline_1  # and it exists
