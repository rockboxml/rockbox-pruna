from orchestrator.models import Goal
from orchestrator.planner.heuristic import HeuristicPlanner
from orchestrator.planner.validate import validate_plan


async def test_image_goal_single_step(registry):
    goal = Goal(text="a watercolor red bicycle")
    plan = await HeuristicPlanner(registry).plan(goal, registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_image"]
    assert plan.final_step == "s1"
    validate_plan(plan, registry, goal)


async def test_audio_goal_single_step(registry):
    goal = Goal(text="a voiceover narration reading the news")
    plan = await HeuristicPlanner(registry).plan(goal, registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_audio"]
    validate_plan(plan, registry, goal)


async def test_narrated_video_is_branched(registry):
    goal = Goal(text="a 5s video clip of a city with voiceover narration")
    plan = await HeuristicPlanner(registry).plan(goal, registry.catalog())
    skills = [s.skill_id for s in plan.steps]
    assert skills == ["generate_image", "generate_video", "generate_audio", "stitch"]
    assert plan.final_step == "s4"
    validate_plan(plan, registry, goal)


async def test_plain_video_no_audio(registry):
    goal = Goal(text="a short video clip of waves")
    plan = await HeuristicPlanner(registry).plan(goal, registry.catalog())
    skills = [s.skill_id for s in plan.steps]
    assert skills == ["generate_image", "generate_video"]
    assert plan.final_step == "s2"
    validate_plan(plan, registry, goal)


async def test_target_media_type_constraint_overrides_text(registry):
    goal = Goal(text="something", constraints={"target_media_type": "audio"})
    plan = await HeuristicPlanner(registry).plan(goal, registry.catalog())
    assert [s.skill_id for s in plan.steps] == ["generate_audio"]
