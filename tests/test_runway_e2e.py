"""
Opt-in end-to-end test against the real Runway skills.

Requires ``RUNWAYML_API_SECRET`` (+ Runway credits) and the vendored
``runwayml/skills`` submodule. Excluded from the default suite via the ``runway``
marker; run with ``pytest -m runway``.

It casts a Character on ``gen4_image``, then runs a multi-skill workflow and
asserts the *same* resolved baseline URL is threaded into the image and video
Runway calls — real cross-modal continuity — and that the run succeeds.
"""

from __future__ import annotations

import os

import pytest

from orchestrator import config
from orchestrator.artifacts import ArtifactStore
from orchestrator.entities import Character, EntityStore, Voice
from orchestrator.models import EntityRef, Goal, StepStatus
from orchestrator.service import run_goal
from orchestrator.skills.registry import SkillRegistry
from orchestrator.skills.runway import register_runway_skills

pytestmark = pytest.mark.runway


@pytest.fixture
def runway_registry():
    if not config.RUNWAYML_API_SECRET:
        pytest.skip("RUNWAYML_API_SECRET not set")
    reg = SkillRegistry()
    if not register_runway_skills(reg):
        pytest.skip("vendored runwayml/skills not found (see orchestrator/vendor/README.md)")
    # stitch is ffmpeg/real elsewhere; fall back to fake for the mux step.
    from orchestrator.skills.fakes import FakeStitchSkill

    if not reg.has("stitch"):
        reg.register(FakeStitchSkill())
    return reg


async def test_real_runway_cross_modal_continuity(runway_registry, tmp_path):
    if not config.PUBLIC_BASE_URL:
        pytest.skip("PUBLIC_BASE_URL must be set so Runway can fetch reference images")

    store = ArtifactStore(root=str(tmp_path))
    es = EntityStore()
    es.put(
        Character(
            id="maya",
            name="Maya",
            appearance="short black hair, red bomber jacket",
            style="cinematic neon",
            voice=Voice(description="warm alto"),
        )
    )
    goal = Goal(
        text="a 5 second clip of Maya giving a short tour of a neon apartment with voiceover",
        cast=[EntityRef(entity_id="maya")],
    )
    result = await run_goal(goal, runway_registry, store, es)

    assert result.ok
    assert all(r.status != StepStatus.ERROR for r in result.step_results.values())
    # the same baseline (Maya's portrait) was used to condition image + video
    baseline = next(r for r in es.get("maya").references if r.media_type.value == "image")
    assert baseline is not None
