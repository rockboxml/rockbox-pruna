"""Shared fixtures: GPU-free registry, artifact store, and a sample cast."""

from __future__ import annotations

import pytest

from orchestrator.artifacts import ArtifactStore
from orchestrator.entities import Character, EntityStore, Location, Voice
from orchestrator.models import EntityRef, Goal
from orchestrator.skills.fakes import FakeStitchSkill, FakeTTSSkill, FakeVideoSkill
from orchestrator.skills.generate_image import FakeImageSkill
from orchestrator.skills.registry import SkillRegistry


@pytest.fixture
def registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(FakeImageSkill())
    reg.register(FakeVideoSkill())
    reg.register(FakeTTSSkill())
    reg.register(FakeStitchSkill())
    return reg


@pytest.fixture
def store(tmp_path) -> ArtifactStore:
    return ArtifactStore(root=str(tmp_path), public_base_url="https://orch.test")


@pytest.fixture
def maya() -> Character:
    return Character(
        id="maya",
        name="Maya",
        appearance="short black hair, red bomber jacket",
        style="cinematic neon",
        voice=Voice(description="warm alto", voice_id="vx_maya"),
    )


@pytest.fixture
def apartment() -> Location:
    return Location(
        id="apt", name="Neon Apartment", appearance="small apartment lit by neon signs"
    )


@pytest.fixture
def entities(maya, apartment) -> EntityStore:
    es = EntityStore()
    es.put(maya)
    es.put(apartment)
    return es


@pytest.fixture
def cast_goal() -> Goal:
    return Goal(
        text="a 5 second video clip of Maya giving a tour of her neon apartment with voiceover narration",
        cast=[EntityRef(entity_id="maya"), EntityRef(entity_id="apt")],
    )
