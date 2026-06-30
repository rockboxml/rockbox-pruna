"""
Humanized, user-facing messages for the execution timeline.

Deterministic and offline (no LLM): a small table keyed by ``(skill_id, phase)``
with a generic fallback. The planner's ``WorkflowStep.rationale`` is already
written for humans, so it is preferred for the "start" phase when present.
"""

from __future__ import annotations

from .models import Plan

_TABLE: dict[tuple[str, str], str] = {
    ("generate_image", "start"): "Sketching the opening frame…",
    ("generate_image", "done"): "Frame ready.",
    ("generate_video", "start"): "Animating the scene…",
    ("generate_video", "done"): "Clip rendered.",
    ("generate_audio", "start"): "Recording the voiceover…",
    ("generate_audio", "done"): "Voiceover ready.",
    ("stitch", "start"): "Mixing picture and sound…",
    ("stitch", "done"): "Final cut assembled.",
}

_GENERIC = {
    "start": "Working on “{skill}”…",
    "done": "“{skill}” complete.",
    "error": "“{skill}” ran into a problem.",
}


def humanize(skill_id: str, phase: str, *, rationale: str = "") -> str:
    """A friendly message for a step's phase (``start`` | ``done`` | ``error``)."""
    if phase == "start" and rationale:
        return rationale
    msg = _TABLE.get((skill_id, phase))
    if msg is not None:
        return msg
    template = _GENERIC.get(phase, _GENERIC["start"])
    return template.format(skill=skill_id)


def humanize_plan(plan: Plan) -> dict:
    """A compact, human-readable preview of the proposed workflow for approval."""
    return {
        "goal": plan.goal.text,
        "final_step": plan.final_step,
        "steps": [
            {
                "id": s.id,
                "skill_id": s.skill_id,
                "title": humanize(s.skill_id, "start", rationale=s.rationale),
                "rationale": s.rationale,
                "entity_refs": [r.entity_id for r in s.entity_refs],
            }
            for s in plan.steps
        ],
    }
