import pytest

from orchestrator.models import (
    EntityRef,
    EntityType,
    Goal,
    InputBinding,
    Plan,
    WorkflowStep,
)
from orchestrator.planner.base import PlanValidationError
from orchestrator.planner.validate import validate_plan


def _img_goal(text="a cat"):
    return Goal(text=text)


def test_valid_linear_plan(registry):
    goal = _img_goal()
    plan = Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"})],
        final_step="s1",
    )
    validate_plan(plan, registry, goal)  # no raise


def test_valid_branched_plan(registry):
    goal = _img_goal("a video with narration")
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
    validate_plan(plan, registry, goal)


def test_unknown_skill(registry):
    goal = _img_goal()
    plan = Plan(goal=goal, steps=[WorkflowStep(id="s1", skill_id="nope")], final_step="s1")
    with pytest.raises(PlanValidationError, match="unknown skill"):
        validate_plan(plan, registry, goal)


def test_cycle(registry):
    goal = _img_goal()
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(
                id="s1",
                skill_id="stitch",
                input_bindings={
                    "video": InputBinding(from_step="s2", port="video"),
                    "audio": InputBinding(from_step="s1", port="video"),
                },
            ),
            WorkflowStep(
                id="s2",
                skill_id="generate_video",
                input_bindings={"image": InputBinding(from_step="s1", port="video")},
            ),
        ],
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="cycle|unknown step"):
        validate_plan(plan, registry, goal)


def test_type_mismatch(registry):
    goal = _img_goal("a video")
    # feed an audio output into the video step's image input
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(id="s1", skill_id="generate_audio", params={"text": "x"}),
            WorkflowStep(
                id="s2",
                skill_id="generate_video",
                input_bindings={"image": InputBinding(from_step="s1", port="audio")},
            ),
        ],
        final_step="s2",
    )
    with pytest.raises(PlanValidationError, match="expects image"):
        validate_plan(plan, registry, goal)


def test_missing_required_input(registry):
    goal = _img_goal("a video")
    plan = Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_video")],  # missing 'image'
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="missing required input"):
        validate_plan(plan, registry, goal)


def test_bad_params(registry):
    goal = _img_goal()
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(
                id="s1",
                skill_id="generate_image",
                params={"prompt": "x", "bogus": 1},  # additionalProperties: false
            )
        ],
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="unknown param"):
        validate_plan(plan, registry, goal)


def test_missing_required_param(registry):
    goal = _img_goal()
    plan = Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_audio", params={})],  # needs text
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="missing required param"):
        validate_plan(plan, registry, goal)


def test_missing_final_step(registry):
    goal = _img_goal()
    plan = Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"})],
        final_step="sX",
    )
    with pytest.raises(PlanValidationError, match="final_step"):
        validate_plan(plan, registry, goal)


def test_entity_ref_not_in_cast(registry):
    goal = _img_goal()  # empty cast
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(
                id="s1",
                skill_id="generate_image",
                params={"prompt": "x"},
                entity_refs=[EntityRef(entity_id="ghost")],
            )
        ],
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="not in the goal cast"):
        validate_plan(plan, registry, goal)


def test_skill_rejects_entity_type(registry):
    goal = Goal(text="x", cast=[EntityRef(entity_id="apt")])
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(
                id="s1",
                skill_id="generate_audio",
                params={"text": "x"},
                entity_refs=[EntityRef(entity_id="apt")],  # location into an audio skill
            )
        ],
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="does not accept location"):
        validate_plan(plan, registry, goal, {"apt": EntityType.LOCATION})


def test_target_media_type_mismatch(registry):
    goal = Goal(text="x", constraints={"target_media_type": "video"})
    plan = Plan(
        goal=goal,
        steps=[WorkflowStep(id="s1", skill_id="generate_image", params={"prompt": "x"})],
        final_step="s1",
    )
    with pytest.raises(PlanValidationError, match="does not produce the requested video"):
        validate_plan(plan, registry, goal)
