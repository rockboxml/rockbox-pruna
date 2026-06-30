from orchestrator.entities import Character
from orchestrator.humanize import humanize, humanize_plan
from orchestrator.models import EntityRef, Goal, Plan, WorkflowStep


def test_table_lookup():
    assert humanize("generate_image", "start") == "Sketching the opening frame…"
    assert humanize("generate_audio", "done") == "Voiceover ready."


def test_generic_fallback():
    assert humanize("upscale", "start") == "Working on “upscale”…"
    assert humanize("upscale", "error") == "“upscale” ran into a problem."


def test_rationale_preferred_for_start():
    assert humanize("generate_image", "start", rationale="Establish the hero frame.") == (
        "Establish the hero frame."
    )
    # rationale only applies to the start phase
    assert humanize("generate_image", "done", rationale="x") == "Frame ready."


def test_humanize_plan_shape():
    goal = Goal(text="a portrait of Maya", cast=[EntityRef(entity_id="maya")])
    plan = Plan(
        goal=goal,
        steps=[
            WorkflowStep(
                id="s1", skill_id="generate_image", rationale="Paint Maya.",
                entity_refs=[EntityRef(entity_id="maya")],
            )
        ],
        final_step="s1",
    )
    out = humanize_plan(plan)
    assert out["goal"] == "a portrait of Maya"
    assert out["final_step"] == "s1"
    assert out["steps"][0]["title"] == "Paint Maya."
    assert out["steps"][0]["entity_refs"] == ["maya"]
