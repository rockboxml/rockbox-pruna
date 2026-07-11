from orchestrator.models import (
    Goal,
    InputBinding,
    Plan,
    WorkflowStep,
)
from orchestrator.planner.binder import bind_plan
from orchestrator.planner.casting import resolve_cast


async def _resolved_goal(registry, store, entities, cast_goal):
    cast = [entities.get(r.entity_id) for r in cast_goal.cast]
    await resolve_cast(cast, registry, store)
    return cast_goal


def _video_plan(goal: Goal) -> Plan:
    return Plan(
        goal=goal,
        steps=[
            WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": goal.text}),
            WorkflowStep(
                id="s2",
                skill_id="generate_video",
                input_bindings={"image": InputBinding(from_step="s1", port="image")},
                params={"prompt": goal.text},
            ),
            WorkflowStep(id="s3", skill_id="generate_audio", params={"text": "hello"}),
            WorkflowStep(
                id="s4",
                skill_id="stitch",
                input_bindings={
                    "video": InputBinding(from_step="s2", port="video"),
                    "audio": InputBinding(from_step="s3", port="audio"),
                },
            ),
        ],
        final_step="s4",
    )


async def test_default_continuity_assigns_cast(registry, store, entities, cast_goal):
    goal = await _resolved_goal(registry, store, entities, cast_goal)
    plan = _video_plan(goal)
    bind_plan(plan, goal, entities, registry)

    s1 = plan.step("s1")
    s3 = plan.step("s3")
    # image skill accepts characters + locations -> both
    assert {r.entity_id for r in s1.entity_refs} == {"maya", "apt"}
    # audio skill accepts only characters -> just maya
    assert {r.entity_id for r in s3.entity_refs} == {"maya"}


async def test_same_baseline_threaded_across_image_and_video(
    registry, store, entities, cast_goal
):
    goal = await _resolved_goal(registry, store, entities, cast_goal)
    plan = _video_plan(goal)
    bind_plan(plan, goal, entities, registry)

    s1 = plan.step("s1")
    s2 = plan.step("s2")
    assert "reference_image" in s1.input_bindings
    assert "reference_image" in s2.input_bindings
    # Both reference ports resolve to the SAME goal seed (the cast baseline).
    idx1 = s1.input_bindings["reference_image"].from_goal
    idx2 = s2.input_bindings["reference_image"].from_goal
    assert goal.seed_inputs[idx1].id == goal.seed_inputs[idx2].id
    assert goal.seed_inputs[idx1].entity_id in {"maya", "apt"}


async def test_voice_id_injected_for_audio(registry, store, entities, cast_goal):
    goal = await _resolved_goal(registry, store, entities, cast_goal)
    plan = _video_plan(goal)
    bind_plan(plan, goal, entities, registry)
    assert plan.step("s3").params.get("voice_id") == "vx_maya"
